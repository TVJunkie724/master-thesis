"""Deterministic runtime and CodeBuild packages for AWS Five-layer v2."""

from __future__ import annotations

from pathlib import Path
from typing import Dict

from src.core.deterministic_zip import atomic_zip_archive, write_zip_file
from src.providers.terraform.package_builders.common import _should_include_file


PROVIDERS_ROOT = Path(__file__).resolve().parents[2]
BRIDGE_RUNTIME_ROOT = PROVIDERS_ROOT.parent / "runtime" / "eventing"
BRIDGE_CORE_SOURCE = BRIDGE_RUNTIME_ROOT / "bridge_core.py"
RUNTIME_PACKAGE_ID = "aws_five-layer-v2"
STORAGE_MOVER_PACKAGE_ID = "aws_five-layer-v2-storage-mover"
# Compatibility alias for callers introduced with the first storage-mover slice.
PACKAGE_ID = STORAGE_MOVER_PACKAGE_ID


def build_aws_v2_graph_app(project_path: Path) -> Dict[str, Path]:
    """Build the standalone v2 Lambda package with its reviewed shared core."""

    source = PROVIDERS_ROOT / "aws" / "lambda_functions" / "five-layer-v2"
    shared = PROVIDERS_ROOT / "aws" / "lambda_functions" / "_shared"
    if (
        not source.is_dir()
        or source.is_symlink()
        or not shared.is_dir()
        or shared.is_symlink()
        or not BRIDGE_CORE_SOURCE.is_file()
        or BRIDGE_CORE_SOURCE.is_symlink()
    ):
        raise ValueError("Unavailable AWS Five-layer v2 runtime source")
    output = Path(project_path) / ".build" / "aws" / "five-layer-v2.zip"
    output.parent.mkdir(parents=True, exist_ok=True)
    with atomic_zip_archive(output) as archive:
        for path in sorted(source.rglob("*")):
            if path.is_file() and _should_include_file(path):
                write_zip_file(archive, path, path.relative_to(source))
        for path in sorted(shared.rglob("*")):
            if path.is_file() and _should_include_file(path):
                write_zip_file(
                    archive,
                    path,
                    Path("_shared") / path.relative_to(shared),
                )
        write_zip_file(archive, BRIDGE_CORE_SOURCE, "bridge_core.py")
        for path in sorted(BRIDGE_RUNTIME_ROOT.rglob("*")):
            if path.is_file() and _should_include_file(path):
                write_zip_file(
                    archive,
                    path,
                    Path("phase8_eventing") / path.relative_to(BRIDGE_RUNTIME_ROOT),
                )
    return {RUNTIME_PACKAGE_ID: output}


def build_aws_v2_storage_mover_context(project_path: Path) -> Dict[str, Path]:
    """Build the graph-selected AWS mover as an S3-compatible ZIP context."""

    source = (
        PROVIDERS_ROOT / "aws" / "lambda_functions" / "five-layer-v2" / "storage-mover"
    )
    if not source.is_dir() or source.is_symlink():
        raise ValueError("Unavailable AWS Five-layer v2 storage-mover context")
    output = Path(project_path) / ".build" / "aws" / "five-layer-v2-storage-mover.zip"
    output.parent.mkdir(parents=True, exist_ok=True)
    with atomic_zip_archive(output) as archive:
        for path in sorted(source.rglob("*")):
            if path.is_file() and _should_include_file(path):
                write_zip_file(archive, path, path.relative_to(source))
    return {STORAGE_MOVER_PACKAGE_ID: output}


__all__ = [
    "PACKAGE_ID",
    "RUNTIME_PACKAGE_ID",
    "STORAGE_MOVER_PACKAGE_ID",
    "build_aws_v2_graph_app",
    "build_aws_v2_storage_mover_context",
]
