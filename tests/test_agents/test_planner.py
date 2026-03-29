from unittest.mock import AsyncMock, patch

import pytest

from ade.agents.planner import planner_node
from ade.agents.state import AgentState
from ade.core.models import LLMResponse


@pytest.fixture
def planner_state():
    """Minimal state for testing the planner node."""
    return AgentState(
        task_id="00000000-0000-0000-0000-000000000001",
        task="Add user authentication to the API",
        project_id="00000000-0000-0000-0000-000000000002",
        project_path="/tmp/test-project",
        plan=[],
        current_step_index=0,
        iteration_count=0,
        code_changes=[],
        execution_results=[],
        context_chunks=[],
        status="planning",
        error="",
    )


SAMPLE_PLAN_XML = """Here's my plan:

<plan>
<step>
<step_number>1</step_number>
<description>Create User model</description>
<target_files>
<file>models/user.py</file>
</target_files>
<dependencies></dependencies>
</step>
<step>
<step_number>2</step_number>
<description>Add auth routes</description>
<target_files>
<file>routes/auth.py</file>
</target_files>
<dependencies>
<dep>1</dep>
</dependencies>
</step>
</plan>"""


@pytest.mark.asyncio
async def test_planner_returns_plan(planner_state):
    """Planner should return a parsed plan in state."""
    mock_llm = AsyncMock()
    mock_llm.complete = AsyncMock(return_value=LLMResponse(
        content=SAMPLE_PLAN_XML,
        model="claude-sonnet-4-20250514",
        input_tokens=100,
        output_tokens=200,
        cached=False,
        latency_ms=500.0,
    ))

    with (
        patch("ade.agents.planner.get_llm", return_value=mock_llm),
        patch("ade.agents.planner._get_context", new_callable=AsyncMock, return_value=[]),
        patch("ade.agents.planner._persist_plan", new_callable=AsyncMock),
    ):
        result = await planner_node(planner_state)

    assert result["status"] == "coding"
    assert len(result["plan"]) == 2
    assert result["plan"][0]["description"] == "Create User model"
    assert result["current_step_index"] == 0


@pytest.mark.asyncio
async def test_planner_calls_rag(planner_state):
    """Planner should call RAG for codebase context."""
    mock_llm = AsyncMock()
    mock_llm.complete = AsyncMock(return_value=LLMResponse(
        content=SAMPLE_PLAN_XML,
        model="claude-sonnet-4-20250514",
        input_tokens=100,
        output_tokens=200,
        cached=False,
        latency_ms=500.0,
    ))

    mock_context = AsyncMock(return_value=["def existing_func(): pass"])

    with (
        patch("ade.agents.planner.get_llm", return_value=mock_llm),
        patch("ade.agents.planner._get_context", mock_context),
        patch("ade.agents.planner._persist_plan", new_callable=AsyncMock),
    ):
        result = await planner_node(planner_state)

    mock_context.assert_called_once()
    assert result["context_chunks"] == ["def existing_func(): pass"]


@pytest.mark.asyncio
async def test_planner_handles_empty_plan(planner_state):
    """If LLM returns no valid plan, status should be 'failed'."""
    mock_llm = AsyncMock()
    mock_llm.complete = AsyncMock(return_value=LLMResponse(
        content="I'm not sure what to do.",
        model="claude-sonnet-4-20250514",
        input_tokens=50,
        output_tokens=20,
        cached=False,
        latency_ms=200.0,
    ))

    with (
        patch("ade.agents.planner.get_llm", return_value=mock_llm),
        patch("ade.agents.planner._get_context", new_callable=AsyncMock, return_value=[]),
    ):
        result = await planner_node(planner_state)

    assert result["status"] == "failed"
    assert "no valid steps" in result["error"]


@pytest.mark.asyncio
async def test_planner_handles_llm_error(planner_state):
    """If LLM raises an exception, planner should fail gracefully."""
    mock_llm = AsyncMock()
    mock_llm.complete = AsyncMock(side_effect=Exception("API error"))

    with (
        patch("ade.agents.planner.get_llm", return_value=mock_llm),
        patch("ade.agents.planner._get_context", new_callable=AsyncMock, return_value=[]),
    ):
        result = await planner_node(planner_state)

    assert result["status"] == "failed"
    assert "error" in result["error"].lower() or "Error" in result["error"]
