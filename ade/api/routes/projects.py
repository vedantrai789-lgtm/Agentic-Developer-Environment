"""Project management endpoints."""

from __future__ import annotations

import asyncio
import sys
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ade.api.dependencies import get_session
from ade.api.schemas import ProjectDetailResponse, ProjectResponse
from ade.core.models import Embedding, Project, ProjectCreate, Task

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("/", response_model=ProjectResponse, status_code=201)
async def create_project(
    body: ProjectCreate,
    session: AsyncSession = Depends(get_session),
):
    """Register a new project and trigger background indexing."""
    # Check for duplicate name
    existing = await session.execute(
        select(Project).where(Project.name == body.name)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Project name already exists")

    project = Project(name=body.name, path=body.path)
    session.add(project)
    await session.flush()

    # Launch indexing in background
    project_id = str(project.id)
    asyncio.create_task(
        _index_project_background(project_id, body.path),
        name=f"index-{project_id}",
    )

    return project


@router.get("/", response_model=list[ProjectResponse])
async def list_projects(
    skip: int = 0,
    limit: int = 50,
    session: AsyncSession = Depends(get_session),
):
    """List all registered projects."""
    result = await session.execute(
        select(Project).order_by(Project.created_at.desc()).offset(skip).limit(limit)
    )
    return result.scalars().all()


@router.get("/{project_id}", response_model=ProjectDetailResponse)
async def get_project(
    project_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Get project details with task and embedding counts."""
    project = await session.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    task_count_result = await session.execute(
        select(func.count()).select_from(Task).where(Task.project_id == project_id)
    )
    task_count = task_count_result.scalar() or 0

    embedding_count_result = await session.execute(
        select(func.count()).select_from(Embedding).where(
            Embedding.project_id == project_id
        )
    )
    embedding_count = embedding_count_result.scalar() or 0

    return ProjectDetailResponse(
        id=project.id,
        name=project.name,
        path=project.path,
        created_at=project.created_at,
        last_indexed_at=project.last_indexed_at,
        task_count=task_count,
        embedding_count=embedding_count,
    )


async def _index_project_background(project_id: str, project_path: str) -> None:
    """Background wrapper for project indexing."""
    try:
        from ade.rag.indexer import index_project

        result = await index_project(project_id, project_path)
        print(
            f"Indexed project {project_id}: "
            f"{result.files_indexed} files, {result.chunks_created} chunks"
        )
    except Exception as e:
        print(f"Background indexing failed for {project_id}: {e}", file=sys.stderr)
