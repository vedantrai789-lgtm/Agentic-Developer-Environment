"""ADE command-line interface."""

from __future__ import annotations

import asyncio
import os
import sys

import click

from ade.cli.client import ADEClient
from ade.cli.formatters import format_status, print_logs, print_project, print_task


def _run(coro):
    """Run an async coroutine from sync click commands."""
    return asyncio.run(coro)


async def _server_available(client: ADEClient) -> bool:
    """Check if the ADE API server is reachable."""
    try:
        await client.health()
        return True
    except Exception:
        return False


@click.group()
@click.version_option(version="0.1.0", prog_name="ade")
def cli():
    """ADE — Agentic Developer Environment CLI."""
    pass


@cli.command()
@click.argument("path", type=click.Path(exists=True))
@click.option("--name", default=None, help="Project name (defaults to directory name)")
def init(path: str, name: str | None):
    """Register and index a project."""
    abs_path = os.path.abspath(path)
    project_name = name or os.path.basename(abs_path)

    async def _init():
        client = ADEClient()
        if await _server_available(client):
            result = await client.create_project(project_name, abs_path)
            click.echo("Project registered via API:")
            print_project(result)
            click.echo("Background indexing started.")
        else:
            click.echo("API server not available. Running directly...")
            await _init_direct(project_name, abs_path)

    _run(_init())


async def _init_direct(name: str, path: str) -> None:
    """Register and index a project directly (no API server)."""
    from ade.core.database import async_session_factory
    from ade.core.models import Project

    async with async_session_factory() as session:
        project = Project(name=name, path=path)
        session.add(project)
        await session.flush()
        project_id = str(project.id)
        await session.commit()

    click.echo(f"Project '{name}' created: {project_id}")
    click.echo("Indexing...")

    from ade.rag.indexer import index_project

    result = await index_project(project_id, path)
    click.echo(
        f"Indexed: {result.files_indexed} files, "
        f"{result.chunks_created} chunks in {result.duration_ms:.0f}ms"
    )


@cli.command()
@click.argument("project")
@click.argument("description")
def task(project: str, description: str):
    """Create and run a task for a project.

    PROJECT can be a UUID or project name.
    """

    async def _task():
        client = ADEClient()
        if await _server_available(client):
            # Resolve project name to ID if needed
            project_id = await _resolve_project(client, project)
            result = await client.create_task(project_id, description)
            click.echo("Task created:")
            print_task(result)
        else:
            click.echo("API server not available. Running directly...")
            await _task_direct(project, description)

    _run(_task())


async def _resolve_project(client: ADEClient, project: str) -> str:
    """Resolve a project name or UUID to a UUID string."""
    # Try as UUID first
    try:
        import uuid

        uuid.UUID(project)
        return project
    except ValueError:
        pass

    # Search by name
    projects = await client.list_projects()
    for p in projects:
        if p["name"] == project:
            return p["id"]

    click.echo(f"Error: Project '{project}' not found.", err=True)
    sys.exit(1)


async def _task_direct(project: str, description: str) -> None:
    """Run a task directly (no API server)."""
    import uuid as uuid_mod

    from sqlalchemy import select

    from ade.core.database import async_session_factory
    from ade.core.models import Project, Task, TaskStatus

    async with async_session_factory() as session:
        # Resolve project
        try:
            pid = uuid_mod.UUID(project)
            proj = await session.get(Project, pid)
        except ValueError:
            result = await session.execute(
                select(Project).where(Project.name == project)
            )
            proj = result.scalar_one_or_none()

        if not proj:
            click.echo(f"Error: Project '{project}' not found.", err=True)
            sys.exit(1)

        task = Task(
            project_id=proj.id, description=description, status=TaskStatus.PENDING
        )
        session.add(task)
        await session.flush()
        task_id = str(task.id)
        project_path = proj.path
        project_id = str(proj.id)
        await session.commit()

    click.echo(f"Task {task_id} created. Running orchestrator...")
    from ade.agents.orchestrator import run_task

    final = await run_task(
        task_id=task_id,
        task=description,
        project_id=project_id,
        project_path=project_path,
    )
    click.echo(f"Result: {format_status(final.get('status', 'unknown'))}")


@cli.command()
@click.argument("task_id")
def status(task_id: str):
    """Check the status of a task."""

    async def _status():
        client = ADEClient()
        if await _server_available(client):
            result = await client.get_task(task_id)
            print_task(result)
        else:
            click.echo("API server not available.", err=True)
            sys.exit(1)

    _run(_status())


@cli.command()
@click.argument("task_id")
@click.option("--agent", default=None, help="Filter by agent name")
def logs(task_id: str, agent: str | None):
    """View agent logs for a task."""

    async def _logs():
        client = ADEClient()
        if await _server_available(client):
            result = await client.get_task_logs(task_id, agent_name=agent)
            print_logs(result)
        else:
            click.echo("API server not available.", err=True)
            sys.exit(1)

    _run(_logs())


@cli.command()
def projects():
    """List all registered projects."""

    async def _projects():
        client = ADEClient()
        if await _server_available(client):
            result = await client.list_projects()
            if not result:
                click.echo("No projects registered.")
                return
            for p in result:
                print_project(p)
        else:
            click.echo("API server not available.", err=True)
            sys.exit(1)

    _run(_projects())


@cli.command()
@click.option("--host", default="0.0.0.0", help="Bind host")
@click.option("--port", default=8000, type=int, help="Bind port")
@click.option("--reload", is_flag=True, help="Enable auto-reload")
def serve(host: str, port: int, reload: bool):
    """Start the ADE API server."""
    import uvicorn

    uvicorn.run("ade.api.main:app", host=host, port=port, reload=reload)


if __name__ == "__main__":
    cli()
