"""Loader for the generated deployment specification contract."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator


SCHEMA_VERSION = "resolved-deployment-specification.v1"
REGISTRY_VERSION = "resolved-deployment-dimensions.v1"
MANIFEST_VERSION = "2.0"
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
