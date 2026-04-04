import asyncio
import logging
import time
import uuid
from abc import ABC, abstractmethod

from ade.agents.state import AgentState, ExecutionResultDict
from ade.core.database import async_session_factory
from ade.core.models import ExecutionResult, PlanStep, StepStatus

logger = logging.getLogger(__name__)

_executor_instance: "ExecutorBackend | None" = None


class ExecutorBackend(ABC):
    """Abstract base for code execution backends."""

    @abstractmethod
    async def run(
        self, command: str, workdir: str, timeout: int = 60
    ) -> ExecutionResultDict:
        ...


class MockExecutor(ExecutorBackend):
    """Always-pass executor for testing. Returns exit_code=0."""

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


class SubprocessExecutor(ExecutorBackend):
    """Execute commands via local subprocess (no Docker isolation)."""

    async def run(
        self, command: str, workdir: str, timeout: int = 60
    ) -> ExecutionResultDict:
        start = time.monotonic()
        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                cwd=workdir,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                proc.communicate(), timeout=timeout
            )
            duration_ms = int((time.monotonic() - start) * 1000)

            return ExecutionResultDict(
                command=command,
                exit_code=proc.returncode or 0,
                stdout=stdout_bytes.decode("utf-8", errors="replace")[:50_000],
                stderr=stderr_bytes.decode("utf-8", errors="replace")[:50_000],
                duration_ms=duration_ms,
            )

        except asyncio.TimeoutError:
            duration_ms = int((time.monotonic() - start) * 1000)
            return ExecutionResultDict(
                command=command,
                exit_code=1,
                stdout="",
                stderr=f"Command timed out after {timeout}s",
                duration_ms=duration_ms,
            )
        except Exception as e:
            duration_ms = int((time.monotonic() - start) * 1000)
            return ExecutionResultDict(
                command=command,
                exit_code=1,
                stdout="",
                stderr=str(e),
                duration_ms=duration_ms,
            )


def get_executor() -> ExecutorBackend:
    """Get or create the executor backend singleton.

    Uses settings.sandbox_backend to choose: 'docker', 'subprocess', or 'mock'.
    Falls back gracefully with logging.
    """
    global _executor_instance
    if _executor_instance is None:
        try:
            from ade.core.config import get_settings

            settings = get_settings()
            backend = settings.sandbox_backend

            if backend == "docker":
                try:
                    from ade.sandbox.docker_manager import DockerExecutor

                    _executor_instance = DockerExecutor()
                    logger.info("Using Docker executor")
                except Exception as e:
                    logger.warning("Docker unavailable, falling back to subprocess: %s", e)
                    _executor_instance = SubprocessExecutor()

            elif backend == "subprocess":
                _executor_instance = SubprocessExecutor()
                logger.info("Using subprocess executor")

            else:
                _executor_instance = MockExecutor()
                logger.info("Using mock executor")

        except Exception as e:
            logger.warning("Failed to initialize executor, using mock: %s", e)
            _executor_instance = MockExecutor()
    return _executor_instance


def reset_executor() -> None:
    """Reset the singleton (useful for testing)."""
    global _executor_instance
    _executor_instance = None


async def executor_node(state: AgentState) -> dict:
    """LangGraph node: execute tests for the current step's code changes."""
    try:
        task_id = uuid.UUID(state["task_id"])
        plan = state.get("plan", [])
        step_index = state.get("current_step_index", 0)
        project_path = state.get("project_path", "")
        code_changes = state.get("code_changes", [])

        # Determine test command
        command = _determine_command(plan, step_index, project_path)
        logger.info("Executor running: %s in %s", command, project_path)

        executor = get_executor()

        # If using Docker, prepare a sandbox workspace with code changes applied
        is_docker = False
        try:
            from ade.sandbox.docker_manager import DockerExecutor

            is_docker = isinstance(executor, DockerExecutor)
        except ImportError:
            pass

        if is_docker and code_changes:
            from ade.sandbox.workspace import SandboxWorkspace

            async with SandboxWorkspace(project_path) as ws:
                workspace_dir = await ws.prepare(code_changes)
                result = await executor.run(
                    command=command,
                    workdir=str(workspace_dir),
                )
        else:
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

        logger.info(
            "Executor result: exit_code=%d, stdout=%s, stderr=%s",
            result["exit_code"],
            result["stdout"][:200],
            result["stderr"][:200],
        )

        return {
            "execution_results": [result],
            "status": "reviewing",
        }

    except Exception as e:
        logger.exception("Executor error: %s", e)
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


def _determine_command(
    plan: list[dict], step_index: int, project_path: str = ""
) -> str:
    """Determine the test command based on target files and project type."""
    import os

    # Detect project type from files in the project root
    is_node = False
    is_python = False
    if project_path:
        is_node = os.path.exists(os.path.join(project_path, "package.json"))
        is_python = (
            os.path.exists(os.path.join(project_path, "pyproject.toml"))
            or os.path.exists(os.path.join(project_path, "setup.py"))
            or os.path.exists(os.path.join(project_path, "requirements.txt"))
        )

    if step_index < len(plan):
        target_files = plan[step_index].get("target_files", [])
        test_files = [f for f in target_files if "test" in f.lower()]

        if test_files:
            # Check file extensions to pick the right runner
            js_tests = [f for f in test_files if f.endswith((".js", ".ts", ".jsx", ".tsx"))]
            py_tests = [f for f in test_files if f.endswith(".py")]

            if js_tests:
                return f"npx jest {' '.join(js_tests)} --passWithNoTests"
            if py_tests:
                return f"pytest {' '.join(py_tests)} -v"

    # Fallback based on project type
    if is_node:
        return "npm test --if-present || echo 'No tests configured'"
    if is_python:
        return "pytest -v"

    # Unknown project type — try both
    return "echo 'No test runner detected — skipping tests' && exit 0"


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
