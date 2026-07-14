"""Resource and path policy for untrusted project ZIP archives."""

from __future__ import annotations

from pathlib import PurePosixPath
import stat
import zipfile


MIB = 1024 * 1024
MAX_COMPRESSED_ARCHIVE_BYTES = 100 * MIB
MAX_TOTAL_UNCOMPRESSED_BYTES = 250 * MIB
MAX_MEMBER_BYTES = 100 * MIB
MAX_MEMBERS = 2_000
MAX_COMPRESSION_RATIO = 200
UPLOAD_READ_CHUNK_BYTES = MIB
ALLOWED_COMPRESSION_TYPES = {zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED}


class ArchivePolicyError(ValueError):
    """Base error for unsafe or unsupported archive content."""


class ArchiveLimitExceeded(ArchivePolicyError):
    """Archive exceeds a bounded resource contract."""


def validate_archive(zf: zipfile.ZipFile) -> None:
    """Reject ambiguous paths, special files, and decompression abuse."""
    members = zf.infolist()
    if len(members) > MAX_MEMBERS:
        raise ArchiveLimitExceeded(
            f"ZIP contains too many entries (maximum {MAX_MEMBERS})"
        )

    names: set[str] = set()
    total_size = 0
    for member in members:
        _validate_member_path(member.filename, names)
        _validate_member_type(member)
        if member.flag_bits & 0x1:
            raise ArchivePolicyError("Encrypted ZIP entries are not supported")
        if member.compress_type not in ALLOWED_COMPRESSION_TYPES:
            raise ArchivePolicyError("ZIP uses an unsupported compression method")
        if member.file_size > MAX_MEMBER_BYTES:
            raise ArchiveLimitExceeded(
                f"ZIP entry exceeds the {MAX_MEMBER_BYTES // MIB}MB per-file limit"
            )
        total_size += member.file_size
        if total_size > MAX_TOTAL_UNCOMPRESSED_BYTES:
            raise ArchiveLimitExceeded(
                "ZIP exceeds the 250MB total uncompressed-size limit"
            )
        if member.file_size and (
            member.file_size / max(1, member.compress_size) > MAX_COMPRESSION_RATIO
        ):
            raise ArchiveLimitExceeded("ZIP entry has an unsafe compression ratio")


def _validate_member_path(raw_name: str, names: set[str]) -> None:
    if not raw_name or "\x00" in raw_name or "\\" in raw_name:
        raise ArchivePolicyError("ZIP contains an unsafe or ambiguous path")
    path = PurePosixPath(raw_name)
    if path.is_absolute() or ".." in path.parts:
        raise ArchivePolicyError("ZIP contains a path outside the project root")
    if path.parts and path.parts[0].endswith(":"):
        raise ArchivePolicyError("ZIP contains an absolute drive path")
    canonical = path.as_posix().rstrip("/")
    if canonical in {"", "."} or canonical in names:
        raise ArchivePolicyError("ZIP contains duplicate or ambiguous entries")
    names.add(canonical)


def _validate_member_type(member: zipfile.ZipInfo) -> None:
    mode = (member.external_attr >> 16) & 0xFFFF
    if stat.S_ISLNK(mode):
        raise ArchivePolicyError("ZIP symbolic links are not supported")
    file_type = stat.S_IFMT(mode)
    if file_type and not (stat.S_ISREG(mode) or stat.S_ISDIR(mode)):
        raise ArchivePolicyError("ZIP special-file entries are not supported")
