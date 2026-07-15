"""Private durable runtime state outside user-visible Deployer projects."""

from __future__ import annotations

import os
from pathlib import Path
import shutil

import file_manager
from src.core.project_storage import ProjectStorage


DEFAULT_RUNTIME_STATE_ROOT = Path("/var/lib/twin2multicloud-deployer/runtime-state")


class RuntimeStateStore:
    """Own Terraform state and generated device credentials by project."""

    def __init__(
        self,
        *,
        root: Path | None = None,
        project_storage: ProjectStorage | None = None,
    ) -> None:
        configured_root = os.environ.get("DEPLOYER_RUNTIME_STATE_ROOT")
        self.root = (
            Path(root)
            if root is not None
            else Path(configured_root)
            if configured_root
            else DEFAULT_RUNTIME_STATE_ROOT
        ).resolve()
        self.project_storage = project_storage or ProjectStorage()

    def project_path(self, project_name: str, *, create: bool = False) -> Path:
        """Resolve one isolated state directory using canonical project naming."""
        safe_name = self.project_storage.context(project_name).project_name
        self._ensure_root()
        path = (self.root / safe_name).resolve()
        if path.parent != self.root:
            raise ValueError("Invalid runtime state path")
        if path.is_symlink():
            raise ValueError("Runtime state path must not be a symbolic link")
        if create:
            path.mkdir(mode=0o700, parents=False, exist_ok=True)
            path.chmod(0o700)
        return path

    def restore_into(self, project_name: str, destination: Path) -> None:
        """Overlay allowlisted durable outputs into an operation package."""
        source = self.project_path(project_name)
        if source.exists():
            file_manager.copy_persisted_runtime_outputs(source, destination)

    def migrate_legacy_project_outputs(
        self,
        project_name: str,
        durable_project_path: Path,
    ) -> None:
        """Move legacy runtime outputs out of an upload project without data loss."""
        if not durable_project_path.is_dir() or durable_project_path.is_symlink():
            return
        state_path = self.project_path(project_name, create=True)
        file_manager.copy_persisted_runtime_outputs(
            durable_project_path,
            state_path,
        )
        file_manager.remove_persisted_runtime_outputs(durable_project_path)

    def delete(self, project_name: str) -> None:
        """Delete all durable execution state for a removed project."""
        path = self.project_path(project_name)
        if path.exists():
            if path.is_symlink() or not path.is_dir():
                raise ValueError("Runtime state path is invalid")
            shutil.rmtree(path)

    def _ensure_root(self) -> None:
        if self.root.is_symlink():
            raise ValueError("Runtime state root must not be a symbolic link")
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.root.chmod(0o700)


_store: RuntimeStateStore | None = None


def get_runtime_state_store() -> RuntimeStateStore:
    global _store
    if _store is None:
        _store = RuntimeStateStore()
    return _store
