"""Resolve trusted, user-scoped AWS IoT TwinMaker pricing-plan context."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import json
import re
from typing import Annotated, Any, Literal

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    model_validator,
)
from sqlalchemy.orm import Session

from src.clients.optimizer_client import OptimizerClient
from src.models.cloud_connection import CloudConnection
from src.models.pricing_refresh_run import PricingRefreshRun
from src.repositories.cloud_connection_repository import CloudConnectionRepository


ACCOUNT_CONTEXT_KEY = "__account_pricing_context__"
ACCOUNT_CONTEXT_SCHEMA_VERSION = "aws-twinmaker-account-pricing-context.v1"
MANAGEMENT_BINDING_SCHEMA_VERSION = "aws-twinmaker-management-binding.v1"
MAX_OBSERVATION_AGE = timedelta(days=7)
AWS_REGION_PATTERN = re.compile(r"^[a-z]{2}(?:-gov)?-[a-z0-9-]+-\d+$")
SHA256_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")
ACCOUNT_ID_PATTERN = re.compile(r"^\d{12}$")
OPTIMIZER_CONTEXT_COMPARABLE_FIELDS = (
    "sourceRefreshRunId",
    "connectionFingerprint",
    "providerAccountId",
    "pricingRegion",
    "catalogSnapshotDigest",
    "observedAt",
    "currentPlan",
    "pendingPlan",
)

PLAN_UNOBSERVED = "AWS_TWINMAKER_PLAN_UNOBSERVED"
PLAN_STALE = "AWS_TWINMAKER_PLAN_STALE"
PLAN_CONNECTION_CHANGED = "AWS_TWINMAKER_PLAN_CONNECTION_CHANGED"
PLAN_ACCOUNT_MISMATCH = "AWS_TWINMAKER_PLAN_ACCOUNT_MISMATCH"
PLAN_RESPONSE_INVALID = "AWS_TWINMAKER_PLAN_RESPONSE_INVALID"
CATALOG_REGION_MISMATCH = "AWS_TWINMAKER_CATALOG_REGION_MISMATCH"
CATALOG_DIGEST_MISMATCH = "AWS_TWINMAKER_CATALOG_DIGEST_MISMATCH"

BundleName = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=128),
]


class _Bundle(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tier: Literal["TIER_1", "TIER_2", "TIER_3", "TIER_4"]
    names: list[BundleName] = Field(default_factory=list, max_length=20)


class _Plan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: Literal["BASIC", "STANDARD", "TIERED_BUNDLE"]
    billable_entity_count: int = Field(ge=0)
    effective_at: AwareDatetime | None = None
    updated_at: AwareDatetime | None = None
    update_reason: str | None = Field(default=None, max_length=500)
    bundle: _Bundle | None = None

    @model_validator(mode="after")
    def validate_bundle_contract(self) -> "_Plan":
        if self.mode == "TIERED_BUNDLE" and self.bundle is None:
            raise ValueError("Tiered Bundle plan requires bundle metadata.")
        if self.mode != "TIERED_BUNDLE" and self.bundle is not None:
            raise ValueError("Only Tiered Bundle plans may contain bundle metadata.")
        return self


class _ObservedAccountContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["aws-twinmaker-account-pricing-context.v1"]
    provider: Literal["aws"]
    service: Literal["iot_twinmaker"]
    region: str = Field(pattern=AWS_REGION_PATTERN.pattern)
    verified_account_id: str = Field(pattern=ACCOUNT_ID_PATTERN.pattern)
    catalog_snapshot_digest: str = Field(pattern=SHA256_PATTERN.pattern)
    observed_at: AwareDatetime
    current_plan: _Plan
    pending_plan: _Plan | None = None


class _ManagementBinding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["aws-twinmaker-management-binding.v1"]
    pricing_connection_id: str = Field(min_length=1, max_length=128)
    connection_fingerprint: str = Field(pattern=SHA256_PATTERN.pattern)
    verified_account_id: str = Field(pattern=ACCOUNT_ID_PATTERN.pattern)
    configured_account_id: str | None = Field(
        default=None,
        pattern=ACCOUNT_ID_PATTERN.pattern,
    )


class _PersistedAccountContext(_ObservedAccountContext):
    management_binding: _ManagementBinding


@dataclass(frozen=True, slots=True)
class ResolvedAwsTwinMakerPricingContext:
    """Internal Optimizer context plus its authoritative refresh-run reference."""

    payload: dict[str, Any]
    source_refresh_run_id: str | None

    @property
    def available(self) -> bool:
        return self.payload.get("status") == "available"


class AwsTwinMakerPricingContextService:
    """Bind and resolve account evidence without exposing cloud credentials."""

    def __init__(
        self,
        db: Session,
        optimizer_client: OptimizerClient | None = None,
        *,
        now: datetime | None = None,
    ):
        self._db = db
        self._optimizer_client = optimizer_client or OptimizerClient()
        self._connections = CloudConnectionRepository(db)
        self._now = _as_utc(now or datetime.now(timezone.utc))

    def bind_refresh_result(
        self,
        connection: CloudConnection,
        result: dict[str, Any],
    ) -> dict[str, Any]:
        """Validate Optimizer account evidence and add the Management binding."""

        if connection.provider != "aws" or connection.purpose != "pricing":
            raise ValueError("AWS pricing CloudConnection is required.")
        raw_context = result.get(ACCOUNT_CONTEXT_KEY)
        observed = _ObservedAccountContext.model_validate(raw_context)
        scope = _cloud_scope(connection)
        configured_account_id = _configured_account_id(scope)
        configured_region = _configured_region(scope)
        if configured_account_id and (
            configured_account_id != observed.verified_account_id
        ):
            raise ValueError(PLAN_ACCOUNT_MISMATCH)
        if configured_region != observed.region:
            raise ValueError(CATALOG_REGION_MISMATCH)

        binding = _ManagementBinding(
            schema_version=MANAGEMENT_BINDING_SCHEMA_VERSION,
            pricing_connection_id=connection.id,
            connection_fingerprint=_normalized_fingerprint(
                connection.payload_fingerprint
            ),
            verified_account_id=observed.verified_account_id,
            configured_account_id=configured_account_id,
        )
        persisted = _PersistedAccountContext(
            **observed.model_dump(),
            management_binding=binding,
        )
        bound_result = deepcopy(result)
        bound_result[ACCOUNT_CONTEXT_KEY] = persisted.model_dump(
            mode="json",
            exclude_none=False,
        )
        return bound_result

    async def resolve(
        self,
        user_id: str,
    ) -> ResolvedAwsTwinMakerPricingContext:
        """Resolve the latest trusted context for the user's current AWS default."""

        connection = self._connections.get_default_pricing(user_id, "aws")
        if connection is None:
            return _unavailable(PLAN_UNOBSERVED)
        if (
            connection.validation_status != "valid"
            or connection.provider != "aws"
            or connection.purpose != "pricing"
        ):
            return _unavailable(PLAN_CONNECTION_CHANGED)

        run = (
            self._db.query(PricingRefreshRun)
            .filter(
                PricingRefreshRun.user_id == user_id,
                PricingRefreshRun.provider == "aws",
                PricingRefreshRun.pricing_connection_id == connection.id,
                PricingRefreshRun.status == "succeeded",
            )
            .order_by(
                PricingRefreshRun.completed_at.desc(),
                PricingRefreshRun.created_at.desc(),
                PricingRefreshRun.id.desc(),
            )
            .first()
        )
        if run is None:
            return _unavailable(PLAN_UNOBSERVED)

        result = _json_object(run.result_summary_json)
        try:
            context = _PersistedAccountContext.model_validate(
                result.get(ACCOUNT_CONTEXT_KEY)
            )
        except (TypeError, ValueError):
            return _unavailable(PLAN_RESPONSE_INVALID)

        binding = context.management_binding
        try:
            current_fingerprint = _normalized_fingerprint(
                connection.payload_fingerprint
            )
        except ValueError:
            return _unavailable(PLAN_CONNECTION_CHANGED)
        if (
            binding.pricing_connection_id != connection.id
            or binding.connection_fingerprint != current_fingerprint
        ):
            return _unavailable(PLAN_CONNECTION_CHANGED)

        scope = _cloud_scope(connection)
        try:
            configured_account_id = _configured_account_id(scope)
            configured_region = _configured_region(scope)
        except ValueError:
            return _unavailable(PLAN_CONNECTION_CHANGED)
        if (
            binding.verified_account_id != context.verified_account_id
            or binding.configured_account_id != configured_account_id
            or (
                configured_account_id
                and configured_account_id != context.verified_account_id
            )
        ):
            return _unavailable(PLAN_ACCOUNT_MISMATCH)
        if configured_region != context.region:
            return _unavailable(CATALOG_REGION_MISMATCH)

        observed_at = _as_utc(context.observed_at)
        if observed_at > self._now or self._now - observed_at > MAX_OBSERVATION_AGE:
            return _unavailable(PLAN_STALE)

        catalog = await self._optimizer_client.export_pricing_snapshot("aws")
        try:
            catalog_error = _catalog_mismatch_reason(catalog, context)
        except (TypeError, ValueError):
            catalog_error = CATALOG_DIGEST_MISMATCH
        if catalog_error:
            return _unavailable(catalog_error)

        return ResolvedAwsTwinMakerPricingContext(
            payload={
                "schemaVersion": ACCOUNT_CONTEXT_SCHEMA_VERSION,
                "status": "available",
                "sourceRefreshRunId": run.id,
                "connectionFingerprint": current_fingerprint,
                "providerAccountId": context.verified_account_id,
                "pricingRegion": context.region,
                "catalogSnapshotDigest": context.catalog_snapshot_digest,
                "observedAt": _iso_utc(observed_at),
                "currentPlan": _optimizer_plan(context.current_plan),
                "pendingPlan": (
                    _optimizer_plan(context.pending_plan)
                    if context.pending_plan is not None
                    else None
                ),
            },
            source_refresh_run_id=run.id,
        )


