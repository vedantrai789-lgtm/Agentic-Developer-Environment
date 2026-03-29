import sys
import uuid
from pathlib import Path

from ade.agents.parsers import parse_plan
from ade.agents.state import AgentState
from ade.core.database import async_session_factory
from ade.core.llm import get_llm
from ade.core.models import PlanStep, Task, TaskStatus

SYSTEM_PROMPT = (Path(__file__).parent / "prompts" / "planner_system.txt").read_text()


async def planner_node(state: AgentState) -> dict:
    """LangGraph node: generate an implementation plan from task + RAG context."""
    try:
        task_id = uuid.UUID(state["task_id"])
        project_id = uuid.UUID(state["project_id"])

        # Get RAG context
        context_chunks = await _get_context(state["task"], project_id)

        # Build the user message
        if context_chunks:
            context_text = "\n\n---\n\n".join(context_chunks)
        else:
            context_text = "No codebase context available."
        user_msg = (
            f"Task: {state['task']}\n\n"
            f"Relevant code from the codebase:\n{context_text}"
        )

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

        return {
            "plan": plan,
            "context_chunks": context_chunks,
            "current_step_index": 0,
            "iteration_count": 0,
            "status": "coding",
        }

    except Exception as e:
        print(f"Planner error: {e}", file=sys.stderr)
        return {"status": "failed", "error": f"Planner error: {e}"}


async def _get_context(task: str, project_id: uuid.UUID) -> list[str]:
    """Retrieve RAG context, returning empty list on failure."""
    try:
        from ade.rag.retriever import retrieve_and_rerank

        results = await retrieve_and_rerank(task, project_id)
        return [r.chunk_text for r in results]
    except Exception:
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
