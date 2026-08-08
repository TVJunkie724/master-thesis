"""Deterministic container context construction for GCP Five-layer v2."""

from __future__ import annotations

import gzip
import io
from pathlib import Path
import stat
import tarfile
from typing import Collection, Dict
import zipfile

from src.core.secure_files import atomic_write_private_bytes
from src.providers.terraform.package_builders.common import _should_include_file


PROVIDERS_ROOT = Path(__file__).resolve().parents[2]
BRIDGE_RUNTIME_ROOT = PROVIDERS_ROOT.parent / "runtime" / "eventing"
BRIDGE_CORE_SOURCE = BRIDGE_RUNTIME_ROOT / "bridge_core.py"
GCP_V2_CONTEXTS = frozenset({"five-layer-v2"})
GCP_V2_EXTENSION_DOCKERFILE = """# syntax=docker/dockerfile:1.7

FROM python:3.11-slim@sha256:baf89808ec37adeaab83cec287adb4a2afa4a11c1d51e961c7ec737877e61af6

ENV PYTHONDONTWRITEBYTECODE=1 \\
    PYTHONUNBUFFERED=1 \\
    PORT=8080

WORKDIR /app
COPY . /app
RUN pip install --no-cache-dir -r /app/requirements.txt \\
 && find /app -maxdepth 1 -type f -name '*.whl' -exec pip install --no-cache-dir --no-deps {} + \\
 && rm -f /app/*.whl \\
 && groupadd --gid 10001 runtime \\
 && useradd --uid 10001 --gid 10001 --home-dir /app --no-create-home --shell /usr/sbin/nologin runtime \\
 && chown -R runtime:runtime /app

USER runtime
EXPOSE 8080
CMD ["functions-framework", "--target=main", "--host=0.0.0.0", "--port=8080"]
"""


def _context_bytes(source: Path, *, additional_files: dict[str, Path] | None = None) -> bytes:
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
        for relative, path in sorted((additional_files or {}).items()):
            if (
                Path(relative).is_absolute()
                or ".." in Path(relative).parts
                or path.is_symlink()
                or not path.is_file()
                or not _should_include_file(path)
            ):
                raise ValueError("Additional GCP context source is unsafe")
            content = path.read_bytes()
            info = tarfile.TarInfo(relative)
            info.size = len(content)
            info.mode = 0o644
            info.mtime = 0
            info.uid = info.gid = 0
            info.uname = info.gname = ""
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
        if not BRIDGE_CORE_SOURCE.is_file() or BRIDGE_CORE_SOURCE.is_symlink():
            raise ValueError("Shared Phase 8 bridge runtime is unavailable")
        atomic_write_private_bytes(
            output,
            _context_bytes(
                source,
                additional_files={
                    "bridge_core.py": BRIDGE_CORE_SOURCE,
                    **{
                        (
                            Path("phase8_eventing")
                            / path.relative_to(BRIDGE_RUNTIME_ROOT)
                        ).as_posix(): path
                        for path in sorted(BRIDGE_RUNTIME_ROOT.rglob("*"))
                        if path.is_file() and _should_include_file(path)
                    },
                },
            ),
        )
        packages[f"gcp_{name}"] = output
    return packages


def build_gcp_v2_extension_container_context(
    project_path: Path,
    extension_package: Path,
) -> Path:
    """Wrap one validated GCP extension ZIP in a deterministic image context."""

    extension_package = Path(extension_package)
    if not extension_package.is_file() or extension_package.is_symlink():
        raise ValueError("Validated GCP processor extension package is unavailable")
    files: dict[str, bytes] = {"Dockerfile": GCP_V2_EXTENSION_DOCKERFILE.encode()}
    with zipfile.ZipFile(extension_package) as archive:
        for info in sorted(archive.infolist(), key=lambda item: item.filename):
            if info.is_dir():
                continue
            path = Path(info.filename)
            mode = info.external_attr >> 16
            if (
                path.is_absolute()
                or ".." in path.parts
                or "\\" in info.filename
                or stat.S_ISLNK(mode)
                or info.filename in files
            ):
                raise ValueError("Validated GCP extension package has an unsafe path")
            files[info.filename] = archive.read(info)
    if "main.py" not in files or "requirements.txt" not in files:
        raise ValueError("Validated GCP extension package lacks its runtime wrapper")

    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w", format=tarfile.PAX_FORMAT) as archive:
        for name, content in sorted(files.items()):
            info = tarfile.TarInfo(name)
            info.size = len(content)
            info.mode = 0o644
            info.mtime = 0
            info.uid = info.gid = 0
            info.uname = info.gname = ""
            archive.addfile(info, io.BytesIO(content))

    output = Path(project_path) / ".build" / "gcp" / "processor-extension.tar.gz"
    output.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_private_bytes(
        output,
        gzip.compress(buffer.getvalue(), compresslevel=9, mtime=0),
    )
    return output
