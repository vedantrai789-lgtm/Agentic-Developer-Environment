"""Workspace preparation: copy project files and apply code changes."""

from __future__ import annotations

import logging
import shutil
import tempfile
from pathlib import Path

from ade.agents.state import CodeChangeDict

logger = logging.getLogger(__name__)


class SandboxWorkspace:
    """Manages a temporary workspace directory for sandbox execution.

    Copies the project into a temp dir, applies pending code changes,
    and cleans up afterward.
    """

    def __init__(self, project_path: str) -> None:
        self.project_path = Path(project_path)
        self._tmpdir: tempfile.TemporaryDirectory | None = None
        self.workspace_path: Path | None = None

    async def prepare(self, code_changes: list[CodeChangeDict]) -> Path:
        """Copy project to temp dir and apply code changes."""
        self._tmpdir = tempfile.TemporaryDirectory(prefix="ade-sandbox-")
        workspace = Path(self._tmpdir.name) / "workspace"

        # Copy project, skipping heavy dirs
        _copy_project(self.project_path, workspace)

        # Apply code changes on top
        _apply_changes(workspace, code_changes)

        self.workspace_path = workspace
        return workspace

    def cleanup(self) -> None:
        """Remove the temporary workspace."""
        if self._tmpdir is not None:
            self._tmpdir.cleanup()
            self._tmpdir = None
            self.workspace_path = None

    async def __aenter__(self) -> SandboxWorkspace:
        return self

    async def __aexit__(self, *exc: object) -> None:
        self.cleanup()


# Directories to skip when copying the project into the sandbox
SKIP_DIRS = {
    ".git", ".venv", "venv", "node_modules", "__pycache__",
    ".mypy_cache", ".pytest_cache", ".ruff_cache", "dist", "build",
}


def _copy_project(src: Path, dst: Path) -> None:
    """Copy project tree, skipping heavy/irrelevant directories."""

    def _ignore(directory: str, contents: list[str]) -> set[str]:
        return {c for c in contents if c in SKIP_DIRS}

    shutil.copytree(src, dst, ignore=_ignore, dirs_exist_ok=True)


def _apply_changes(workspace: Path, changes: list[CodeChangeDict]) -> None:
    """Apply a list of code changes to the workspace directory."""
    for change in changes:
        file_path = workspace / change["file_path"]

        if change["change_type"] == "delete":
            if file_path.exists():
                file_path.unlink()
            continue

        # create or modify
        file_path.parent.mkdir(parents=True, exist_ok=True)

        if change.get("full_content") is not None:
            file_path.write_text(change["full_content"])
        elif change.get("diff") is not None:
            # For diffs, write the diff content; in a real system
            # we'd apply a unified diff patch here
            _apply_diff(file_path, change["diff"])


def _apply_diff(file_path: Path, diff: str) -> None:
    """Best-effort diff application. Falls back to overwrite if file is new."""
    if not file_path.exists():
        # New file with only a diff — write raw content
        file_path.write_text(diff)
        return

    # Simple line-level patch: process unified diff hunks
    original = file_path.read_text().splitlines(keepends=True)
    patched = _patch_lines(original, diff)
    file_path.write_text("".join(patched))


def _patch_lines(original: list[str], diff: str) -> list[str]:
    """Apply a unified diff to a list of lines.

    This is a simplified patcher that handles the most common case.
    Falls back to returning original lines on parse failure.
    """
    import re

    result = list(original)
    hunk_re = re.compile(r"^@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@")
    lines = diff.splitlines(keepends=True)

    offset = 0
    i = 0
    while i < len(lines):
        m = hunk_re.match(lines[i])
        if not m:
            i += 1
            continue

        orig_start = int(m.group(1)) - 1  # 0-indexed
        i += 1
        pos = orig_start + offset

        while i < len(lines) and not lines[i].startswith("@@"):
            line = lines[i]
            if line.startswith("-"):
                if pos < len(result):
                    result.pop(pos)
                    offset -= 1
            elif line.startswith("+"):
                content = line[1:]
                result.insert(pos, content)
                pos += 1
                offset += 1
            else:
                # context line
                pos += 1
            i += 1

    return result


def apply_changes_to_project(
    project_path: str, code_changes: list[CodeChangeDict]
) -> list[str]:
    """Apply code changes to the real project directory.

    Creates backups of modified files in .ade-backup/ before overwriting.
    Returns the list of file paths that were modified.
    """
    root = Path(project_path)
    backup_dir = root / ".ade-backup"
    modified: list[str] = []

    for change in code_changes:
        file_path = root / change["file_path"]

        # Back up existing files before modifying
        if file_path.exists() and change["change_type"] != "create":
            backup_dir.mkdir(parents=True, exist_ok=True)
            backup_dest = backup_dir / change["file_path"]
            backup_dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(file_path, backup_dest)
            logger.info("Backed up %s -> %s", file_path, backup_dest)

        modified.append(change["file_path"])

    # Reuse the existing apply logic
    _apply_changes(root, code_changes)

    logger.info(
        "Applied %d changes to project at %s", len(code_changes), project_path
    )
    return modified
