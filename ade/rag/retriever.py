import json
import sys
import uuid

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ade.core.config import get_settings
from ade.core.database import async_session_factory
from ade.core.llm import get_llm
from ade.rag.embeddings import get_embedder
from ade.rag.types import RetrievalResult


async def retrieve(
    query: str,
    project_id: uuid.UUID,
    k: int | None = None,
    session: AsyncSession | None = None,
) -> list[RetrievalResult]:
    """Retrieve the top-k most relevant chunks for a query using pgvector cosine similarity."""
    settings = get_settings()
    k = k or settings.rag_retrieval_k
    embedder = get_embedder()

    # Embed the query
    query_vectors = await embedder.embed_batch([query])
    query_vec = query_vectors[0]

    # Format vector for pgvector
    vec_str = "[" + ",".join(str(v) for v in query_vec) + "]"

    sql = text("""
        SELECT chunk_id, file_path, chunk_text, chunk_type, start_line, end_line,
               1 - (embedding <=> :query_vec::vector) AS score
        FROM embeddings
        WHERE project_id = :project_id
        ORDER BY embedding <=> :query_vec::vector
        LIMIT :k
    """)

    async def _execute(sess: AsyncSession) -> list[RetrievalResult]:
        result = await sess.execute(
            sql,
            {"query_vec": vec_str, "project_id": str(project_id), "k": k},
        )
        return [
            RetrievalResult(
                chunk_id=row.chunk_id,
                file_path=row.file_path,
                chunk_text=row.chunk_text,
                chunk_type=row.chunk_type,
                start_line=row.start_line,
                end_line=row.end_line,
                score=float(row.score),
            )
            for row in result
        ]

    if session:
        return await _execute(session)

    async with async_session_factory() as sess:
        return await _execute(sess)


async def rerank(
    query: str,
    results: list[RetrievalResult],
    top_n: int | None = None,
) -> list[RetrievalResult]:
    """Re-rank retrieval results using Claude to score relevance.

    Returns the top_n most relevant results sorted by rerank_score.
    Falls back to original order if LLM call fails.
    """
    if not results:
        return []

    settings = get_settings()
    top_n = top_n or settings.rag_rerank_top_n

    # Build the reranking prompt
    chunks_text = "\n\n".join(
        f"[{i}] ({r.file_path}:{r.start_line}-{r.end_line})\n{r.chunk_text[:1000]}"
        for i, r in enumerate(results)
    )

    system = (
        "You are a code relevance scorer. Given a query and code chunks, "
        "rate each chunk's relevance from 0.0 to 1.0. "
        'Return ONLY valid JSON: [{"index": 0, "score": 0.85}, ...]'
    )
    user_msg = f"Query: {query}\n\nChunks:\n{chunks_text}"

    try:
        llm = get_llm()
        response = await llm.complete(
            messages=[{"role": "user", "content": user_msg}],
            system=system,
            model=settings.default_rerank_model,
            max_tokens=1024,
            temperature=0.0,
            use_cache=True,
            agent_name="reranker",
        )

        scores = json.loads(response.content)
        score_map = {s["index"]: float(s["score"]) for s in scores}

        for i, result in enumerate(results):
            result.rerank_score = score_map.get(i, 0.0)

        # Sort by rerank_score descending
        results.sort(key=lambda r: r.rerank_score or 0.0, reverse=True)

    except Exception as e:
        print(f"Warning: reranking failed, returning original order: {e}", file=sys.stderr)

    return results[:top_n]


async def retrieve_and_rerank(
    query: str,
    project_id: uuid.UUID,
    k: int | None = None,
    top_n: int | None = None,
) -> list[RetrievalResult]:
    """Retrieve chunks then re-rank with Claude. Convenience wrapper."""
    results = await retrieve(query, project_id, k=k)
    return await rerank(query, results, top_n=top_n)
