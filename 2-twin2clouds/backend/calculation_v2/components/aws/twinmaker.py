"""AWS IoT TwinMaker pricing-plan-aware cost calculation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from math import isfinite
from typing import Any, Mapping

from ..types import AWSComponent, FormulaType


DEDICATED_ACCOUNT_FULL_COST = "DEDICATED_ACCOUNT_FULL_COST"
TIER_IDS = ("TIER_1", "TIER_2", "TIER_3", "TIER_4")
ACCOUNT_CONTEXT_SCHEMA_VERSION = "aws-twinmaker-account-pricing-context.v1"
MAX_OBSERVATION_AGE = timedelta(days=7)
MAX_FUTURE_SKEW = timedelta(minutes=5)


@dataclass(frozen=True, slots=True)
class TwinMakerStandardCost:
    total: float
    entity_cost: float
    query_cost: float
    api_call_cost: float
    entity_count: int
    entity_price_per_month: float
    queries_per_month: float
    query_price: float
    api_calls_per_month: float
    api_call_price: float


@dataclass(frozen=True, slots=True)
class TwinMakerBundleAccountCost:
    total: float
    monthly_base_price: float
    query_overage: float
    query_overage_cost: float
    api_call_overage: float
    api_call_overage_cost: float


@dataclass(frozen=True, slots=True)
class TwinMakerContextEvaluation:
    comparable: bool
    reason_code: str | None
    diagnostic: Mapping[str, Any]


class AWSTwinMakerCalculator:
    """Calculate only explicit TwinMaker pricing modes."""

    component_type = AWSComponent.TWINMAKER
    formula_type = FormulaType.CA

    def calculate_standard_cost(
        self,
        *,
        entity_count: int,
        queries_per_month: float,
        api_calls_per_month: float,
        pricing: Mapping[str, Any],
    ) -> TwinMakerStandardCost:
        entity_count = _nonnegative_integer("entity_count", entity_count)
        queries = _nonnegative_number("queries_per_month", queries_per_month)
        api_calls = _nonnegative_number(
            "api_calls_per_month",
            api_calls_per_month,
        )
        aws = _required_mapping(pricing.get("aws"), "aws")
        rates = _required_mapping(
            aws.get("iotTwinMaker"),
            "aws.iotTwinMaker",
        )
        usage_rates = _required_mapping(
            rates.get("usageRates"),
            "aws.iotTwinMaker.usageRates",
        )
        entity_price = _positive_price(
            usage_rates,
            "entityPricePerMonth",
        )
        query_price = _positive_price(usage_rates, "queryPrice")
        api_price = _positive_price(
            usage_rates,
            "unifiedDataAccessApiCallPrice",
        )
        entity_cost = entity_count * entity_price
        query_cost = queries * query_price
        api_call_cost = api_calls * api_price
        return TwinMakerStandardCost(
            total=entity_cost + query_cost + api_call_cost,
            entity_cost=entity_cost,
            query_cost=query_cost,
            api_call_cost=api_call_cost,
            entity_count=entity_count,
            entity_price_per_month=entity_price,
            queries_per_month=queries,
            query_price=query_price,
            api_calls_per_month=api_calls,
            api_call_price=api_price,
        )

    def calculate_cost(
        self,
        entity_count: int,
        queries_per_month: float,
        api_calls_per_month: float,
        pricing: Mapping[str, Any],
        model_storage_gb: float = 0.0,
    ) -> float:
        """Compatibility method with strict Standard semantics and no aliases."""

        if model_storage_gb:
            raise ValueError(
                "AWS TwinMaker model storage has no approved pricing contract."
            )
        return self.calculate_standard_cost(
            entity_count=entity_count,
            queries_per_month=queries_per_month,
            api_calls_per_month=api_calls_per_month,
            pricing=pricing,
        ).total


def calculate_tiered_bundle_account_cost(
    *,
    observed_tier: str,
    account_entity_count: int,
    account_queries_per_month: float,
    account_api_calls_per_month: float,
    allocation_policy: str,
    pricing: Mapping[str, Any],
) -> TwinMakerBundleAccountCost:
    """Calculate full account bundle cost only for an explicit allocation policy."""

    if allocation_policy != DEDICATED_ACCOUNT_FULL_COST:
        raise ValueError(
            "TwinMaker Tiered Bundle requires DEDICATED_ACCOUNT_FULL_COST."
        )
    if observed_tier not in TIER_IDS:
        raise ValueError(f"Unknown TwinMaker bundle tier: {observed_tier!r}")

    entities = _nonnegative_integer("account_entity_count", account_entity_count)
    queries = _nonnegative_number(
        "account_queries_per_month",
        account_queries_per_month,
    )
    api_calls = _nonnegative_number(
        "account_api_calls_per_month",
        account_api_calls_per_month,
    )
    aws = _required_mapping(pricing.get("aws"), "aws")
    twinmaker = _required_mapping(
        aws.get("iotTwinMaker"),
        "aws.iotTwinMaker",
    )
    bundle = _required_mapping(
        twinmaker.get("tieredBundle"),
        "aws.iotTwinMaker.tieredBundle",
    )
    tiers = bundle.get("tiers")
    if not isinstance(tiers, list) or len(tiers) != 4:
        raise ValueError("TwinMaker Tiered Bundle requires exactly four tiers.")
    matching = [
        tier
        for tier in tiers
        if isinstance(tier, Mapping) and tier.get("tierId") == observed_tier
    ]
    if len(matching) != 1:
        raise ValueError(
            f"TwinMaker bundle pricing for {observed_tier} is missing or duplicated."
        )
    tier = matching[0]
    minimum = _nonnegative_integer("minimumEntities", tier.get("minimumEntities"))
    maximum = _nonnegative_integer("maximumEntities", tier.get("maximumEntities"))
    if not minimum <= entities <= maximum:
        raise ValueError(
            f"Account entity count {entities} does not belong to {observed_tier} "
            f"range {minimum}-{maximum}."
        )

    base = _positive_price(tier, "monthlyBasePrice")
    included_queries = _nonnegative_integer(
        "includedQueries",
        tier.get("includedQueries"),
    )
    included_api_calls = _nonnegative_integer(
        "includedApiCalls",
        tier.get("includedApiCalls"),
    )
    query_rate = _positive_price(tier, "queryOveragePrice")
    api_rate = _positive_price(tier, "apiCallOveragePrice")
    query_overage = max(0.0, queries - included_queries)
    api_overage = max(0.0, api_calls - included_api_calls)
    query_cost = query_overage * query_rate
    api_cost = api_overage * api_rate
    return TwinMakerBundleAccountCost(
        total=base + query_cost + api_cost,
        monthly_base_price=base,
        query_overage=query_overage,
        query_overage_cost=query_cost,
        api_call_overage=api_overage,
        api_call_overage_cost=api_cost,
    )


def evaluate_twinmaker_context(
    context: Mapping[str, Any] | None,
    pricing: Mapping[str, Any],
    *,
    now: datetime | None = None,
) -> TwinMakerContextEvaluation:
    """Evaluate account-plan compatibility against the loaded public catalog."""

    if not isinstance(context, Mapping) or context.get("status") == "unavailable":
        reason = (
            context.get("reasonCode")
            if isinstance(context, Mapping)
            else None
        ) or "AWS_TWINMAKER_PLAN_UNOBSERVED"
        return _context_evaluation(
            False,
            str(reason),
            context,
            status="unavailable",
        )
    if context.get("status") != "available":
        raise ValueError("AWS TwinMaker pricing context status is invalid.")
    if context.get("schemaVersion") != ACCOUNT_CONTEXT_SCHEMA_VERSION:
        raise ValueError("AWS TwinMaker pricing context schema is unsupported.")

    aws = _required_mapping(pricing.get("aws"), "aws")
    schema = aws.get("__schema__")
    # Combined pricing stores metadata outside provider payloads.
    if not isinstance(schema, Mapping):
        schema = pricing.get("__aws_schema__")
    if not isinstance(schema, Mapping):
        return _context_evaluation(
            False,
            "AWS_TWINMAKER_CATALOG_METADATA_MISSING",
            context,
            status="contract_invalid",
        )
    region = context.get("pricingRegion")
    digest = context.get("catalogSnapshotDigest")
    if region != schema.get("pricing_region"):
        return _context_evaluation(
            False,
            "AWS_TWINMAKER_CATALOG_REGION_MISMATCH",
            context,
            status="contract_invalid",
        )
    if digest != schema.get("snapshot_digest"):
        return _context_evaluation(
            False,
            "AWS_TWINMAKER_CATALOG_DIGEST_MISMATCH",
            context,
            status="contract_invalid",
        )

    observed_at = _aware_datetime("observedAt", context.get("observedAt"))
    current_time = now or datetime.now(timezone.utc)
    if current_time.tzinfo is None:
        raise ValueError("TwinMaker context evaluation time must be timezone-aware.")
    current_time = current_time.astimezone(timezone.utc)
    observed_utc = observed_at.astimezone(timezone.utc)
    if observed_utc > current_time + MAX_FUTURE_SKEW:
        return _context_evaluation(
            False,
            "AWS_TWINMAKER_OBSERVATION_FROM_FUTURE",
            context,
            status="contract_invalid",
        )
    observation_age_seconds = max(
        0.0,
        (current_time - observed_utc).total_seconds(),
    )
    if current_time - observed_utc > MAX_OBSERVATION_AGE:
        return _context_evaluation(
            False,
            "AWS_TWINMAKER_PLAN_STALE",
            context,
            status="unavailable",
            observation_age_seconds=observation_age_seconds,
        )
    if context.get("pendingPlan") is not None:
        return _context_evaluation(
            False,
            "AWS_TWINMAKER_PENDING_PLAN_CHANGE",
            context,
            status="pending_change",
            observation_age_seconds=observation_age_seconds,
        )

    current_plan = _required_mapping(
        context.get("currentPlan"),
        "providerPricingContexts.awsTwinMaker.currentPlan",
    )
    mode = current_plan.get("mode")
    if mode == "BASIC":
        return _context_evaluation(
            False,
            "AWS_TWINMAKER_BASIC_FUNCTIONALLY_INCOMPLETE",
            context,
            status="functionally_incomplete",
            observation_age_seconds=observation_age_seconds,
        )
    if mode == "TIERED_BUNDLE":
        return _context_evaluation(
            False,
            "AWS_TWINMAKER_BUNDLE_ALLOCATION_REQUIRED",
            context,
            status="account_allocation_required",
            observation_age_seconds=observation_age_seconds,
        )
    if mode != "STANDARD":
        return _context_evaluation(
            False,
            "AWS_TWINMAKER_PRICING_MODE_UNSUPPORTED",
            context,
            status="contract_invalid",
            observation_age_seconds=observation_age_seconds,
        )
    return _context_evaluation(
        True,
        None,
        context,
        status="compatible",
        observation_age_seconds=observation_age_seconds,
    )


def _context_evaluation(
    comparable: bool,
    reason_code: str | None,
    context: Mapping[str, Any] | None,
    *,
    status: str,
    observation_age_seconds: float | None = None,
) -> TwinMakerContextEvaluation:
    source = context if isinstance(context, Mapping) else {}
    plan = source.get("currentPlan")
    observed_mode = plan.get("mode") if isinstance(plan, Mapping) else None
    diagnostic = {
        "status": status,
        "reasonCode": reason_code,
        "observedMode": observed_mode,
        "modeledMode": "STANDARD" if comparable else None,
        "scope": "account",
        "sourceRefreshRunId": source.get("sourceRefreshRunId"),
        "connectionFingerprint": source.get("connectionFingerprint"),
        "providerAccountId": source.get("providerAccountId"),
        "pricingRegion": source.get("pricingRegion"),
        "catalogSnapshotDigest": source.get("catalogSnapshotDigest"),
        "observedAt": _json_datetime(source.get("observedAt")),
        "observationAgeSeconds": (
            round(observation_age_seconds, 3)
            if observation_age_seconds is not None
            else None
        ),
        "currentPlan": _json_safe(source.get("currentPlan")),
        "pendingPlan": _json_safe(source.get("pendingPlan")),
        "functionalCompatibility": _functional_compatibility(status),
        "allocationPolicy": None,
        "requiredAllocationPolicy": (
            DEDICATED_ACCOUNT_FULL_COST
            if status == "account_allocation_required"
            else None
        ),
    }
    return TwinMakerContextEvaluation(
        comparable=comparable,
        reason_code=reason_code,
        diagnostic=diagnostic,
    )


def _functional_compatibility(status: str) -> str:
    if status == "compatible":
        return "compatible"
    if status == "functionally_incomplete":
        return "incomplete"
    if status in {"account_allocation_required", "pending_change"}:
        return "non_comparable"
    if status == "contract_invalid":
        return "invalid"
    return "unknown"


def _aware_datetime(label: str, value: Any) -> datetime:
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError(f"{label} must be an ISO-8601 timestamp.") from exc
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ValueError(f"{label} must be timezone-aware.")
    return value


def _json_datetime(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    return value


def _json_safe(value: Any) -> Any:
    if isinstance(value, datetime):
        return _json_datetime(value)
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


def _required_mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} pricing object is required.")
    return value


def _positive_price(mapping: Mapping[str, Any], key: str) -> float:
    value = mapping.get(key)
    normalized = _nonnegative_number(key, value)
    if normalized <= 0:
        raise ValueError(f"{key} must be positive.")
    return normalized


def _nonnegative_number(label: str, value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be numeric.")
    normalized = float(value)
    if not isfinite(normalized) or normalized < 0:
        raise ValueError(f"{label} must be finite and non-negative.")
    return normalized


def _nonnegative_integer(label: str, value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{label} must be a non-negative integer.")
    return value
