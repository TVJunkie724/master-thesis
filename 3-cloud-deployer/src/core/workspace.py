"""Ephemeral deployment workspace management."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
import shutil
import tempfile
from typing import Iterator

import constants as CONSTANTS


EXCLUDED_DIR_NAMES = {
    CONSTANTS.PROJECT_VERSIONS_DIR_NAME,
    ".build",
    ".terraform",
    ".mypy_cache",
    ".pytest_cache",
    "__pycache__",
}
EXCLUDED_FILE_NAMES = {
    ".DS_Store",
}


@dataclass(frozen=True)
class EphemeralWorkspace:
    """A temporary, isolated copy of a deployment project."""

    project_name: str
    source_path: Path
    workspace_path: Path

    @property
    def terraform_dir(self) -> Path:
        """Return the workspace-local Terraform directory."""
        return self.workspace_path / "terraform"

    @property
    def state_path(self) -> Path:
        """Return the workspace-local Terraform state path."""
        return self.terraform_dir / "terraform.tfstate"

    def cleanup(self) -> None:
        """Remove the workspace directory if it still exists."""
        shutil.rmtree(self.workspace_path, ignore_errors=True)


def create_ephemeral_workspace(context, workspace_root: Path | None = None) -> EphemeralWorkspace:
    """
    Copy a validated project context into a temporary workspace.

    The copy intentionally excludes deployer-internal caches and archived ZIP
    versions. Symlinks are rejected to prevent copying files outside the project
    boundary into the temporary workspace.
    """
    source_path = Path(context.project_path).resolve()
    if not source_path.exists():
        raise ValueError("Cannot create ephemeral workspace: project path does not exist.")
    if not source_path.is_dir():
        raise ValueError("Cannot create ephemeral workspace: project path is not a directory.")

    root = _workspace_root_path(workspace_root)
    if _is_relative_to(root, source_path):
        raise ValueError("Ephemeral workspace root must not be inside the source project.")
    _ensure_workspace_root(root)

    _assert_no_symlinks(source_path)

    workspace_path = Path(tempfile.mkdtemp(
        prefix=f"{_safe_prefix(context.project_name)}-",
        dir=root,
    )).resolve()

    try:
        shutil.copytree(
            source_path,
            workspace_path,
            dirs_exist_ok=True,
            ignore=_ignore_internal_artifacts,
        )
    except Exception:
        shutil.rmtree(workspace_path, ignore_errors=True)
        raise

    return EphemeralWorkspace(
        project_name=context.project_name,
        source_path=source_path,
        workspace_path=workspace_path,
    )


@contextmanager
def ephemeral_workspace(context, workspace_root: Path | None = None) -> Iterator[EphemeralWorkspace]:
    """Create and clean up an ephemeral workspace around a deployment operation."""
    workspace = create_ephemeral_workspace(context, workspace_root=workspace_root)
    try:
        yield workspace
    finally:
        workspace.cleanup()


def _workspace_root_path(workspace_root: Path | None) -> Path:
    root = (
        Path(workspace_root)
        if workspace_root is not None
        else Path(tempfile.gettempdir()) / "twin2multicloud-deployer-workspaces"
    )
    if root.is_symlink():
        raise ValueError("Ephemeral workspace root must not be a symlink.")
    return root.resolve()


def _ensure_workspace_root(root: Path) -> None:
    if root.is_symlink():
        raise ValueError("Ephemeral workspace root must not be a symlink.")
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    root.chmod(0o700)


def _ignore_internal_artifacts(_directory: str, names: list[str]) -> set[str]:
    ignored = set()
    for name in names:
        if name in EXCLUDED_DIR_NAMES or name in EXCLUDED_FILE_NAMES:
            ignored.add(name)
        elif name.endswith(".pyc"):
            ignored.add(name)
    return ignored


def _assert_no_symlinks(source_path: Path) -> None:
    for path in source_path.rglob("*"):
        if _is_ignored_path(path, source_path):
            continue
        if path.is_symlink():
            raise ValueError("Cannot create ephemeral workspace: project contains symlinks.")


def _is_ignored_path(path: Path, source_path: Path) -> bool:
    try:
        relative_parts = path.relative_to(source_path).parts
    except ValueError:
        return False
    return any(part in EXCLUDED_DIR_NAMES for part in relative_parts)


def _safe_prefix(project_name: str) -> str:
    safe = "".join(
        character if character.isalnum() or character in {"-", "_"} else "-"
        for character in project_name
    ).strip("-_")
    return safe or "project"


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False
