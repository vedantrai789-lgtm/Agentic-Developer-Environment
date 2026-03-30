"""Output formatting utilities for the CLI."""

from __future__ import annotations

import click

STATUS_COLORS = {
    "pending": "yellow",
    "planning": "cyan",
    "executing": "blue",
    "completed": "green",
    "failed": "red",
}


def format_status(status: str) -> str:
    """Return a colored status string."""
    color = STATUS_COLORS.get(status, "white")
    return click.style(status.upper(), fg=color, bold=True)


def print_project(project: dict) -> None:
    """Print a project summary."""
    click.echo(f"  ID:      {project['id']}")
    click.echo(f"  Name:    {project['name']}")
    click.echo(f"  Path:    {project['path']}")
    indexed = project.get("last_indexed_at") or "never"
    click.echo(f"  Indexed: {indexed}")
    click.echo()


def print_task(task: dict) -> None:
    """Print a task summary."""
    click.echo(f"  ID:      {task['id']}")
    click.echo(f"  Status:  {format_status(task['status'])}")
    click.echo(f"  Desc:    {task['description']}")
    click.echo(f"  Created: {task['created_at']}")
    if task.get("completed_at"):
        click.echo(f"  Done:    {task['completed_at']}")

    # Show plan step progress if available
    steps = task.get("plan_steps", [])
    if steps:
        completed = sum(1 for s in steps if s.get("status") == "completed")
        click.echo(f"  Steps:   {completed}/{len(steps)} completed")
    click.echo()


def print_logs(logs: list[dict]) -> None:
    """Print agent logs as a formatted table."""
    if not logs:
        click.echo("  No logs found.")
        return

    # Header
    click.echo(
        f"  {'AGENT':<12} {'ACTION':<20} {'IN_TOK':>7} {'OUT_TOK':>8} "
        f"{'LATENCY':>9} {'TIMESTAMP'}"
    )
    click.echo("  " + "-" * 80)

    for log in logs:
        click.echo(
            f"  {log['agent_name']:<12} {log['action']:<20} "
            f"{log['input_tokens']:>7} {log['output_tokens']:>8} "
            f"{log['latency_ms']:>8.0f}ms {log['timestamp']}"
        )
