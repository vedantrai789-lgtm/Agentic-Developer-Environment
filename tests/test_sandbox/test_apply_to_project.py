"""Tests for apply_changes_to_project."""


import pytest

from ade.sandbox.workspace import apply_changes_to_project


@pytest.fixture
def project_dir(tmp_path):
    """Create a minimal project directory with existing files."""
    (tmp_path / "main.py").write_text("print('hello')\n")
    (tmp_path / "utils.py").write_text("def helper(): pass\n")
    return tmp_path


def test_apply_create_new_file(project_dir):
    changes = [
        {
            "file_path": "new_module.py",
            "change_type": "create",
            "full_content": "# new module\n",
            "diff": None,
        }
    ]
    modified = apply_changes_to_project(str(project_dir), changes)
    assert modified == ["new_module.py"]
    assert (project_dir / "new_module.py").read_text() == "# new module\n"


def test_apply_create_nested_file(project_dir):
    changes = [
        {
            "file_path": "pkg/sub/deep.py",
            "change_type": "create",
            "full_content": "x = 1\n",
            "diff": None,
        }
    ]
    modified = apply_changes_to_project(str(project_dir), changes)
    assert "pkg/sub/deep.py" in modified
    assert (project_dir / "pkg" / "sub" / "deep.py").read_text() == "x = 1\n"


def test_apply_modify_creates_backup(project_dir):
    original = (project_dir / "main.py").read_text()
    changes = [
        {
            "file_path": "main.py",
            "change_type": "modify",
            "full_content": "print('updated')\n",
            "diff": None,
        }
    ]
    modified = apply_changes_to_project(str(project_dir), changes)
    assert "main.py" in modified

    # File should be updated
    assert (project_dir / "main.py").read_text() == "print('updated')\n"

    # Backup should exist with original content
    backup = project_dir / ".ade-backup" / "main.py"
    assert backup.exists()
    assert backup.read_text() == original


def test_apply_delete_creates_backup(project_dir):
    original = (project_dir / "utils.py").read_text()
    changes = [
        {
            "file_path": "utils.py",
            "change_type": "delete",
            "full_content": None,
            "diff": None,
        }
    ]
    modified = apply_changes_to_project(str(project_dir), changes)
    assert "utils.py" in modified

    # File should be deleted
    assert not (project_dir / "utils.py").exists()

    # Backup should exist
    backup = project_dir / ".ade-backup" / "utils.py"
    assert backup.exists()
    assert backup.read_text() == original


def test_apply_multiple_changes(project_dir):
    changes = [
        {
            "file_path": "main.py",
            "change_type": "modify",
            "full_content": "print('v2')\n",
            "diff": None,
        },
        {
            "file_path": "new.py",
            "change_type": "create",
            "full_content": "# new\n",
            "diff": None,
        },
    ]
    modified = apply_changes_to_project(str(project_dir), changes)
    assert len(modified) == 2
    assert (project_dir / "main.py").read_text() == "print('v2')\n"
    assert (project_dir / "new.py").read_text() == "# new\n"


def test_apply_no_backup_dir_when_only_creates(tmp_path):
    """No .ade-backup directory should be created for create-only changes."""
    changes = [
        {
            "file_path": "brand_new.py",
            "change_type": "create",
            "full_content": "x = 1\n",
            "diff": None,
        }
    ]
    apply_changes_to_project(str(tmp_path), changes)
    assert not (tmp_path / ".ade-backup").exists()
