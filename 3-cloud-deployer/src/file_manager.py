"""Atomic, secret-safe deployment workspace materialization."""

import io
import json
import os
import shutil
import tempfile
import zipfile
from pathlib import Path
from uuid import uuid4

import constants as CONSTANTS
from logger import logger
import src.validator as validator
from src.core.project_storage import ProjectStorage, is_sensitive_project_file
from src.core.secure_files import atomic_write_private_bytes
from src.validation.accessors import ZipFileAccessor
from src.project_archive.policy import (
    ArchiveLimitExceeded,
    MAX_COMPRESSED_ARCHIVE_BYTES,
    validate_archive,
)


GENERATED_PROJECT_PATHS = (
    ".build",
    ".terraform_zips",
    "terraform",
    "versions",
    "project_info.json",
)
PERSISTED_RUNTIME_FILES = (
    Path("terraform/terraform.tfstate"),
    Path("terraform/terraform.tfstate.backup"),
)
def _get_project_base_path():
    """Get the base path for projects. Uses PYTHONPATH or app detection."""
    # Prefer /app in container, fallback to parent of src/
    app_path = "/app"
    if os.path.exists(app_path):
        return app_path
    # Fallback: go up from this file's directory
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _get_project_storage(project_path: str = None) -> ProjectStorage:
    """Return the project storage boundary for legacy file_manager callers."""
    if project_path is None:
        project_path = _get_project_base_path()
    return ProjectStorage(project_root=Path(project_path))


# ==========================================
# 1. Twin-owned deployment workspace materialization
# ==========================================
def create_project_from_zip(project_name, zip_source, project_path: str = None):
    """
    Creates a new project from a validated zip file.

    Args:
        project_name (str): Name of the project to create.
        zip_source (str | BytesIO): Zip file source.
        project_path (str): Base project path. If None, auto-detected.
    Returns:
        dict: Result with message and any warnings.

    Raises:
        ValueError: If project name is invalid, project already exists, zip is invalid,
                    or its manifest does not match the Twin resource name.
    """
    if project_path is None:
        project_path = _get_project_base_path()

    # Simple validation using os.path to prevent directory traversal
    safe_name = os.path.basename(project_name)
    if safe_name != project_name:
        raise ValueError("Invalid project name.")

    zip_source = _buffer_zip_source(zip_source)

    # Validate before extraction (Universal Validation)
    warnings = validator.validate_project_zip(zip_source)
    if warnings is None:
        warnings = []

    zip_source.seek(0)
    _validate_project_name_matches_manifest(
        safe_name, _extract_deployment_manifest(zip_source)
    )

    storage = _get_project_storage(project_path)
    target_dir = storage.deployment_project_path(safe_name)
    if target_dir.exists():
        raise ValueError(f"Project '{project_name}' already exists.")

    _replace_project_from_archive(target_dir, zip_source)

    logger.info(f"Created project '{project_name}' from zip.")
    return {"message": f"Project '{project_name}' created.", "warnings": warnings}


def update_project_from_zip(project_name, zip_source, project_path: str = None):
    """
    Replaces an existing Twin workspace atomically from a validated ZIP.

    Args:
        project_name (str): Name of the project to update.
        zip_source (str | BytesIO): Zip file source.
        project_path (str): Base project path. If None, auto-detected.
    Returns:
        dict: Result with message and any warnings.

    Raises:
        ValueError: If project name is invalid, the project does not exist, or ZIP is invalid.
    """
    if project_path is None:
        project_path = _get_project_base_path()

    safe_name = os.path.basename(project_name)
    if safe_name != project_name:
        raise ValueError("Invalid project name.")

    zip_source = _buffer_zip_source(zip_source)

    # Validate entire zip content first (Universal Validation)
    warnings = validator.validate_project_zip(zip_source)
    if warnings is None:
        warnings = []

    zip_source.seek(0)
    _validate_project_name_matches_manifest(
        safe_name, _extract_deployment_manifest(zip_source)
    )

    storage = _get_project_storage(project_path)
    target_dir = storage.deployment_project_path(safe_name)

    if not target_dir.is_dir() or target_dir.is_symlink():
        raise ValueError(f"Project '{project_name}' does not exist.")

    _replace_project_from_archive(target_dir, zip_source)

    logger.info(f"Updated project '{project_name}' from zip.")
    return {"message": f"Project '{project_name}' updated.", "warnings": warnings}


# ==========================================
# 2. Validated operation-package handling
# ==========================================
def _buffer_zip_source(zip_source) -> io.BytesIO:
    """Return a bounded, seekable copy of one supported ZIP source."""
    if isinstance(zip_source, bytes):
        content = zip_source
    elif isinstance(zip_source, (str, os.PathLike)):
        source_path = Path(zip_source)
        if source_path.stat().st_size > MAX_COMPRESSED_ARCHIVE_BYTES:
            raise ArchiveLimitExceeded("ZIP exceeds the 100MB compressed-size limit")
        content = source_path.read_bytes()
    elif hasattr(zip_source, "read") and hasattr(zip_source, "seek"):
        zip_source.seek(0)
        content = zip_source.read(MAX_COMPRESSED_ARCHIVE_BYTES + 1)
    else:
        raise TypeError("zip_source must be bytes, a path, or a seekable binary stream")

    if len(content) > MAX_COMPRESSED_ARCHIVE_BYTES:
        raise ArchiveLimitExceeded("ZIP exceeds the 100MB compressed-size limit")
    return io.BytesIO(content)


