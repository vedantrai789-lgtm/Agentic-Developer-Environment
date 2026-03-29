import sys
import uuid
from datetime import datetime, timezone

from langgraph.graph import END, START, StateGraph

from ade.agents.codegen import codegen_node
from ade.agents.executor import executor_node
from ade.agents.planner import planner_node
from ade.agents.state import AgentState
from ade.core.database import async_session_factory
from ade.core.models import Task, TaskStatus

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
    return "complete"


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
        print(f"Failed to mark task complete: {e}", file=sys.stderr)

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
        print(f"Failed to mark task failed: {e}", file=sys.stderr)

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
            "complete": "complete",
            "fail": "fail",
        },
    )

    # After advance: loop back to codegen for next step
    graph.add_edge("advance", "codegen")

    # After retry: loop back to codegen with incremented counter
    graph.add_edge("retry", "codegen")

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
    """Entry point: build the graph and run it for a task.

    Args:
        task_id: UUID string of the Task row in the database.
        task: Natural language task description from the user.
        project_id: UUID string of the Project row.
        project_path: Absolute filesystem path to the project.

    Returns:
        Final AgentState after the graph completes.
    """
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
