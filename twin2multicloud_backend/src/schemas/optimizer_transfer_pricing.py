"""Strict Management read contracts for Optimizer transfer-pricing evidence."""

from __future__ import annotations

from decimal import Decimal
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)


Provider = Literal["aws", "azure", "gcp"]
TransferRouteClass = Literal[
    "same_provider_same_region",
    "cross_provider_public_internet",
]
TransferNetworkTier = Literal[
    "not_applicable",
    "provider_default",
    "microsoft_premium_global_network",
    "premium",
]
PricedTransferNetworkTier = Literal[
    "provider_default",
    "microsoft_premium_global_network",
    "premium",
]
TransferBillingScope = Literal[
    "account_aggregate_public_egress",
    "sku_account_aggregate_public_egress",
]
TransferBillingUnit = Literal["gb", "gib"]

_REGION_PATTERN = r"^[a-z][a-z0-9-]{1,62}$"
_SNAPSHOT_PATTERN = r"^pcs_[0-9a-f]{64}$"
_IDENTIFIER_PATTERN = r"^[a-zA-Z0-9][a-zA-Z0-9_.:-]{0,255}$"
_MAX_NUMERIC_EVIDENCE = Decimal("1e30")
_LAYER_NAMES = Literal[
    "L1_INGESTION",
    "L2_PROCESSING",
    "L3_HOT_STORAGE",
    "L3_COOL_STORAGE",
    "L3_ARCHIVE_STORAGE",
    "L4_TWIN_MANAGEMENT",
    "L5_VISUALIZATION",
]


def _to_camel(value: str) -> str:
    head, *tail = value.split("_")
    return head + "".join(part.capitalize() for part in tail)


class _TransferModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        allow_inf_nan=False,
        populate_by_name=True,
        alias_generator=_to_camel,
    )


class OptimizerTransferEndpoint(_TransferModel):
    layer: _LAYER_NAMES
    provider: Provider
    region: str = Field(pattern=_REGION_PATTERN)
    geography: Literal["europe"]


class OptimizerTransferTierContribution(_TransferModel):
    tier_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    from_quantity: Decimal = Field(ge=0, le=_MAX_NUMERIC_EVIDENCE)
    to_quantity: Decimal = Field(gt=0, le=_MAX_NUMERIC_EVIDENCE)
    billable_quantity: Decimal = Field(gt=0, le=_MAX_NUMERIC_EVIDENCE)
    unit_price: Decimal = Field(ge=0, le=_MAX_NUMERIC_EVIDENCE)
    cost: Decimal = Field(ge=0, le=_MAX_NUMERIC_EVIDENCE)

    @field_validator(
        "from_quantity",
        "to_quantity",
        "billable_quantity",
        "unit_price",
        "cost",
        mode="before",
    )
    @classmethod
    def reject_boolean_numbers(cls, value):
        return _normalize_numeric_evidence(value)

    @model_validator(mode="after")
    def validate_arithmetic(self) -> "OptimizerTransferTierContribution":
        if self.to_quantity <= self.from_quantity:
            raise ValueError("to_quantity must exceed from_quantity")
        if not _close(
            self.billable_quantity,
            self.to_quantity - self.from_quantity,
        ):
            raise ValueError(
                "billable_quantity must equal to_quantity - from_quantity"
            )
        if not _close(self.cost, self.billable_quantity * self.unit_price):
            raise ValueError("cost must equal billable_quantity * unit_price")
        return self


