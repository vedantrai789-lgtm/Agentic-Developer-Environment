"""Tests for task endpoints."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.asyncio
async def test_create_task(client, mock_session, mock_project, mock_task, sample_project_id):
    """POST /projects/{id}/tasks should create a task and return 201."""
    mock_session.get = AsyncMock(return_value=mock_project)
    mock_session.flush = AsyncMock()

    with (
        patch("ade.api.routes.tasks.Task") as mock_task_cls,
        patch("ade.api.routes.tasks.launch_task") as mock_launch,
    ):
        mock_task_cls.return_value = mock_task
        mock_launch.return_value = MagicMock()

        resp = await client.post(
            f"/projects/{sample_project_id}/tasks",
            json={"description": "Test task"},
        )

    assert resp.status_code == 201
    data = resp.json()
    assert data["description"] == "Test task"
    mock_launch.assert_called_once()


@pytest.mark.asyncio
async def test_create_task_project_not_found(client, mock_session, sample_project_id):
    """POST /projects/{id}/tasks should 404 when project doesn't exist."""
    mock_session.get = AsyncMock(return_value=None)

    resp = await client.post(
        f"/projects/{sample_project_id}/tasks",
        json={"description": "Test task"},
    )

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_list_tasks(client, mock_session, mock_task, sample_project_id):
    """GET /projects/{id}/tasks should return tasks."""
    mock_result = MagicMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = [mock_task]
    mock_result.scalars.return_value = mock_scalars
    mock_session.execute = AsyncMock(return_value=mock_result)

    resp = await client.get(f"/projects/{sample_project_id}/tasks")

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1


@pytest.mark.asyncio
async def test_get_task_not_found(client, mock_session, sample_task_id):
    """GET /tasks/{id} should return 404 for unknown task."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute = AsyncMock(return_value=mock_result)

    resp = await client.get(f"/tasks/{sample_task_id}")

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_task_logs_not_found(client, mock_session, sample_task_id):
    """GET /tasks/{id}/logs should 404 when task doesn't exist."""
    mock_session.get = AsyncMock(return_value=None)

    resp = await client.get(f"/tasks/{sample_task_id}/logs")

    assert resp.status_code == 404
