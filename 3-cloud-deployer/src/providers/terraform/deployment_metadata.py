"""Deployment-state metadata for user function packages.

Package builders record reproducible build evidence. This module advances that
evidence to deployed only after Terraform has successfully applied the package.
"""

from __future__ import annotations

import logging
from pathlib import Path

from src.function_metadata import load_function_metadata, mark_function_deployed

logger = logging.getLogger(__name__)


def mark_built_packages_deployed(project_path: Path) -> int:
    """Mark current package hashes as deployed and return the updated count."""
    metadata_dir = project_path / ".build" / "metadata"
    if not metadata_dir.is_dir():
        return 0

    updated = 0
    for metadata_path in sorted(metadata_dir.glob("*.json")):
        metadata = load_function_metadata(metadata_path)
        if metadata is None:
            logger.warning(
                "Skipping invalid deployment metadata %s",
                metadata_path.name,
            )
            continue
        if mark_function_deployed(
            metadata_path,
            expected_artifact_hash=metadata["artifact_hash"],
        ):
            updated += 1

    return updated