class OptimizerTransferRoute(_TransferModel):
    segment_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    source: OptimizerTransferEndpoint
    destination: OptimizerTransferEndpoint
    route_class: TransferRouteClass
    network_tier: TransferNetworkTier
    volume_bytes: Decimal = Field(ge=0, le=_MAX_NUMERIC_EVIDENCE)
    pool_id: str | None = Field(default=None, pattern=_IDENTIFIER_PATTERN)
    catalog_snapshot_id: str | None = Field(
        default=None,
        pattern=_SNAPSHOT_PATTERN,
    )
    evidence_id: str | None = Field(
        default=None,
        pattern=_IDENTIFIER_PATTERN,
    )
    tier_contributions: tuple[OptimizerTransferTierContribution, ...] = Field(
        max_length=32,
    )
    egress_cost: Decimal = Field(ge=0, le=_MAX_NUMERIC_EVIDENCE)
    glue_cost: Decimal = Field(ge=0, le=_MAX_NUMERIC_EVIDENCE)
    total_cost: Decimal = Field(ge=0, le=_MAX_NUMERIC_EVIDENCE)
    assumptions: tuple[str, ...] = Field(max_length=32)

    @field_validator(
        "volume_bytes",
        "egress_cost",
        "glue_cost",
        "total_cost",
        mode="before",
    )
    @classmethod
    def reject_boolean_numbers(cls, value):
        return _normalize_numeric_evidence(value)

    @field_validator("assumptions")
    @classmethod
    def validate_assumptions(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if any(not item.strip() or len(item) > 512 for item in value):
            raise ValueError("assumptions must contain bounded non-empty text")
        return value

    @model_validator(mode="after")
    def validate_arithmetic(self) -> "OptimizerTransferRoute":
        contribution_cost = sum(
            (item.cost for item in self.tier_contributions),
            Decimal(0),
        )
        if not _close(self.egress_cost, contribution_cost):
            raise ValueError("egress_cost must equal tier contribution cost")
        if not _close(self.total_cost, self.egress_cost + self.glue_cost):
            raise ValueError("total_cost must equal egress_cost + glue_cost")
        return self


class OptimizerTransferPool(_TransferModel):
    pool_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    provider: Provider
    route_class: Literal["cross_provider_public_internet"]
    source_geography: Literal["europe"]
    destination_geography: Literal["europe"]
    network_tier: PricedTransferNetworkTier
    billing_scope: TransferBillingScope
    billing_unit: TransferBillingUnit
    bytes_per_billing_unit: int = Field(gt=0, strict=True)
    catalog_snapshot_id: str = Field(pattern=_SNAPSHOT_PATTERN)
    evidence_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    aggregate_volume_bytes: Decimal = Field(
        ge=0,
        le=_MAX_NUMERIC_EVIDENCE,
    )
    aggregate_egress_cost: Decimal = Field(
        ge=0,
        le=_MAX_NUMERIC_EVIDENCE,
    )

    @field_validator("aggregate_volume_bytes", "aggregate_egress_cost", mode="before")
    @classmethod
    def reject_boolean_numbers(cls, value):
        return _normalize_numeric_evidence(value)


class OptimizerTransferPricingContext(_TransferModel):
    schema_version: Literal["complete-path-transfer-pricing.v1"]
    currency: Literal["USD", "EUR"]
    assumptions: tuple[str, ...] = Field(max_length=32)
    routes: tuple[OptimizerTransferRoute, ...] = Field(
        min_length=6,
        max_length=6,
    )
    pools: tuple[OptimizerTransferPool, ...] = Field(max_length=3)

    @field_validator("assumptions")
    @classmethod
    def validate_assumptions(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if any(not item.strip() or len(item) > 512 for item in value):
            raise ValueError("assumptions must contain bounded non-empty text")
        return value

    @model_validator(mode="after")
    def validate_unique_identities(self) -> "OptimizerTransferPricingContext":
        segment_ids = [route.segment_id for route in self.routes]
        if len(set(segment_ids)) != len(segment_ids):
            raise ValueError("route segment IDs must be unique")
        pool_ids = [pool.pool_id for pool in self.pools]
        if len(set(pool_ids)) != len(pool_ids):
            raise ValueError("pricing pool IDs must be unique")
        return self


class OptimizerPathDiagnostics(_TransferModel):
    schema_version: Literal["complete-path-optimization.v1"]
    enumerated_path_count: int = Field(gt=0, le=10_000_000, strict=True)
    evaluated_path_count: int = Field(gt=0, le=10_000_000, strict=True)
    rejected_path_count: int = Field(ge=0, le=10_000_000, strict=True)
    rejected_by_error_code: dict[str, int]
    winning_candidate_id: str = Field(pattern=r"^(aws|azure|gcp)(\|(aws|azure|gcp)){6}$")
    winning_score: Decimal = Field(ge=0, le=_MAX_NUMERIC_EVIDENCE)
    winning_layer_cost: Decimal = Field(ge=0, le=_MAX_NUMERIC_EVIDENCE)
    winning_transfer_cost: Decimal = Field(
        ge=0,
        le=_MAX_NUMERIC_EVIDENCE,
    )
    tie_break_policy: Literal["canonical_provider_order"]
    canonical_provider_order: tuple[Literal["aws", "azure", "gcp"], ...] = Field(
        min_length=3,
        max_length=3,
    )
    score_unit: Literal["USD/month", "EUR/month"]

    @field_validator(
        "winning_score",
        "winning_layer_cost",
        "winning_transfer_cost",
        mode="before",
    )
    @classmethod
    def reject_boolean_numbers(cls, value):
        return _normalize_numeric_evidence(value)

    @field_validator("rejected_by_error_code", mode="before")
    @classmethod
    def validate_rejected_counts(cls, value):
        if not isinstance(value, dict) or len(value) > 64:
            raise ValueError("rejected path diagnostics must be a bounded object")
        if any(
            not isinstance(code, str)
            or not code
            or len(code) > 128
            or isinstance(count, bool)
            or not isinstance(count, int)
            or count <= 0
            for code, count in value.items()
        ):
            raise ValueError(
                "rejected path diagnostics require positive integer counts"
            )
        return value

    @model_validator(mode="after")
    def validate_counts_and_score(self) -> "OptimizerPathDiagnostics":
        if (
            self.evaluated_path_count + self.rejected_path_count
            != self.enumerated_path_count
        ):
            raise ValueError(
                "evaluated and rejected path counts must equal enumerated paths"
            )
        if sum(self.rejected_by_error_code.values()) != self.rejected_path_count:
            raise ValueError("rejected path diagnostics must match rejected count")
        if not _close(
            self.winning_score,
            self.winning_layer_cost + self.winning_transfer_cost,
        ):
            raise ValueError(
                "winning score must equal layer and transfer cost"
            )
        if self.canonical_provider_order != ("aws", "azure", "gcp"):
            raise ValueError("canonical provider order is invalid")
        return self


def _normalize_numeric_evidence(value) -> Decimal:
    if isinstance(value, bool) or not isinstance(
        value,
        (int, float, Decimal),
    ):
        raise ValueError("numeric evidence must be a JSON number")
    return Decimal(str(value))


def _close(left: Decimal, right: Decimal) -> bool:
    return abs(left - right) <= Decimal("0.000000001")
