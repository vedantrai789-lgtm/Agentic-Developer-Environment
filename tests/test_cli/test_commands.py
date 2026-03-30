"""Tests for CLI commands using click.testing.CliRunner."""

from unittest.mock import AsyncMock, patch

from click.testing import CliRunner

from ade.cli.main import cli


def test_cli_version():
    """--version should print version info."""
    runner = CliRunner()
    result = runner.invoke(cli, ["--version"])
    assert result.exit_code == 0
    assert "0.1.0" in result.output


def test_cli_help():
    """--help should print usage."""
    runner = CliRunner()
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "ADE" in result.output


def test_projects_command_server_down():
    """'projects' should show error when server is down."""
    runner = CliRunner()
    with patch("ade.cli.main._server_available", new_callable=AsyncMock, return_value=False):
        result = runner.invoke(cli, ["projects"])
    assert "not available" in result.output


def test_status_command_server_down():
    """'status' should show error when server is down."""
    runner = CliRunner()
    with patch("ade.cli.main._server_available", new_callable=AsyncMock, return_value=False):
        result = runner.invoke(cli, ["status", "some-task-id"])
    assert "not available" in result.output


def test_logs_command_server_down():
    """'logs' should show error when server is down."""
    runner = CliRunner()
    with patch("ade.cli.main._server_available", new_callable=AsyncMock, return_value=False):
        result = runner.invoke(cli, ["logs", "some-task-id"])
    assert "not available" in result.output


def test_projects_command_with_server():
    """'projects' should list projects when server is available."""
    runner = CliRunner()

    mock_client = AsyncMock()
    mock_client.health = AsyncMock(return_value={"status": "healthy"})
    mock_client.list_projects = AsyncMock(return_value=[
        {
            "id": "00000000-0000-0000-0000-000000000001",
            "name": "test-proj",
            "path": "/tmp/proj",
            "created_at": "2024-01-01T00:00:00Z",
            "last_indexed_at": None,
        }
    ])

    with (
        patch("ade.cli.main._server_available", new_callable=AsyncMock, return_value=True),
        patch("ade.cli.main.ADEClient", return_value=mock_client),
    ):
        result = runner.invoke(cli, ["projects"])

    assert result.exit_code == 0
    assert "test-proj" in result.output


def test_serve_command():
    """'serve' should call uvicorn.run."""
    runner = CliRunner()
    with patch("uvicorn.run") as mock_run:
        result = runner.invoke(cli, ["serve", "--port", "9000"])

    assert result.exit_code == 0
    mock_run.assert_called_once_with(
        "ade.api.main:app", host="0.0.0.0", port=9000, reload=False
    )
