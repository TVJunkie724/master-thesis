"""Read-only user-function build and deployment metadata status."""

from __future__ import annotations

import json
from typing import Any

from logger import logger
from src.core.observability import redact_sensitive
from src.core.paths import resolve_project_context_path


def check_code_hashes(project_name: str) -> dict[str, Any]:
    """Report deployed only when current build and deployed hashes agree."""
    project_path = resolve_project_context_path(project_name)
    metadata_dir = project_path / ".build" / "metadata"
    if not metadata_dir.is_dir():
        return {"status": "no_deployments", "functions": {}}
    try:
        metadata_dir.resolve().relative_to(project_path.resolve())
    except (OSError, ValueError):
        logger.warning("Ignoring metadata directory outside project boundary")
        return {"status": "no_deployments", "functions": {}}

    functions = {}
    for metadata_path in sorted(metadata_dir.glob("*.json")):
        if metadata_path.is_symlink() or not metadata_path.is_file():
            continue
        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            if not isinstance(metadata, dict):
                raise ValueError("metadata root must be an object")
            function_name = metadata.get("function") or metadata_path.stem
            if not isinstance(function_name, str) or not function_name:
                raise ValueError("function name must be a non-empty string")
            built_hash = metadata.get("zip_hash")
            deployed_hash = metadata.get("deployed_zip_hash")
            deployed = bool(
                metadata.get("last_deployed")
                and isinstance(built_hash, str)
                and built_hash
                and deployed_hash == built_hash
            )
            function_key = function_name
            if function_key in functions:
                provider = metadata.get("provider") or metadata_path.stem
                function_key = f"{function_name}@{provider}"
            functions[function_key] = {
                "deployed": deployed,
                "state": "deployed" if deployed else "built",
                "provider": metadata.get("provider"),
                "hash": built_hash,
                "last_updated": (
                    metadata.get("last_deployed")
                    if deployed
                    else metadata.get("last_built")
                ),
            }
        except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
            logger.warning(
                "Failed to read hash metadata %s: %s",
                metadata_path.name,
                redact_sensitive(exc),
            )

    deployed_count = sum(
        1 for function in functions.values() if function["deployed"]
    )
    if not functions:
        status = "no_deployments"
    elif deployed_count == len(functions):
        status = "deployed"
    elif deployed_count:
        status = "partial"
    else:
        status = "built"
    return {"status": status, "functions": functions}
