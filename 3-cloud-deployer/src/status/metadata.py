"""Read-only user-function build and deployment metadata status."""

from __future__ import annotations

from typing import Any
from pathlib import Path

from logger import logger
from src.core.paths import resolve_project_context_path
from src.function_metadata import load_function_metadata


def check_function_artifacts(
    project_name: str,
    project_path: Path | None = None,
) -> dict[str, Any]:
    """Report deployed only when current build and deployed hashes agree."""
    project_path = project_path or resolve_project_context_path(project_name)
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
        metadata = load_function_metadata(metadata_path)
        if metadata is None:
            logger.warning(
                "Ignoring invalid function metadata %s",
                metadata_path.name,
            )
            continue
        function_name = metadata["function"]
        artifact_hash = metadata["artifact_hash"]
        deployed = bool(
            metadata.get("last_deployed")
            and metadata.get("deployed_artifact_hash") == artifact_hash
        )
        function_key = function_name
        if function_key in functions:
            function_key = f"{function_name}@{metadata['provider']}"
        functions[function_key] = {
            "deployed": deployed,
            "state": "deployed" if deployed else "built",
            "provider": metadata["provider"],
            "hash": artifact_hash,
            "source_hash": metadata["source_hash"],
            "last_updated": (
                metadata.get("last_deployed") if deployed else metadata["last_built"]
            ),
        }

    deployed_count = sum(1 for function in functions.values() if function["deployed"])
    if not functions:
        status = "no_deployments"
    elif deployed_count == len(functions):
        status = "deployed"
    elif deployed_count:
        status = "partial"
    else:
        status = "built"
    return {"status": status, "functions": functions}
