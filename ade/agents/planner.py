import logging
import uuid
from pathlib import Path

from ade.agents.parsers import parse_plan
from ade.agents.state import AgentState
from ade.core.database import async_session_factory
from ade.core.llm import get_llm
from ade.core.models import PlanStep, Task, TaskStatus

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (Path(__file__).parent / "prompts" / "planner_system.txt").read_text()

# Dirs to skip when building the file tree (same as sandbox workspace)
_SKIP_DIRS = {
    ".git", ".venv", "venv", "node_modules", "__pycache__",
    ".mypy_cache", ".pytest_cache", ".ruff_cache", "dist", "build",
    ".ade-backup",
}


async def planner_node(state: AgentState) -> dict:
    """LangGraph node: generate an implementation plan from task + RAG context."""
    try:
        task_id = uuid.UUID(state["task_id"])
        project_id = uuid.UUID(state["project_id"])
        project_path = state.get("project_path", "")

        await _publish_event(state, "status_change", {"status": "planning"})

        # Get RAG context
        context_chunks = await _get_context(state["task"], project_id)

        # Get project file tree
        file_tree = _get_file_tree(project_path) if project_path else ""

        # Build the user message
        parts = [f"Task: {state['task']}"]

        if file_tree:
            parts.append(f"\nProject file tree:\n{file_tree}")

        if context_chunks:
            context_text = "\n\n---\n\n".join(context_chunks)
            parts.append(f"\nRelevant code from the codebase:\n{context_text}")
        else:
            parts.append("\nNo codebase context available.")

        user_msg = "\n".join(parts)

        # Call LLM
        llm = get_llm()
        response = await llm.complete(
            messages=[{"role": "user", "content": user_msg}],
            system=SYSTEM_PROMPT,
            task_id=task_id,
            agent_name="planner",
        )

        # Parse plan
        plan = parse_plan(response.content)
        if not plan:
            return {
                "status": "failed",
                "error": "Planner produced no valid steps",
            }

        # Persist to DB
        await _persist_plan(task_id, plan)

        await _publish_event(
            state, "step_started",
            {"message": f"Plan created with {len(plan)} steps"},
        )

        return {
            "plan": plan,
            "context_chunks": context_chunks,
            "current_step_index": 0,
            "iteration_count": 0,
            "status": "coding",
        }

    except Exception as e:
        logger.exception("Planner error: %s", e)
        return {"status": "failed", "error": f"Planner error: {e}"}


def _get_file_tree(project_path: str, max_depth: int = 3, max_lines: int = 100) -> str:
    """Build a concise file tree string for the project."""
    lines: list[str] = []
    root = Path(project_path)

    def _walk(path: Path, prefix: str, depth: int) -> None:
        if depth > max_depth or len(lines) >= max_lines:
            return

        try:
            entries = sorted(path.iterdir(), key=lambda p: (p.is_file(), p.name))
        except PermissionError:
            return

        dirs = [e for e in entries if e.is_dir() and e.name not in _SKIP_DIRS]
        files = [e for e in entries if e.is_file()]

        for f in files:
            if len(lines) >= max_lines:
                lines.append(f"{prefix}... (truncated)")
                return
            lines.append(f"{prefix}{f.name}")

        for d in dirs:
            if len(lines) >= max_lines:
                lines.append(f"{prefix}... (truncated)")
                return
            lines.append(f"{prefix}{d.name}/")
            _walk(d, prefix + "  ", depth + 1)

    _walk(root, "", 0)
    return "\n".join(lines)


async def _get_context(task: str, project_id: uuid.UUID) -> list[str]:
    """Retrieve RAG context, returning empty list on failure."""
    try:
        from ade.rag.retriever import retrieve_and_rerank

        results = await retrieve_and_rerank(task, project_id)
        return [r.chunk_text for r in results]
    except Exception as e:
        logger.warning("RAG context retrieval failed: %s", e)
        return []


async def _persist_plan(task_id: uuid.UUID, plan: list[dict]) -> None:
    """Save plan steps to the database."""
    async with async_session_factory() as session:
        task = await session.get(Task, task_id)
        if task:
            task.status = TaskStatus.PLANNING

        for step_dict in plan:
            step = PlanStep(
                task_id=task_id,
                step_number=step_dict["step_number"],
                description=step_dict["description"],
                target_files=step_dict["target_files"],
            )
            session.add(step)
        await session.commit()


async def _publish_event(state: AgentState, event_type: str, data: dict) -> None:
    """Best-effort event publishing."""
    try:
        from ade.api.events import publish_task_event

        await publish_task_event(state.get("task_id", ""), event_type, data)
    except Exception:
        pass
