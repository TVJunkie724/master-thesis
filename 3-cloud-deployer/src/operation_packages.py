"""Private, short-lived credential packages for one Deployer operation."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import json
import logging
import os
from pathlib import Path
import secrets
import shutil
import tempfile
from typing import Iterator

import file_manager
from src.core.project_storage import ProjectStorage
from src.core.secure_files import atomic_write_private_bytes
from src.core.workspace import EphemeralWorkspace, sync_runtime_outputs
from src.runtime_state import RuntimeStateStore


DEFAULT_PACKAGE_TTL_SECONDS = 3600
METADATA_FILE = ".operation-package.json"
LOCK_FILE = ".operation-package.lock"
logger = logging.getLogger(__name__)


class OperationPackageError(ValueError):
    """Raised when an operation package cannot be staged or acquired."""


class InvalidOperationPackageError(OperationPackageError):
    """Raised for missing, expired, malformed, or project-mismatched tokens."""


class OperationPackageInUseError(OperationPackageError):
    """Raised when a one-shot package is already owned by another operation."""


@dataclass(frozen=True)
class StagedOperationPackage:
    project_name: str
    token: str
    expires_at: datetime
    warnings: list[str]


class OperationPackageStore:
    """Stages credential-bearing project packages outside durable project storage."""

    def __init__(
        self,
        *,
        root: Path | None = None,
        project_storage: ProjectStorage | None = None,
        runtime_state_store: RuntimeStateStore | None = None,
        ttl_seconds: int = DEFAULT_PACKAGE_TTL_SECONDS,
    ) -> None:
        if ttl_seconds <= 0:
            raise ValueError("Operation package TTL must be positive")
        configured_root = os.environ.get("DEPLOYER_OPERATION_PACKAGE_ROOT")
        self.root = (
            Path(root)
            if root is not None
            else Path(configured_root)
            if configured_root
            else Path(tempfile.gettempdir()) / "twin2multicloud-operation-packages"
        ).resolve()
        self.project_storage = project_storage or ProjectStorage()
        self.runtime_state_store = runtime_state_store or RuntimeStateStore(
            project_storage=self.project_storage
        )
        self.ttl = timedelta(seconds=ttl_seconds)

    def stage(self, project_name: str, archive: bytes) -> StagedOperationPackage:
        """Extract one validated package and return an opaque operation token."""
        safe_name = self.project_storage.context(project_name).project_name
        self._ensure_root()
        self.cleanup_expired()
        token = secrets.token_urlsafe(32)
        package_path = self.root / token
        package_path.mkdir(mode=0o700)
        now = datetime.now(timezone.utc)
        expires_at = now + self.ttl
        try:
            warnings = file_manager.extract_operation_archive(
                safe_name,
                archive,
                package_path,
            )
            metadata = {
                "project_name": safe_name,
                "created_at": now.isoformat(),
                "expires_at": expires_at.isoformat(),
            }
            atomic_write_private_bytes(
                package_path / METADATA_FILE,
                json.dumps(metadata, separators=(",", ":")).encode("utf-8"),
            )
            self._make_tree_private(package_path)
            durable_path = self.project_storage.deployment_project_path(safe_name)
            self.runtime_state_store.migrate_legacy_project_outputs(
                safe_name,
                durable_path,
            )
        except Exception:
            shutil.rmtree(package_path, ignore_errors=True)
            raise
        return StagedOperationPackage(
            project_name=safe_name,
            token=token,
            expires_at=expires_at,
            warnings=list(warnings),
        )

    @contextmanager
    def acquire(self, project_name: str, token: str) -> Iterator[Path]:
        """Acquire a package once, merge durable state, sync outputs, then destroy it."""
        package_path = self._resolve(project_name, token)
        lock_path = package_path / LOCK_FILE
        workspace: EphemeralWorkspace | None = None
        try:
            lock_fd = os.open(
                lock_path,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                0o600,
            )
            with os.fdopen(lock_fd, "w", encoding="utf-8") as lock_file:
                lock_file.write(str(os.getpid()))
        except FileExistsError as exc:
            raise OperationPackageInUseError(
                "Operation package is already in use"
            ) from exc

        try:
            durable_path = self.project_storage.deployment_project_path(project_name)
            if not durable_path.is_dir() or durable_path.is_symlink():
                raise OperationPackageError("Durable project definition is unavailable")

            self.runtime_state_store.restore_into(project_name, package_path)
            runtime_state_path = self.runtime_state_store.project_path(
                project_name,
                create=True,
            )
            workspace = EphemeralWorkspace(
                project_name=project_name,
                source_path=runtime_state_path,
                workspace_path=package_path,
            )
            yield package_path
        except BaseException:
            if workspace is not None:
                try:
                    sync_runtime_outputs(workspace)
                except Exception as sync_exc:
                    logger.error(
                        "Runtime output sync failed while preserving the original operation error (%s)",
                        type(sync_exc).__name__,
                    )
            raise
        else:
            if workspace is not None:
                sync_runtime_outputs(workspace)
        finally:
            self.discard(token)

    def discard(self, token: str) -> None:
        """Delete an operation package without exposing whether it existed."""
        package_path = self._token_path(token)
        if package_path is not None:
            shutil.rmtree(package_path, ignore_errors=True)

    def discard_project(self, project_name: str) -> None:
        """Invalidate every unused package for a project before project deletion."""
        safe_name = self.project_storage.context(project_name).project_name
        self._ensure_root()
        self.cleanup_expired()
        matching_paths: list[Path] = []
        for package_path in self.root.iterdir():
            if package_path.is_symlink() or not package_path.is_dir():
                continue
            try:
                metadata = self._read_metadata(package_path)
            except (OSError, ValueError, TypeError, json.JSONDecodeError):
                continue
            if metadata.get("project_name") != safe_name:
                continue
            lock_path = package_path / LOCK_FILE
            if lock_path.exists() and self._lock_is_active(lock_path):
                raise OperationPackageInUseError(
                    "Project has an active deployment operation"
                )
            matching_paths.append(package_path)

        for package_path in matching_paths:
            shutil.rmtree(package_path, ignore_errors=True)

    def cleanup_expired(self) -> None:
        """Remove expired and malformed package directories."""
        if not self.root.exists():
            return
        now = datetime.now(timezone.utc)
        for path in self.root.iterdir():
            if path.is_symlink() or not path.is_dir():
                continue
            lock_path = path / LOCK_FILE
            if lock_path.exists():
                if self._lock_is_active(lock_path):
                    continue
                shutil.rmtree(path, ignore_errors=True)
                continue
            try:
                metadata = self._read_metadata(path)
                expires_at = datetime.fromisoformat(metadata["expires_at"])
            except (KeyError, OSError, ValueError, TypeError, json.JSONDecodeError):
                shutil.rmtree(path, ignore_errors=True)
                continue
            if expires_at <= now:
                shutil.rmtree(path, ignore_errors=True)

    def _resolve(self, project_name: str, token: str) -> Path:
        safe_name = self.project_storage.context(project_name).project_name
        package_path = self._token_path(token)
        if (
            package_path is None
            or not package_path.is_dir()
            or package_path.is_symlink()
        ):
            raise InvalidOperationPackageError(
                "Operation package is invalid or expired"
            )
        try:
            metadata = self._read_metadata(package_path)
        except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
            self.discard(token)
            raise InvalidOperationPackageError(
                "Operation package is invalid or expired"
            ) from exc
        try:
            expires_at = datetime.fromisoformat(metadata["expires_at"])
        except (KeyError, ValueError, TypeError) as exc:
            self.discard(token)
            raise InvalidOperationPackageError(
                "Operation package is invalid or expired"
            ) from exc
        if metadata.get("project_name") != safe_name:
            raise InvalidOperationPackageError(
                "Operation package does not belong to this project"
            )
        if expires_at <= datetime.now(timezone.utc):
            self.discard(token)
            raise InvalidOperationPackageError(
                "Operation package is invalid or expired"
            )
        return package_path

    def _token_path(self, token: str) -> Path | None:
        if (
            not token
            or len(token) > 128
            or any(
                character
                not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_"
                for character in token
            )
        ):
            return None
        candidate = (self.root / token).resolve()
        if candidate.parent != self.root:
            return None
        return candidate

    @staticmethod
    def _read_metadata(package_path: Path) -> dict:
        return json.loads((package_path / METADATA_FILE).read_text(encoding="utf-8"))

    @staticmethod
    def _lock_is_active(lock_path: Path) -> bool:
        """Return whether a lock belongs to a process that is still alive."""
        try:
            pid = int(lock_path.read_text(encoding="utf-8"))
            if pid <= 0:
                return False
            os.kill(pid, 0)
        except PermissionError:
            return True
        except (OSError, ValueError):
            return False
        return True

    def _ensure_root(self) -> None:
        if self.root.is_symlink():
            raise OperationPackageError("Operation package root must not be a symlink")
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.root.chmod(0o700)

    @staticmethod
    def _make_tree_private(root: Path) -> None:
        root.chmod(0o700)
        for path in root.rglob("*"):
            if path.is_symlink():
                raise OperationPackageError(
                    "Operation package contains a symbolic link"
                )
            path.chmod(0o700 if path.is_dir() else 0o600)


_store: OperationPackageStore | None = None


def get_operation_package_store() -> OperationPackageStore:
    global _store
    if _store is None:
        _store = OperationPackageStore()
    return _store
