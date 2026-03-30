"""Tests for project endpoints."""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.asyncio
async def test_create_project(client, mock_session):
    """POST /projects/ should create a project and return 201."""
    # Mock: no existing project with same name
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute = AsyncMock(return_value=mock_result)

    # Capture the Project object when add() is called and set its id
    added_objects = []

    def capture_add(obj):
        obj.id = uuid.UUID("00000000-0000-0000-0000-000000000099")
        obj.created_at = datetime(2024, 1, 1, tzinfo=timezone.utc)
        obj.last_indexed_at = None
        added_objects.append(obj)

    mock_session.add = capture_add
    mock_session.flush = AsyncMock()

    with patch("ade.api.routes.projects.asyncio") as mock_asyncio:
        mock_asyncio.create_task = MagicMock()

        resp = await client.post(
            "/projects/", json={"name": "test-project", "path": "/tmp/test-project"}
        )

    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "test-project"
    assert data["path"] == "/tmp/test-project"


@pytest.mark.asyncio
async def test_create_project_duplicate(client, mock_session, mock_project):
    """POST /projects/ should return 409 for duplicate name."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_project
    mock_session.execute = AsyncMock(return_value=mock_result)

    resp = await client.post(
        "/projects/", json={"name": "test-project", "path": "/tmp/test-project"}
    )

    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_list_projects(client, mock_session, mock_project):
    """GET /projects/ should return a list of projects."""
    mock_result = MagicMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = [mock_project]
    mock_result.scalars.return_value = mock_scalars
    mock_session.execute = AsyncMock(return_value=mock_result)

    resp = await client.get("/projects/")

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["name"] == "test-project"


@pytest.mark.asyncio
async def test_get_project_not_found(client, mock_session, sample_project_id):
    """GET /projects/{id} should return 404 for unknown project."""
    mock_session.get = AsyncMock(return_value=None)

    resp = await client.get(f"/projects/{sample_project_id}")

    assert resp.status_code == 404
