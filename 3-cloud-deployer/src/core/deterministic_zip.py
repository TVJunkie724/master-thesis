"""Deterministic and traversal-safe ZIP archive primitives."""

from contextlib import contextmanager
import zipfile
from pathlib import Path, PurePosixPath
from uuid import uuid4

_CANONICAL_TIMESTAMP = (1980, 1, 1, 0, 0, 0)
_CANONICAL_FILE_MODE = 0o644


def write_zip_bytes(
    archive: zipfile.ZipFile,
    archive_name: str | Path,
    content: str | bytes,
) -> None:
    """Write one normalized ZIP member with stable metadata and no duplicates."""
    normalized = PurePosixPath(str(archive_name).replace("\\", "/"))
    if normalized.is_absolute() or ".." in normalized.parts or not normalized.parts:
        raise ValueError(f"Unsafe ZIP member path: {archive_name}")
    member_name = normalized.as_posix()
    if member_name in archive.NameToInfo:
        raise ValueError(f"Duplicate ZIP member path: {member_name}")

    payload = content.encode("utf-8") if isinstance(content, str) else content
    info = zipfile.ZipInfo(member_name, date_time=_CANONICAL_TIMESTAMP)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.create_system = 3
    info.external_attr = (_CANONICAL_FILE_MODE & 0xFFFF) << 16
    archive.writestr(info, payload)


def write_zip_file(
    archive: zipfile.ZipFile,
    source_path: Path,
    archive_name: str | Path,
) -> None:
    """Write one regular source file without following symbolic links."""
    if source_path.is_symlink() or not source_path.is_file():
        raise ValueError(f"Unsafe or missing ZIP source file: {source_path}")
    write_zip_bytes(archive, archive_name, source_path.read_bytes())


def atomic_write_bytes(target_path: Path, content: bytes) -> None:
    """Replace a generated artifact only after its complete content is durable."""
    temporary_path = target_path.with_suffix(
        target_path.suffix + f".{uuid4().hex}.tmp"
    )
    try:
        temporary_path.write_bytes(content)
        temporary_path.replace(target_path)
    finally:
        temporary_path.unlink(missing_ok=True)


@contextmanager
def atomic_zip_archive(target_path: Path):
    """Yield a deterministic ZIP writer and atomically publish it on success."""
    temporary_path = target_path.with_suffix(
        target_path.suffix + f".{uuid4().hex}.tmp"
    )
    try:
        with zipfile.ZipFile(temporary_path, "w", zipfile.ZIP_DEFLATED) as archive:
            yield archive
        temporary_path.replace(target_path)
    finally:
        temporary_path.unlink(missing_ok=True)
