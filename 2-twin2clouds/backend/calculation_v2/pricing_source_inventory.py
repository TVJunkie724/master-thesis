"""
Pricing source inventory.

The strategy contract defines which pricing fields are needed. This module
classifies where each field comes from, whether it is refreshable, and how the
system must behave when the primary source cannot provide a safe value.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Dict, Mapping, Optional, Tuple

from backend.calculation_v2.strategy_contracts import (
    EvidenceRequirement,
    OptimizationStrategyContract,
    PricingFieldContract,
    PricingSourceType,
    cost_strategy_contract,
)


class Refreshability(str, Enum):
    """Whether a field can be refreshed automatically."""

    REFRESHABLE = "refreshable"
    STATIC_NON_FETCHABLE = "static_non_fetchable"
    REVIEWED_PERSISTED = "reviewed_persisted"
    DERIVED_AT_RUNTIME = "derived_at_runtime"
    UNSUPPORTED = "unsupported"


class PricingFailureBehavior(str, Enum):
    """Allowed behavior when the primary pricing source is unavailable."""

    REJECT_FIELD = "reject_field"
    REQUIRE_REVIEW = "require_review"
    USE_REVIEWED_DECISION = "use_reviewed_decision"
    DERIVE_FROM_USAGE_MODEL = "derive_from_usage_model"
    MARK_UNSUPPORTED = "mark_unsupported"


@dataclass(frozen=True)
class PricingSourcePolicy:
    """Source policy for one contract field."""

    primary_source_type: PricingSourceType
    refreshability: Refreshability
    failure_behavior: PricingFailureBehavior
    evidence: EvidenceRequirement
    emergency_fallback_source_type: Optional[PricingSourceType] = None
    emergency_fallback_allowed: bool = False


@dataclass(frozen=True)
class PricingSourceRecord:
    """Flattened inventory record for one pricing field."""

    record_id: str
    intent_id: str
    provider: str
    layer: str
    service_key: str
    field_id: str
    key_path: Tuple[str, ...]
    aliases: Tuple[Tuple[str, ...], ...]
    canonical_unit: str
    source_unit: str
    quantity_basis: str
    normalizer: Optional[str]
    policy: PricingSourcePolicy

    def as_dict(self) -> Dict[str, object]:
        return {
            "record_id": self.record_id,
            "intent_id": self.intent_id,
            "provider": self.provider,
            "layer": self.layer,
            "service_key": self.service_key,
            "field_id": self.field_id,
            "key_path": list(self.key_path),
            "aliases": [list(alias) for alias in self.aliases],
            "canonical_unit": self.canonical_unit,
            "source_unit": self.source_unit,
            "quantity_basis": self.quantity_basis,
            "normalizer": self.normalizer,
            "primary_source_type": self.policy.primary_source_type.value,
            "refreshability": self.policy.refreshability.value,
            "failure_behavior": self.policy.failure_behavior.value,
            "evidence": self.policy.evidence.value,
            "emergency_fallback_source_type": (
                self.policy.emergency_fallback_source_type.value
                if self.policy.emergency_fallback_source_type
                else None
            ),
            "emergency_fallback_allowed": self.policy.emergency_fallback_allowed,
        }


STATIC_OFFICIAL_FIELDS = frozenset(
    {
        "aws.l2.lambda.free_requests",
        "aws.l2.lambda.free_compute",
        "aws.l3.dynamodb.free_storage",
        "aws.l5.grafana.editor",
        "aws.l5.grafana.viewer",
        "azure.l2.functions.free_requests",
        "azure.l2.functions.free_compute",
        "azure.l4.digital_twins.query_unit_tiers",
        "azure.l5.grafana.user",
        "azure.l5.grafana.hour",
        "gcp.l1.pubsub.device_month",
        "gcp.l2.functions.free_requests",
        "gcp.l2.functions.free_compute",
    }
)

DERIVED_USAGE_MODEL_FIELDS = frozenset(
    {
        "azure.l3.cosmos_db.ru_per_read",
        "azure.l3.cosmos_db.ru_per_write",
    }
)

CURRENT_EMERGENCY_FALLBACK_FIELDS = frozenset(
    {
        "aws.l1.iot_core.device_month",
        "aws.l1.iot_core.rule_action",
        "aws.l2.lambda.free_requests",
        "aws.l2.lambda.free_compute",
        "aws.l3.dynamodb.free_storage",
        "aws.l3.s3_ia.write",
        "aws.l5.grafana.editor",
        "aws.l5.grafana.viewer",
        "azure.l1.iot_hub.message_tiers",
        "azure.l2.functions.free_requests",
        "azure.l2.functions.free_compute",
        "azure.l3.cosmos_db.ru_per_read",
        "azure.l3.cosmos_db.ru_per_write",
        "azure.l4.digital_twins.query_unit_tiers",
        "azure.l5.grafana.user",
        "azure.l5.grafana.hour",
        "gcp.l1.pubsub.device_month",
        "gcp.l2.functions.free_requests",
        "gcp.l2.functions.free_compute",
        "gcp.l4.self_hosted_twin.vm_hour",
        "gcp.l5.self_hosted_grafana.vm_hour",
    }
)


def _record_id(intent_id: str, field: PricingFieldContract) -> str:
    return f"{intent_id}.{field.field_id}"


def _classify_source(record_id: str, field: PricingFieldContract) -> PricingSourceType:
    if record_id in STATIC_OFFICIAL_FIELDS:
        return PricingSourceType.STATIC_OFFICIAL_TABLE
    if record_id in DERIVED_USAGE_MODEL_FIELDS:
        return PricingSourceType.DERIVED_CALCULATION
    return field.source_type


def _policy_for(record_id: str, field: PricingFieldContract) -> PricingSourcePolicy:
    source_type = _classify_source(record_id, field)
    emergency_fallback_source_type = (
        field.emergency_fallback_source_type
        or (
            PricingSourceType.STATIC_OFFICIAL_TABLE
            if record_id in CURRENT_EMERGENCY_FALLBACK_FIELDS
            else None
        )
    )

    if source_type == PricingSourceType.DYNAMIC_PROVIDER_API:
        refreshability = Refreshability.REFRESHABLE
        failure_behavior = (
            PricingFailureBehavior.REQUIRE_REVIEW
            if emergency_fallback_source_type
            else PricingFailureBehavior.REJECT_FIELD
        )
    elif source_type == PricingSourceType.STATIC_OFFICIAL_TABLE:
        refreshability = Refreshability.STATIC_NON_FETCHABLE
        failure_behavior = PricingFailureBehavior.REQUIRE_REVIEW
    elif source_type == PricingSourceType.REVIEWED_DECISION:
        refreshability = Refreshability.REVIEWED_PERSISTED
        failure_behavior = PricingFailureBehavior.USE_REVIEWED_DECISION
    elif source_type == PricingSourceType.DERIVED_CALCULATION:
        refreshability = Refreshability.DERIVED_AT_RUNTIME
        failure_behavior = PricingFailureBehavior.DERIVE_FROM_USAGE_MODEL
    else:
        refreshability = Refreshability.UNSUPPORTED
        failure_behavior = PricingFailureBehavior.MARK_UNSUPPORTED

    return PricingSourcePolicy(
        primary_source_type=source_type,
        refreshability=refreshability,
        failure_behavior=failure_behavior,
        evidence=field.evidence,
        emergency_fallback_source_type=emergency_fallback_source_type,
        emergency_fallback_allowed=field.emergency_fallback_allowed,
    )


def pricing_source_inventory(
    contract: OptimizationStrategyContract | None = None,
) -> Tuple[PricingSourceRecord, ...]:
    """Build the flattened pricing source inventory for a strategy contract."""

    strategy = contract or cost_strategy_contract()
    records = []

    for intent in strategy.pricing_intents:
        for field in intent.fields:
            record_id = _record_id(intent.intent_id, field)
            records.append(
                PricingSourceRecord(
                    record_id=record_id,
                    intent_id=intent.intent_id,
                    provider=intent.provider.value,
                    layer=intent.layer.name,
                    service_key=intent.service_key,
                    field_id=field.field_id,
                    key_path=field.key_path,
                    aliases=field.aliases,
                    canonical_unit=field.canonical_unit,
                    source_unit=field.source_unit,
                    quantity_basis=field.quantity_basis,
                    normalizer=field.normalizer,
                    policy=_policy_for(record_id, field),
                )
            )

    return tuple(records)


def pricing_source_inventory_by_id(
    contract: OptimizationStrategyContract | None = None,
) -> Mapping[str, PricingSourceRecord]:
    """Return the source inventory keyed by record id."""

    return {record.record_id: record for record in pricing_source_inventory(contract)}
