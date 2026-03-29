from __future__ import annotations

from typing import TypedDict


class PlanStepDict(TypedDict):
    step_number: int
    description: str
    target_files: list[str]
    dependencies: list[int]


class CodeChangeDict(TypedDict):
    file_path: str
    change_type: str  # "create" | "modify" | "delete"
    diff: str | None
    full_content: str | None


class ExecutionResultDict(TypedDict):
    command: str
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: int


class AgentState(TypedDict, total=False):
    # Inputs (set once at start)
    task_id: str
    task: str
    project_id: str
    project_path: str

    # Planner outputs
    plan: list[PlanStepDict]

    # Iteration tracking
    current_step_index: int
    iteration_count: int

    # Codegen outputs (for current step)
    code_changes: list[CodeChangeDict]

    # Executor outputs (for current step)
    execution_results: list[ExecutionResultDict]

    # RAG context
    context_chunks: list[str]

    # Graph control
    status: str
    error: str
