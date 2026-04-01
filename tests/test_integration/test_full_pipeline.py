"""Integration tests for the full agent pipeline.

These tests exercise the full LangGraph pipeline (planner → codegen → executor
→ apply → complete) with mocked LLM and executor backends.
"""

from unittest.mock import AsyncMock, patch

import pytest

from ade.agents.executor import MockExecutor
from ade.agents.orchestrator import run_task
from ade.core.models import LLMResponse

PLAN_1_STEP = """<plan>
<step>
<step_number>1</step_number>
<description>Create greeting module</description>
<target_files><file>greet.py</file></target_files>
<dependencies></dependencies>
</step>
</plan>"""

PLAN_2_STEPS = """<plan>
<step>
<step_number>1</step_number>
<description>Create utils module</description>
<target_files><file>utils.py</file></target_files>
<dependencies></dependencies>
</step>
<step>
<step_number>2</step_number>
<description>Create main module using utils</description>
<target_files><file>main.py</file></target_files>
<dependencies><dep>1</dep></dependencies>
</step>
</plan>"""

CODEGEN_GREET = """<code_changes>
<change>
<file_path>greet.py</file_path>
<change_type>create</change_type>
<full_content>def greet(name):
    return f"Hello, {name}!"
</full_content>
</change>
</code_changes>"""

CODEGEN_UTILS = """<code_changes>
<change>
<file_path>utils.py</file_path>
<change_type>create</change_type>
<full_content>def add(a, b):
    return a + b
</full_content>
</change>
</code_changes>"""

CODEGEN_MAIN = """<code_changes>
<change>
<file_path>main.py</file_path>
<change_type>create</change_type>
<full_content>from utils import add
print(add(1, 2))
</full_content>
</change>
</code_changes>"""


def _make_response(content: str) -> LLMResponse:
    return LLMResponse(
        content=content, model="test", input_tokens=10,
        output_tokens=10, cached=False, latency_ms=50.0,
    )


def _standard_patches(mock_llm, extra_patches=None):
    """Return a combined context manager with all standard mocks."""
    from contextlib import ExitStack

    patches = [
        patch("ade.agents.planner.get_llm", return_value=mock_llm),
        patch("ade.agents.planner._get_context", new_callable=AsyncMock, return_value=[]),
        patch("ade.agents.planner._persist_plan", new_callable=AsyncMock),
        patch("ade.agents.planner._get_file_tree", return_value=""),
        patch("ade.agents.codegen.get_llm", return_value=mock_llm),
        patch("ade.agents.codegen._get_step_id", new_callable=AsyncMock, return_value=None),
        patch("ade.agents.executor._get_step_id", new_callable=AsyncMock, return_value=None),
        patch("ade.agents.executor.get_executor", return_value=MockExecutor()),
        patch(
            "ade.agents.orchestrator.apply_changes",
            AsyncMock(return_value={"status": "complete"}),
        ),
        patch(
            "ade.agents.orchestrator.mark_complete",
            AsyncMock(return_value={"status": "complete"}),
        ),
    ]
    if extra_patches:
        patches.extend(extra_patches)

    stack = ExitStack()
    for p in patches:
        stack.enter_context(p)
    return stack


@pytest.mark.asyncio
async def test_single_step_pipeline():
    """Single-step plan should complete successfully."""
    mock_llm = AsyncMock()
    mock_llm.complete = AsyncMock(
        side_effect=[_make_response(PLAN_1_STEP), _make_response(CODEGEN_GREET)]
    )

    with _standard_patches(mock_llm):
        final = await run_task(
            task_id="00000000-0000-0000-0000-000000000001",
            task="Create a greeting module",
            project_id="00000000-0000-0000-0000-000000000002",
            project_path="/tmp/fake",
        )

    assert final["status"] == "complete"
    assert len(final["plan"]) == 1
    assert final["plan"][0]["description"] == "Create greeting module"


@pytest.mark.asyncio
async def test_multi_step_pipeline():
    """Two-step plan should advance through both steps then complete."""
    mock_llm = AsyncMock()
    mock_llm.complete = AsyncMock(
        side_effect=[
            _make_response(PLAN_2_STEPS),
            _make_response(CODEGEN_UTILS),
            _make_response(CODEGEN_MAIN),
        ]
    )

    with _standard_patches(mock_llm):
        final = await run_task(
            task_id="00000000-0000-0000-0000-000000000001",
            task="Create utils and main",
            project_id="00000000-0000-0000-0000-000000000002",
            project_path="/tmp/fake",
        )

    assert final["status"] == "complete"
    assert len(final["plan"]) == 2
    # Should have advanced past step 0 to step 1
    assert final["current_step_index"] == 1


@pytest.mark.asyncio
async def test_pipeline_planner_failure():
    """If planner produces no plan, the pipeline should fail."""
    mock_llm = AsyncMock()
    mock_llm.complete = AsyncMock(
        return_value=_make_response("I don't know how to do that.")
    )

    mock_fail = AsyncMock(return_value={"status": "failed", "error": "No plan"})

    with _standard_patches(mock_llm, [
        patch("ade.agents.orchestrator.mark_failed", mock_fail),
    ]):
        final = await run_task(
            task_id="00000000-0000-0000-0000-000000000001",
            task="Do something impossible",
            project_id="00000000-0000-0000-0000-000000000002",
            project_path="/tmp/fake",
        )

    assert final["status"] == "failed"


@pytest.mark.asyncio
async def test_pipeline_codegen_failure():
    """If codegen produces no valid changes, pipeline should fail."""
    mock_llm = AsyncMock()
    mock_llm.complete = AsyncMock(
        side_effect=[
            _make_response(PLAN_1_STEP),
            _make_response("Sorry, I can't generate code for that."),
        ]
    )

    mock_fail = AsyncMock(return_value={"status": "failed", "error": "Codegen failed"})

    with _standard_patches(mock_llm, [
        patch("ade.agents.orchestrator.mark_failed", mock_fail),
    ]):
        final = await run_task(
            task_id="00000000-0000-0000-0000-000000000001",
            task="Create something",
            project_id="00000000-0000-0000-0000-000000000002",
            project_path="/tmp/fake",
        )

    assert final["status"] == "failed"


@pytest.mark.asyncio
async def test_pipeline_executor_retry_then_pass():
    """Executor failure should trigger retry, then pass on second attempt."""
    from ade.agents.executor import ExecutionResultDict, ExecutorBackend

    call_count = 0

    class FailThenPassExecutor(ExecutorBackend):
        async def run(self, command, workdir, timeout=60):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return ExecutionResultDict(
                    exit_code=1, command=command,
                    stdout="", stderr="error", duration_ms=10,
                )
            return ExecutionResultDict(
                exit_code=0, command=command,
                stdout="OK", stderr="", duration_ms=10,
            )

    mock_llm = AsyncMock()
    # Plan, codegen attempt 1, codegen attempt 2 (retry)
    mock_llm.complete = AsyncMock(
        side_effect=[
            _make_response(PLAN_1_STEP),
            _make_response(CODEGEN_GREET),
            _make_response(CODEGEN_GREET),
        ]
    )

    with _standard_patches(mock_llm, [
        patch("ade.agents.executor.get_executor", return_value=FailThenPassExecutor()),
    ]):
        final = await run_task(
            task_id="00000000-0000-0000-0000-000000000001",
            task="Create greeting",
            project_id="00000000-0000-0000-0000-000000000002",
            project_path="/tmp/fake",
        )

    assert final["status"] == "complete"
    assert call_count == 2
