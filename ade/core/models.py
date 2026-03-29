import enum
import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from pydantic import BaseModel
from sqlalchemy import (
    JSON,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

# --- SQLAlchemy ORM Models ---


class Base(DeclarativeBase):
    type_annotation_map = {
        datetime: DateTime(timezone=True),
    }


class TaskStatus(str, enum.Enum):
    PENDING = "pending"
    PLANNING = "planning"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"


class StepStatus(str, enum.Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class ChangeType(str, enum.Enum):
    CREATE = "create"
    MODIFY = "modify"
    DELETE = "delete"


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    path: Mapped[str] = mapped_column(String(1024), nullable=False)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    last_indexed_at: Mapped[datetime | None] = mapped_column(nullable=True)

    tasks: Mapped[list["Task"]] = relationship(back_populates="project", cascade="all, delete")
    embeddings: Mapped[list["Embedding"]] = relationship(
        back_populates="project", cascade="all, delete"
    )


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False
    )
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[TaskStatus] = mapped_column(
        Enum(TaskStatus, native_enum=False), default=TaskStatus.PENDING
    )
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(nullable=True)

    project: Mapped["Project"] = relationship(back_populates="tasks")
    plan_steps: Mapped[list["PlanStep"]] = relationship(
        back_populates="task", cascade="all, delete"
    )
    agent_logs: Mapped[list["AgentLog"]] = relationship(
        back_populates="task", cascade="all, delete"
    )


class PlanStep(Base):
    __tablename__ = "plan_steps"
    __table_args__ = (UniqueConstraint("task_id", "step_number", name="uq_task_step"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    task_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tasks.id"), nullable=False
    )
    step_number: Mapped[int] = mapped_column(Integer, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    target_files: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    status: Mapped[StepStatus] = mapped_column(
        Enum(StepStatus, native_enum=False), default=StepStatus.PENDING
    )
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    task: Mapped["Task"] = relationship(back_populates="plan_steps")
    code_changes: Mapped[list["CodeChange"]] = relationship(
        back_populates="step", cascade="all, delete"
    )
    execution_results: Mapped[list["ExecutionResult"]] = relationship(
        back_populates="step", cascade="all, delete"
    )
    agent_logs: Mapped[list["AgentLog"]] = relationship(
        back_populates="step", cascade="all, delete"
    )


class CodeChange(Base):
    __tablename__ = "code_changes"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    step_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("plan_steps.id"), nullable=False
    )
    file_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    change_type: Mapped[ChangeType] = mapped_column(
        Enum(ChangeType, native_enum=False), nullable=False
    )
    diff: Mapped[str | None] = mapped_column(Text, nullable=True)
    full_content: Mapped[str | None] = mapped_column(Text, nullable=True)

    step: Mapped["PlanStep"] = relationship(back_populates="code_changes")


class ExecutionResult(Base):
    __tablename__ = "execution_results"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    step_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("plan_steps.id"), nullable=False
    )
    command: Mapped[str] = mapped_column(Text, nullable=False)
    exit_code: Mapped[int] = mapped_column(Integer, nullable=False)
    stdout: Mapped[str] = mapped_column(Text, default="")
    stderr: Mapped[str] = mapped_column(Text, default="")
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    step: Mapped["PlanStep"] = relationship(back_populates="execution_results")


class AgentLog(Base):
    __tablename__ = "agent_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    task_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tasks.id"), nullable=True
    )
    step_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("plan_steps.id"), nullable=True
    )
    agent_name: Mapped[str] = mapped_column(String(100), nullable=False)
    action: Mapped[str] = mapped_column(String(255), nullable=False)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    latency_ms: Mapped[float] = mapped_column(Float, default=0.0)
    timestamp: Mapped[datetime] = mapped_column(server_default=func.now())

    task: Mapped["Task | None"] = relationship(back_populates="agent_logs")
    step: Mapped["PlanStep | None"] = relationship(back_populates="agent_logs")


class Embedding(Base):
    __tablename__ = "embeddings"

    chunk_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False
    )
    file_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    chunk_text: Mapped[str] = mapped_column(Text, nullable=False)
    chunk_type: Mapped[str] = mapped_column(String(50), nullable=False)
    start_line: Mapped[int] = mapped_column(Integer, nullable=False)
    end_line: Mapped[int] = mapped_column(Integer, nullable=False)
    embedding = mapped_column(Vector(1536), nullable=False)
    last_modified: Mapped[datetime] = mapped_column(nullable=False)

    project: Mapped["Project"] = relationship(back_populates="embeddings")


# --- Pydantic Schemas ---


class ProjectCreate(BaseModel):
    name: str
    path: str


class TaskCreate(BaseModel):
    project_id: uuid.UUID
    description: str


class LLMResponse(BaseModel):
    content: str
    model: str
    input_tokens: int
    output_tokens: int
    cached: bool
    latency_ms: float
