import sys
import uuid
from abc import ABC, abstractmethod

from ade.agents.state import AgentState, ExecutionResultDict
from ade.core.database import async_session_factory
from ade.core.models import ExecutionResult, PlanStep, StepStatus

_executor_instance: "ExecutorBackend | None" = None


class ExecutorBackend(ABC):
    """Abstract base for code execution backends."""

    @abstractmethod
    async def run(
        self, command: str, workdir: str, timeout: int = 60
    ) -> ExecutionResultDict:
        ...


class MockExecutor(ExecutorBackend):
    """Always-pass executor for Phase 3. Replaced by DockerExecutor in Phase 4."""

    async def run(
        self, command: str, workdir: str, timeout: int = 60
    ) -> ExecutionResultDict:
        return ExecutionResultDict(
            command=command,
            exit_code=0,
            stdout="All tests passed.\n1 passed in 0.01s",
            stderr="",
            duration_ms=100,
        )


def get_executor() -> ExecutorBackend:
    """Get or create the executor backend singleton."""
    global _executor_instance
    if _executor_instance is None:
        _executor_instance = MockExecutor()
    return _executor_instance


async def executor_node(state: AgentState) -> dict:
    """LangGraph node: execute tests for the current step's code changes."""
    try:
        task_id = uuid.UUID(state["task_id"])
        plan = state.get("plan", [])
        step_index = state.get("current_step_index", 0)
        project_path = state.get("project_path", "")

        # Determine test command
        command = _determine_command(plan, step_index)

        # Run
        executor = get_executor()
        result = await executor.run(
            command=command,
            workdir=project_path,
        )

        # Persist to DB
        current_step = plan[step_index] if step_index < len(plan) else None
        if current_step:
            step_id = await _get_step_id(task_id, current_step["step_number"])
            if step_id:
                await _persist_result(step_id, result)

        return {
            "execution_results": [result],
            "status": "reviewing",
        }

    except Exception as e:
        print(f"Executor error: {e}", file=sys.stderr)
        return {
            "execution_results": [ExecutionResultDict(
                command="unknown",
                exit_code=1,
                stdout="",
                stderr=str(e),
                duration_ms=0,
            )],
            "status": "reviewing",
        }


def _determine_command(plan: list[dict], step_index: int) -> str:
    """Determine the test command based on target files."""
    if step_index < len(plan):
        target_files = plan[step_index].get("target_files", [])
        test_files = [f for f in target_files if "test" in f.lower()]
        if test_files:
            return f"pytest {' '.join(test_files)} -v"
    return "pytest -v"


async def _get_step_id(
    task_id: uuid.UUID, step_number: int
) -> uuid.UUID | None:
    """Look up the PlanStep DB id."""
    try:
        from sqlalchemy import select

        async with async_session_factory() as session:
            result = await session.execute(
                select(PlanStep.id).where(
                    PlanStep.task_id == task_id,
                    PlanStep.step_number == step_number,
                )
            )
            return result.scalar_one_or_none()
    except Exception:
        return None


async def _persist_result(
    step_id: uuid.UUID, result: ExecutionResultDict
) -> None:
    """Save execution result to the database."""
    async with async_session_factory() as session:
        step = await session.get(PlanStep, step_id)
        if step:
            if result["exit_code"] == 0:
                step.status = StepStatus.COMPLETED
            else:
                step.status = StepStatus.FAILED

        exec_result = ExecutionResult(
            step_id=step_id,
            command=result["command"],
            exit_code=result["exit_code"],
            stdout=result["stdout"],
            stderr=result["stderr"],
            duration_ms=result["duration_ms"],
        )
        session.add(exec_result)
        await session.commit()
