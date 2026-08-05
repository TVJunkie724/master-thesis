"""Loader for the generated deployment specification contract."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator


SCHEMA_VERSION = "resolved-deployment-specification.v1"
V2_SCHEMA_VERSION = "resolved-deployment-specification.v2"
REGISTRY_VERSION = "resolved-deployment-dimensions.v1"
MANIFEST_VERSION = "3.0"
V4_MANIFEST_VERSION = "4.0"
HISTORICAL_MANIFEST_VERSION = "2.0"
PROVIDERS = ("aws", "azure", "gcp")
SLOT_ORDER = (
    "l1_ingestion",
    "l2_processing",
    "l3_hot_storage",
    "l3_cool_storage",
    "l3_archive_storage",
    "l4_twin_state",
    "l5_visualization",
)
CONTRACT_ROOT = (
    Path(__file__).resolve().parents[1]
    / "contracts"
    / "generated"
    / "resolved-deployment-specification"
    / "v1"
)
V2_CONTRACT_ROOT = CONTRACT_ROOT.parent / "v2"
MANIFEST_CONTRACT_ROOT = (
    Path(__file__).resolve().parents[1]
    / "contracts"
    / "generated"
    / "deployment-manifest"
    / "v3"
)
V4_MANIFEST_CONTRACT_ROOT = MANIFEST_CONTRACT_ROOT.parent / "v4"


@lru_cache(maxsize=1)
def load_contract() -> tuple[dict[str, Any], dict[str, Any]]:
    """Load and sanity-check the generated schema and semantic registry."""

    try:
        schema = json.loads((CONTRACT_ROOT / "schema.json").read_text("utf-8"))
        registry = json.loads(
            (CONTRACT_ROOT / "deployment-dimensions.json").read_text("utf-8")
        )
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError("Resolved deployment contract is unavailable") from exc

    Draft202012Validator.check_schema(schema)
    if registry.get("registry_version") != REGISTRY_VERSION:
        raise RuntimeError("Resolved deployment registry version is unsupported")
    if registry.get("specification_schema_version") != SCHEMA_VERSION:
        raise RuntimeError("Resolved deployment schema and registry versions differ")
    return schema, registry


@lru_cache(maxsize=1)
def load_v2_contract() -> tuple[dict[str, Any], dict[str, Any]]:
    """Load the additive generic component-selection contract."""

    try:
        schema = json.loads((V2_CONTRACT_ROOT / "schema.json").read_text("utf-8"))
        registry = json.loads(
            (V2_CONTRACT_ROOT / "component-capacity-registry.json").read_text(
                "utf-8"
            )
        )
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError("Resolved deployment v2 contract is unavailable") from exc

    Draft202012Validator.check_schema(schema)
    if schema.get("properties", {}).get("schema_version", {}).get("const") != (
        V2_SCHEMA_VERSION
    ):
        raise RuntimeError("Resolved deployment v2 schema version is unsupported")
    return schema, registry


@lru_cache(maxsize=2)
def load_manifest_schema(version: str = MANIFEST_VERSION) -> dict[str, Any]:
    """Load a synchronized current DeploymentManifest schema."""

    root = (
        MANIFEST_CONTRACT_ROOT
        if version == MANIFEST_VERSION
        else V4_MANIFEST_CONTRACT_ROOT
        if version == V4_MANIFEST_VERSION
        else None
    )
    if root is None:
        raise RuntimeError("DeploymentManifest contract version is unsupported")
    try:
        schema = json.loads((root / "schema.json").read_text("utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError("DeploymentManifest contract is unavailable") from exc
    Draft202012Validator.check_schema(schema)
    return schema
