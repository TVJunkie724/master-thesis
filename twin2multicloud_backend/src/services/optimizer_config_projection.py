"""Projection helpers for persisted optimizer configuration state."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from pydantic import ValidationError

from src.models.optimizer_config import OptimizerConfiguration
from src.schemas.optimizer_config import CheapestPathResponse, OptimizerConfigResponse
from src.schemas.pricing_catalog import PricingCatalogContext


CHEAPEST_PATH_FIELDS = (
    "cheapest_l1",
    "cheapest_l2",
    "cheapest_l3_hot",
    "cheapest_l3_cool",
    "cheapest_l3_archive",
    "cheapest_l4",
    "cheapest_l5",
)


def safe_json_loads(value: str | None) -> dict[str, Any] | None:
    """Decode a persisted JSON object, returning None for empty or invalid values."""
    if not value:
        return None
    try:
        decoded = json.loads(value)
    except json.JSONDecodeError:
        return None
    return decoded if isinstance(decoded, dict) else None


def to_json(value: dict[str, Any] | None) -> str | None:
    """Encode optional JSON object state for persistence."""
    if value is None:
        return None
    return json.dumps(value)


def optimizer_config_to_response(config: OptimizerConfiguration) -> OptimizerConfigResponse:
    """Map an optimizer configuration model to the public API schema."""
    pricing_catalog_context = None
    raw_context = safe_json_loads(config.pricing_catalog_context_json)
    if raw_context is not None:
        try:
            pricing_catalog_context = PricingCatalogContext.model_validate(raw_context)
        except ValidationError:
            pricing_catalog_context = None
    return OptimizerConfigResponse(
        id=config.id,
        twin_id=config.twin_id,
        params=safe_json_loads(config.params),
        result=safe_json_loads(config.result_json),
        pricing_catalog_context=pricing_catalog_context,
        cheapest_path=_cheapest_path_response(config) if config.cheapest_l1 else None,
        calculated_at=config.calculated_at,
        updated_at=config.updated_at or datetime.now(timezone.utc),
    )


def cheapest_path_dict(config: OptimizerConfiguration) -> dict[str, str | None]:
    """Return the cheapest-path columns as the deployment-facing response dict."""
    return {
        "l1": config.cheapest_l1,
        "l2": config.cheapest_l2,
        "l3_hot": config.cheapest_l3_hot,
        "l3_cool": config.cheapest_l3_cool,
        "l3_archive": config.cheapest_l3_archive,
        "l4": config.cheapest_l4,
        "l5": config.cheapest_l5,
    }


def set_cheapest_columns_from_payload(
    config: OptimizerConfiguration,
    *,
    cheapest_path: dict[str, Any] | None = None,
    optimizer_result: dict[str, Any] | None = None,
) -> None:
    """Populate cheapest_l* columns from explicit path data and optimizer result fallbacks."""
    explicit = cheapest_path or {}
    derived = _derive_cheapest_path(optimizer_result)

    config.cheapest_l1 = _normalize_provider(explicit.get("l1")) or derived.get("l1")
    config.cheapest_l2 = _normalize_provider(explicit.get("l2")) or derived.get("l2")
    config.cheapest_l3_hot = _normalize_provider(explicit.get("l3_hot")) or derived.get("l3_hot")
    config.cheapest_l3_cool = _normalize_provider(explicit.get("l3_cool")) or derived.get("l3_cool")
    config.cheapest_l3_archive = _normalize_provider(explicit.get("l3_archive")) or derived.get("l3_archive")
    config.cheapest_l4 = _normalize_provider(explicit.get("l4")) or derived.get("l4")
    config.cheapest_l5 = _normalize_provider(explicit.get("l5")) or derived.get("l5")


def _cheapest_path_response(config: OptimizerConfiguration) -> CheapestPathResponse:
    return CheapestPathResponse(**cheapest_path_dict(config))


def _derive_cheapest_path(optimizer_result: dict[str, Any] | None) -> dict[str, str | None]:
    if not optimizer_result or not isinstance(optimizer_result, dict):
        return {}

    def from_path(prefix: str) -> str | None:
        path = optimizer_result.get("cheapestPath")
        if not isinstance(path, list):
            return None
        for segment in path:
            if isinstance(segment, str) and segment.startswith(prefix):
                return _normalize_provider(segment[len(prefix):])
        return None

    def from_calc(*keys: str) -> str | None:
        node: Any = optimizer_result.get("calculationResult")
        for key in keys:
            if not isinstance(node, dict):
                return None
            node = node.get(key)
        return _normalize_provider(node)

    return {
        "l1": from_path("L1_") or from_calc("L1"),
        "l2": from_path("L2_") or from_calc("L2"),
        "l3_hot": from_path("L3_hot_") or from_calc("L3", "Hot"),
        "l3_cool": from_path("L3_cool_") or from_calc("L3", "Cool"),
        "l3_archive": from_path("L3_archive_") or from_calc("L3", "Archive"),
        "l4": from_path("L4_") or from_calc("L4"),
        "l5": from_path("L5_") or from_calc("L5"),
    }


def _normalize_provider(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped.lower() if stripped else None
