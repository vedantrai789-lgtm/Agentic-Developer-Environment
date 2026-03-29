import pytest

from ade.agents.state import CodeChangeDict
from ade.sandbox.workspace import (
    SandboxWorkspace,
    _apply_changes,
    _copy_project,
    _patch_lines,
)


@pytest.fixture
def sample_project(tmp_path):
    """Create a minimal project directory."""
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("def hello():\n    return 'hello'\n")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_main.py").write_text("def test_hello(): pass\n")
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "HEAD").write_text("ref: refs/heads/main\n")
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "pkg").mkdir()
    (tmp_path / "node_modules" / "pkg" / "index.js").write_text("module.exports = {}")
    return tmp_path


def test_copy_project_skips_heavy_dirs(sample_project, tmp_path):
    """Should copy project but skip .git, node_modules, etc."""
    dest = tmp_path / "copy"
    _copy_project(sample_project, dest)

    assert (dest / "src" / "main.py").exists()
    assert (dest / "tests" / "test_main.py").exists()
    assert not (dest / ".git").exists()
    assert not (dest / "node_modules").exists()


def test_apply_changes_create_file(tmp_path):
    """Should create a new file."""
    changes = [CodeChangeDict(
        file_path="new_module.py",
        change_type="create",
        diff=None,
        full_content="print('new')\n",
    )]
    _apply_changes(tmp_path, changes)

    assert (tmp_path / "new_module.py").read_text() == "print('new')\n"


def test_apply_changes_create_nested(tmp_path):
    """Should create parent directories as needed."""
    changes = [CodeChangeDict(
        file_path="pkg/sub/mod.py",
        change_type="create",
        diff=None,
        full_content="x = 1\n",
    )]
    _apply_changes(tmp_path, changes)

    assert (tmp_path / "pkg" / "sub" / "mod.py").read_text() == "x = 1\n"


def test_apply_changes_modify_file(tmp_path):
    """Should overwrite existing file with full_content."""
    (tmp_path / "existing.py").write_text("old content")
    changes = [CodeChangeDict(
        file_path="existing.py",
        change_type="modify",
        diff=None,
        full_content="new content",
    )]
    _apply_changes(tmp_path, changes)

    assert (tmp_path / "existing.py").read_text() == "new content"


def test_apply_changes_delete_file(tmp_path):
    """Should delete the specified file."""
    (tmp_path / "to_delete.py").write_text("bye")
    changes = [CodeChangeDict(
        file_path="to_delete.py",
        change_type="delete",
        diff=None,
        full_content=None,
    )]
    _apply_changes(tmp_path, changes)

    assert not (tmp_path / "to_delete.py").exists()


def test_apply_changes_delete_nonexistent(tmp_path):
    """Deleting a non-existent file should not raise."""
    changes = [CodeChangeDict(
        file_path="ghost.py",
        change_type="delete",
        diff=None,
        full_content=None,
    )]
    _apply_changes(tmp_path, changes)  # no error


def test_patch_lines_add():
    """Should add lines from a unified diff."""
    original = ["line1\n", "line2\n", "line3\n"]
    diff = "@@ -2,1 +2,2 @@\n line2\n+inserted\n"
    result = _patch_lines(original, diff)
    assert "inserted\n" in "".join(result)


def test_patch_lines_remove():
    """Should remove lines from a unified diff."""
    original = ["line1\n", "line2\n", "line3\n"]
    diff = "@@ -1,3 +1,2 @@\n line1\n-line2\n line3\n"
    result = _patch_lines(original, diff)
    assert "line2" not in "".join(result)


@pytest.mark.asyncio
async def test_sandbox_workspace_lifecycle(sample_project):
    """Full prepare + cleanup lifecycle."""
    changes = [CodeChangeDict(
        file_path="new_file.py",
        change_type="create",
        diff=None,
        full_content="print('sandbox')\n",
    )]

    async with SandboxWorkspace(str(sample_project)) as ws:
        workspace = await ws.prepare(changes)
        assert workspace.exists()
        assert (workspace / "src" / "main.py").exists()
        assert (workspace / "new_file.py").exists()
        assert not (workspace / ".git").exists()
        ws_path = workspace

    # After cleanup the temp dir should be gone
    assert not ws_path.exists()
