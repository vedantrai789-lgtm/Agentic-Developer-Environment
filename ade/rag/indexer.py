import os
import time
from datetime import datetime, timezone

import pathspec
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from ade.core.config import get_settings
from ade.core.database import async_session_factory
from ade.core.models import Embedding, Project
from ade.rag.chunking import chunk_file
from ade.rag.embeddings import get_embedder
from ade.rag.types import IndexResult

INDEXABLE_EXTENSIONS = {
    ".py", ".js", ".ts", ".tsx", ".jsx",
    ".md", ".txt", ".rst",
    ".yaml", ".yml", ".json", ".toml", ".cfg", ".ini",
    ".sql", ".sh", ".bash",
    ".html", ".css", ".scss",
    ".go", ".rs", ".java", ".c", ".cpp", ".h", ".hpp",
    ".rb", ".ex", ".exs", ".kt",
    ".dockerfile", ".env.example",
}

# Always ignore these directories regardless of .gitignore
ALWAYS_IGNORE = {
    ".git", "node_modules", "__pycache__", ".venv", "venv",
    ".mypy_cache", ".ruff_cache",
}


def _load_gitignore_spec(project_path: str) -> pathspec.PathSpec:
    """Load .gitignore patterns from the project root."""
    gitignore_path = os.path.join(project_path, ".gitignore")
    patterns: list[str] = []
    if os.path.isfile(gitignore_path):
        with open(gitignore_path) as f:
            patterns = f.read().splitlines()
    # Add hardcoded ignores
    for d in ALWAYS_IGNORE:
        patterns.append(f"{d}/")
    return pathspec.PathSpec.from_lines("gitwildmatch", patterns)


def _walk_project_files(project_path: str) -> list[str]:
    """Walk the project directory and return indexable file paths (relative)."""
    settings = get_settings()
    spec = _load_gitignore_spec(project_path)
    files: list[str] = []

    for root, dirs, filenames in os.walk(project_path):
        # Filter dirs in-place to prevent descending into ignored directories
        rel_root = os.path.relpath(root, project_path)
        dirs[:] = [
            d for d in dirs
            if d not in ALWAYS_IGNORE
            and not spec.match_file(os.path.join(rel_root, d) + "/")
        ]

        for filename in filenames:
            rel_path = os.path.relpath(os.path.join(root, filename), project_path)
            _, ext = os.path.splitext(filename)

            # Check extension
            if ext.lower() not in INDEXABLE_EXTENSIONS and filename not in INDEXABLE_EXTENSIONS:
                continue

            # Check gitignore
            if spec.match_file(rel_path):
                continue

            # Check file size
            full_path = os.path.join(root, filename)
            try:
                if os.path.getsize(full_path) > settings.rag_max_file_size:
                    continue
            except OSError:
                continue

            files.append(rel_path)

    return sorted(files)


def _get_file_mtime(project_path: str, file_path: str) -> datetime:
    """Get the modification time of a file as a timezone-aware datetime."""
    full_path = os.path.join(project_path, file_path)
    mtime = os.path.getmtime(full_path)
    return datetime.fromtimestamp(mtime, tz=timezone.utc)


async def _get_stale_files(
    session: AsyncSession,
    project_id: "str",
    project_path: str,
    file_paths: list[str],
) -> list[str]:
    """Return files that are new or modified since last indexing."""
    if not file_paths:
        return []

    # Get existing embeddings' last_modified per file
    result = await session.execute(
        select(Embedding.file_path, Embedding.last_modified)
        .where(Embedding.project_id == project_id)
        .distinct(Embedding.file_path)
    )
    indexed: dict[str, datetime] = {row.file_path: row.last_modified for row in result}

    stale: list[str] = []
    for fp in file_paths:
        mtime = _get_file_mtime(project_path, fp)
        if fp not in indexed or mtime > indexed[fp]:
            stale.append(fp)
    return stale


async def _delete_file_embeddings(
    session: AsyncSession, project_id: "str", file_path: str
) -> None:
    """Delete all embeddings for a file before re-indexing."""
    await session.execute(
        delete(Embedding).where(
            Embedding.project_id == project_id,
            Embedding.file_path == file_path,
        )
    )


async def index_project(
    project_id: "str",
    project_path: str,
    force: bool = False,
) -> IndexResult:
    """Index a project: walk files, chunk, embed, store in pgvector.

    Args:
        project_id: UUID of the project in the database.
        project_path: Absolute path to the project directory.
        force: If True, re-index all files regardless of staleness.
    """
    start_time = time.monotonic()
    embedder = get_embedder()

    # Walk files
    all_files = _walk_project_files(project_path)

    async with async_session_factory() as session:
        # Determine which files need indexing
        if force:
            stale_files = all_files
        else:
            stale_files = await _get_stale_files(session, project_id, project_path, all_files)

        if not stale_files:
            duration_ms = (time.monotonic() - start_time) * 1000
            return IndexResult(
                files_indexed=0,
                chunks_created=0,
                files_skipped=len(all_files),
                files_removed=0,
                duration_ms=duration_ms,
            )

        # Chunk all stale files
        all_chunks = []
        files_skipped = 0
        for file_path in stale_files:
            full_path = os.path.join(project_path, file_path)
            try:
                with open(full_path, encoding="utf-8", errors="replace") as f:
                    content = f.read()
            except OSError:
                files_skipped += 1
                continue

            chunks = chunk_file(content, file_path)
            if not chunks:
                files_skipped += 1
                continue

            # Delete old embeddings for this file
            await _delete_file_embeddings(session, project_id, file_path)

            mtime = _get_file_mtime(project_path, file_path)
            for chunk in chunks:
                all_chunks.append((chunk, file_path, mtime))

        # Generate embeddings in batches
        if all_chunks:
            texts = [c[0].text for c in all_chunks]
            embeddings = await embedder.embed_batch(texts)

            # Create Embedding rows
            for (chunk, file_path, mtime), embedding in zip(all_chunks, embeddings):
                emb = Embedding(
                    project_id=project_id,
                    file_path=file_path,
                    chunk_text=chunk.text,
                    chunk_type=chunk.metadata.chunk_type,
                    start_line=chunk.metadata.start_line,
                    end_line=chunk.metadata.end_line,
                    embedding=embedding,
                    last_modified=mtime,
                )
                session.add(emb)

        # Remove embeddings for files that no longer exist
        files_removed = await _remove_deleted_files(session, project_id, project_path)

        # Update project's last_indexed_at
        project = await session.get(Project, project_id)
        if project:
            project.last_indexed_at = datetime.now(tz=timezone.utc)

        await session.commit()

    duration_ms = (time.monotonic() - start_time) * 1000
    return IndexResult(
        files_indexed=len(stale_files) - files_skipped,
        chunks_created=len(all_chunks),
        files_skipped=files_skipped + (len(all_files) - len(stale_files)),
        files_removed=files_removed,
        duration_ms=duration_ms,
    )


async def _remove_deleted_files(
    session: AsyncSession, project_id: "str", project_path: str
) -> int:
    """Remove embeddings for files that no longer exist on disk."""
    result = await session.execute(
        select(Embedding.file_path)
        .where(Embedding.project_id == project_id)
        .distinct()
    )
    indexed_files = {row.file_path for row in result}

    removed = 0
    for file_path in indexed_files:
        full_path = os.path.join(project_path, file_path)
        if not os.path.isfile(full_path):
            await _delete_file_embeddings(session, project_id, file_path)
            removed += 1
    return removed
