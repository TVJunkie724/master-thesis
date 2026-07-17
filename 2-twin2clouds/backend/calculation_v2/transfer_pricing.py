"""Route-aware transfer pricing contracts and exact tier arithmetic."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from enum import Enum
import re
from types import MappingProxyType
from typing import Any

from backend.calculation_v2.components.types import LayerType, Provider


TRANSFER_ROUTES_SCHEMA_VERSION = "pricing-registry-transfer-routes.v1"

_IDENTIFIER_PATTERN = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.:-]{0,127}$")
_REGION_PATTERN = re.compile(r"^[a-z][a-z0-9-]{1,62}$")
_CATALOG_SNAPSHOT_PATTERN = re.compile(r"^pcs_[0-9a-f]{64}$")
_CURRENCY_PATTERN = re.compile(r"^[A-Z]{3}$")
_FORBIDDEN_PRICE_KEYS = {
    "amount",
    "price",
    "rate",
    "retail_price",
    "unit_price",
}


class TransferPricingContractError(ValueError):
    """Raised when a transfer-pricing contract is internally inconsistent."""

    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(f"{code}: {message}")


class TransferRouteClass(str, Enum):
    SAME_PROVIDER_SAME_REGION = "same_provider_same_region"
    SAME_PROVIDER_INTER_REGION = "same_provider_inter_region"
    CROSS_PROVIDER_PUBLIC_INTERNET = "cross_provider_public_internet"


class TransferNetworkTier(str, Enum):
    NOT_APPLICABLE = "not_applicable"
    PROVIDER_DEFAULT = "provider_default"
    MICROSOFT_PREMIUM_GLOBAL_NETWORK = "microsoft_premium_global_network"
    PREMIUM = "premium"
    STANDARD = "standard"


class TransferBillingUnit(str, Enum):
    GB = "gb"
    GIB = "gib"


class TransferGeography(str, Enum):
    EUROPE = "europe"


class TransferBillingScope(str, Enum):
    ACCOUNT_AGGREGATE_PUBLIC_EGRESS = "account_aggregate_public_egress"
    SKU_ACCOUNT_AGGREGATE_PUBLIC_EGRESS = (
        "sku_account_aggregate_public_egress"
    )


class TransferChargePolicy(str, Enum):
    NO_EGRESS_CHARGE = "no_egress_charge"
    SOURCE_PROVIDER_EGRESS = "source_provider_egress"


@dataclass(frozen=True)
class TransferEndpoint:
    """One provider, region, geography, and logical architecture layer."""

    layer: LayerType
    provider: Provider
    region: str
    geography: TransferGeography

    def __post_init__(self) -> None:
        if not isinstance(self.layer, LayerType):
            _fail("TRANSFER_LAYER_INVALID", "layer must be a LayerType")
        if not isinstance(self.provider, Provider):
            _fail("TRANSFER_PROVIDER_INVALID", "provider must be a Provider")
        if not isinstance(self.region, str) or not _REGION_PATTERN.fullmatch(
            self.region
        ):
            _fail(
                "TRANSFER_REGION_INVALID",
                "region must use a canonical lowercase cloud-region identifier",
            )
        if not isinstance(self.geography, TransferGeography):
            _fail(
                "TRANSFER_GEOGRAPHY_INVALID",
                "geography must be a supported TransferGeography",
            )


@dataclass(frozen=True)
class TransferRouteIntent:
    """Canonical byte volume moving between two architecture endpoints."""

    segment_id: str
    source: TransferEndpoint
    destination: TransferEndpoint
    route_class: TransferRouteClass
    network_tier: TransferNetworkTier
    volume_bytes: Decimal
    assumptions: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _validate_identifier("segment_id", self.segment_id)
        if not isinstance(self.source, TransferEndpoint) or not isinstance(
            self.destination,
            TransferEndpoint,
        ):
            _fail(
                "TRANSFER_ENDPOINTS_INVALID",
                "source and destination must be TransferEndpoint objects",
            )
        if self.source.layer == self.destination.layer:
            _fail(
                "TRANSFER_ENDPOINTS_INVALID",
                "source and destination layers must differ",
            )
        if not isinstance(self.route_class, TransferRouteClass):
            _fail(
                "TRANSFER_ROUTE_CLASS_INVALID",
                "route_class must be a TransferRouteClass",
            )
        if not isinstance(self.network_tier, TransferNetworkTier):
            _fail(
                "TRANSFER_NETWORK_TIER_INVALID",
                "network_tier must be a TransferNetworkTier",
            )
        object.__setattr__(
            self,
            "volume_bytes",
            _decimal(self.volume_bytes, "volume_bytes"),
        )
        object.__setattr__(
            self,
            "assumptions",
            _validated_assumptions(self.assumptions),
        )

        expected_class = classify_route(self.source, self.destination)
        if self.route_class != expected_class:
            _fail(
                "TRANSFER_ROUTE_CLASS_MISMATCH",
                f"route_class must be {expected_class.value!r} for its endpoints",
            )
        if (
            self.route_class == TransferRouteClass.CROSS_PROVIDER_PUBLIC_INTERNET
            and self.network_tier == TransferNetworkTier.NOT_APPLICABLE
        ):
            _fail(
                "TRANSFER_NETWORK_TIER_INVALID",
                "cross-provider routes require an explicit source network tier",
            )
        if (
            self.route_class != TransferRouteClass.CROSS_PROVIDER_PUBLIC_INTERNET
            and self.network_tier != TransferNetworkTier.NOT_APPLICABLE
        ):
            _fail(
                "TRANSFER_NETWORK_TIER_INVALID",
                "same-provider routes must use not_applicable network tier",
            )


@dataclass(frozen=True)
class TransferTier:
    """One explicit cumulative billing range, interpreted as ``[start, end)``."""

    tier_id: str
    start_quantity: Decimal
    end_quantity: Decimal | None
    unit_price: Decimal

    def __post_init__(self) -> None:
        _validate_identifier("tier_id", self.tier_id)
        start = _decimal(self.start_quantity, "start_quantity")
        end = (
            None
            if self.end_quantity is None
            else _decimal(self.end_quantity, "end_quantity")
        )
        price = _decimal(self.unit_price, "unit_price")
        if end is not None and end <= start:
            _fail(
                "TRANSFER_TIER_RANGE_INVALID",
                f"tier {self.tier_id!r} end_quantity must exceed start_quantity",
            )
        object.__setattr__(self, "start_quantity", start)
        object.__setattr__(self, "end_quantity", end)
        object.__setattr__(self, "unit_price", price)


@dataclass(frozen=True)
class TransferTierContribution:
    """Exact portion of one tier consumed by a segment."""

    tier_id: str
    from_quantity: Decimal
    to_quantity: Decimal
    billable_quantity: Decimal
    unit_price: Decimal
    cost: Decimal

    def __post_init__(self) -> None:
        _validate_identifier("tier_id", self.tier_id)
        start = _decimal(self.from_quantity, "from_quantity")
        end = _decimal(self.to_quantity, "to_quantity")
        billable = _decimal(self.billable_quantity, "billable_quantity")
        unit_price = _decimal(self.unit_price, "unit_price")
        cost = _decimal(self.cost, "cost")
        if end <= start:
            _fail(
                "TRANSFER_TIER_CONTRIBUTION_INVALID",
                "to_quantity must exceed from_quantity",
            )
        if billable != end - start:
            _fail(
                "TRANSFER_TIER_CONTRIBUTION_INVALID",
                "billable_quantity must equal to_quantity - from_quantity",
            )
        if cost != billable * unit_price:
            _fail(
                "TRANSFER_TIER_CONTRIBUTION_INVALID",
                "cost must equal billable_quantity * unit_price",
            )
        object.__setattr__(self, "from_quantity", start)
        object.__setattr__(self, "to_quantity", end)
        object.__setattr__(self, "billable_quantity", billable)
        object.__setattr__(self, "unit_price", unit_price)
        object.__setattr__(self, "cost", cost)


@dataclass(frozen=True)
class TransferTierTable:
    """Validated terminal tier series with exact provider billing-unit semantics."""

    tiers: tuple[TransferTier, ...]
    billing_unit: TransferBillingUnit
    bytes_per_billing_unit: int
    currency: str
    evidence_id: str

    def __post_init__(self) -> None:
        try:
            tiers = tuple(self.tiers)
        except TypeError as exc:
            raise TransferPricingContractError(
                "TRANSFER_TIER_TABLE_INVALID",
                "tiers must be a sequence of TransferTier objects",
            ) from exc
        if not tiers:
            _fail(
                "TRANSFER_TIER_TABLE_INVALID",
                "tier table must contain at least one tier",
            )
        if any(not isinstance(tier, TransferTier) for tier in tiers):
            _fail(
                "TRANSFER_TIER_TABLE_INVALID",
                "tiers must contain only TransferTier objects",
            )
        if len({tier.tier_id for tier in tiers}) != len(tiers):
            _fail(
                "TRANSFER_TIER_TABLE_INVALID",
                "tier IDs must be unique",
            )
        if tiers[0].start_quantity != Decimal("0"):
            _fail(
                "TRANSFER_TIER_TABLE_INVALID",
                "first tier must start at zero",
            )
        previous_end: Decimal | None = None
        for index, tier in enumerate(tiers):
            if index > 0 and tier.start_quantity != previous_end:
                _fail(
                    "TRANSFER_TIER_TABLE_INVALID",
                    "tiers must be ordered, contiguous, and non-overlapping",
                )
            if tier.end_quantity is None and index != len(tiers) - 1:
                _fail(
                    "TRANSFER_TIER_TABLE_INVALID",
                    "only the last tier may be open-ended",
                )
            previous_end = tier.end_quantity
        if tiers[-1].end_quantity is not None:
            _fail(
                "TRANSFER_TIER_TABLE_INVALID",
                "tier table must have one terminal open-ended tier",
            )
        if not isinstance(self.billing_unit, TransferBillingUnit):
            _fail(
                "TRANSFER_BILLING_UNIT_INVALID",
                "billing_unit must be a TransferBillingUnit",
            )
        if (
            isinstance(self.bytes_per_billing_unit, bool)
            or not isinstance(self.bytes_per_billing_unit, int)
            or self.bytes_per_billing_unit <= 0
        ):
            _fail(
                "TRANSFER_BILLING_UNIT_INVALID",
                "bytes_per_billing_unit must be a positive integer",
            )
        expected_bytes = {
            TransferBillingUnit.GB: 1_000_000_000,
            TransferBillingUnit.GIB: 1_073_741_824,
        }[self.billing_unit]
        if self.bytes_per_billing_unit != expected_bytes:
            _fail(
                "TRANSFER_BILLING_UNIT_INVALID",
                f"{self.billing_unit.value} requires {expected_bytes} bytes",
            )
        if (
            not isinstance(self.currency, str)
            or not _CURRENCY_PATTERN.fullmatch(self.currency)
        ):
            _fail(
                "TRANSFER_CURRENCY_INVALID",
                "currency must be a three-letter uppercase code",
            )
        _validate_identifier("evidence_id", self.evidence_id)
        object.__setattr__(self, "tiers", tiers)

    def quantity_for_bytes(self, volume_bytes: Decimal | int | str) -> Decimal:
        normalized = _decimal(volume_bytes, "volume_bytes")
        return normalized / Decimal(self.bytes_per_billing_unit)

    def contributions_between(
        self,
        from_quantity: Decimal | int | str,
        to_quantity: Decimal | int | str,
    ) -> tuple[TransferTierContribution, ...]:
        start = _decimal(from_quantity, "from_quantity")
        end = _decimal(to_quantity, "to_quantity")
        if end < start:
            _fail(
                "TRANSFER_TIER_RANGE_INVALID",
                "to_quantity must not be less than from_quantity",
            )
        if end == start:
            return ()

        contributions: list[TransferTierContribution] = []
        for tier in self.tiers:
            tier_end = tier.end_quantity
            overlap_start = max(start, tier.start_quantity)
            overlap_end = end if tier_end is None else min(end, tier_end)
            if overlap_end <= overlap_start:
                continue
            billable = overlap_end - overlap_start
            contributions.append(
                TransferTierContribution(
                    tier_id=tier.tier_id,
                    from_quantity=overlap_start,
                    to_quantity=overlap_end,
                    billable_quantity=billable,
                    unit_price=tier.unit_price,
                    cost=billable * tier.unit_price,
                )
            )
            if overlap_end == end:
                break
        if not contributions or contributions[-1].to_quantity != end:
            _fail(
                "TRANSFER_TIER_TABLE_INVALID",
                "tier table does not cover the requested quantity",
            )
        return tuple(contributions)

    def cost_between(
        self,
        from_quantity: Decimal | int | str,
        to_quantity: Decimal | int | str,
    ) -> Decimal:
        return sum(
            (
                contribution.cost
                for contribution in self.contributions_between(
                    from_quantity,
                    to_quantity,
                )
            ),
            Decimal("0"),
        )

    def cost_for_bytes(self, volume_bytes: Decimal | int | str) -> Decimal:
        return self.cost_between(
            Decimal("0"),
            self.quantity_for_bytes(volume_bytes),
        )


@dataclass(frozen=True)
class TransferPricingPool:
    """One aggregate provider billing pool backed by exact catalog evidence."""

    pool_id: str
    provider: Provider
    route_class: TransferRouteClass
    source_geography: TransferGeography
    destination_geography: TransferGeography
    network_tier: TransferNetworkTier
    billing_scope: TransferBillingScope
    catalog_snapshot_id: str
    evidence_id: str
    tier_table: TransferTierTable

    def __post_init__(self) -> None:
        _validate_identifier("pool_id", self.pool_id)
        if not isinstance(self.provider, Provider):
            _fail("TRANSFER_PROVIDER_INVALID", "provider must be a Provider")
        if not isinstance(self.route_class, TransferRouteClass):
            _fail(
                "TRANSFER_ROUTE_CLASS_INVALID",
                "route_class must be a TransferRouteClass",
            )
        if self.route_class != TransferRouteClass.CROSS_PROVIDER_PUBLIC_INTERNET:
            _fail(
                "TRANSFER_POOL_INVALID",
                "pricing pools currently support cross-provider public routes only",
            )
        if not isinstance(self.source_geography, TransferGeography):
            _fail(
                "TRANSFER_GEOGRAPHY_INVALID",
                "source_geography must be supported",
            )
        if not isinstance(self.destination_geography, TransferGeography):
            _fail(
                "TRANSFER_GEOGRAPHY_INVALID",
                "destination_geography must be supported",
            )
        if not isinstance(self.network_tier, TransferNetworkTier):
            _fail(
                "TRANSFER_NETWORK_TIER_INVALID",
                "network_tier must be a TransferNetworkTier",
            )
        if self.network_tier == TransferNetworkTier.NOT_APPLICABLE:
            _fail(
                "TRANSFER_NETWORK_TIER_INVALID",
                "pricing pool requires an explicit network tier",
            )
        if not isinstance(self.billing_scope, TransferBillingScope):
            _fail(
                "TRANSFER_BILLING_SCOPE_INVALID",
                "billing_scope must be a TransferBillingScope",
            )
        if not isinstance(self.tier_table, TransferTierTable):
            _fail(
                "TRANSFER_TIER_TABLE_INVALID",
                "tier_table must be a TransferTierTable",
            )
        if not _CATALOG_SNAPSHOT_PATTERN.fullmatch(self.catalog_snapshot_id):
            _fail(
                "TRANSFER_CATALOG_INVALID",
                "catalog_snapshot_id must use the pcs_<sha256> format",
            )
        _validate_identifier("evidence_id", self.evidence_id)
        if self.evidence_id != self.tier_table.evidence_id:
            _fail(
                "TRANSFER_EVIDENCE_MISMATCH",
                "pool and tier table evidence IDs must match",
            )

    @property
    def billing_unit(self) -> TransferBillingUnit:
        return self.tier_table.billing_unit

    @property
    def bytes_per_billing_unit(self) -> int:
        return self.tier_table.bytes_per_billing_unit


@dataclass(frozen=True)
class TransferSegmentCharge:
    """Marginal pool charge and optional glue charge for one route segment."""

    route: TransferRouteIntent
    pool_id: str
    tier_contributions: tuple[TransferTierContribution, ...]
    egress_cost: Decimal
    glue_cost: Decimal
    total_cost: Decimal
    assumptions: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _validate_identifier("pool_id", self.pool_id)
        contributions = tuple(self.tier_contributions)
        egress = _decimal(self.egress_cost, "egress_cost")
        glue = _decimal(self.glue_cost, "glue_cost")
        total = _decimal(self.total_cost, "total_cost")
        if egress != sum(
            (contribution.cost for contribution in contributions),
            Decimal("0"),
        ):
            _fail(
                "TRANSFER_SEGMENT_CHARGE_INVALID",
                "egress_cost must equal its tier contributions",
            )
        if total != egress + glue:
            _fail(
                "TRANSFER_SEGMENT_CHARGE_INVALID",
                "total_cost must equal egress_cost + glue_cost",
            )
        object.__setattr__(self, "tier_contributions", contributions)
        object.__setattr__(self, "egress_cost", egress)
        object.__setattr__(self, "glue_cost", glue)
        object.__setattr__(self, "total_cost", total)
        object.__setattr__(
            self,
            "assumptions",
            _validated_assumptions(self.assumptions),
        )


@dataclass(frozen=True)
class TransferProviderPolicy:
    provider: Provider
    public_route_tier: TransferNetworkTier
    billing_scope: TransferBillingScope
    catalog_tier_path: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.provider, Provider):
            _fail("TRANSFER_PROVIDER_INVALID", "provider must be a Provider")
        if not isinstance(self.public_route_tier, TransferNetworkTier):
            _fail(
                "TRANSFER_NETWORK_TIER_INVALID",
                "public_route_tier must be a TransferNetworkTier",
            )
        if not isinstance(self.billing_scope, TransferBillingScope):
            _fail(
                "TRANSFER_BILLING_SCOPE_INVALID",
                "billing_scope must be a TransferBillingScope",
            )
        expected_tiers = {
            Provider.AWS: TransferNetworkTier.PROVIDER_DEFAULT,
            Provider.AZURE: TransferNetworkTier.MICROSOFT_PREMIUM_GLOBAL_NETWORK,
            Provider.GCP: TransferNetworkTier.PREMIUM,
        }
        if self.public_route_tier != expected_tiers[self.provider]:
            _fail(
                "TRANSFER_NETWORK_TIER_INVALID",
                f"{self.provider.value} baseline requires "
                f"{expected_tiers[self.provider].value!r}",
            )
        path = tuple(self.catalog_tier_path)
        if not path or any(
            not isinstance(part, str) or not _IDENTIFIER_PATTERN.fullmatch(part)
            for part in path
        ):
            _fail(
                "TRANSFER_CATALOG_PATH_INVALID",
                "catalog_tier_path must contain canonical path segments",
            )
        if path[:2] != (self.provider.value, "transfer"):
            _fail(
                "TRANSFER_CATALOG_PATH_INVALID",
                "catalog_tier_path must start with provider and transfer",
            )
        if path[-1] != "pricing_tiers":
            _fail(
                "TRANSFER_CATALOG_PATH_INVALID",
                "catalog_tier_path must address canonical pricing_tiers",
            )
        object.__setattr__(self, "catalog_tier_path", path)


@dataclass(frozen=True)
class TransferRoutePolicy:
    route_class: TransferRouteClass
    charge_policy: TransferChargePolicy
    source_geographies: tuple[TransferGeography, ...] = ()
    destination_geographies: tuple[TransferGeography, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.route_class, TransferRouteClass):
            _fail(
                "TRANSFER_ROUTE_CLASS_INVALID",
                "route_class must be a TransferRouteClass",
            )
        if not isinstance(self.charge_policy, TransferChargePolicy):
            _fail(
                "TRANSFER_ROUTE_POLICY_INVALID",
                "charge_policy must be a TransferChargePolicy",
            )
        source = tuple(self.source_geographies)
        destination = tuple(self.destination_geographies)
        if any(not isinstance(item, TransferGeography) for item in source):
            _fail(
                "TRANSFER_GEOGRAPHY_INVALID",
                "source_geographies contain an unsupported geography",
            )
        if any(not isinstance(item, TransferGeography) for item in destination):
            _fail(
                "TRANSFER_GEOGRAPHY_INVALID",
                "destination_geographies contain an unsupported geography",
            )
        if len(set(source)) != len(source) or len(set(destination)) != len(
            destination
        ):
            _fail(
                "TRANSFER_ROUTE_POLICY_INVALID",
                "route geographies must be unique",
            )
        if self.route_class == TransferRouteClass.SAME_PROVIDER_SAME_REGION:
            if self.charge_policy != TransferChargePolicy.NO_EGRESS_CHARGE:
                _fail(
                    "TRANSFER_ROUTE_POLICY_INVALID",
                    "same-provider same-region routes must be zero egress",
                )
            if source or destination:
                _fail(
                    "TRANSFER_ROUTE_POLICY_INVALID",
                    "same-region route policy must not declare geographies",
                )
        elif self.route_class == TransferRouteClass.CROSS_PROVIDER_PUBLIC_INTERNET:
            if self.charge_policy != TransferChargePolicy.SOURCE_PROVIDER_EGRESS:
                _fail(
                    "TRANSFER_ROUTE_POLICY_INVALID",
                    "cross-provider routes must charge source-provider egress",
                )
            if not source or not destination:
                _fail(
                    "TRANSFER_ROUTE_POLICY_INVALID",
                    "cross-provider routes require source and destination geographies",
                )
        else:
            _fail(
                "TRANSFER_ROUTE_POLICY_INVALID",
                "unsupported route classes cannot declare an active policy",
            )
        object.__setattr__(self, "source_geographies", source)
        object.__setattr__(self, "destination_geographies", destination)


@dataclass(frozen=True)
class TransferRouteRegistry:
    """Price-free, closed-world route and region registry."""

    registry_version: str
    region_geographies: Mapping[Provider, Mapping[str, TransferGeography]]
    provider_policies: Mapping[Provider, TransferProviderPolicy]
    supported_routes: Mapping[TransferRouteClass, TransferRoutePolicy]
    unsupported_route_classes: frozenset[TransferRouteClass]

    def __post_init__(self) -> None:
        if not isinstance(self.registry_version, str) or not self.registry_version:
            _fail(
                "TRANSFER_REGISTRY_INVALID",
                "registry_version must be a non-empty string",
            )
        expected_providers = set(Provider)
        if any(
            not isinstance(provider, Provider)
            for provider in self.region_geographies
        ):
            _fail(
                "TRANSFER_REGISTRY_INVALID",
                "region_geographies keys must be Provider values",
            )
        if set(self.region_geographies) != expected_providers:
            _fail(
                "TRANSFER_REGISTRY_INVALID",
                "region_geographies must contain exactly aws, azure, and gcp",
            )
        if any(
            not isinstance(provider, Provider)
            for provider in self.provider_policies
        ):
            _fail(
                "TRANSFER_REGISTRY_INVALID",
                "provider_policies keys must be Provider values",
            )
        if set(self.provider_policies) != expected_providers:
            _fail(
                "TRANSFER_REGISTRY_INVALID",
                "provider_policies must contain exactly aws, azure, and gcp",
            )
        frozen_regions: dict[Provider, Mapping[str, TransferGeography]] = {}
        for provider, regions in self.region_geographies.items():
            if not isinstance(regions, Mapping):
                _fail(
                    "TRANSFER_REGISTRY_INVALID",
                    f"{provider.value} regions must be an object",
                )
            if not regions:
                _fail(
                    "TRANSFER_REGISTRY_INVALID",
                    f"{provider.value} must declare at least one region",
                )
            if any(
                not isinstance(region, str)
                or not _REGION_PATTERN.fullmatch(region)
                or not isinstance(geography, TransferGeography)
                for region, geography in regions.items()
            ):
                _fail(
                    "TRANSFER_REGISTRY_INVALID",
                    f"{provider.value} regions contain invalid values",
                )
            frozen_regions[provider] = MappingProxyType(dict(regions))
        if any(
            not isinstance(policy, TransferProviderPolicy)
            or policy.provider != provider
            for provider, policy in self.provider_policies.items()
        ):
            _fail(
                "TRANSFER_REGISTRY_INVALID",
                "provider policy keys and provider values must match",
            )
        supported = dict(self.supported_routes)
        if any(
            not isinstance(route_class, TransferRouteClass)
            for route_class in supported
        ):
            _fail(
                "TRANSFER_REGISTRY_INVALID",
                "supported_routes keys must be TransferRouteClass values",
            )
        required_supported = {
            TransferRouteClass.SAME_PROVIDER_SAME_REGION,
            TransferRouteClass.CROSS_PROVIDER_PUBLIC_INTERNET,
        }
        if set(supported) != required_supported:
            _fail(
                "TRANSFER_REGISTRY_INVALID",
                "supported_routes must contain same-region and cross-provider routes",
            )
        if any(
            not isinstance(policy, TransferRoutePolicy)
            or policy.route_class != route_class
            for route_class, policy in supported.items()
        ):
            _fail(
                "TRANSFER_REGISTRY_INVALID",
                "supported route keys and policy route classes must match",
            )
        if not isinstance(self.unsupported_route_classes, frozenset):
            _fail(
                "TRANSFER_REGISTRY_INVALID",
                "unsupported_route_classes must be a frozenset",
            )
        if any(
            not isinstance(route_class, TransferRouteClass)
            for route_class in self.unsupported_route_classes
        ):
            _fail(
                "TRANSFER_REGISTRY_INVALID",
                "unsupported_route_classes must contain TransferRouteClass values",
            )
        if self.unsupported_route_classes != frozenset(
            {TransferRouteClass.SAME_PROVIDER_INTER_REGION}
        ):
            _fail(
                "TRANSFER_REGISTRY_INVALID",
                "same_provider_inter_region must be the explicit unsupported route",
            )
        object.__setattr__(
            self,
            "region_geographies",
            MappingProxyType(frozen_regions),
        )
        object.__setattr__(
            self,
            "provider_policies",
            MappingProxyType(dict(self.provider_policies)),
        )
        object.__setattr__(
            self,
            "supported_routes",
            MappingProxyType(supported),
        )

    @classmethod
    def from_document(cls, document: Mapping[str, Any]) -> "TransferRouteRegistry":
        _assert_mapping_keys(
            document,
            {
                "schema_version",
                "registry_version",
                "region_geographies",
                "provider_policies",
                "supported_routes",
                "unsupported_route_classes",
            },
            "transfer_routes.yaml",
        )
        if document["schema_version"] != TRANSFER_ROUTES_SCHEMA_VERSION:
            _fail(
                "TRANSFER_REGISTRY_SCHEMA_INVALID",
                f"expected schema_version {TRANSFER_ROUTES_SCHEMA_VERSION!r}",
            )
        _reject_price_values(document)

        raw_regions = _mapping(document["region_geographies"], "region_geographies")
        _assert_provider_keys(raw_regions, "region_geographies")
        regions: dict[Provider, Mapping[str, TransferGeography]] = {}
        for provider in Provider:
            provider_regions = _mapping(
                raw_regions[provider.value],
                f"region_geographies.{provider.value}",
            )
            parsed_regions: dict[str, TransferGeography] = {}
            for region, geography in provider_regions.items():
                if not isinstance(region, str) or not _REGION_PATTERN.fullmatch(
                    region
                ):
                    _fail(
                        "TRANSFER_REGION_INVALID",
                        f"invalid region {region!r} for {provider.value}",
                    )
                parsed_regions[region] = _enum(
                    TransferGeography,
                    geography,
                    f"region_geographies.{provider.value}.{region}",
                )
            regions[provider] = parsed_regions

        raw_policies = _mapping(
            document["provider_policies"],
            "provider_policies",
        )
        _assert_provider_keys(raw_policies, "provider_policies")
        provider_policies: dict[Provider, TransferProviderPolicy] = {}
        for provider in Provider:
            label = f"provider_policies.{provider.value}"
            raw_policy = _mapping(raw_policies[provider.value], label)
            _assert_mapping_keys(
                raw_policy,
                {"public_route_tier", "billing_scope", "catalog_tier_path"},
                label,
            )
            path = raw_policy["catalog_tier_path"]
            if not isinstance(path, list):
                _fail(
                    "TRANSFER_CATALOG_PATH_INVALID",
                    f"{label}.catalog_tier_path must be a list",
                )
            provider_policies[provider] = TransferProviderPolicy(
                provider=provider,
                public_route_tier=_enum(
                    TransferNetworkTier,
                    raw_policy["public_route_tier"],
                    f"{label}.public_route_tier",
                ),
                billing_scope=_enum(
                    TransferBillingScope,
                    raw_policy["billing_scope"],
                    f"{label}.billing_scope",
                ),
                catalog_tier_path=tuple(path),
            )

        raw_supported = _mapping(
            document["supported_routes"],
            "supported_routes",
        )
        supported_routes: dict[TransferRouteClass, TransferRoutePolicy] = {}
        for raw_class, raw_policy_value in raw_supported.items():
            route_class = _enum(
                TransferRouteClass,
                raw_class,
                f"supported_routes.{raw_class}",
            )
            label = f"supported_routes.{route_class.value}"
            raw_policy = _mapping(raw_policy_value, label)
            if route_class == TransferRouteClass.SAME_PROVIDER_SAME_REGION:
                expected_keys = {"charge_policy"}
            elif (
                route_class
                == TransferRouteClass.CROSS_PROVIDER_PUBLIC_INTERNET
            ):
                expected_keys = {
                    "charge_policy",
                    "source_geographies",
                    "destination_geographies",
                }
            else:
                _fail(
                    "TRANSFER_ROUTE_UNSUPPORTED",
                    f"{route_class.value} cannot be an active route",
                )
            _assert_mapping_keys(raw_policy, expected_keys, label)
            source = _geography_sequence(
                raw_policy.get("source_geographies", []),
                f"{label}.source_geographies",
            )
            destination = _geography_sequence(
                raw_policy.get("destination_geographies", []),
                f"{label}.destination_geographies",
            )
            supported_routes[route_class] = TransferRoutePolicy(
                route_class=route_class,
                charge_policy=_enum(
                    TransferChargePolicy,
                    raw_policy["charge_policy"],
                    f"{label}.charge_policy",
                ),
                source_geographies=source,
                destination_geographies=destination,
            )

        raw_unsupported = document["unsupported_route_classes"]
        if not isinstance(raw_unsupported, list):
            _fail(
                "TRANSFER_REGISTRY_INVALID",
                "unsupported_route_classes must be a list",
            )
        unsupported = frozenset(
            _enum(
                TransferRouteClass,
                value,
                f"unsupported_route_classes[{index}]",
            )
            for index, value in enumerate(raw_unsupported)
        )
        if len(unsupported) != len(raw_unsupported):
            _fail(
                "TRANSFER_REGISTRY_INVALID",
                "unsupported_route_classes must be unique",
            )

        registry_version = document["registry_version"]
        if not isinstance(registry_version, str) or not registry_version.strip():
            _fail(
                "TRANSFER_REGISTRY_INVALID",
                "registry_version must be a non-empty string",
            )

        return cls(
            registry_version=registry_version,
            region_geographies=regions,
            provider_policies=provider_policies,
            supported_routes=supported_routes,
            unsupported_route_classes=unsupported,
        )

    def endpoint(
        self,
        *,
        layer: LayerType,
        provider: Provider,
        region: str,
    ) -> TransferEndpoint:
        if not isinstance(provider, Provider):
            _fail("TRANSFER_PROVIDER_INVALID", "provider must be a Provider")
        if not isinstance(region, str) or not _REGION_PATTERN.fullmatch(region):
            _fail(
                "TRANSFER_REGION_INVALID",
                "region must use a canonical lowercase cloud-region identifier",
            )
        try:
            geography = self.region_geographies[provider][region]
        except KeyError as exc:
            _fail(
                "TRANSFER_REGION_UNMAPPED",
                f"no transfer geography for {provider.value}.{region}",
            )
            raise AssertionError("unreachable") from exc
        return TransferEndpoint(
            layer=layer,
            provider=provider,
            region=region,
            geography=geography,
        )

    def resolve_route(
        self,
        *,
        segment_id: str,
        source: TransferEndpoint,
        destination: TransferEndpoint,
        volume_bytes: Decimal | int | str,
        assumptions: Sequence[str] = (),
    ) -> TransferRouteIntent:
        if not isinstance(source, TransferEndpoint) or not isinstance(
            destination,
            TransferEndpoint,
        ):
            _fail(
                "TRANSFER_ENDPOINTS_INVALID",
                "source and destination must be TransferEndpoint objects",
            )
        route_class = classify_route(source, destination)
        if route_class in self.unsupported_route_classes:
            _fail(
                "TRANSFER_ROUTE_UNSUPPORTED",
                f"route class {route_class.value!r} is unsupported",
            )
        try:
            policy = self.supported_routes[route_class]
        except KeyError as exc:
            _fail(
                "TRANSFER_ROUTE_UNSUPPORTED",
                f"route class {route_class.value!r} has no active policy",
            )
            raise AssertionError("unreachable") from exc
        if (
            policy.source_geographies
            and source.geography not in policy.source_geographies
        ):
            _fail(
                "TRANSFER_ROUTE_UNSUPPORTED",
                f"source geography {source.geography.value!r} is unsupported",
            )
        if (
            policy.destination_geographies
            and destination.geography not in policy.destination_geographies
        ):
            _fail(
                "TRANSFER_ROUTE_UNSUPPORTED",
                f"destination geography {destination.geography.value!r} is unsupported",
            )
        tier = (
            TransferNetworkTier.NOT_APPLICABLE
            if route_class == TransferRouteClass.SAME_PROVIDER_SAME_REGION
            else self.provider_policies[source.provider].public_route_tier
        )
        return TransferRouteIntent(
            segment_id=segment_id,
            source=source,
            destination=destination,
            route_class=route_class,
            network_tier=tier,
            volume_bytes=_decimal(volume_bytes, "volume_bytes"),
            assumptions=tuple(assumptions),
        )


def classify_route(
    source: TransferEndpoint,
    destination: TransferEndpoint,
) -> TransferRouteClass:
    if not isinstance(source, TransferEndpoint) or not isinstance(
        destination,
        TransferEndpoint,
    ):
        _fail(
            "TRANSFER_ENDPOINTS_INVALID",
            "source and destination must be TransferEndpoint objects",
        )
    if source.provider != destination.provider:
        return TransferRouteClass.CROSS_PROVIDER_PUBLIC_INTERNET
    if source.region == destination.region:
        return TransferRouteClass.SAME_PROVIDER_SAME_REGION
    return TransferRouteClass.SAME_PROVIDER_INTER_REGION


def allocate_transfer_pool(
    pool: TransferPricingPool,
    routes: Sequence[TransferRouteIntent],
    *,
    glue_costs: Mapping[str, Decimal | int | str] | None = None,
) -> tuple[TransferSegmentCharge, ...]:
    """Allocate one aggregate tier schedule in deterministic route order."""

    if not isinstance(pool, TransferPricingPool):
        _fail(
            "TRANSFER_POOL_INVALID",
            "pool must be a TransferPricingPool",
        )
    route_tuple = tuple(routes)
    if any(not isinstance(route, TransferRouteIntent) for route in route_tuple):
        _fail(
            "TRANSFER_ROUTE_INVALID",
            "routes must contain only TransferRouteIntent objects",
        )
    if len({route.segment_id for route in route_tuple}) != len(route_tuple):
        _fail(
            "TRANSFER_SEGMENT_DUPLICATE",
            "segment IDs must be unique within a pricing pool",
        )
    if glue_costs is not None and not isinstance(glue_costs, Mapping):
        _fail(
            "TRANSFER_GLUE_COST_INVALID",
            "glue_costs must be a segment-to-cost mapping",
        )
    normalized_glue = {
        segment_id: _decimal(value, f"glue_costs.{segment_id}")
        for segment_id, value in (glue_costs or {}).items()
    }
    unknown_glue = set(normalized_glue) - {
        route.segment_id for route in route_tuple
    }
    if unknown_glue:
        _fail(
            "TRANSFER_GLUE_COST_INVALID",
            "glue costs reference unknown segments: "
            + ", ".join(sorted(unknown_glue)),
        )

    consumed_quantity = Decimal("0")
    charges: list[TransferSegmentCharge] = []
    for route in route_tuple:
        _validate_route_for_pool(pool, route)
        segment_quantity = pool.tier_table.quantity_for_bytes(route.volume_bytes)
        next_quantity = consumed_quantity + segment_quantity
        contributions = pool.tier_table.contributions_between(
            consumed_quantity,
            next_quantity,
        )
        egress_cost = sum(
            (contribution.cost for contribution in contributions),
            Decimal("0"),
        )
        glue_cost = normalized_glue.get(route.segment_id, Decimal("0"))
        charges.append(
            TransferSegmentCharge(
                route=route,
                pool_id=pool.pool_id,
                tier_contributions=contributions,
                egress_cost=egress_cost,
                glue_cost=glue_cost,
                total_cost=egress_cost + glue_cost,
                assumptions=route.assumptions,
            )
        )
        consumed_quantity = next_quantity

    expected_egress = pool.tier_table.cost_between(
        Decimal("0"),
        consumed_quantity,
    )
    allocated_egress = sum(
        (charge.egress_cost for charge in charges),
        Decimal("0"),
    )
    if allocated_egress != expected_egress:
        _fail(
            "TRANSFER_ALLOCATION_INVALID",
            "allocated segment egress does not equal aggregate pool cost",
        )
    return tuple(charges)


def _validate_route_for_pool(
    pool: TransferPricingPool,
    route: TransferRouteIntent,
) -> None:
    if route.route_class != pool.route_class:
        _fail(
            "TRANSFER_POOL_MISMATCH",
            f"segment {route.segment_id!r} route class does not match pool",
        )
    if route.source.provider != pool.provider:
        _fail(
            "TRANSFER_POOL_MISMATCH",
            f"segment {route.segment_id!r} source provider does not match pool",
        )
    if route.source.geography != pool.source_geography:
        _fail(
            "TRANSFER_POOL_MISMATCH",
            f"segment {route.segment_id!r} source geography does not match pool",
        )
    if route.destination.geography != pool.destination_geography:
        _fail(
            "TRANSFER_POOL_MISMATCH",
            f"segment {route.segment_id!r} destination geography does not match pool",
        )
    if route.network_tier != pool.network_tier:
        _fail(
            "TRANSFER_POOL_MISMATCH",
            f"segment {route.segment_id!r} network tier does not match pool",
        )


def _decimal(value: Any, label: str) -> Decimal:
    if isinstance(value, bool):
        _fail(
            "TRANSFER_QUANTITY_INVALID",
            f"{label} must be a finite non-negative number",
        )
    try:
        normalized = value if isinstance(value, Decimal) else Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise TransferPricingContractError(
            "TRANSFER_QUANTITY_INVALID",
            f"{label} must be a finite non-negative number",
        ) from exc
    if not normalized.is_finite() or normalized < 0:
        _fail(
            "TRANSFER_QUANTITY_INVALID",
            f"{label} must be a finite non-negative number",
        )
    return normalized


def _validated_assumptions(values: Sequence[str]) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
        _fail(
            "TRANSFER_ASSUMPTION_INVALID",
            "assumptions must be a sequence of non-empty strings",
        )
    try:
        normalized = tuple(values)
    except TypeError as exc:
        raise TransferPricingContractError(
            "TRANSFER_ASSUMPTION_INVALID",
            "assumptions must be a sequence of non-empty strings",
        ) from exc
    if any(not isinstance(value, str) or not value.strip() for value in normalized):
        _fail(
            "TRANSFER_ASSUMPTION_INVALID",
            "assumptions must be non-empty strings",
        )
    return normalized


def _validate_identifier(label: str, value: Any) -> None:
    if not isinstance(value, str) or not _IDENTIFIER_PATTERN.fullmatch(value):
        _fail(
            "TRANSFER_IDENTIFIER_INVALID",
            f"{label} must be a canonical identifier",
        )


def _mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        _fail("TRANSFER_REGISTRY_INVALID", f"{label} must be an object")
    return value


def _assert_mapping_keys(
    value: Mapping[str, Any],
    expected: set[str],
    label: str,
) -> None:
    actual = set(value)
    missing = expected - actual
    unknown = actual - expected
    if missing:
        _fail(
            "TRANSFER_REGISTRY_INVALID",
            f"{label} is missing fields: {', '.join(sorted(missing))}",
        )
    if unknown:
        _fail(
            "TRANSFER_REGISTRY_INVALID",
            f"{label} has unknown fields: "
            + ", ".join(sorted(str(item) for item in unknown)),
        )


def _assert_provider_keys(value: Mapping[str, Any], label: str) -> None:
    expected = {provider.value for provider in Provider}
    actual = set(value)
    if actual != expected:
        _fail(
            "TRANSFER_REGISTRY_INVALID",
            f"{label} must contain exactly aws, azure, and gcp",
        )


def _enum(enum_type: type[Enum], value: Any, label: str):
    try:
        return enum_type(value)
    except (TypeError, ValueError) as exc:
        _fail(
            "TRANSFER_REGISTRY_ENUM_INVALID",
            f"{label} has unsupported value {value!r}",
        )
        raise AssertionError("unreachable") from exc


def _geography_sequence(
    value: Any,
    label: str,
) -> tuple[TransferGeography, ...]:
    if not isinstance(value, list):
        _fail("TRANSFER_REGISTRY_INVALID", f"{label} must be a list")
    return tuple(
        _enum(TransferGeography, item, f"{label}[{index}]")
        for index, item in enumerate(value)
    )


def _reject_price_values(value: Any, path: str = "transfer_routes.yaml") -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            normalized_key = str(key).lower()
            if normalized_key in _FORBIDDEN_PRICE_KEYS:
                _fail(
                    "TRANSFER_REGISTRY_PRICE_FORBIDDEN",
                    f"{path}.{key} must not define pricing values",
                )
            _reject_price_values(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _reject_price_values(child, f"{path}[{index}]")


def _fail(code: str, message: str) -> None:
    raise TransferPricingContractError(code, message)