def extract_operation_archive(
    project_name: str,
    zip_source,
    destination: Path,
    *,
    prevalidated: bool = False,
) -> list[str]:
    """Validate and extract one secret-bearing package into a private runtime path."""
    buffered = _buffer_zip_source(zip_source)
    warnings = (
        []
        if prevalidated
        else validate_deployment_operation_archive(buffered)
    )
    buffered.seek(0)
    _validate_project_name_matches_manifest(
        project_name,
        _extract_deployment_manifest(buffered),
    )
    buffered.seek(0)
    with zipfile.ZipFile(buffered, "r") as archive:
        _extract_canonical_project(archive, destination)
    _remove_generated_project_paths(destination)
    return warnings


def validate_deployment_operation_archive(zip_source) -> list[str]:
    """Require the canonical manifest contract before staging runtime state."""
    buffered = _buffer_zip_source(zip_source)
    warnings = validator.validate_project_zip(
        buffered,
        require_deployment_manifest=True,
    )
    return warnings or []


def _replace_project_from_archive(
    target_dir: Path,
    zip_source: io.BytesIO,
) -> None:
    """Build a complete project in staging and atomically publish it."""
    target_dir.parent.mkdir(parents=True, exist_ok=True)
    staging_dir = Path(
        tempfile.mkdtemp(prefix=f".{target_dir.name}.staging-", dir=target_dir.parent)
    )
    try:
        zip_source.seek(0)
        with zipfile.ZipFile(zip_source, "r") as archive:
            _extract_canonical_project(archive, staging_dir)
        _remove_generated_project_paths(staging_dir)
        _remove_sensitive_project_files(staging_dir)

        _publish_staged_project(staging_dir, target_dir)
    finally:
        if staging_dir.exists():
            shutil.rmtree(staging_dir)


def _extract_canonical_project(
    archive: zipfile.ZipFile,
    staging_dir: Path,
) -> None:
    """Extract only the validated project root and flatten one ZIP wrapper folder."""
    validate_archive(archive)
    project_root = ZipFileAccessor(archive).get_project_root()
    root_entry = project_root.rstrip("/")
    for member in archive.infolist():
        member_name = member.filename.rstrip("/")
        if project_root:
            if member_name == root_entry:
                continue
            if not member.filename.startswith(project_root):
                raise ValueError(
                    "ZIP contains files outside the canonical project root"
                )
            relative_name = member.filename[len(project_root) :].rstrip("/")
        else:
            relative_name = member_name
        if not relative_name:
            continue

        target = staging_dir.joinpath(*relative_name.split("/"))
        if member.is_dir():
            target.mkdir(parents=True, exist_ok=True)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        with archive.open(member, "r") as source:
            if is_sensitive_project_file(relative_name):
                atomic_write_private_bytes(target, source.read())
            else:
                with target.open("xb") as destination:
                    shutil.copyfileobj(source, destination)


def _remove_generated_project_paths(staging_dir: Path) -> None:
    """Prevent uploaded archives from restoring generated runtime state."""
    for relative_path in GENERATED_PROJECT_PATHS:
        generated_path = staging_dir / relative_path
        if generated_path.is_dir() and not generated_path.is_symlink():
            shutil.rmtree(generated_path)
        else:
            generated_path.unlink(missing_ok=True)


def _remove_sensitive_project_files(staging_dir: Path) -> None:
    """Keep durable project definitions free of credential material."""
    for path in sorted(staging_dir.rglob("*"), reverse=True):
        if path.is_file() and is_sensitive_project_file(
            path.relative_to(staging_dir).as_posix()
        ):
            path.unlink()
        elif path.is_dir() and not any(path.iterdir()):
            path.rmdir()


def copy_persisted_runtime_outputs(existing_target: Path, staging_dir: Path) -> None:
    """Carry forward only runtime outputs required by later operations."""
    for relative_path in PERSISTED_RUNTIME_FILES:
        source = existing_target / relative_path
        if source.is_file() and not source.is_symlink():
            destination = staging_dir / relative_path
            atomic_write_private_bytes(destination, source.read_bytes())

    _copy_private_runtime_tree(
        existing_target / "iot_devices_auth",
        staging_dir / "iot_devices_auth",
    )
    _copy_matching_private_files(
        existing_target / "iot_device_simulator",
        staging_dir / "iot_device_simulator",
        "config_generated*.json",
    )
    _copy_matching_runtime_files(
        existing_target / ".build" / "metadata",
        staging_dir / ".build" / "metadata",
        "*.json",
    )


