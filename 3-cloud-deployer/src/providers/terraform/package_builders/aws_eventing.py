"""Deterministic AWS Six-layer Eventing Lambda package."""

from __future__ import annotations

from pathlib import Path
from typing import Dict

from src.core.deterministic_zip import atomic_zip_archive, write_zip_file
from src.providers.terraform.package_builders.common import _should_include_file


PROVIDERS_ROOT = Path(__file__).resolve().parents[2]
RUNTIME_ROOT = PROVIDERS_ROOT.parent / "runtime" / "eventing"
SOURCE_ROOT = (
    PROVIDERS_ROOT / "aws" / "lambda_functions" / "six-layer-eventing"
)
PACKAGE_ID = "aws_six-layer-eventing"


def build_aws_eventing_app(project_path: Path) -> Dict[str, Path]:
    """Build the provider adapter with its immutable shared bridge dependency."""

    if (
        not SOURCE_ROOT.is_dir()
        or SOURCE_ROOT.is_symlink()
        or not RUNTIME_ROOT.is_dir()
        or RUNTIME_ROOT.is_symlink()
    ):
        raise ValueError("Unavailable AWS Six-layer Eventing runtime source")
    output = Path(project_path) / ".build" / "aws" / "six-layer-eventing.zip"
    output.parent.mkdir(parents=True, exist_ok=True)
    with atomic_zip_archive(output) as archive:
        for path in sorted(SOURCE_ROOT.rglob("*")):
            if path.is_file() and _should_include_file(path):
                write_zip_file(archive, path, path.relative_to(SOURCE_ROOT))
        for path in sorted(RUNTIME_ROOT.rglob("*")):
            if path.is_file() and _should_include_file(path):
                write_zip_file(
                    archive,
                    path,
                    Path("phase8_eventing") / path.relative_to(RUNTIME_ROOT),
                )
    return {PACKAGE_ID: output}


__all__ = ["PACKAGE_ID", "build_aws_eventing_app"]
