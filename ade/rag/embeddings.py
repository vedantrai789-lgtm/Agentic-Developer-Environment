from typing import Protocol

from ade.core.config import Settings, get_settings

_embedder_instance: "EmbeddingProvider | None" = None


class EmbeddingProvider(Protocol):
    """Protocol for embedding providers."""

    @property
    def dimension(self) -> int: ...

    async def embed_batch(self, texts: list[str]) -> list[list[float]]: ...


class OpenAIEmbedder:
    """OpenAI embeddings via text-embedding-3-small (1536-dim)."""

    def __init__(self, settings: Settings) -> None:
        import openai

        self.client = openai.AsyncOpenAI(api_key=settings.openai_api_key)
        self.model = settings.embedding_model
        self._dimension = settings.embedding_dimension
        self.batch_size = settings.embedding_batch_size

    @property
    def dimension(self) -> int:
        return self._dimension

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed a list of texts, handling internal batching."""
        all_embeddings: list[list[float]] = []
        for i in range(0, len(texts), self.batch_size):
            batch = texts[i : i + self.batch_size]
            response = await self.client.embeddings.create(
                model=self.model,
                input=batch,
            )
            # Sort by index to preserve order
            sorted_data = sorted(response.data, key=lambda x: x.index)
            all_embeddings.extend([d.embedding for d in sorted_data])
        return all_embeddings


class VoyageEmbedder:
    """Voyage AI embeddings."""

    def __init__(self, settings: Settings) -> None:
        import voyageai

        self.client = voyageai.AsyncClient(api_key=settings.voyage_api_key)
        self.model = settings.embedding_model
        self._dimension = settings.embedding_dimension
        self.batch_size = settings.embedding_batch_size

    @property
    def dimension(self) -> int:
        return self._dimension

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed a list of texts, handling internal batching."""
        all_embeddings: list[list[float]] = []
        for i in range(0, len(texts), self.batch_size):
            batch = texts[i : i + self.batch_size]
            result = await self.client.embed(batch, model=self.model)
            all_embeddings.extend(result.embeddings)
        return all_embeddings


def get_embedder(settings: Settings | None = None) -> EmbeddingProvider:
    """Get or create the embedding provider singleton."""
    global _embedder_instance
    if _embedder_instance is None:
        settings = settings or get_settings()
        if settings.embedding_provider == "voyage":
            _embedder_instance = VoyageEmbedder(settings)
        else:
            _embedder_instance = OpenAIEmbedder(settings)
    return _embedder_instance
