"""
File Manager - Project File Operations.

This module provides functions for creating projects from zip files,
managing configuration files, and updating function code.

All functions require the project_path parameter.
"""

import os
import zipfile
import json
import shutil
from datetime import datetime
from pathlib import Path
import constants as CONSTANTS
from logger import logger
import io
import tempfile
from uuid import uuid4

import src.validator as validator
from src.core.project_storage import ProjectStorage, is_sensitive_project_file
from src.core.secure_files import atomic_write_private_bytes
from src.core.deterministic_zip import (
    atomic_zip_archive,
    write_zip_bytes,
    write_zip_file,
)
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
    CONSTANTS.PROJECT_VERSIONS_DIR_NAME,
)
PERSISTED_RUNTIME_FILES = (
    Path("terraform/terraform.tfstate"),
    Path("terraform/terraform.tfstate.backup"),
)
EXPORT_EXCLUDED_DIR_NAMES = frozenset(
    {
        *GENERATED_PROJECT_PATHS,
        CONSTANTS.PROJECT_VERSIONS_DIR_NAME,
        CONSTANTS.IOT_DATA_DIR_NAME,
        "__pycache__",
    }
)


def _is_sensitive_project_file(relative_path: str) -> bool:
    """Return True when a project file may contain live cloud credentials."""
    return is_sensitive_project_file(relative_path)


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
# 1. Project Creation & Update (Zip Handling)
# ==========================================
def create_project_from_zip(
    project_name, zip_source, project_path: str = None, description: str = None
):
    """
    Creates a new project from a validated zip file.

    Args:
        project_name (str): Name of the project to create.
        zip_source (str | BytesIO): Zip file source.
        project_path (str): Base project path. If None, auto-detected.
        description (str): Optional project description. If None, generated from digital_twin_name.

    Returns:
        dict: Result with message and any warnings.

    Raises:
        ValueError: If project name is invalid, project already exists, zip is invalid,
                    or duplicate project detected.
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

    # Extract twin_name and creds from zip for duplicate check
    zip_source.seek(0)
    twin_name, creds = _extract_identity_from_zip(zip_source)

    # Check for duplicate project (same twin_name + same credentials)
    conflicting_project = validator.check_duplicate_project(
        twin_name, creds, exclude_project=project_name, project_path=project_path
    )
    if conflicting_project:
        raise ValueError(
            f"Duplicate project detected: '{conflicting_project}' has the same "
            f"digital_twin_name and credentials."
        )

    storage = _get_project_storage(project_path)
    target_dir = storage.deployment_project_path(safe_name)
    if target_dir.exists():
        raise ValueError(f"Project '{project_name}' already exists.")

    _replace_project_from_archive(
        target_dir,
        zip_source,
        description=description,
        existing_target=None,
    )

    logger.info(f"Created project '{project_name}' from zip.")
    return {"message": f"Project '{project_name}' created.", "warnings": warnings}


def update_project_from_zip(
    project_name, zip_source, project_path: str = None, description: str = None
):
    """
    Updates an existing project from a zip file (Overwrites existing files).
    Archives the new version before extracting.

    Args:
        project_name (str): Name of the project to update.
        zip_source (str | BytesIO): Zip file source.
        project_path (str): Base project path. If None, auto-detected.
        description (str): Optional project description. If None, keeps existing or generates.

    Returns:
        dict: Result with message and any warnings.

    Raises:
        ValueError: If project name is invalid, zip is invalid, or duplicate detected.
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

    # Extract twin_name and creds from zip for duplicate check
    zip_source.seek(0)
    twin_name, creds = _extract_identity_from_zip(zip_source)

    # Check for duplicate project (exclude self)
    conflicting_project = validator.check_duplicate_project(
        twin_name, creds, exclude_project=project_name, project_path=project_path
    )
    if conflicting_project:
        raise ValueError(
            f"Duplicate project detected: '{conflicting_project}' has the same "
            f"digital_twin_name and credentials."
        )

    storage = _get_project_storage(project_path)
    target_dir = storage.deployment_project_path(safe_name)

    if not target_dir.is_dir() or target_dir.is_symlink():
        raise ValueError(f"Project '{project_name}' does not exist.")

    _replace_project_from_archive(
        target_dir,
        zip_source,
        description=description,
        existing_target=target_dir,
    )

    logger.info(f"Updated project '{project_name}' from zip.")
    return {"message": f"Project '{project_name}' updated.", "warnings": warnings}


