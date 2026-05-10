"""Ephemeral deployment workspace management."""

from __future__ import annotations

import copy
from contextlib import contextmanager
from dataclasses import dataclass, is_dataclass, replace
import logging
from pathlib import Path
import shutil
import tempfile
from typing import Iterator

import constants as CONSTANTS


logger = logging.getLogger(__name__)

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


@contextmanager
def deployment_workspace(context, workspace_root: Path | None = None) -> Iterator[tuple[object, EphemeralWorkspace]]:
    """
    Run a deployment against an isolated workspace and sync durable outputs.

    The runtime context keeps the original project metadata but points
    `project_path` at the temporary workspace. On exit, only explicitly
    allowlisted runtime outputs are copied back to the source project.
    """
    workspace = create_ephemeral_workspace(context, workspace_root=workspace_root)
    runtime_context = _clone_context_with_project_path(context, workspace.workspace_path)

    try:
        yield runtime_context, workspace
    except Exception:
        try:
            sync_runtime_outputs(workspace)
        except Exception as sync_error:
            logger.warning("Failed to sync runtime outputs after deployment error: %s", sync_error)
        raise
    else:
        sync_runtime_outputs(workspace)
    finally:
        workspace.cleanup()


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


def sync_runtime_outputs(workspace: EphemeralWorkspace) -> None:
    """
    Copy durable deployment outputs from a workspace back to the source project.

    Build products, generated tfvars and provider caches stay ephemeral. Terraform
    state and simulator runtime assets are durable because subsequent destroy and
    simulator/download flows depend on them.
    """
    _copy_file_if_exists(
        workspace.state_path,
        workspace.source_path / "terraform" / "terraform.tfstate",
        workspace.source_path,
    )
    _copy_file_if_exists(
        workspace.terraform_dir / "terraform.tfstate.backup",
        workspace.source_path / "terraform" / "terraform.tfstate.backup",
        workspace.source_path,
    )
    _copy_directory_if_exists(
        workspace.workspace_path / "iot_devices_auth",
        workspace.source_path / "iot_devices_auth",
        workspace.source_path,
    )
    _sync_generated_simulator_configs(workspace)
    _sync_build_metadata(workspace)


def _clone_context_with_project_path(context, project_path: Path):
    if is_dataclass(context):
        return replace(context, project_path=project_path)

    runtime_context = copy.copy(context)
    runtime_context.project_path = project_path
    return runtime_context


def _copy_file_if_exists(source: Path, destination: Path, destination_root: Path) -> None:
    if not source.exists():
        return
    if source.is_symlink():
        raise ValueError("Refusing to sync symlinked runtime output.")
    _ensure_safe_destination(destination, destination_root)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def _copy_directory_if_exists(source: Path, destination: Path, destination_root: Path) -> None:
    if not source.exists():
        return
    if source.is_symlink():
        raise ValueError("Refusing to sync symlinked runtime output directory.")
    _assert_tree_has_no_symlinks(source)
    _ensure_safe_destination(destination, destination_root)
    if destination.exists():
        _assert_tree_has_no_symlinks(destination)
    destination.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, destination, dirs_exist_ok=True)


def _sync_generated_simulator_configs(workspace: EphemeralWorkspace) -> None:
    simulator_root = workspace.workspace_path / "iot_device_simulator"
    if not simulator_root.exists():
        return
    if simulator_root.is_symlink():
        raise ValueError("Refusing to sync symlinked simulator output directory.")

    for source in simulator_root.rglob("config_generated*.json"):
        if source.is_symlink():
            raise ValueError("Refusing to sync symlinked simulator output.")
        relative_path = source.relative_to(workspace.workspace_path)
        _copy_file_if_exists(source, workspace.source_path / relative_path, workspace.source_path)


def _sync_build_metadata(workspace: EphemeralWorkspace) -> None:
    metadata_root = workspace.workspace_path / ".build" / "metadata"
    if not metadata_root.exists():
        return
    if metadata_root.is_symlink():
        raise ValueError("Refusing to sync symlinked build metadata directory.")

    for source in metadata_root.rglob("*.json"):
        if source.is_symlink():
            raise ValueError("Refusing to sync symlinked build metadata.")
        relative_path = source.relative_to(workspace.workspace_path)
        _copy_file_if_exists(source, workspace.source_path / relative_path, workspace.source_path)


def _ensure_safe_destination(destination: Path, destination_root: Path) -> None:
    root = destination_root.resolve()
    parent = destination.parent.resolve()
    if not _is_relative_to(parent, root):
        raise ValueError("Refusing to sync runtime output outside the source project.")
    if destination.exists() and destination.is_symlink():
        raise ValueError("Refusing to overwrite symlinked runtime output destination.")


def _assert_tree_has_no_symlinks(root: Path) -> None:
    for path in root.rglob("*"):
        if path.is_symlink():
            raise ValueError("Refusing to sync runtime output containing symlinks.")


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
