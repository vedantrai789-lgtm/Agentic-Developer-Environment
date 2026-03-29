import pytest

from ade.agents.executor import MockExecutor, _determine_command, executor_node
from ade.agents.state import AgentState


@pytest.mark.asyncio
async def test_mock_executor_returns_success():
    """MockExecutor should always return exit code 0."""
    executor = MockExecutor()
    result = await executor.run("pytest -v", "/tmp/project")
    assert result["exit_code"] == 0
    assert result["command"] == "pytest -v"
    assert "passed" in result["stdout"].lower()


@pytest.mark.asyncio
async def test_executor_node_returns_result():
    """Executor node should return execution results in state."""
    state = AgentState(
        task_id="00000000-0000-0000-0000-000000000001",
        task="Test task",
        project_id="00000000-0000-0000-0000-000000000002",
        project_path="/tmp/test-project",
        plan=[{
            "step_number": 1,
            "description": "Test step",
            "target_files": ["test_main.py"],
            "dependencies": [],
        }],
        current_step_index=0,
        iteration_count=0,
        code_changes=[],
        execution_results=[],
        context_chunks=[],
        status="executing",
        error="",
    )

    # Mock DB calls and force MockExecutor
    from unittest.mock import AsyncMock, patch

    with (
        patch("ade.agents.executor._get_step_id", new_callable=AsyncMock, return_value=None),
        patch("ade.agents.executor.get_executor", return_value=MockExecutor()),
    ):
        result = await executor_node(state)

    assert result["status"] == "reviewing"
    assert len(result["execution_results"]) == 1
    assert result["execution_results"][0]["exit_code"] == 0


def test_determine_command_with_test_files():
    """Should include test files in the pytest command."""
    plan = [{"target_files": ["src/main.py", "tests/test_main.py"], "step_number": 1}]
    cmd = _determine_command(plan, 0)
    assert "test_main.py" in cmd
    assert cmd.startswith("pytest")


def test_determine_command_without_test_files():
    """Should fall back to generic pytest when no test files."""
    plan = [{"target_files": ["src/main.py", "src/utils.py"], "step_number": 1}]
    cmd = _determine_command(plan, 0)
    assert cmd == "pytest -v"


def test_determine_command_empty_plan():
    """Should fall back to generic pytest for empty plan."""
    cmd = _determine_command([], 0)
    assert cmd == "pytest -v"
