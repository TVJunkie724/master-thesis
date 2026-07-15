#!/usr/bin/env python3
"""Create durable local Management API secrets without disclosing their values."""

from __future__ import annotations

import argparse
import base64
import os
import re
import secrets
import sqlite3
import stat
import sys
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path

# Docker secret filename, not an embedded credential value.
JWT_SECRET_FILENAME = "JWT_SECRET_KEY"  # nosec B105
ENCRYPTION_KEY_FILENAME = "ENCRYPTION_KEY"
SECRET_FILENAMES = (JWT_SECRET_FILENAME, ENCRYPTION_KEY_FILENAME)
MIN_SECRET_LENGTH = 32
MAX_SECRET_FILE_BYTES = 4096
KNOWN_INSECURE_VALUES = {
    "local-development-jwt-secret-change-me",
    "local-development-encryption-key-change-me",
    "your-secret-key-change-in-production",
    "your-fernet-key-here",
    "dev-secret-change-in-production",
    "dev-secret-key",
}


class SecretBootstrapError(RuntimeError):
    """A public, secret-safe local bootstrap failure."""


@dataclass(frozen=True)
class SecretBootstrapResult:
    statuses: Mapping[str, str]
    secrets_dir: Path


SecretFileCreator = Callable[[Path, str], None]


def bootstrap_local_runtime_secrets(
    secrets_dir: Path,
    database_path: Path,
    *,
    environment: Mapping[str, str] | None = None,
    create_secret_file: SecretFileCreator | None = None,
) -> SecretBootstrapResult:
    """Create or validate the local JWT/encryption secret pair."""
    env = os.environ if environment is None else environment
    creator = create_secret_file or _create_secret_file
    target_dir = secrets_dir.expanduser().absolute()
    _ensure_private_directory(target_dir)

    values: dict[str, str] = {}
    statuses: dict[str, str] = {}
    missing: list[str] = []
    for filename in SECRET_FILENAMES:
        path = target_dir / filename
        if _path_exists(path):
            value = _read_secret_file(path)
            _validate_secret(filename, value)
            values[filename] = value
            statuses[filename] = "preserved"
        else:
            missing.append(filename)

    if (
        ENCRYPTION_KEY_FILENAME in missing
        and not env.get(ENCRYPTION_KEY_FILENAME, "")
        and _encrypted_cloud_connection_count(database_path) > 0
    ):
        raise SecretBootstrapError(
            "ENCRYPTION_KEY is missing while encrypted CloudConnections exist. "
            "Restore a valid original key through the ENCRYPTION_KEY environment "
            "variable. Data written with a removed insecure development placeholder "
            "must be migrated explicitly or the local development database reset."
        )

    for filename in missing:
        explicit_value = env.get(filename, "")
        if explicit_value:
            _validate_secret(filename, explicit_value)
            values[filename] = explicit_value
            statuses[filename] = "imported"
        else:
            values[filename] = _generate_secret(filename)
            statuses[filename] = "created"

    if values[JWT_SECRET_FILENAME] == values[ENCRYPTION_KEY_FILENAME]:
        raise SecretBootstrapError("JWT_SECRET_KEY and ENCRYPTION_KEY must be different.")

    created_paths: list[Path] = []
    try:
        for filename in missing:
            path = target_dir / filename
            creator(path, values[filename])
            created_paths.append(path)
    except Exception as exc:
        for path in reversed(created_paths):
            _remove_created_file(path)
        if isinstance(exc, SecretBootstrapError):
            raise
        raise SecretBootstrapError(
            "Failed to persist the complete local runtime secret pair."
        ) from exc

    for filename in SECRET_FILENAMES:
        _normalize_secret_permissions(target_dir / filename)

    return SecretBootstrapResult(statuses=dict(statuses), secrets_dir=target_dir)


def _ensure_private_directory(path: Path) -> None:
    parent = path.parent
    if _path_exists(parent):
        _require_real_directory(parent, label="Secret parent")
    else:
        parent.mkdir(parents=True, mode=0o700)

    if _path_exists(path):
        _require_real_directory(path, label="Secret directory")
    else:
        path.mkdir(mode=0o700)
    os.chmod(path, 0o700)


def _require_real_directory(path: Path, *, label: str) -> None:
    try:
        metadata = path.lstat()
    except OSError as exc:
        raise SecretBootstrapError(f"{label} cannot be inspected: {path}") from exc
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISDIR(metadata.st_mode):
        raise SecretBootstrapError(f"{label} must be a real directory: {path}")
    if hasattr(os, "getuid") and metadata.st_uid != os.getuid():
        raise SecretBootstrapError(f"{label} must be owned by the current user: {path}")


def _read_secret_file(path: Path) -> str:
    _require_regular_secret_file(path)
    flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor: int | None = None
    try:
        descriptor = os.open(path, flags)
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode):
            raise SecretBootstrapError(f"Secret target must be a regular file: {path}")
        if metadata.st_nlink != 1:
            raise SecretBootstrapError(f"Secret target must not be hard-linked: {path}")
        if metadata.st_size > MAX_SECRET_FILE_BYTES:
            raise SecretBootstrapError(f"Secret file is unexpectedly large: {path}")
        chunks: list[bytes] = []
        total_bytes = 0
        while total_bytes <= MAX_SECRET_FILE_BYTES:
            chunk = os.read(
                descriptor,
                min(1024, MAX_SECRET_FILE_BYTES + 1 - total_bytes),
            )
            if not chunk:
                break
            chunks.append(chunk)
            total_bytes += len(chunk)
        raw = b"".join(chunks)
        if len(raw) > MAX_SECRET_FILE_BYTES:
            raise SecretBootstrapError(f"Secret file is unexpectedly large: {path}")
        value = raw.decode("utf-8")
    except SecretBootstrapError:
        raise
    except (OSError, UnicodeDecodeError) as exc:
        raise SecretBootstrapError(f"Secret file cannot be read safely: {path}") from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)
    value = value.removesuffix("\n")
    if value != value.strip():
        raise SecretBootstrapError(f"Secret file contains surrounding whitespace: {path}")
    return value


