from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ade.core.config import Settings
from ade.rag.embeddings import OpenAIEmbedder, get_embedder


@pytest.fixture
def test_settings():
    return Settings(
        anthropic_api_key="sk-ant-test",
        openai_api_key="sk-test-openai",
        database_url="postgresql+asyncpg://ade:ade@localhost:5432/ade_test",
        database_url_sync="postgresql+psycopg2://ade:ade@localhost:5432/ade_test",
        embedding_provider="openai",
        embedding_model="text-embedding-3-small",
        embedding_batch_size=2,
    )


@pytest.mark.asyncio
async def test_openai_embedder_calls_api(test_settings):
    """OpenAIEmbedder should call the OpenAI API with correct parameters."""
    mock_client = AsyncMock()
    mock_data = [MagicMock(index=0, embedding=[0.1] * 1536)]
    mock_response = MagicMock(data=mock_data)
    mock_client.embeddings.create = AsyncMock(return_value=mock_response)

    with patch("openai.AsyncOpenAI", return_value=mock_client):
        embedder = OpenAIEmbedder(test_settings)

    result = await embedder.embed_batch(["Hello world"])

    embedder.client.embeddings.create.assert_called_once()
    assert len(result) == 1
    assert len(result[0]) == 1536


@pytest.mark.asyncio
async def test_openai_embedder_batching(test_settings):
    """With batch_size=2, 3 texts should produce 2 API calls."""
    mock_client = AsyncMock()

    def make_response(n):
        data = [MagicMock(index=i, embedding=[0.1 * i] * 1536) for i in range(n)]
        return MagicMock(data=data)

    mock_client.embeddings.create = AsyncMock(
        side_effect=[make_response(2), make_response(1)]
    )

    with patch("openai.AsyncOpenAI", return_value=mock_client):
        embedder = OpenAIEmbedder(test_settings)

    result = await embedder.embed_batch(["text1", "text2", "text3"])

    assert embedder.client.embeddings.create.call_count == 2
    assert len(result) == 3


def test_get_embedder_selects_openai():
    """get_embedder should create an OpenAIEmbedder when provider is 'openai'."""
    import ade.rag.embeddings as emb_module

    # Reset singleton
    emb_module._embedder_instance = None

    settings = Settings(
        anthropic_api_key="sk-ant-test",
        openai_api_key="sk-test-openai",
        database_url="postgresql+asyncpg://ade:ade@localhost:5432/ade_test",
        database_url_sync="postgresql+psycopg2://ade:ade@localhost:5432/ade_test",
        embedding_provider="openai",
    )

    with patch("openai.AsyncOpenAI"):
        embedder = get_embedder(settings)
        assert isinstance(embedder, OpenAIEmbedder)

    # Clean up singleton
    emb_module._embedder_instance = None


def test_embedder_dimension(test_settings):
    """Embedder dimension should match settings."""
    with patch("openai.AsyncOpenAI"):
        embedder = OpenAIEmbedder(test_settings)
        assert embedder.dimension == 1024
