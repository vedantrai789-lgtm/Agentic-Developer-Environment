from unittest.mock import MagicMock, patch

import pytest

from ade.sandbox.docker_manager import DockerExecutor, _truncate
from ade.sandbox.security import SandboxSecurityPolicy


@pytest.fixture
def mock_policy():
    return SandboxSecurityPolicy(
        memory_limit="256m",
        cpu_limit=0.5,
        timeout_seconds=30,
        network_disabled=True,
    )


@pytest.fixture
def mock_container():
    """A mock Docker container that returns success."""
    container = MagicMock()
    container.wait.return_value = {"StatusCode": 0}
    container.logs.side_effect = lambda stdout=False, stderr=False: (
        b"All tests passed\n" if stdout else b""
    )
    container.remove = MagicMock()
    return container


@pytest.fixture
def mock_docker_client(mock_container):
    """A mock Docker client."""
    client = MagicMock()
    client.containers.run.return_value = mock_container
    client.images.get.return_value = MagicMock()
    return client


@pytest.mark.asyncio
async def test_docker_executor_run_success(mock_docker_client, mock_policy):
    """Should run command in container and return results."""
    with patch("ade.sandbox.docker_manager.get_settings") as mock_settings:
        mock_settings.return_value = MagicMock(
            sandbox_docker_image="ade-sandbox:latest",
            sandbox_memory_limit="256m",
            sandbox_cpu_limit=0.5,
            sandbox_timeout_seconds=30,
            sandbox_network_disabled=True,
        )
        executor = DockerExecutor(policy=mock_policy)
        executor._client = mock_docker_client

        result = await executor.run("pytest -v", "/tmp/workspace")

    assert result["exit_code"] == 0
    assert result["command"] == "pytest -v"
    assert "passed" in result["stdout"].lower()
    assert result["duration_ms"] >= 0

    # Container should be cleaned up
    mock_docker_client.containers.run.assert_called_once()
    mock_docker_client.containers.run.return_value.remove.assert_called_once_with(
        force=True
    )


@pytest.mark.asyncio
async def test_docker_executor_run_failure(mock_docker_client, mock_policy):
    """Should capture non-zero exit code."""
    mock_container = MagicMock()
    mock_container.wait.return_value = {"StatusCode": 1}
    mock_container.logs.side_effect = lambda stdout=False, stderr=False: (
        b"" if stdout else b"FAILED test_foo.py::test_bar\n"
    )
    mock_container.remove = MagicMock()
    mock_docker_client.containers.run.return_value = mock_container

    with patch("ade.sandbox.docker_manager.get_settings") as mock_settings:
        mock_settings.return_value = MagicMock(
            sandbox_docker_image="ade-sandbox:latest",
            sandbox_memory_limit="256m",
            sandbox_cpu_limit=0.5,
            sandbox_timeout_seconds=30,
            sandbox_network_disabled=True,
        )
        executor = DockerExecutor(policy=mock_policy)
        executor._client = mock_docker_client

        result = await executor.run("pytest -v", "/tmp/workspace")

    assert result["exit_code"] == 1
    assert "FAILED" in result["stderr"]


@pytest.mark.asyncio
async def test_docker_executor_handles_exception(mock_docker_client, mock_policy):
    """Should return error result when container creation fails."""
    mock_docker_client.containers.run.side_effect = Exception("Image not found")

    with patch("ade.sandbox.docker_manager.get_settings") as mock_settings:
        mock_settings.return_value = MagicMock(
            sandbox_docker_image="ade-sandbox:latest",
            sandbox_memory_limit="256m",
            sandbox_cpu_limit=0.5,
            sandbox_timeout_seconds=30,
            sandbox_network_disabled=True,
        )
        executor = DockerExecutor(policy=mock_policy)
        executor._client = mock_docker_client

        result = await executor.run("pytest -v", "/tmp/workspace")

    assert result["exit_code"] == 1
    assert "Image not found" in result["stderr"]


@pytest.mark.asyncio
async def test_docker_executor_container_always_removed(
    mock_docker_client, mock_policy
):
    """Container should be force-removed even on error."""
    mock_container = MagicMock()
    mock_container.wait.side_effect = Exception("timeout")
    mock_container.remove = MagicMock()
    mock_docker_client.containers.run.return_value = mock_container

    with patch("ade.sandbox.docker_manager.get_settings") as mock_settings:
        mock_settings.return_value = MagicMock(
            sandbox_docker_image="ade-sandbox:latest",
            sandbox_memory_limit="256m",
            sandbox_cpu_limit=0.5,
            sandbox_timeout_seconds=30,
            sandbox_network_disabled=True,
        )
        executor = DockerExecutor(policy=mock_policy)
        executor._client = mock_docker_client

        await executor.run("pytest -v", "/tmp/workspace")

    mock_container.remove.assert_called_once_with(force=True)


def test_truncate_short():
    """Short text should pass through unchanged."""
    assert _truncate("hello", max_bytes=100) == "hello"


def test_truncate_long():
    """Long text should be truncated with a marker."""
    text = "x" * 100
    result = _truncate(text, max_bytes=50)
    assert len(result) < 100
    assert "truncated" in result


def test_ensure_image_exists(mock_docker_client, mock_policy):
    """Should return True if image already exists."""
    with patch("ade.sandbox.docker_manager.get_settings") as mock_settings:
        mock_settings.return_value = MagicMock(
            sandbox_docker_image="ade-sandbox:latest",
            sandbox_memory_limit="256m",
            sandbox_cpu_limit=0.5,
            sandbox_timeout_seconds=30,
            sandbox_network_disabled=True,
        )
        executor = DockerExecutor(policy=mock_policy)
        executor._client = mock_docker_client

        assert executor.ensure_image() is True
        mock_docker_client.images.get.assert_called_once()