# ==========================================
# 2. Project Listing
# ==========================================
def list_projects(project_path: str = None, include_templates: bool = False):
    """
    Returns a list of available project names.

    Args:
        project_path: Base project path. If None, auto-detected.
        include_templates: Include legacy template folders that still live under upload.
    """
    if project_path is None:
        project_path = _get_project_base_path()

    return _get_project_storage(project_path).list_projects(
        include_templates=include_templates
    )


# ==========================================
# 3. Configuration Management
# ==========================================
def update_config_file(
    project_name, config_filename, config_content, project_path: str = None
):
    """
    Updates a specific configuration file for a project.

    Args:
        project_name: Name of the project
        config_filename: Name of the config file
        config_content: JSON content to write
        project_path: Base project path. If None, auto-detected.
    """
    if project_path is None:
        project_path = _get_project_base_path()

    storage = _get_project_storage(project_path)
    target_dir = storage.deployment_project_path(project_name)

    if not target_dir.exists():
        raise ValueError(f"Project '{project_name}' does not exist.")

    # Verify content is valid JSON
    if isinstance(config_content, str):
        try:
            json_content = json.loads(config_content)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON content for {config_filename}: {e}")
    else:
        json_content = config_content

    # Validate Schema
    validator.validate_config_content(config_filename, json_content)

    storage.write_json(project_name, config_filename, json_content)

    logger.info(f"Updated {config_filename} for project '{project_name}'.")


# ==========================================
# 4. Function Management
# ==========================================
def get_provider_for_function(project_name, function_name, project_path: str = None):
    """Proxy for validator.get_provider_for_function"""
    if project_path is None:
        project_path = _get_project_base_path()
    return validator.get_provider_for_function(
        project_name, function_name, project_path
    )


def update_function_code_file(
    project_name, function_name, file_name, code_content, project_path: str = None
):
    """
    Updates the code file for a specific function, with provider-specific validation.

    Args:
        project_name: Name of the project
        function_name: Name of the function
        file_name: Name of the file to update
        code_content: Code content to write
        project_path: Base project path. If None, auto-detected.
    """
    if project_path is None:
        project_path = _get_project_base_path()

    storage = _get_project_storage(project_path)
    function_dir = f"{CONSTANTS.LAMBDA_FUNCTIONS_DIR_NAME}/{function_name}"
    target_dir = storage.resolve_file(project_name, function_dir)

    if not target_dir.exists():
        raise ValueError(
            f"Function directory '{function_name}' does not exist in project '{project_name}'."
        )

    # Validate Python Code
    if file_name.endswith(".py"):
        provider = validator.get_provider_for_function(
            project_name, function_name, project_path
        )
        if provider == "aws":
            validator.validate_python_code_aws(code_content)
        elif provider == "azure":
            validator.validate_python_code_azure(code_content)
        elif provider == "google":
            validator.validate_python_code_google(code_content)

    # Write File
    target_file = storage.resolve_file(
        project_name, f"{function_dir}/{file_name}", for_write=True
    )
    target_file.write_text(code_content, encoding="utf-8")

    logger.info(
        f"Updated function code '{file_name}' for function '{function_name}' in project '{project_name}'."
    )


# ==========================================
# 5. Versioning & Metadata Helpers
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
) -> list[str]:
    """Validate and extract one secret-bearing package into a private runtime path."""
    buffered = _buffer_zip_source(zip_source)
    warnings = validator.validate_project_zip(buffered) or []
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


