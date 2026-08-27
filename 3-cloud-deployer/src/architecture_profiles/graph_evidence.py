"""Secret-free graph digest and evidence projection."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from .graph_models import ResolvedDeploymentGraph


def canonical_json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def content_digest(value: object) -> str:
    return f"sha256:{hashlib.sha256(canonical_json(value).encode()).hexdigest()}"


def graph_evidence(graph: ResolvedDeploymentGraph) -> dict[str, Any]:
    """Return bounded operation evidence without graph values or source."""

    selected_artifacts: dict[str, dict[str, str]] = {}
    extension_artifacts: dict[tuple[str, str], dict[str, str]] = {}
    for node in graph.nodes:
        for artifact in node.package_artifacts:
            selected_artifacts[str(artifact["id"])] = {
                "id": str(artifact["id"]),
                "version": str(artifact["version"]),
                "source_digest": str(artifact["source_digest"]),
                "builder_adapter_id": str(artifact["builder_adapter_id"]),
            }
        for extension in node.extension_artifact_refs:
            identity = (
                str(extension["slot_id"]),
                str(extension["slot_version"]),
            )
            extension_artifacts[identity] = {
                "slot_id": identity[0],
                "slot_version": identity[1],
                "artifact_id": str(extension["artifact_id"]),
                "artifact_digest": str(extension["artifact_digest"]),
            }
    package_selection_digest = content_digest(
        {
            "artifacts": [
                selected_artifacts[key] for key in sorted(selected_artifacts)
            ],
            "extensions": [
                extension_artifacts[key] for key in sorted(extension_artifacts)
            ],
        }
    )
    return {
        "graph_schema_version": graph.graph_schema_version,
        "graph_id": graph.graph_id,
        "calculation_run_id": graph.calculation_run_id,
        "graph_digest": graph.content_digest,
        "architecture_digest": graph.architecture_ref["digest"],
        "profile_id": graph.profile_ref["id"],
        "profile_version": graph.profile_ref["version"],
        "catalog_id": graph.catalog_ref["id"],
        "catalog_version": graph.catalog_ref["version"],
        "catalog_digest": graph.catalog_ref["digest"],
        "specification_digest": graph.specification_ref["digest"],
        "package_selection_digest": package_selection_digest,
        "requirements_digest": graph.requirements_digest,
        "node_count": len(graph.nodes),
        "edge_count": len(graph.edges),
        "binding_count": len(graph.bindings),
        "requirement_count": len(graph.requirements),
        "requirement_types": sorted(
            {requirement.requirement_type for requirement in graph.requirements}
        ),
        "required_providers": sorted(
            {requirement.provider for requirement in graph.requirements}
        ),
        "stage_ids": [stage.stage_id for stage in graph.stages],
    }
