import json
import uuid
from unittest.mock import AsyncMock, patch

import pytest

from ade.core.models import LLMResponse
from ade.rag.retriever import rerank
from ade.rag.types import RetrievalResult


@pytest.fixture
def sample_results():
    """Sample retrieval results for reranking tests."""
    return [
        RetrievalResult(
            chunk_id=uuid.uuid4(),
            file_path="auth.py",
            chunk_text="def authenticate(user, password): ...",
            chunk_type="function",
            start_line=1,
            end_line=10,
            score=0.85,
        ),
        RetrievalResult(
            chunk_id=uuid.uuid4(),
            file_path="utils.py",
            chunk_text="def format_date(dt): ...",
            chunk_type="function",
            start_line=5,
            end_line=15,
            score=0.80,
        ),
        RetrievalResult(
            chunk_id=uuid.uuid4(),
            file_path="models.py",
            chunk_text="class User: ...",
            chunk_type="class",
            start_line=1,
            end_line=20,
            score=0.75,
        ),
    ]


@pytest.mark.asyncio
async def test_rerank_scores_and_sorts(sample_results):
    """Reranking should assign scores and sort by relevance."""
    rerank_response = json.dumps([
        {"index": 0, "score": 0.9},
        {"index": 1, "score": 0.3},
        {"index": 2, "score": 0.7},
    ])

    mock_llm = AsyncMock()
    mock_llm.complete = AsyncMock(return_value=LLMResponse(
        content=rerank_response,
        model="claude-haiku-235-20250301",
        input_tokens=100,
        output_tokens=50,
        cached=False,
        latency_ms=200.0,
    ))

    with patch("ade.rag.retriever.get_llm", return_value=mock_llm):
        results = await rerank("authentication logic", sample_results, top_n=2)

    assert len(results) == 2
    # First result should be auth.py (score 0.9)
    assert results[0].file_path == "auth.py"
    assert results[0].rerank_score == 0.9
    # Second should be models.py (score 0.7)
    assert results[1].file_path == "models.py"
    assert results[1].rerank_score == 0.7


@pytest.mark.asyncio
async def test_rerank_handles_llm_failure(sample_results):
    """If LLM call fails, reranking should return original order."""
    mock_llm = AsyncMock()
    mock_llm.complete = AsyncMock(side_effect=Exception("API error"))

    with patch("ade.rag.retriever.get_llm", return_value=mock_llm):
        results = await rerank("query", sample_results, top_n=2)

    assert len(results) == 2
    # Should return in original order (first two)
    assert results[0].file_path == "auth.py"
    assert results[1].file_path == "utils.py"


@pytest.mark.asyncio
async def test_rerank_empty_results():
    """Reranking empty results should return empty list."""
    results = await rerank("query", [], top_n=5)
    assert results == []