def optimizer_aws_l4_selection_matches_context(
    result: dict[str, Any],
    expected: ResolvedAwsTwinMakerPricingContext,
) -> bool:
    """Verify an AWS L4 choice against the exact Management-injected context."""

    calculation_result = result.get("calculationResult")
    selected = (
        calculation_result.get("L4")
        if isinstance(calculation_result, dict)
        else None
    )
    if not isinstance(selected, str) or selected.strip().lower() != "aws":
        return True
    provider_contexts = result.get("providerPricingContexts")
    actual = (
        provider_contexts.get("awsTwinMaker")
        if isinstance(provider_contexts, dict)
        else None
    )
    return bool(
        expected.available
        and isinstance(actual, dict)
        and actual.get("status") == "compatible"
        and all(
            actual.get(field) == expected.payload.get(field)
            for field in OPTIMIZER_CONTEXT_COMPARABLE_FIELDS
        )
    )


def _optimizer_plan(plan: _Plan) -> dict[str, Any]:
    return {
        "mode": plan.mode,
        "billableEntityCount": plan.billable_entity_count,
        "effectiveAt": _iso_utc(plan.effective_at) if plan.effective_at else None,
        "updatedAt": _iso_utc(plan.updated_at) if plan.updated_at else None,
        "updateReason": plan.update_reason,
        "bundle": (
            {"tier": plan.bundle.tier, "names": list(plan.bundle.names)}
            if plan.bundle
            else None
        ),
    }


