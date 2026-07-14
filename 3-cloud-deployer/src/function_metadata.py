"""Canonical build and deployment evidence for user-function artifacts."""

from __future__ import annotations

import datetime
import hashlib
import json
import os
from pathlib import Path

from src.core.deterministic_zip import atomic_write_bytes
from src.core.paths import validate_path_component


FUNCTION_METADATA_SCHEMA_VERSION = 2


def canonical_provider(provider: str) -> str:
    validate_path_component(provider, "provider name")
    normalized = provider.lower()
    return "gcp" if normalized == "google" else normalized


def hash_bytes(content: bytes) -> str:
    return f"sha256:{hashlib.sha256(content).hexdigest()}"


def hash_directory(directory: str | Path) -> str:
    """Hash exactly the regular source files eligible for function packaging."""
    root = Path(directory)
    if root.is_symlink() or not root.is_dir():
        raise ValueError(f"Function directory not found or unsafe: {directory}")

    hasher = hashlib.sha256()
    for current_root, directories, filenames in sorted(os.walk(root)):
        current_path = Path(current_root)
        for directory_name in directories:
            if (current_path / directory_name).is_symlink():
                raise ValueError("Symbolic links are not allowed in function sources")
        directories[:] = sorted(
            name
            for name in directories
            if name != "__pycache__" and not name.startswith(".git")
        )
        for filename in sorted(filenames):
            path = current_path / filename
            if path.is_symlink():
                raise ValueError("Symbolic links are not allowed in function sources")
            if (
                filename == ".DS_Store"
                or filename.startswith(".git")
                or path.suffix.lower() in {".pyc", ".zip"}
            ):
                continue
            hasher.update(path.relative_to(root).as_posix().encode("utf-8"))
            with path.open("rb") as source:
                for chunk in iter(lambda: source.read(8192), b""):
                    hasher.update(chunk)
    return f"sha256:{hasher.hexdigest()}"


def metadata_path(
    project_path: Path,
    function_name: str,
    provider: str,
) -> Path:
    validate_path_component(function_name, "function name")
    normalized_provider = canonical_provider(provider)
    return (
        project_path
        / ".build"
        / "metadata"
        / f"{function_name}.{normalized_provider}.json"
    )


def record_function_build(
    project_path: Path,
    function_name: str,
    provider: str,
    source_hash: str,
    artifact_hash: str,
) -> Path:
    """Atomically publish build evidence after an artifact is complete."""
    target = metadata_path(project_path, function_name, provider)
    _ensure_metadata_directory(target.parent)
    previous = load_function_metadata(target)
    metadata = {
        "schema_version": FUNCTION_METADATA_SCHEMA_VERSION,
        "function": function_name,
        "provider": canonical_provider(provider),
        "source_hash": _require_hash(source_hash, "source_hash"),
        "artifact_hash": _require_hash(artifact_hash, "artifact_hash"),
        "last_built": _utc_now(),
    }
    if previous and previous.get("deployed_artifact_hash") == artifact_hash:
        metadata["deployed_artifact_hash"] = artifact_hash
        if isinstance(previous.get("last_deployed"), str):
            metadata["last_deployed"] = previous["last_deployed"]
    _write_metadata(target, metadata)
    return target


def mark_function_deployed(
    target: Path,
    *,
    expected_artifact_hash: str,
    deployed_at: str | None = None,
) -> bool:
    """Advance valid build evidence to deployed after provider success."""
    _require_hash(expected_artifact_hash, "expected_artifact_hash")
    metadata = load_function_metadata(target)
    if metadata is None or metadata["artifact_hash"] != expected_artifact_hash:
        return False
    metadata["deployed_artifact_hash"] = metadata["artifact_hash"]
    metadata["last_deployed"] = deployed_at or _utc_now()
    _write_metadata(target, metadata)
    return True


def mark_provider_artifact_deployed(
    project_path: Path,
    provider: str,
    artifact_hash: str,
) -> list[str]:
    """Mark every function represented by one provider bundle as deployed."""
    normalized_provider = canonical_provider(provider)
    metadata_dir = project_path / ".build" / "metadata"
    if not metadata_dir.is_dir() or metadata_dir.is_symlink():
        return []
    deployed_at = _utc_now()
    deployed = []
    for target in sorted(metadata_dir.glob(f"*.{normalized_provider}.json")):
        metadata = load_function_metadata(target)
        if metadata is None or metadata.get("artifact_hash") != artifact_hash:
            continue
        if mark_function_deployed(
            target,
            expected_artifact_hash=artifact_hash,
            deployed_at=deployed_at,
        ):
            deployed.append(metadata["function"])
    return deployed


def load_function_metadata(target: Path) -> dict | None:
    if not target.is_file() or target.is_symlink():
        return None
    try:
        metadata = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(metadata, dict):
        return None
    if metadata.get("schema_version") != FUNCTION_METADATA_SCHEMA_VERSION:
        return None
    required = ("function", "provider", "source_hash", "artifact_hash", "last_built")
    if not all(isinstance(metadata.get(key), str) and metadata[key] for key in required):
        return None
    try:
        validate_path_component(metadata["function"], "function name")
        if canonical_provider(metadata["provider"]) != metadata["provider"]:
            return None
        _require_hash(metadata["source_hash"], "source_hash")
        _require_hash(metadata["artifact_hash"], "artifact_hash")
        if "deployed_artifact_hash" in metadata:
            _require_hash(
                metadata["deployed_artifact_hash"],
                "deployed_artifact_hash",
            )
    except ValueError:
        return None
    return metadata


def reconcile_function_metadata(
    project_path: Path,
    provider: str,
    active_function_names: set[str],
) -> None:
    """Remove evidence not represented by the current L2 package contract."""
    normalized_provider = canonical_provider(provider)
    metadata_dir = project_path / ".build" / "metadata"
    if not metadata_dir.is_dir() or metadata_dir.is_symlink():
        return
    for target in sorted(metadata_dir.glob("*.json")):
        metadata = load_function_metadata(target)
        if (
            metadata is None
            or metadata.get("provider") != normalized_provider
            or metadata.get("function") not in active_function_names
        ):
            target.unlink()


def _ensure_metadata_directory(metadata_dir: Path) -> None:
    build_dir = metadata_dir.parent
    project_dir = build_dir.parent
    if project_dir.is_symlink() or not project_dir.is_dir():
        raise ValueError("Function metadata requires a regular project directory")
    for path in (build_dir, metadata_dir):
        if path.exists() and path.is_symlink():
            raise ValueError("Function metadata directory cannot be a symbolic link")
    metadata_dir.mkdir(parents=True, exist_ok=True)


def _require_hash(value: str, field: str) -> str:
    if not isinstance(value, str) or not value.startswith("sha256:") or len(value) != 71:
        raise ValueError(f"{field} must be a SHA-256 digest")
    return value


def _write_metadata(target: Path, metadata: dict) -> None:
    payload = json.dumps(metadata, indent=2, sort_keys=True).encode("utf-8") + b"\n"
    atomic_write_bytes(target, payload)


def _utc_now() -> str:
    return (
        datetime.datetime.now(datetime.timezone.utc)
        .isoformat()
        .replace("+00:00", "Z")
    )
