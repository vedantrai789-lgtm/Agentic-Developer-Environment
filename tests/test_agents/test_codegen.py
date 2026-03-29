import os
import tempfile
from unittest.mock import AsyncMock, patch

import pytest

from ade.agents.codegen import _read_target_files, codegen_node
from ade.agents.state import AgentState
from ade.core.models import LLMResponse

SAMPLE_CODEGEN_XML = """<code_changes>
<change>
<file_path>models/user.py</file_path>
<change_type>create</change_type>
<full_content>
class User:
    def __init__(self, name: str):
        self.name = name
</full_content>
</change>
</code_changes>"""


@pytest.fixture
def codegen_state():
    return AgentState(
        task_id="00000000-0000-0000-0000-000000000001",
        task="Add user model",
        project_id="00000000-0000-0000-0000-000000000002",
        project_path="/tmp/test-project",
        plan=[{
            "step_number": 1,
            "description": "Create user model",
            "target_files": ["models/user.py"],
            "dependencies": [],
        }],
        current_step_index=0,
        iteration_count=0,
        code_changes=[],
        execution_results=[],
        context_chunks=[],
        status="coding",
        error="",
    )


@pytest.mark.asyncio
async def test_codegen_returns_changes(codegen_state):
    """Codegen should return parsed code changes in state."""
    mock_llm = AsyncMock()
    mock_llm.complete = AsyncMock(return_value=LLMResponse(
        content=SAMPLE_CODEGEN_XML,
        model="claude-sonnet-4-20250514",
        input_tokens=200,
        output_tokens=100,
        cached=False,
        latency_ms=800.0,
    ))

    with (
        patch("ade.agents.codegen.get_llm", return_value=mock_llm),
        patch("ade.agents.codegen._get_step_id", new_callable=AsyncMock, return_value=None),
    ):
        result = await codegen_node(codegen_state)

    assert result["status"] == "executing"
    assert len(result["code_changes"]) == 1
    assert result["code_changes"][0]["file_path"] == "models/user.py"
    assert result["code_changes"][0]["change_type"] == "create"


@pytest.mark.asyncio
async def test_codegen_includes_error_on_retry(codegen_state):
    """On retry, codegen should include previous error in prompt."""
    codegen_state["iteration_count"] = 1
    codegen_state["execution_results"] = [{
        "command": "pytest tests/ -v",
        "exit_code": 1,
        "stdout": "",
        "stderr": "NameError: name 'User' is not defined",
        "duration_ms": 50,
    }]

    mock_llm = AsyncMock()
    mock_llm.complete = AsyncMock(return_value=LLMResponse(
        content=SAMPLE_CODEGEN_XML,
        model="claude-sonnet-4-20250514",
        input_tokens=200,
        output_tokens=100,
        cached=False,
        latency_ms=800.0,
    ))

    with (
        patch("ade.agents.codegen.get_llm", return_value=mock_llm),
        patch("ade.agents.codegen._get_step_id", new_callable=AsyncMock, return_value=None),
    ):
        await codegen_node(codegen_state)

    # Check that the user message included error context
    call_kwargs = mock_llm.complete.call_args.kwargs
    user_content = call_kwargs["messages"][0]["content"]
    assert "PREVIOUS ATTEMPT FAILED" in user_content
    assert "NameError" in user_content


@pytest.mark.asyncio
async def test_codegen_handles_llm_error(codegen_state):
    """Codegen should fail gracefully on LLM error."""
    mock_llm = AsyncMock()
    mock_llm.complete = AsyncMock(side_effect=Exception("API timeout"))

    with (
        patch("ade.agents.codegen.get_llm", return_value=mock_llm),
        patch("ade.agents.codegen._get_step_id", new_callable=AsyncMock, return_value=None),
    ):
        result = await codegen_node(codegen_state)

    assert result["status"] == "failed"


def test_read_target_files_existing():
    """Should read contents of existing files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        os.makedirs(os.path.join(tmpdir, "models"))
        with open(os.path.join(tmpdir, "models", "user.py"), "w") as f:
            f.write("class User: pass")

        contents = _read_target_files(tmpdir, ["models/user.py"])
        assert "class User: pass" in contents["models/user.py"]


def test_read_target_files_missing():
    """Should handle missing files gracefully."""
    with tempfile.TemporaryDirectory() as tmpdir:
        contents = _read_target_files(tmpdir, ["nonexistent.py"])
        assert "does not exist" in contents["nonexistent.py"]
