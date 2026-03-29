import os
import tempfile

import pytest

from ade.rag.indexer import _load_gitignore_spec, _walk_project_files


@pytest.fixture
def temp_project():
    """Create a temporary project directory with various files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a .gitignore
        with open(os.path.join(tmpdir, ".gitignore"), "w") as f:
            f.write("*.log\nbuild/\n")

        # Create Python files
        os.makedirs(os.path.join(tmpdir, "src"))
        with open(os.path.join(tmpdir, "src", "main.py"), "w") as f:
            f.write("def main():\n    print('hello')\n")
        with open(os.path.join(tmpdir, "src", "utils.py"), "w") as f:
            f.write("def helper():\n    return 42\n")

        # Create a markdown file
        with open(os.path.join(tmpdir, "README.md"), "w") as f:
            f.write("# Test Project\n\nA test project.\n")

        # Create files that should be ignored
        with open(os.path.join(tmpdir, "debug.log"), "w") as f:
            f.write("log entry")
        os.makedirs(os.path.join(tmpdir, "build"))
        with open(os.path.join(tmpdir, "build", "output.js"), "w") as f:
            f.write("compiled")

        # Create a binary-like file (no indexable extension)
        with open(os.path.join(tmpdir, "image.png"), "wb") as f:
            f.write(b"\x89PNG\r\n")

        # Create node_modules (always ignored)
        os.makedirs(os.path.join(tmpdir, "node_modules", "pkg"))
        with open(os.path.join(tmpdir, "node_modules", "pkg", "index.js"), "w") as f:
            f.write("module.exports = {}")

        # Create __pycache__ (always ignored)
        os.makedirs(os.path.join(tmpdir, "__pycache__"))
        with open(os.path.join(tmpdir, "__pycache__", "main.cpython-311.pyc"), "wb") as f:
            f.write(b"\x00")

        yield tmpdir


def test_walk_project_files_finds_code(temp_project):
    """Should find Python and Markdown files."""
    files = _walk_project_files(temp_project)
    assert "src/main.py" in files
    assert "src/utils.py" in files
    assert "README.md" in files


def test_walk_project_files_respects_gitignore(temp_project):
    """Should exclude files matching .gitignore patterns."""
    files = _walk_project_files(temp_project)
    assert "debug.log" not in files
    assert "build/output.js" not in files


def test_walk_project_files_ignores_node_modules(temp_project):
    """Should always ignore node_modules."""
    files = _walk_project_files(temp_project)
    assert not any("node_modules" in f for f in files)


def test_walk_project_files_ignores_pycache(temp_project):
    """Should always ignore __pycache__."""
    files = _walk_project_files(temp_project)
    assert not any("__pycache__" in f for f in files)


def test_walk_project_files_filters_extensions(temp_project):
    """Should skip files with non-indexable extensions."""
    files = _walk_project_files(temp_project)
    assert "image.png" not in files


def test_load_gitignore_spec_without_file():
    """Should work even if no .gitignore exists."""
    with tempfile.TemporaryDirectory() as tmpdir:
        spec = _load_gitignore_spec(tmpdir)
        # Should still have hardcoded ignores
        assert spec.match_file("node_modules/")
        assert spec.match_file("__pycache__/")


def test_walk_project_files_skips_large_files(temp_project):
    """Should skip files exceeding max file size."""
    large_path = os.path.join(temp_project, "huge.py")
    with open(large_path, "w") as f:
        f.write("x = 1\n" * 50000)  # ~300KB

    files = _walk_project_files(temp_project)
    assert "huge.py" not in files
