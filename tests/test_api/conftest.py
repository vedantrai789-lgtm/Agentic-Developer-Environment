"""Fixtures for API tests using httpx ASGI transport."""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.fixture
def mock_session():
    """A mock async DB session."""
    session = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.flush = AsyncMock()
    session.add = lambda x: None
    return session


@pytest.fixture
def app(mock_session):
    """Create a FastAPI app with mocked dependencies."""
    from ade.api.main import create_app

    test_app = create_app()

    # Override DB session dependency
    from ade.api.dependencies import get_session

    async def override_session():
        yield mock_session

    test_app.dependency_overrides[get_session] = override_session
    return test_app


@pytest.fixture
async def client(app):
    """Async test client for the API."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def sample_project_id():
    return uuid.UUID("00000000-0000-0000-0000-000000000001")


@pytest.fixture
def sample_task_id():
    return uuid.UUID("00000000-0000-0000-0000-000000000010")


@pytest.fixture
def mock_project(sample_project_id):
    """A mock Project ORM object."""
    from unittest.mock import MagicMock

    project = MagicMock()
    project.id = sample_project_id
    project.name = "test-project"
    project.path = "/tmp/test-project"
    project.created_at = datetime(2024, 1, 1, tzinfo=timezone.utc)
    project.last_indexed_at = None
    return project


@pytest.fixture
def mock_task(sample_task_id, sample_project_id):
    """A mock Task ORM object."""
    from unittest.mock import MagicMock

    task = MagicMock()
    task.id = sample_task_id
    task.project_id = sample_project_id
    task.description = "Test task"
    task.status = "pending"
    task.created_at = datetime(2024, 1, 1, tzinfo=timezone.utc)
    task.completed_at = None
    task.plan_steps = []
    return task
