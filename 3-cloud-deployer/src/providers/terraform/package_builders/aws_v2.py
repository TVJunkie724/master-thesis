"""Deterministic CodeBuild context construction for AWS Five-layer v2."""

from __future__ import annotations

from pathlib import Path
from typing import Dict

from src.core.deterministic_zip import atomic_zip_archive, write_zip_file
from src.providers.terraform.package_builders.common import _should_include_file


PROVIDERS_ROOT = Path(__file__).resolve().parents[2]
PACKAGE_ID = "aws_five-layer-v2-storage-mover"


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
    return {PACKAGE_ID: output}


__all__ = ["PACKAGE_ID", "build_aws_v2_storage_mover_context"]
