"""Background task execution with event publishing."""

from __future__ import annotations

import asyncio
import sys

from ade.api.events import publish_task_event

# Track running tasks for potential cancellation
_running_tasks: dict[str, asyncio.Task] = {}


async def execute_task_in_background(
    task_id: str,
    description: str,
    project_id: str,
    project_path: str,
) -> None:
    """Run the agent orchestrator and publish lifecycle events."""
    try:
        await publish_task_event(task_id, "status_change", {"status": "planning"})

        from ade.agents.orchestrator import run_task

        final_state = await run_task(
            task_id=task_id,
            task=description,
            project_id=project_id,
            project_path=project_path,
        )

        status = final_state.get("status", "failed")
        if status == "complete":
            await publish_task_event(task_id, "task_completed", {"status": "completed"})
        else:
            await publish_task_event(
                task_id, "task_failed",
                {"status": "failed", "error": final_state.get("error", "")},
            )

    except Exception as e:
        print(f"Background task {task_id} failed: {e}", file=sys.stderr)
        await publish_task_event(
            task_id, "task_failed", {"status": "failed", "error": str(e)}
        )
    finally:
        _running_tasks.pop(task_id, None)


def launch_task(
    task_id: str,
    description: str,
    project_id: str,
    project_path: str,
) -> asyncio.Task:
    """Launch a task as a background asyncio.Task."""
    coro = execute_task_in_background(task_id, description, project_id, project_path)
    bg_task = asyncio.create_task(coro, name=f"ade-task-{task_id}")
    _running_tasks[task_id] = bg_task
    return bg_task


def get_running_tasks() -> dict[str, asyncio.Task]:
    """Return the dict of currently running background tasks."""
    return _running_tasks
