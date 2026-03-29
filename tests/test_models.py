import uuid

from ade.core.models import (
    ChangeType,
    CodeChange,
    LLMResponse,
    PlanStep,
    Project,
    ProjectCreate,
    Task,
    TaskCreate,
    TaskStatus,
)


def test_project_model_instantiation():
    """Project ORM model should instantiate with required fields."""
    p = Project(name="test-project", path="/tmp/test")
    assert p.name == "test-project"
    assert p.path == "/tmp/test"
    # id and created_at are populated at insert time, not at __init__


def test_task_model_instantiation():
    """Task ORM model should instantiate with basic fields."""
    project_id = uuid.uuid4()
    t = Task(project_id=project_id, description="Add auth")
    assert t.description == "Add auth"
    assert t.project_id == project_id
    assert t.completed_at is None


def test_plan_step_model():
    """PlanStep should accept JSON target_files."""
    step = PlanStep(
        task_id=uuid.uuid4(),
        step_number=1,
        description="Create user model",
        target_files=["models/user.py", "tests/test_user.py"],
    )
    assert step.step_number == 1
    assert step.description == "Create user model"
    assert len(step.target_files) == 2


def test_code_change_model():
    """CodeChange should accept change_type enum."""
    cc = CodeChange(
        step_id=uuid.uuid4(),
        file_path="models/user.py",
        change_type=ChangeType.CREATE,
        full_content="class User:\n    pass",
    )
    assert cc.change_type == ChangeType.CREATE
    assert cc.diff is None


def test_task_status_enum():
    """TaskStatus enum values should match expected strings."""
    assert TaskStatus.PENDING.value == "pending"
    assert TaskStatus.COMPLETED.value == "completed"
    assert TaskStatus.FAILED.value == "failed"


# --- Pydantic schema tests ---


def test_project_create_schema():
    """ProjectCreate Pydantic model should validate correctly."""
    pc = ProjectCreate(name="my-project", path="/home/user/project")
    assert pc.name == "my-project"
    assert pc.path == "/home/user/project"


def test_task_create_schema():
    """TaskCreate Pydantic model should validate UUID and description."""
    pid = uuid.uuid4()
    tc = TaskCreate(project_id=pid, description="Build the feature")
    assert tc.project_id == pid
    assert tc.description == "Build the feature"


def test_llm_response_schema():
    """LLMResponse Pydantic model should accept all fields."""
    resp = LLMResponse(
        content="Hello!",
        model="claude-sonnet-4-20250514",
        input_tokens=10,
        output_tokens=5,
        cached=False,
        latency_ms=150.5,
    )
    assert resp.content == "Hello!"
    assert resp.cached is False
    assert resp.latency_ms == 150.5
