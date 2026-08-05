"""Deterministic container context construction for GCP Five-layer v2."""

from __future__ import annotations

import gzip
import io
from pathlib import Path
import tarfile
from typing import Collection, Dict

from src.core.secure_files import atomic_write_private_bytes
from src.providers.terraform.package_builders.common import _should_include_file


PROVIDERS_ROOT = Path(__file__).resolve().parents[2]
GCP_V2_CONTEXTS = frozenset({"five-layer-v2"})


def _context_bytes(source: Path) -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w", format=tarfile.PAX_FORMAT) as archive:
        for path in sorted(source.rglob("*")):
            if not path.is_file() or not _should_include_file(path):
                continue
            relative = path.relative_to(source).as_posix()
            content = path.read_bytes()
            info = tarfile.TarInfo(relative)
            info.size = len(content)
            info.mode = 0o644
            info.mtime = 0
            info.uid = 0
            info.gid = 0
            info.uname = ""
            info.gname = ""
            archive.addfile(info, io.BytesIO(content))
    return gzip.compress(buffer.getvalue(), compresslevel=9, mtime=0)


def build_gcp_v2_container_contexts(
    project_path: Path,
    selected_context_names: Collection[str],
) -> Dict[str, Path]:
    """Build graph-selected, content-addressable Cloud Build contexts."""

    selected = set(selected_context_names)
    unknown = selected - GCP_V2_CONTEXTS
    if unknown:
        raise ValueError(f"Unknown GCP Five-layer v2 context: {sorted(unknown)}")
    if not selected:
        return {}

    build_dir = Path(project_path) / ".build" / "gcp"
    build_dir.mkdir(parents=True, exist_ok=True)
    packages: Dict[str, Path] = {}
    for name in sorted(selected):
        source = PROVIDERS_ROOT / "gcp" / "containers" / name
        if not source.is_dir() or source.is_symlink():
            raise ValueError(f"Unavailable GCP Five-layer v2 context: {name}")
        output = build_dir / f"{name}.tar.gz"
        atomic_write_private_bytes(output, _context_bytes(source))
        packages[f"gcp_{name}"] = output
    return packages
