from unittest.mock import AsyncMock, patch

import pytest

from ade.agents.orchestrator import (
    advance_step,
    build_graph,
    increment_retry,
    route_after_executor,
    run_task,
)
from ade.agents.state import AgentState

PASS_RESULT = {
    "exit_code": 0, "command": "", "stdout": "",
    "stderr": "", "duration_ms": 0,
}
FAIL_RESULT = {
    "exit_code": 1, "command": "", "stdout": "",
    "stderr": "", "duration_ms": 0,
}


def test_route_after_executor_pass_more_steps():
    """Should route to 'advance' when tests pass and more steps remain."""
    state = AgentState(
        execution_results=[PASS_RESULT],
        current_step_index=0,
        plan=[{"step_number": 1}, {"step_number": 2}],
    )
    assert route_after_executor(state) == "advance"


def test_route_after_executor_pass_done():
    """Should route to 'complete' when tests pass and all steps done."""
    state = AgentState(
        execution_results=[PASS_RESULT],
        current_step_index=1,
        plan=[{"step_number": 1}, {"step_number": 2}],
    )
    assert route_after_executor(state) == "complete"


def test_route_after_executor_fail_retry():
    """Should route to 'retry' when tests fail but retries remain."""
    state = AgentState(
        execution_results=[FAIL_RESULT],
        iteration_count=1,
        plan=[{"step_number": 1}],
    )
    assert route_after_executor(state) == "retry"


def test_route_after_executor_fail_exhausted():
    """Should route to 'fail' when retries are exhausted."""
    state = AgentState(
        execution_results=[FAIL_RESULT],
        iteration_count=3,
        plan=[{"step_number": 1}],
    )
    assert route_after_executor(state) == "fail"


def test_advance_step():
    """Should increment step index and reset per-step state."""
    state = AgentState(
        current_step_index=0,
        iteration_count=2,
    )
    result = advance_step(state)
    assert result["current_step_index"] == 1
    assert result["iteration_count"] == 0
    assert result["code_changes"] == []
    assert result["execution_results"] == []


def test_increment_retry():
    """Should increment iteration count."""
    state = AgentState(iteration_count=1)
    result = increment_retry(state)
    assert result["iteration_count"] == 2


def test_build_graph_compiles():
    """The graph should compile without errors."""
    graph = build_graph()
    app = graph.compile()
    assert app is not None


PLAN_XML = """<plan>
<step>
<step_number>1</step_number>
<description>Create module</description>
<target_files><file>main.py</file></target_files>
<dependencies></dependencies>
</step>
</plan>"""

CODEGEN_XML = """<code_changes>
<change>
<file_path>main.py</file_path>
<change_type>create</change_type>
<full_content>print("hello")</full_content>
</change>
</code_changes>"""


@pytest.mark.asyncio
async def test_run_task_happy_path():
    """Full graph should complete successfully with mocked agents."""
    from ade.core.models import LLMResponse

    plan_response = LLMResponse(
        content=PLAN_XML, model="test", input_tokens=10,
        output_tokens=10, cached=False, latency_ms=100.0,
    )
    codegen_response = LLMResponse(
        content=CODEGEN_XML, model="test", input_tokens=10,
        output_tokens=10, cached=False, latency_ms=100.0,
    )

    mock_llm = AsyncMock()
    mock_llm.complete = AsyncMock(
        side_effect=[plan_response, codegen_response]
    )

    mock_complete = AsyncMock(return_value={"status": "complete"})

    with (
        patch("ade.agents.planner.get_llm", return_value=mock_llm),
        patch("ade.agents.planner._get_context", new_callable=AsyncMock, return_value=[]),
        patch("ade.agents.planner._persist_plan", new_callable=AsyncMock),
        patch("ade.agents.codegen.get_llm", return_value=mock_llm),
        patch("ade.agents.codegen._get_step_id", new_callable=AsyncMock, return_value=None),
        patch("ade.agents.executor._get_step_id", new_callable=AsyncMock, return_value=None),
        patch("ade.agents.orchestrator.mark_complete", mock_complete),
    ):
        final = await run_task(
            task_id="00000000-0000-0000-0000-000000000001",
            task="Create a hello world module",
            project_id="00000000-0000-0000-0000-000000000002",
            project_path="/tmp/test",
        )

    assert final["status"] == "complete"
    assert len(final["plan"]) == 1
