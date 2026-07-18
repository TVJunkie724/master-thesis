"""Authenticated, exact pricing-catalog diagnostics."""

from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError as PydanticValidationError

from src.clients.optimizer_client import OptimizerClient
from src.schemas.pricing_catalog import PricingCatalogReference
from src.services.errors import ExternalServiceError, ExternalServiceUnavailable
from src.services.external_service_mapping import map_optimizer_client_error
from src.services.service_errors import ValidationError


_REGION_PATTERN = re.compile(r"^[a-z][a-z0-9-]{1,62}$")
_AWS_REGION_PATTERN = re.compile(r"^[a-z]{2}(?:-gov)?-[a-z0-9-]+-\d+$")
_SNAPSHOT_ID_PATTERN = re.compile(r"^pcs_[0-9a-f]{64}$")


class _ExactCatalogIdentity(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: Literal["aws", "azure", "gcp"]
    pricing_region: str = Field(pattern=_REGION_PATTERN.pattern)
    snapshot_id: str = Field(pattern=_SNAPSHOT_ID_PATTERN.pattern)


class OptimizerPricingCatalogService:
    """Own the bounded proxy for one immutable catalog identity."""

    def __init__(self, optimizer_client: OptimizerClient | None = None):
        self._optimizer_client = optimizer_client or OptimizerClient()

    async def get_exact_snapshot(
        self,
        provider: str,
        pricing_region: str,
        snapshot_id: str,
    ) -> dict[str, Any]:
        identity = self._validate_identity(provider, pricing_region, snapshot_id)
        try:
            payload = await self._optimizer_client.get_exact_pricing_catalog_snapshot(
                identity.provider,
                identity.pricing_region,
                identity.snapshot_id,
            )
        except (ExternalServiceError, ExternalServiceUnavailable) as exc:
            raise map_optimizer_client_error(exc) from exc

        reference = self._validate_response(payload)
        if (
            reference.provider != identity.provider
            or reference.pricing_region != identity.pricing_region
            or reference.snapshot_id != identity.snapshot_id
        ):
            raise ValidationError(
                "Optimizer returned a different pricing catalog identity."
            )
        return payload

    @staticmethod
    def _validate_identity(
        provider: str,
        pricing_region: str,
        snapshot_id: str,
    ) -> _ExactCatalogIdentity:
        try:
            identity = _ExactCatalogIdentity.model_validate(
                {
                    "provider": provider.strip().lower(),
                    "pricing_region": pricing_region.strip().lower(),
                    "snapshot_id": snapshot_id.strip(),
                }
            )
        except (AttributeError, PydanticValidationError) as exc:
            raise ValidationError("Invalid pricing catalog identity.") from exc
        if (
            identity.provider == "aws"
            and not _AWS_REGION_PATTERN.fullmatch(identity.pricing_region)
        ):
            raise ValidationError("Invalid AWS pricing region.")
        return identity

    @staticmethod
    def _validate_response(payload: dict[str, Any]) -> PricingCatalogReference:
        pricing = payload.get("pricing")
        if not isinstance(pricing, dict):
            raise ValidationError(
                "Optimizer pricing catalog response is missing pricing data."
            )
        try:
            return PricingCatalogReference.model_validate(payload.get("reference"))
        except PydanticValidationError as exc:
            raise ValidationError(
                "Optimizer pricing catalog response has an invalid reference."
            ) from exc
