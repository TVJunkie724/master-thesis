"""Deterministic ACR Task context for the Azure Five-layer v2 mover."""

from __future__ import annotations

import gzip
import io
from pathlib import Path
import tarfile
from typing import Dict

from src.core.secure_files import atomic_write_private_bytes
from src.providers.terraform.package_builders.common import _should_include_file


PROVIDERS_ROOT = Path(__file__).resolve().parents[2]
PACKAGE_ID = "azure_five-layer-v2-storage-mover"


def _context_bytes(source: Path) -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w", format=tarfile.PAX_FORMAT) as archive:
        for path in sorted(source.rglob("*")):
            if not path.is_file() or not _should_include_file(path):
                continue
            content = path.read_bytes()
            info = tarfile.TarInfo(path.relative_to(source).as_posix())
            info.size = len(content)
            info.mode = 0o644
            info.mtime = 0
            info.uid = info.gid = 0
            info.uname = info.gname = ""
            archive.addfile(info, io.BytesIO(content))
    return gzip.compress(buffer.getvalue(), compresslevel=9, mtime=0)


def build_azure_v2_storage_mover_context(project_path: Path) -> Dict[str, Path]:
    source = (
        PROVIDERS_ROOT
        / "azure"
        / "azure_functions"
        / "five-layer-v2"
        / "storage-mover"
    )
    if not source.is_dir() or source.is_symlink():
        raise ValueError("Unavailable Azure Five-layer v2 storage-mover context")
    output = (
        Path(project_path)
        / ".build"
        / "azure"
        / "five-layer-v2-storage-mover.tar.gz"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_private_bytes(output, _context_bytes(source))
    return {PACKAGE_ID: output}


__all__ = ["PACKAGE_ID", "build_azure_v2_storage_mover_context"]