def _require_regular_secret_file(path: Path) -> os.stat_result:
    try:
        metadata = path.lstat()
    except OSError as exc:
        raise SecretBootstrapError(f"Secret file cannot be inspected: {path}") from exc
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
        raise SecretBootstrapError(f"Secret target must be a regular file: {path}")
    if metadata.st_nlink != 1:
        raise SecretBootstrapError(f"Secret target must not be hard-linked: {path}")
    if hasattr(os, "getuid") and metadata.st_uid != os.getuid():
        raise SecretBootstrapError(f"Secret target must be owned by the current user: {path}")
    return metadata


def _normalize_secret_permissions(path: Path) -> None:
    _require_regular_secret_file(path)
    try:
        os.chmod(path, 0o600, follow_symlinks=False)
    except OSError as exc:
        raise SecretBootstrapError(f"Secret file permissions cannot be secured: {path}") from exc


def _validate_secret(filename: str, value: str) -> None:
    if value != value.strip():
        raise SecretBootstrapError(f"{filename} contains surrounding whitespace.")
    if len(value) < MIN_SECRET_LENGTH:
        raise SecretBootstrapError(f"{filename} must contain at least 32 characters.")
    if value in KNOWN_INSECURE_VALUES:
        raise SecretBootstrapError(f"{filename} uses a known insecure placeholder.")
    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        raise SecretBootstrapError(f"{filename} contains control characters.")
    if filename == ENCRYPTION_KEY_FILENAME:
        if re.fullmatch(r"[A-Za-z0-9_-]+={0,2}", value) is None:
            raise SecretBootstrapError(
                "ENCRYPTION_KEY must be a URL-safe base64 value."
            )
        try:
            decoded = base64.b64decode(
                value.encode("ascii"),
                altchars=b"-_",
                validate=True,
            )
        except (ValueError, UnicodeEncodeError) as exc:
            raise SecretBootstrapError(
                "ENCRYPTION_KEY must be a URL-safe base64 value."
            ) from exc
        if len(decoded) != 32:
            raise SecretBootstrapError(
                "ENCRYPTION_KEY must encode exactly 32 random bytes."
            )


def _generate_secret(filename: str) -> str:
    if filename == JWT_SECRET_FILENAME:
        return secrets.token_urlsafe(48)
    if filename == ENCRYPTION_KEY_FILENAME:
        return base64.urlsafe_b64encode(secrets.token_bytes(32)).decode("ascii")
    raise SecretBootstrapError(f"Unsupported secret target: {filename}")


def _create_secret_file(path: Path, value: str) -> None:
    if _path_exists(path):
        raise SecretBootstrapError(f"Secret target already exists: {path}")
    temp_path = path.with_name(f".{path.name}.{os.getpid()}.{secrets.token_hex(8)}.tmp")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor: int | None = None
    try:
        descriptor = os.open(temp_path, flags, 0o600)
        payload = f"{value}\n".encode("utf-8")
        offset = 0
        while offset < len(payload):
            written = os.write(descriptor, payload[offset:])
            if written <= 0:
                raise OSError("Secret file write made no progress")
            offset += written
        os.fsync(descriptor)
        os.close(descriptor)
        descriptor = None
        os.link(temp_path, path, follow_symlinks=False)
        os.chmod(path, 0o600, follow_symlinks=False)
        directory_descriptor = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_descriptor)
        finally:
            os.close(directory_descriptor)
    except FileExistsError as exc:
        raise SecretBootstrapError(f"Secret target was created concurrently: {path}") from exc
    except OSError as exc:
        raise SecretBootstrapError(f"Secret file cannot be created securely: {path}") from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)
        try:
            temp_path.unlink(missing_ok=True)
        except OSError:
            pass


def _remove_created_file(path: Path) -> None:
    try:
        metadata = path.lstat()
        if stat.S_ISREG(metadata.st_mode) and not stat.S_ISLNK(metadata.st_mode):
            path.unlink()
    except FileNotFoundError:
        return
    except OSError:
        return


def _encrypted_cloud_connection_count(database_path: Path) -> int:
    path = database_path.expanduser().absolute()
    if not _path_exists(path):
        return 0
    if path.is_symlink() or not path.is_file():
        raise SecretBootstrapError(f"Local database must be a regular file: {path}")
    try:
        connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        try:
            table_exists = connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
                ("cloud_connections",),
            ).fetchone()
            if table_exists is None:
                return 0
            result = connection.execute("SELECT COUNT(*) FROM cloud_connections").fetchone()
            return int(result[0]) if result is not None else 0
        finally:
            connection.close()
    except sqlite3.Error as exc:
        raise SecretBootstrapError(
            "Local database cannot be checked before encryption-key bootstrap."
        ) from exc


def _path_exists(path: Path) -> bool:
    return os.path.lexists(path)


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--secrets-dir", required=True, type=Path)
    parser.add_argument("--database", required=True, type=Path)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    try:
        result = bootstrap_local_runtime_secrets(args.secrets_dir, args.database)
    except SecretBootstrapError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    for filename in SECRET_FILENAMES:
        print(f"{filename}: {result.statuses[filename]} ({result.secrets_dir / filename})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
