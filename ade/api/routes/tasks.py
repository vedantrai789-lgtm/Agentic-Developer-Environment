"""Task management endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ade.api.dependencies import get_session
from ade.api.schemas import (
    AgentLogResponse,
    TaskCreateRequest,
    TaskDetailResponse,
    TaskResponse,
)
from ade.api.task_runner import launch_task
from ade.core.models import AgentLog, PlanStep, Project, Task, TaskStatus

router = APIRouter(tags=["tasks"])


@router.post(
    "/projects/{project_id}/tasks",
    response_model=TaskResponse,
    status_code=201,
)
async def create_task(
    project_id: uuid.UUID,
    body: TaskCreateRequest,
    session: AsyncSession = Depends(get_session),
):
    """Create a new task and launch the agent orchestrator."""
    project = await session.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    task = Task(
        project_id=project_id,
        description=body.description,
        status=TaskStatus.PENDING,
    )
    session.add(task)
    await session.flush()
    # Commit now so the background task can see the row
    await session.commit()

    # Launch orchestrator in background
    launch_task(
        task_id=str(task.id),
        description=body.description,
        project_id=str(project_id),
        project_path=project.path,
    )

    # Refresh to get the committed state for the response
    await session.refresh(task)
    return task


@router.get(
    "/projects/{project_id}/tasks",
    response_model=list[TaskResponse],
)
async def list_tasks(
    project_id: uuid.UUID,
    status: str | None = None,
    skip: int = 0,
    limit: int = 50,
    session: AsyncSession = Depends(get_session),
):
    """List tasks for a project, optionally filtered by status."""
    query = select(Task).where(Task.project_id == project_id)
    if status:
        query = query.where(Task.status == status)
    query = query.order_by(Task.created_at.desc()).offset(skip).limit(limit)

    result = await session.execute(query)
    return result.scalars().all()


@router.get("/tasks/{task_id}", response_model=TaskDetailResponse)
async def get_task(
    task_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Get task details with plan steps, code changes, and execution results."""
    result = await session.execute(
        select(Task)
        .where(Task.id == task_id)
        .options(
            selectinload(Task.plan_steps)
            .selectinload(PlanStep.code_changes),
            selectinload(Task.plan_steps)
            .selectinload(PlanStep.execution_results),
        )
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.get("/tasks/{task_id}/logs", response_model=list[AgentLogResponse])
async def get_task_logs(
    task_id: uuid.UUID,
    agent_name: str | None = None,
    skip: int = 0,
    limit: int = 100,
    session: AsyncSession = Depends(get_session),
):
    """Get agent logs for a task."""
    # Verify task exists
    task = await session.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    query = select(AgentLog).where(AgentLog.task_id == task_id)
    if agent_name:
        query = query.where(AgentLog.agent_name == agent_name)
    query = query.order_by(AgentLog.timestamp).offset(skip).limit(limit)

    result = await session.execute(query)
    return result.scalars().all()
