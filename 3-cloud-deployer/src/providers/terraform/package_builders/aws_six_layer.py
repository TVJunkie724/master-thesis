"""Deterministic runtime and CodeBuild packages for standalone AWS Six-layer."""

from __future__ import annotations

from pathlib import Path
from typing import Dict

from src.core.deterministic_zip import atomic_zip_archive, write_zip_file
from src.providers.terraform.package_builders.common import _should_include_file


PROVIDERS_ROOT = Path(__file__).resolve().parents[2]
BRIDGE_RUNTIME_ROOT = (
    PROVIDERS_ROOT.parent / "runtime" / "six_layer_eventing"
)
RUNTIME_PACKAGE_ID = "aws_six-layer-domain"
BRIDGE_PACKAGE_ID = "aws_six-layer-domain-bridge"
STORAGE_MOVER_PACKAGE_ID = "aws_six-layer-domain-storage-mover"
PACKAGE_ID = STORAGE_MOVER_PACKAGE_ID


def _build_graph_app(
    project_path: Path,
    *,
    source_name: str,
    output_name: str,
    package_id: str,
    runtime_root: Path,
) -> Dict[str, Path]:
    source = PROVIDERS_ROOT / "aws" / "lambda_functions" / source_name
    shared = PROVIDERS_ROOT / "aws" / "lambda_functions" / "_shared"
    bridge_core_source = runtime_root / "bridge_core.py"
    if (
        not source.is_dir()
        or source.is_symlink()
        or not shared.is_dir()
        or shared.is_symlink()
        or not bridge_core_source.is_file()
        or bridge_core_source.is_symlink()
    ):
        raise ValueError(f"Unavailable AWS {source_name} runtime source")
    output = Path(project_path) / ".build" / "aws" / output_name
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
        write_zip_file(archive, bridge_core_source, "bridge_core.py")
        for path in sorted(runtime_root.rglob("*")):
            if path.is_file() and _should_include_file(path):
                write_zip_file(
                    archive,
                    path,
                    Path("phase8_eventing") / path.relative_to(runtime_root),
                )
    return {package_id: output}


def build_aws_six_layer_domain_app(project_path: Path) -> Dict[str, Path]:
    """Build the standalone Six-layer domain runtime."""

    return _build_graph_app(
        project_path,
        source_name="six-layer-domain",
        output_name="six-layer-domain.zip",
        package_id=RUNTIME_PACKAGE_ID,
        runtime_root=BRIDGE_RUNTIME_ROOT,
    )


def build_aws_six_layer_storage_mover_context(project_path: Path) -> Dict[str, Path]:
    """Build the graph-selected AWS mover as an S3-compatible ZIP context."""

    source = (
        PROVIDERS_ROOT
        / "aws"
        / "lambda_functions"
        / "six-layer-domain"
        / "storage-mover"
    )
    if not source.is_dir() or source.is_symlink():
        raise ValueError("Unavailable AWS Six-layer storage-mover context")
    output = (
        Path(project_path)
        / ".build"
        / "aws"
        / "six-layer-domain-storage-mover.zip"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    with atomic_zip_archive(output) as archive:
        for path in sorted(source.rglob("*")):
            if path.is_file() and _should_include_file(path):
                write_zip_file(archive, path, path.relative_to(source))
    return {STORAGE_MOVER_PACKAGE_ID: output}


def build_aws_six_layer_bridge_context(project_path: Path) -> Dict[str, Path]:
    """Build the Six-layer source bridge with its profile-local runtime."""

    source = (
        PROVIDERS_ROOT / "aws" / "lambda_functions" / "six-layer-domain" / "bridge"
    )
    if (
        not source.is_dir()
        or source.is_symlink()
        or not BRIDGE_RUNTIME_ROOT.is_dir()
        or BRIDGE_RUNTIME_ROOT.is_symlink()
    ):
        raise ValueError("Unavailable AWS Six-layer bridge context")
    output = Path(project_path) / ".build" / "aws" / "six-layer-domain-bridge.zip"
    output.parent.mkdir(parents=True, exist_ok=True)
    with atomic_zip_archive(output) as archive:
        for path in sorted(source.rglob("*")):
            if path.is_file() and _should_include_file(path):
                write_zip_file(archive, path, path.relative_to(source))
        for path in sorted(BRIDGE_RUNTIME_ROOT.rglob("*")):
            if path.is_file() and _should_include_file(path):
                write_zip_file(
                    archive,
                    path,
                    Path("phase8_eventing")
                    / path.relative_to(BRIDGE_RUNTIME_ROOT),
                )
    return {BRIDGE_PACKAGE_ID: output}


__all__ = [
    "PACKAGE_ID",
    "BRIDGE_PACKAGE_ID",
    "RUNTIME_PACKAGE_ID",
    "STORAGE_MOVER_PACKAGE_ID",
    "build_aws_six_layer_domain_app",
    "build_aws_six_layer_bridge_context",
    "build_aws_six_layer_storage_mover_context",
]
