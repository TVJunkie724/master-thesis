"""Deployment-state metadata for user function packages.

Package builders record reproducible build evidence. This module advances that
evidence to deployed only after Terraform has successfully applied the package.
"""

from __future__ import annotations

import datetime
import json
import logging
from pathlib import Path

from src.core.deterministic_zip import atomic_write_bytes

logger = logging.getLogger(__name__)


def mark_built_packages_deployed(project_path: Path) -> int:
    """Mark current package hashes as deployed and return the updated count."""
    metadata_dir = project_path / ".build" / "metadata"
    if not metadata_dir.is_dir():
        return 0

    deployed_at = (
        datetime.datetime.now(datetime.timezone.utc)
        .isoformat()
        .replace("+00:00", "Z")
    )
    updated = 0
    for metadata_path in sorted(metadata_dir.glob("*.json")):
        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning(
                "Skipping invalid deployment metadata %s: %s",
                metadata_path.name,
                type(exc).__name__,
            )
            continue

        built_hash = metadata.get("zip_hash")
        if not isinstance(built_hash, str) or not built_hash:
            logger.warning(
                "Skipping deployment metadata without zip_hash: %s",
                metadata_path.name,
            )
            continue

        metadata["deployed_zip_hash"] = built_hash
        metadata["last_deployed"] = deployed_at
        payload = json.dumps(metadata, indent=2, sort_keys=True).encode("utf-8") + b"\n"
        atomic_write_bytes(metadata_path, payload)
        updated += 1

    return updated

