"""Pydantic response schemas for the ADE API."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ProjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    path: str
    created_at: datetime
    last_indexed_at: datetime | None = None


class ProjectDetailResponse(ProjectResponse):
    task_count: int = 0
    embedding_count: int = 0


class TaskResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    description: str
    status: str
    created_at: datetime
    completed_at: datetime | None = None


class CodeChangeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    file_path: str
    change_type: str
    diff: str | None = None


class ExecutionResultResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    command: str
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: int


class PlanStepResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    step_number: int
    description: str
    target_files: list | dict | None = None
    status: str
    code_changes: list[CodeChangeResponse] = []
    execution_results: list[ExecutionResultResponse] = []


class TaskDetailResponse(TaskResponse):
    plan_steps: list[PlanStepResponse] = []


class AgentLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    agent_name: str
    action: str
    input_tokens: int
    output_tokens: int
    latency_ms: float
    timestamp: datetime
    step_id: uuid.UUID | None = None


class TaskCreateRequest(BaseModel):
    description: str


class HealthResponse(BaseModel):
    status: str
    database: bool
    redis: bool