def remove_persisted_runtime_outputs(project_path: Path) -> None:
    """Remove runtime state after it has been copied to protected storage."""
    for relative_path in PERSISTED_RUNTIME_FILES:
        (project_path / relative_path).unlink(missing_ok=True)
    _remove_runtime_path(project_path / "iot_devices_auth")
    simulator_root = project_path / "iot_device_simulator"
    if simulator_root.is_dir() and not simulator_root.is_symlink():
        for path in simulator_root.rglob("config_generated*.json"):
            if path.is_symlink():
                raise ValueError("Legacy runtime output contains a symbolic link")
            path.unlink()
    _remove_runtime_path(project_path / ".build" / "metadata")


def _remove_runtime_path(path: Path) -> None:
    """Remove one allowlisted runtime path without following symbolic links."""
    if path.is_symlink() or path.is_file():
        path.unlink(missing_ok=True)
    elif path.is_dir():
        shutil.rmtree(path)


def _copy_private_runtime_tree(source: Path, destination: Path) -> None:
    if not source.exists():
        return
    if source.is_symlink() or not source.is_dir():
        raise ValueError("Persisted runtime output contains an invalid directory")
    for path in source.rglob("*"):
        if path.is_symlink():
            raise ValueError("Persisted runtime output contains a symbolic link")
        if path.is_file():
            target = destination / path.relative_to(source)
            atomic_write_private_bytes(target, path.read_bytes())


def _copy_matching_private_files(
    source_root: Path,
    destination_root: Path,
    pattern: str,
) -> None:
    if not source_root.exists():
        return
    if source_root.is_symlink() or not source_root.is_dir():
        raise ValueError("Persisted runtime output contains an invalid directory")
    for source in source_root.rglob(pattern):
        if source.is_symlink() or not source.is_file():
            raise ValueError("Persisted runtime output contains an invalid file")
        target = destination_root / source.relative_to(source_root)
        atomic_write_private_bytes(target, source.read_bytes())


def _copy_matching_runtime_files(
    source_root: Path,
    destination_root: Path,
    pattern: str,
) -> None:
    if not source_root.exists():
        return
    if source_root.is_symlink() or not source_root.is_dir():
        raise ValueError("Persisted runtime output contains an invalid directory")
    for source in source_root.rglob(pattern):
        if source.is_symlink() or not source.is_file():
            raise ValueError("Persisted runtime output contains an invalid file")
        target = destination_root / source.relative_to(source_root)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)


def _publish_staged_project(staging_dir: Path, target_dir: Path) -> None:
    """Atomically replace a project and roll back if publication fails."""
    backup_dir = target_dir.parent / f".{target_dir.name}.backup-{uuid4().hex}"
    had_existing_target = target_dir.exists()
    if had_existing_target:
        target_dir.replace(backup_dir)
    try:
        staging_dir.replace(target_dir)
    except BaseException:
        if had_existing_target and backup_dir.exists() and not target_dir.exists():
            backup_dir.replace(target_dir)
        raise
    if backup_dir.exists():
        try:
            shutil.rmtree(backup_dir)
        except OSError as exc:
            logger.warning(
                "Published project but could not remove prior project backup (%s)",
                type(exc).__name__,
            )


def _extract_deployment_manifest(zip_source):
    """Extract deployment_manifest.json from a validated ZIP, if present."""
    return _read_archive_json(
        zip_source,
        CONSTANTS.DEPLOYMENT_MANIFEST_FILE,
        required=False,
    )


def _read_archive_json(
    zip_source,
    filename: str,
    *,
    required: bool,
):
    """Read JSON from the archive's one canonical project root."""
    zip_source.seek(0)
    with zipfile.ZipFile(zip_source, "r") as archive:
        accessor = ZipFileAccessor(archive)
        path = accessor.get_project_root() + filename
        if not accessor.file_exists(path):
            if required:
                raise ValueError(f"Missing required archive file: {filename}")
            return None
        return json.loads(accessor.read_text(path))


def _validate_project_name_matches_manifest(
    project_name: str, manifest: dict | None
) -> None:
    """Ensure a manifest-backed upload lands under its declared resource name."""
    if not manifest:
        return

    twin = manifest.get("twin")
    if not isinstance(twin, dict):
        raise ValueError(
            "deployment_manifest.json twin metadata must be a JSON object."
        )

    resource_name = twin.get("resource_name")
    if not isinstance(resource_name, str) or not resource_name:
        raise ValueError("deployment_manifest.json twin.resource_name is required.")

    if resource_name != project_name:
        raise ValueError(
            "deployment_manifest.json twin.resource_name does not match requested project_name."
        )


# ==========================================
# 3. Workspace deletion
# ==========================================
def delete_project(project_name, project_path: str = None):
    """
    Deletes an entire project directory.

    Args:
        project_name: Name of the project to delete.
        project_path: Base project path. If None, auto-detected.

    Raises:
        ValueError: If project does not exist.
    """
    if project_path is None:
        project_path = _get_project_base_path()

    target_dir = _get_project_storage(project_path).deployment_project_path(
        project_name
    )

    if not target_dir.exists():
        raise ValueError(f"Project '{project_name}' does not exist.")

    shutil.rmtree(target_dir)
    logger.info(f"Deleted project '{project_name}'.")