def _replace_project_from_archive(
    target_dir: Path,
    zip_source: io.BytesIO,
    *,
    description: str | None,
    existing_target: Path | None,
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

        existing_info = _read_project_info(existing_target)
        if existing_target is not None:
            _copy_version_history(existing_target, staging_dir)
        _archive_zip_version(zip_source, staging_dir)
        _write_project_info(
            staging_dir,
            zip_source,
            description,
            existing_info=existing_info,
        )
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
    (staging_dir / CONSTANTS.PROJECT_INFO_FILE).unlink(missing_ok=True)


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


def _copy_version_history(existing_target: Path, staging_dir: Path) -> None:
    source = existing_target / CONSTANTS.PROJECT_VERSIONS_DIR_NAME
    if source.is_dir() and not source.is_symlink():
        destination = staging_dir / CONSTANTS.PROJECT_VERSIONS_DIR_NAME
        destination.mkdir()
        for version in sorted(source.iterdir()):
            if version.is_symlink():
                raise ValueError("Project version history contains a symbolic link")
            if version.is_file() and version.suffix == ".zip":
                shutil.copy2(version, destination / version.name)


def _read_project_info(existing_target: Path | None) -> dict:
    if existing_target is None:
        return {}
    info_path = existing_target / CONSTANTS.PROJECT_INFO_FILE
    try:
        value = json.loads(info_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


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


def _archive_zip_version(zip_source, target_dir):
    """
    Archives the uploaded zip to {target_dir}/versions/{timestamp}.zip.

    Args:
        zip_source: BytesIO containing the zip file.
        target_dir: Project directory to archive into.
    """
    versions_dir = os.path.join(target_dir, CONSTANTS.PROJECT_VERSIONS_DIR_NAME)
    os.makedirs(versions_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S.%f")
    version_path = Path(versions_dir) / f"{timestamp}.zip"
    zip_source.seek(0)
    with zipfile.ZipFile(zip_source, "r") as source_archive:
        accessor = ZipFileAccessor(source_archive)
        project_root = accessor.get_project_root()
        with atomic_zip_archive(version_path) as version_archive:
            for member in source_archive.infolist():
                if member.is_dir() or not member.filename.startswith(project_root):
                    continue
                relative_path = member.filename[len(project_root) :]
                top_level = relative_path.split("/", 1)[0]
                if (
                    not relative_path
                    or is_sensitive_project_file(relative_path)
                    or top_level in GENERATED_PROJECT_PATHS
                    or relative_path == CONSTANTS.PROJECT_INFO_FILE
                ):
                    continue
                write_zip_bytes(
                    version_archive,
                    relative_path,
                    accessor.read_binary(member.filename),
                )

    logger.info("Archived redacted project version to %s", version_path)


def _write_project_info(
    target_dir,
    zip_source,
    description: str = None,
    *,
    existing_info: dict | None = None,
):
    """
    Writes project_info.json with description and timestamps.
    If description is None, generates from config.json's digital_twin_name.

    Args:
        target_dir: Project directory.
        zip_source: BytesIO containing the zip file.
        description: Optional description string.
    """
    existing_info = existing_info or {}
    if not description:
        description = existing_info.get("description")
    if not description:
        config = _read_archive_json(zip_source, CONSTANTS.CONFIG_FILE, required=True)
        twin_name = (
            config.get("digital_twin_name") if isinstance(config, dict) else None
        )
        if not twin_name:
            raise ValueError("Missing mandatory 'digital_twin_name' in config.json")
        description = f"Project builds the digital twin with prefix name '{twin_name}'"

    now = datetime.now().isoformat()
    info = {
        "description": description,
        "created_at": existing_info.get("created_at", now),
    }
    if existing_info:
        info["updated_at"] = now
    info_path = Path(target_dir) / CONSTANTS.PROJECT_INFO_FILE
    temporary_path = info_path.with_suffix(".json.tmp")
    temporary_path.write_text(json.dumps(info, indent=2), encoding="utf-8")
    temporary_path.replace(info_path)


def _extract_identity_from_zip(zip_source):
    """
    Extracts digital_twin_name and credentials from a zip file.

    Args:
        zip_source: BytesIO containing the zip file.

    Returns:
        tuple: (digital_twin_name, credentials_dict)
    """
    config = _read_archive_json(zip_source, CONSTANTS.CONFIG_FILE, required=False)
    credentials = _read_archive_json(
        zip_source,
        CONSTANTS.CONFIG_CREDENTIALS_FILE,
        required=False,
    )
    twin_name = config.get("digital_twin_name") if isinstance(config, dict) else None
    return twin_name, credentials if isinstance(credentials, dict) else {}


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
# 6. Project CRUD Operations
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


def update_project_info(project_name, description: str, project_path: str = None):
    """
    Updates the description in project_info.json.

    Args:
        project_name: Name of the project.
        description: New description.
        project_path: Base project path. If None, auto-detected.

    Raises:
        ValueError: If project does not exist.
    """
    if project_path is None:
        project_path = _get_project_base_path()

    storage = _get_project_storage(project_path)
    target_dir = storage.deployment_project_path(project_name)
    info_path = target_dir / CONSTANTS.PROJECT_INFO_FILE

    if not target_dir.exists():
        raise ValueError(f"Project '{project_name}' does not exist.")

    info = {}
    if info_path.exists():
        with info_path.open("r") as f:
            info = json.load(f)

    info["description"] = description
    info["updated_at"] = datetime.now().isoformat()

    storage.write_json(project_name, CONSTANTS.PROJECT_INFO_FILE, info)

    logger.info(f"Updated info for project '{project_name}'.")


def export_project_to_zip(project_name: str, project_path: str = None) -> io.BytesIO:
    """
    Export a portable, non-secret project definition to an in-memory ZIP.

    Args:
        project_name: Name of the project to export.
        project_path: Base project path. If None, auto-detected.

    Returns:
        BytesIO: In-memory zip file buffer.

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

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for root, dirs, files in os.walk(target_dir, followlinks=False):
            dirs[:] = sorted(
                directory
                for directory in dirs
                if directory not in EXPORT_EXCLUDED_DIR_NAMES
                and not (Path(root) / directory).is_symlink()
            )

            for filename in sorted(files):
                full_path = Path(root) / filename
                rel_path = full_path.relative_to(target_dir)
                if not _is_exportable_project_file(rel_path):
                    continue
                write_zip_file(zip_file, full_path, rel_path)

    zip_buffer.seek(0)
    return zip_buffer


def _is_exportable_project_file(relative_path: Path) -> bool:
    """Return True only for portable project-definition artifacts."""
    filename = relative_path.name
    if filename == CONSTANTS.PROJECT_INFO_FILE or filename.endswith(".pyc"):
        return False
    if _is_sensitive_project_file(relative_path.as_posix()):
        return False
    if filename.startswith("config_generated") and filename.endswith(".json"):
        return False
    if filename.startswith("terraform.tfstate") or filename == "generated.tfvars.json":
        return False
    return True


def _resolve_project_target_dir(
    project_name: str,
    project_path: str = None,
    project_context_path: str = None,
) -> str:
    """Resolve a project directory from either a base path or an explicit context path."""
    if project_context_path is not None:
        return os.fspath(project_context_path)

    if project_path is None:
        project_path = _get_project_base_path()

    safe_name = os.path.basename(project_name)
    return os.path.join(project_path, CONSTANTS.PROJECT_UPLOAD_DIR_NAME, safe_name)


def get_project_file_tree(
    project_name: str,
    project_path: str = None,
    project_context_path: str = None,
) -> list:
    """
    Returns a recursive file tree structure for the project.
    """
    target_dir = _resolve_project_target_dir(
        project_name, project_path, project_context_path
    )

    if not os.path.exists(target_dir):
        raise ValueError(f"Project '{project_name}' does not exist.")

    def build_tree(current_path, rel_base):
        items = []
        try:
            entries = sorted(os.listdir(current_path))
        except OSError:
            return []

        for entry in entries:
            # Skip hidden/internal folders
            if entry.startswith(".") or entry in [
                CONSTANTS.PROJECT_VERSIONS_DIR_NAME,
                "__pycache__",
            ]:
                continue
            if entry == CONSTANTS.PROJECT_INFO_FILE:
                continue

            full_path = os.path.join(current_path, entry)
            rel_path = os.path.join(rel_base, entry).replace(
                "\\", "/"
            )  # force posix path for API
            if os.path.isfile(full_path) and _is_sensitive_project_file(rel_path):
                continue

            item = {"name": entry, "path": rel_path}

            if os.path.isdir(full_path):
                item["type"] = "directory"
                item["children"] = build_tree(full_path, rel_path)
            else:
                item["type"] = "file"
                item["size"] = os.path.getsize(full_path)

            items.append(item)
        return items

    return build_tree(target_dir, "")


def get_project_file_content(
    project_name: str,
    relative_path: str,
    project_path: str = None,
    project_context_path: str = None,
) -> dict:
    """
    Returns the content of a specific file.
    """
    target_dir = _resolve_project_target_dir(
        project_name, project_path, project_context_path
    )

    # Security check: prevent directory traversal
    target_file = os.path.abspath(os.path.join(target_dir, relative_path))
    if os.path.commonpath(
        [os.path.abspath(target_dir), target_file]
    ) != os.path.abspath(target_dir):
        raise ValueError("Invalid file path: Traversal attempt detected.")

    if _is_sensitive_project_file(relative_path):
        raise PermissionError(
            f"Access denied for protected sensitive project file '{relative_path}'."
        )

    if not os.path.exists(target_file):
        raise ValueError(f"File '{relative_path}' not found.")

    if os.path.isdir(target_file):
        raise ValueError(f"'{relative_path}' is a directory, not a file.")

    try:
        with open(target_file, "r", encoding="utf-8") as f:
            content = f.read()

        result = {"path": relative_path, "raw": content}

        # Try parsing JSON if applicable. Example files keep their source suffix
        # (for example config_credentials.json.example) but still carry JSON.
        if relative_path.endswith(".json") or relative_path.endswith(".json.example"):
            try:
                result["content"] = json.loads(content)
            except json.JSONDecodeError:
                pass

        return result
    except UnicodeDecodeError:
        raise ValueError("Cannot read binary file as text.")
