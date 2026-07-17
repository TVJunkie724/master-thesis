"""Resolve owner-safe immutable pricing catalogs for Optimizer calculations."""

from __future__ import annotations

from collections.abc import Iterator
import json
from datetime import datetime, timedelta, timezone
from typing import Any, cast

from pydantic import ValidationError
from sqlalchemy.orm import Session

from src.clients.optimizer_client import OptimizerClient
from src.models.pricing_refresh_run import PricingRefreshRun
from src.schemas.pricing_catalog import (
    PricingCatalogContext,
    PricingCatalogReference,
    Provider,
)
from src.services.errors import (
    ExternalServiceError,
    OptimizerContractError,
    PricingCatalogUnavailable,
)


PROVIDERS: tuple[Provider, ...] = ("aws", "azure", "gcp")


class PricingCatalogContextService:
    """Build and verify exact three-provider contexts without loading pricing."""

    def __init__(
        self,
        db: Session,
        optimizer_client: OptimizerClient | None = None,
        *,
        now: datetime | None = None,
    ) -> None:
        self._db = db
        self._optimizer_client = optimizer_client or OptimizerClient()
        self._now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)

    async def resolve_for_user(self, user_id: str) -> PricingCatalogContext:
        catalogs = {
            provider: await self._resolve_provider_reference(user_id, provider)
            for provider in PROVIDERS
        }
        return PricingCatalogContext(
            schema_version="provider-pricing-catalog-context.v1",
            catalogs=catalogs,
        )

    async def verify_context(
        self,
        context: PricingCatalogContext,
    ) -> PricingCatalogContext:
        verified: dict[Provider, PricingCatalogReference] = {}
        for provider, reference in context.catalogs.items():
            try:
                exact = await self._verify_reference(reference)
            except ExternalServiceError as exc:
                if exc.upstream_status_code != 404:
                    raise
                raise PricingCatalogUnavailable(
                    f"The stored {provider.upper()} pricing catalog no longer exists.",
                    error_code="PRICING_CATALOG_NOT_FOUND",
                ) from exc
            if exact is None:
                raise PricingCatalogUnavailable(
                    f"The stored {provider.upper()} pricing catalog is stale.",
                    error_code="PRICING_CATALOG_STALE",
                )
            verified[provider] = exact
        return PricingCatalogContext(
            schema_version="provider-pricing-catalog-context.v1",
            catalogs=verified,
        )

    async def status_for_user(
        self,
        user_id: str,
    ) -> dict[Provider, dict[str, Any]]:
        """Project the exact references selected by the calculation resolver."""

        statuses: dict[Provider, dict[str, Any]] = {}
        for provider in PROVIDERS:
            try:
                reference = await self._resolve_provider_reference(
                    user_id,
                    provider,
                )
            except PricingCatalogUnavailable as exc:
                statuses[provider] = await self._unavailable_status(
                    provider,
                    exc,
                )
                continue
            statuses[provider] = self._available_status(reference)
        return statuses

    async def _resolve_provider_reference(
        self,
        user_id: str,
        provider: Provider,
    ) -> PricingCatalogReference:
        for reference in self._owner_references(user_id, provider):
            verified = await self._verify_reference(reference, missing_is_unusable=True)
            if verified is not None:
                return verified

        baseline = await self._baseline_reference(provider)
        try:
            verified_baseline = await self._verify_reference(baseline)
        except ExternalServiceError as exc:
            if exc.upstream_status_code != 404:
                raise
            raise PricingCatalogUnavailable(
                f"No published {provider.upper()} pricing catalog is available.",
                error_code="PRICING_CATALOG_NOT_FOUND",
            ) from exc
        if verified_baseline is None:
            raise PricingCatalogUnavailable(
                f"No fresh reviewed {provider.upper()} pricing catalog is available.",
                error_code="PRICING_CATALOG_STALE",
            )
        return verified_baseline

    def _owner_references(
        self,
        user_id: str,
        provider: Provider,
    ) -> Iterator[PricingCatalogReference]:
        runs = (
            self._db.query(PricingRefreshRun)
            .filter(
                PricingRefreshRun.user_id == user_id,
                PricingRefreshRun.provider == provider,
                PricingRefreshRun.status == "succeeded",
            )
            .order_by(
                PricingRefreshRun.completed_at.desc(),
                PricingRefreshRun.created_at.desc(),
                PricingRefreshRun.id.desc(),
            )
            .all()
        )
        for run in runs:
            payload = _json_object(run.result_summary_json)
            raw_reference = payload.get("activeCalculationReference")
            try:
                reference = PricingCatalogReference.model_validate(raw_reference)
            except ValidationError:
                continue
            if reference.provider == provider:
                yield reference

    async def _baseline_reference(
        self,
        provider: Provider,
    ) -> PricingCatalogReference:
        payload = await self._optimizer_client.get_pricing_catalog_baseline(provider)
        try:
            reference = PricingCatalogReference.model_validate(payload)
        except ValidationError as exc:
            raise OptimizerContractError(
                "Optimizer baseline pricing reference is invalid.",
                [
                    {
                        "field": f"pricingCatalogs.catalogs.{provider}",
                        "message": "Invalid baseline reference",
                    }
                ],
            ) from exc
        if reference.provider != provider:
            raise OptimizerContractError(
                "Optimizer baseline pricing reference has the wrong provider."
            )
        return reference

    async def _verify_reference(
        self,
        reference: PricingCatalogReference,
        *,
        missing_is_unusable: bool = False,
    ) -> PricingCatalogReference | None:
        try:
            payload = (
                await self._optimizer_client.get_exact_pricing_catalog_reference(
                    reference.provider,
                    reference.pricing_region,
                    reference.snapshot_id,
                )
            )
        except ExternalServiceError as exc:
            if missing_is_unusable and exc.upstream_status_code == 404:
                return None
            raise

        try:
            verified = PricingCatalogReference.model_validate(
                payload.get("reference")
            )
        except ValidationError as exc:
            raise OptimizerContractError(
                "Optimizer exact pricing reference is invalid."
            ) from exc
        if verified != reference:
            if missing_is_unusable:
                return None
            raise OptimizerContractError(
                "Optimizer exact pricing reference does not match the requested identity."
            )
        if payload.get("isFresh") is not True:
            return None
        return verified

    def _available_status(
        self,
        reference: PricingCatalogReference,
    ) -> dict[str, Any]:
        return {
            "age": _format_age(self._now - reference.fetched_at),
            "status": "valid",
            "missing_keys": [],
            "is_fresh": True,
            "threshold_days": 7,
            "active_reference": reference.to_http_dict(),
        }

    async def _unavailable_status(
        self,
        provider: Provider,
        error: PricingCatalogUnavailable,
    ) -> dict[str, Any]:
        if error.error_code == "PRICING_CATALOG_STALE":
            reference = await self._baseline_reference(provider)
            return {
                "age": _format_age(self._now - reference.fetched_at),
                "status": "valid",
                "missing_keys": [],
                "is_fresh": False,
                "threshold_days": 7,
                "active_reference": reference.to_http_dict(),
                "error_code": error.error_code,
            }
        return {
            "age": "missing",
            "status": "missing",
            "missing_keys": [],
            "is_fresh": False,
            "threshold_days": 7,
            "active_reference": None,
            "error_code": error.error_code,
        }


def parse_pricing_catalog_context(value: Any) -> PricingCatalogContext:
    """Validate a persisted or downstream three-provider context."""

    try:
        return PricingCatalogContext.model_validate(value)
    except ValidationError as exc:
        raise OptimizerContractError(
            "Optimizer pricing catalog context is invalid.",
            [{"field": "pricingCatalogs", "message": "Invalid exact reference set"}],
        ) from exc


def pricing_catalog_contexts_match(
    expected: PricingCatalogContext,
    actual: Any,
) -> bool:
    try:
        parsed = PricingCatalogContext.model_validate(actual)
    except ValidationError:
        return False
    return parsed == expected


def _json_object(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if not value or not isinstance(value, str):
        return {}
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return {}
    return cast(dict[str, Any], parsed) if isinstance(parsed, dict) else {}


def _format_age(delta: timedelta) -> str:
    total_seconds = max(0, int(delta.total_seconds()))
    if total_seconds < 3600:
        return f"{total_seconds // 60} minutes"
    if total_seconds < 86400:
        return f"{total_seconds // 3600} hours"
    return f"{total_seconds // 86400} days"