def _unavailable(reason_code: str) -> ResolvedAwsTwinMakerPricingContext:
    return ResolvedAwsTwinMakerPricingContext(
        payload={"status": "unavailable", "reasonCode": reason_code},
        source_refresh_run_id=None,
    )


def _catalog_mismatch_reason(
    export: Any,
    context: _PersistedAccountContext,
) -> str | None:
    if not isinstance(export, dict) or export.get("provider") != "aws":
        return CATALOG_DIGEST_MISMATCH
    pricing = export.get("pricing")
    if not isinstance(pricing, dict):
        return CATALOG_DIGEST_MISMATCH
    schema = pricing.get("__schema__")
    if not isinstance(schema, dict):
        return CATALOG_DIGEST_MISMATCH
    if schema.get("pricing_region") != context.region:
        return CATALOG_REGION_MISMATCH
    declared_digest = schema.get("snapshot_digest")
    if (
        not isinstance(declared_digest, str)
        or not SHA256_PATTERN.fullmatch(declared_digest)
        or declared_digest != _canonical_snapshot_digest(pricing)
        or declared_digest != context.catalog_snapshot_digest
    ):
        return CATALOG_DIGEST_MISMATCH
    return None


def _canonical_snapshot_digest(pricing: dict[str, Any]) -> str:
    canonical = deepcopy(pricing)
    canonical.pop(ACCOUNT_CONTEXT_KEY, None)
    schema = canonical.get("__schema__")
    if isinstance(schema, dict):
        schema.pop("generated_at", None)
        schema.pop("snapshot_digest", None)
    encoded = json.dumps(
        canonical,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def _cloud_scope(connection: CloudConnection) -> dict[str, Any]:
    return _json_object(connection.cloud_scope)


def _configured_account_id(scope: dict[str, Any]) -> str | None:
    value = scope.get("account_id")
    if value is None:
        return None
    normalized = str(value).strip()
    if not ACCOUNT_ID_PATTERN.fullmatch(normalized):
        raise ValueError("Configured AWS account ID is invalid.")
    return normalized


def _configured_region(scope: dict[str, Any]) -> str:
    value = scope.get("region")
    normalized = str(value or "").strip()
    if not AWS_REGION_PATTERN.fullmatch(normalized):
        raise ValueError("Configured AWS pricing region is invalid.")
    return normalized


def _normalized_fingerprint(value: Any) -> str:
    normalized = str(value or "").strip().lower()
    if re.fullmatch(r"[0-9a-f]{64}", normalized):
        normalized = f"sha256:{normalized}"
    if not SHA256_PATTERN.fullmatch(normalized):
        raise ValueError("CloudConnection fingerprint is invalid.")
    return normalized


def _json_object(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if not raw or not isinstance(raw, str):
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("Timestamp must be timezone-aware.")
    return value.astimezone(timezone.utc)


def _iso_utc(value: datetime) -> str:
    return _as_utc(value).isoformat().replace("+00:00", "Z")
