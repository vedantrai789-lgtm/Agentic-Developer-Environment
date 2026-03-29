import uuid

from pydantic import BaseModel


class ChunkMetadata(BaseModel):
    file_path: str
    chunk_type: str  # "function", "class", "module", "block"
    start_line: int
    end_line: int
    token_count: int


class Chunk(BaseModel):
    text: str
    metadata: ChunkMetadata


class RetrievalResult(BaseModel):
    chunk_id: uuid.UUID
    file_path: str
    chunk_text: str
    chunk_type: str
    start_line: int
    end_line: int
    score: float
    rerank_score: float | None = None


class IndexResult(BaseModel):
    files_indexed: int
    chunks_created: int
    files_skipped: int
    files_removed: int
    duration_ms: float
