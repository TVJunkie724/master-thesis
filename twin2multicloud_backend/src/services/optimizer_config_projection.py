"""Projection helpers for persisted optimizer configuration state."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from pydantic import ValidationError

from src.models.optimizer_config import OptimizerConfiguration
from src.schemas.optimizer_config import OptimizerConfigResponse
from src.schemas.pricing_catalog import PricingCatalogContext


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


def optimizer_config_to_response(
    config: OptimizerConfiguration,
) -> OptimizerConfigResponse:
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
        cheapest_path=None,
        calculated_at=config.calculated_at,
        updated_at=config.updated_at or datetime.now(timezone.utc),
    )
