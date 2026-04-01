import logging
import os
import uuid
from pathlib import Path

from sqlalchemy import select

from ade.agents.parsers import parse_code_changes
from ade.agents.state import AgentState
from ade.core.database import async_session_factory
from ade.core.llm import get_llm
from ade.core.models import CodeChange, PlanStep, StepStatus

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (Path(__file__).parent / "prompts" / "codegen_system.txt").read_text()


async def codegen_node(state: AgentState) -> dict:
    """LangGraph node: generate code changes for the current plan step."""
    try:
        task_id = uuid.UUID(state["task_id"])
        plan = state.get("plan", [])
        step_index = state.get("current_step_index", 0)

        if step_index >= len(plan):
            return {"status": "failed", "error": "Step index out of range"}

        current_step = plan[step_index]
        project_path = state.get("project_path", "")

        # Read target file contents for context
        file_contents = _read_target_files(project_path, current_step["target_files"])

        # Build user message
        user_msg = _build_user_message(state, current_step, file_contents)

        # Call LLM
        llm = get_llm()
        step_id = await _get_step_id(task_id, current_step["step_number"])

        response = await llm.complete(
            messages=[{"role": "user", "content": user_msg}],
            system=SYSTEM_PROMPT,
            task_id=task_id,
            step_id=step_id,
            agent_name="codegen",
            use_cache=False,  # Don't cache codegen — context changes each time
        )

        # Parse code changes
        changes = parse_code_changes(response.content)
        if not changes:
            return {
                "status": "failed",
                "error": "Codegen produced no valid changes",
            }

        # Persist to DB
        if step_id:
            await _persist_changes(step_id, changes)

        return {
            "code_changes": changes,
            "status": "executing",
        }

    except Exception as e:
        logger.exception("Codegen error: %s", e)
        return {"status": "failed", "error": f"Codegen error: {e}"}


def _read_target_files(project_path: str, target_files: list[str]) -> dict[str, str]:
    """Read the current contents of target files."""
    contents: dict[str, str] = {}
    for file_path in target_files:
        full_path = os.path.join(project_path, file_path)
        try:
            with open(full_path, encoding="utf-8", errors="replace") as f:
                contents[file_path] = f.read()
        except FileNotFoundError:
            contents[file_path] = "(file does not exist yet)"
        except OSError:
            contents[file_path] = "(unable to read file)"
    return contents


def _build_user_message(
    state: AgentState,
    current_step: dict,
    file_contents: dict[str, str],
) -> str:
    """Build the user message for the codegen LLM call."""
    parts = [
        f"Task: {state.get('task', '')}",
        f"\nCurrent step ({current_step['step_number']}): {current_step['description']}",
        f"\nTarget files: {', '.join(current_step['target_files'])}",
    ]

    # Include existing file contents
    if file_contents:
        parts.append("\nExisting file contents:")
        for fp, content in file_contents.items():
            parts.append(f"\n--- {fp} ---\n{content}")

    # Include RAG context
    context = state.get("context_chunks", [])
    if context:
        parts.append("\nRelevant codebase context:")
        for chunk in context[:5]:  # Limit to 5 chunks
            parts.append(f"\n{chunk}")

    # Include error from previous attempt if retrying
    iteration = state.get("iteration_count", 0)
    if iteration > 0:
        results = state.get("execution_results", [])
        if results:
            last = results[-1]
            parts.append(
                f"\n\nPREVIOUS ATTEMPT FAILED (attempt {iteration}):"
                f"\nCommand: {last.get('command', 'unknown')}"
                f"\nExit code: {last.get('exit_code', -1)}"
                f"\nStderr:\n{last.get('stderr', '')}"
                f"\nStdout:\n{last.get('stdout', '')}"
                f"\n\nPlease fix the issue and try again."
            )

    return "\n".join(parts)


async def _get_step_id(
    task_id: uuid.UUID, step_number: int
) -> uuid.UUID | None:
    """Look up the PlanStep DB id for a given task and step number."""
    try:
        async with async_session_factory() as session:
            result = await session.execute(
                select(PlanStep.id).where(
                    PlanStep.task_id == task_id,
                    PlanStep.step_number == step_number,
                )
            )
            row = result.scalar_one_or_none()
            return row
    except Exception:
        return None


async def _persist_changes(
    step_id: uuid.UUID, changes: list[dict]
) -> None:
    """Save code changes to the database."""
    async with async_session_factory() as session:
        step = await session.get(PlanStep, step_id)
        if step:
            step.status = StepStatus.IN_PROGRESS

        for change_dict in changes:
            change = CodeChange(
                step_id=step_id,
                file_path=change_dict["file_path"],
                change_type=change_dict["change_type"],
                diff=change_dict.get("diff"),
                full_content=change_dict.get("full_content"),
            )
            session.add(change)
        await session.commit()
