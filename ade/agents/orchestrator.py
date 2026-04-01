import logging
import uuid
from datetime import datetime, timezone

from langgraph.graph import END, START, StateGraph
from sqlalchemy import select

from ade.agents.codegen import codegen_node
from ade.agents.executor import executor_node
from ade.agents.planner import planner_node
from ade.agents.state import AgentState
from ade.core.database import async_session_factory
from ade.core.models import CodeChange, PlanStep, Task, TaskStatus

logger = logging.getLogger(__name__)

MAX_RETRIES = 3


def route_after_executor(state: AgentState) -> str:
    """Routing function: decide what happens after executor runs."""
    results = state.get("execution_results", [])
    last_result = results[-1] if results else None

    # Check if execution failed
    if last_result and last_result["exit_code"] != 0:
        if state.get("iteration_count", 0) < MAX_RETRIES:
            return "retry"
        else:
            return "fail"

    # Execution passed — check if more steps remain
    next_index = state.get("current_step_index", 0) + 1
    if next_index < len(state.get("plan", [])):
        return "advance"
    return "apply"


def route_after_planner(state: AgentState) -> str:
    """Route after planner: proceed to codegen or fail."""
    if state.get("status") == "failed":
        return "fail"
    return "codegen"


def advance_step(state: AgentState) -> dict:
    """Increment step index and reset per-step state."""
    return {
        "current_step_index": state.get("current_step_index", 0) + 1,
        "iteration_count": 0,
        "code_changes": [],
        "execution_results": [],
        "status": "coding",
    }


def increment_retry(state: AgentState) -> dict:
    """Increment retry counter for the current step."""
    return {
        "iteration_count": state.get("iteration_count", 0) + 1,
        "status": "coding",
    }


async def apply_changes(state: AgentState) -> dict:
    """Apply all accumulated code changes to the real project directory."""
    try:
        task_id = uuid.UUID(state["task_id"])
        project_path = state.get("project_path", "")

        if not project_path:
            logger.warning("No project_path in state, skipping apply")
            return {"status": "complete"}

        # Gather all code changes from DB (across all steps)
        changes = await _gather_all_changes(task_id)

        if changes:
            from ade.sandbox.workspace import apply_changes_to_project

            modified = apply_changes_to_project(project_path, changes)
            logger.info("Applied %d changes to %s", len(modified), project_path)
        else:
            logger.info("No code changes to apply for task %s", task_id)

        return {"status": "complete"}

    except Exception as e:
        logger.exception("Failed to apply changes: %s", e)
        return {"status": "complete"}  # Don't fail the task over apply errors


async def _gather_all_changes(task_id: uuid.UUID) -> list[dict]:
    """Query all CodeChange rows for a task, ordered by step number."""
    try:
        async with async_session_factory() as session:
            result = await session.execute(
                select(CodeChange)
                .join(PlanStep, CodeChange.step_id == PlanStep.id)
                .where(PlanStep.task_id == task_id)
                .order_by(PlanStep.step_number)
            )
            rows = result.scalars().all()
            return [
                {
                    "file_path": r.file_path,
                    "change_type": (
                        r.change_type.value
                        if hasattr(r.change_type, "value")
                        else r.change_type
                    ),
                    "diff": r.diff,
                    "full_content": r.full_content,
                }
                for r in rows
            ]
    except Exception as e:
        logger.exception("Failed to gather changes from DB: %s", e)
        return []


async def mark_complete(state: AgentState) -> dict:
    """Persist task completion to the database."""
    try:
        task_id = uuid.UUID(state["task_id"])
        async with async_session_factory() as session:
            task = await session.get(Task, task_id)
            if task:
                task.status = TaskStatus.COMPLETED
                task.completed_at = datetime.now(tz=timezone.utc)
            await session.commit()
    except Exception as e:
        logger.exception("Failed to mark task complete: %s", e)

    return {"status": "complete"}


async def mark_failed(state: AgentState) -> dict:
    """Persist task failure to the database."""
    try:
        task_id = uuid.UUID(state["task_id"])
        async with async_session_factory() as session:
            task = await session.get(Task, task_id)
            if task:
                task.status = TaskStatus.FAILED
            await session.commit()
    except Exception as e:
        logger.exception("Failed to mark task failed: %s", e)

    error = state.get("error", "Unknown error")
    return {"status": "failed", "error": error}


def build_graph() -> StateGraph:
    """Build the LangGraph state graph for the agent pipeline."""
    graph = StateGraph(AgentState)

    # Add nodes
    graph.add_node("planner", planner_node)
    graph.add_node("codegen", codegen_node)
    graph.add_node("executor", executor_node)
    graph.add_node("advance", advance_step)
    graph.add_node("retry", increment_retry)
    graph.add_node("apply", apply_changes)
    graph.add_node("complete", mark_complete)
    graph.add_node("fail", mark_failed)

    # Entry: start with planner
    graph.add_edge(START, "planner")

    # After planner: proceed to codegen or fail
    graph.add_conditional_edges(
        "planner",
        route_after_planner,
        {"codegen": "codegen", "fail": "fail"},
    )

    # After codegen: run executor (or fail if codegen failed)
    graph.add_conditional_edges(
        "codegen",
        lambda s: "fail" if s.get("status") == "failed" else "executor",
        {"executor": "executor", "fail": "fail"},
    )

    # After executor: conditional routing
    graph.add_conditional_edges(
        "executor",
        route_after_executor,
        {
            "advance": "advance",
            "retry": "retry",
            "apply": "apply",
            "fail": "fail",
        },
    )

    # After advance: loop back to codegen for next step
    graph.add_edge("advance", "codegen")

    # After retry: loop back to codegen with incremented counter
    graph.add_edge("retry", "codegen")

    # After apply: mark complete
    graph.add_edge("apply", "complete")

    # Terminal nodes
    graph.add_edge("complete", END)
    graph.add_edge("fail", END)

    return graph


async def run_task(
    task_id: str,
    task: str,
    project_id: str,
    project_path: str,
) -> AgentState:
    """Entry point: build the graph and run it for a task."""
    graph = build_graph()
    app = graph.compile()

    initial_state: AgentState = {
        "task_id": task_id,
        "task": task,
        "project_id": project_id,
        "project_path": project_path,
        "plan": [],
        "current_step_index": 0,
        "iteration_count": 0,
        "code_changes": [],
        "execution_results": [],
        "context_chunks": [],
        "status": "planning",
        "error": "",
    }

    final_state = await app.ainvoke(initial_state)
    return final_state
