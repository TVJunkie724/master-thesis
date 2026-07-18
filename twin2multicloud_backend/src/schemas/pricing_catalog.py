"""Strict cross-service contracts for immutable pricing catalog references."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import re
from types import MappingProxyType
from typing import Any, Literal, Mapping

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator, model_validator


Provider = Literal["aws", "azure", "gcp"]
CatalogSource = Literal[
    "provider_api",
    "official_static_documentation",
    "official_calculator_reference",
    "curated_model_constant",
    "reviewed_baseline",
]
CalculationSource = Literal["fresh", "last_known_good", "reviewed_baseline"]

_DIGEST_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")
_SNAPSHOT_ID_PATTERN = re.compile(r"^pcs_[0-9a-f]{64}$")
_REGION_PATTERN = re.compile(r"^[a-z][a-z0-9-]{1,62}$")
_AWS_REGION_PATTERN = re.compile(r"^[a-z]{2}(?:-gov)?-[a-z0-9-]+-\d+$")


def _to_camel(value: str) -> str:
    head, *tail = value.split("_")
    return head + "".join(part.capitalize() for part in tail)


class PricingCatalogReference(BaseModel):
    """One immutable provider-region pricing identity."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        allow_inf_nan=False,
        populate_by_name=True,
        alias_generator=_to_camel,
    )

    schema_version: Literal["pricing-catalog-reference.v1"]
    snapshot_id: str = Field(pattern=_SNAPSHOT_ID_PATTERN.pattern)
    provider: Provider
    pricing_region: str = Field(pattern=_REGION_PATTERN.pattern)
    provider_schema_version: str = Field(min_length=1, max_length=128)
    contract_version: str = Field(min_length=1, max_length=128)
    registry_version: str = Field(min_length=1, max_length=128)
    mapping_versions: tuple[str, ...]
    fetched_at: datetime
    content_digest: str = Field(pattern=_DIGEST_PATTERN.pattern)
    source: CatalogSource
    review_status: Literal["reviewed"]
    publication_status: Literal["published"]
    calculation_source: CalculationSource

    @field_validator("mapping_versions")
    @classmethod
    def validate_mapping_versions(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if not value:
            raise ValueError("mapping_versions must not be empty")
        if any(not item or len(item) > 128 for item in value):
            raise ValueError("mapping_versions contains an invalid version")
        if tuple(sorted(set(value))) != value:
            raise ValueError("mapping_versions must be sorted and unique")
        return value

    @field_validator("fetched_at")
    @classmethod
    def validate_fetched_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("fetched_at must be timezone-aware")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def validate_provider_region(self) -> "PricingCatalogReference":
        if self.provider == "aws" and not _AWS_REGION_PATTERN.fullmatch(
            self.pricing_region
        ):
            raise ValueError("AWS pricing_region is invalid")
        if (self.source == "reviewed_baseline") != (
            self.calculation_source == "reviewed_baseline"
        ):
            raise ValueError(
                "reviewed_baseline source and calculation_source must agree"
            )
        expected_snapshot_id = build_pricing_catalog_snapshot_id(
            provider=self.provider,
            pricing_region=self.pricing_region,
            provider_schema_version=self.provider_schema_version,
            contract_version=self.contract_version,
            registry_version=self.registry_version,
            mapping_versions=self.mapping_versions,
            fetched_at=self.fetched_at,
            content_digest=self.content_digest,
            source=self.source,
            review_status=self.review_status,
        )
        if self.snapshot_id != expected_snapshot_id:
            raise ValueError("snapshot_id does not match reference identity")
        return self

    def to_http_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json", by_alias=True)


class PricingCatalogContext(BaseModel):
    """Exact reviewed AWS, Azure, and GCP references for one calculation."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        populate_by_name=True,
        alias_generator=_to_camel,
    )

    schema_version: Literal["provider-pricing-catalog-context.v1"]
    catalogs: Mapping[Provider, PricingCatalogReference]

    @model_validator(mode="after")
    def validate_catalogs(self) -> "PricingCatalogContext":
        if set(self.catalogs) != {"aws", "azure", "gcp"}:
            raise ValueError("catalogs must contain exactly aws, azure, and gcp")
        for provider, reference in self.catalogs.items():
            if provider != reference.provider:
                raise ValueError("catalog map key must equal reference provider")
        object.__setattr__(self, "catalogs", MappingProxyType(dict(self.catalogs)))
        return self

    @field_serializer("catalogs")
    def serialize_catalogs(
        self,
        value: Mapping[Provider, PricingCatalogReference],
    ) -> dict[str, dict[str, Any]]:
        return {
            provider: reference.to_http_dict()
            for provider, reference in sorted(value.items())
        }

    def to_http_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json", by_alias=True)

    def canonical_json(self) -> str:
        return self.model_dump_json(by_alias=True)


def build_pricing_catalog_snapshot_id(
    *,
    provider: str,
    pricing_region: str,
    provider_schema_version: str,
    contract_version: str,
    registry_version: str,
    mapping_versions: tuple[str, ...] | list[str],
    fetched_at: datetime,
    content_digest: str,
    source: str,
    review_status: str,
) -> str:
    """Build the cross-runtime immutable reference identity."""

    identity = {
        "provider": provider,
        "pricing_region": pricing_region,
        "provider_schema_version": provider_schema_version,
        "contract_version": contract_version,
        "registry_version": registry_version,
        "mapping_versions": list(mapping_versions),
        "fetched_at": fetched_at.astimezone(timezone.utc)
        .isoformat()
        .replace("+00:00", "Z"),
        "content_digest": content_digest,
        "source": source,
        "review_status": review_status,
    }
    encoded = json.dumps(
        identity,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")
    return f"pcs_{hashlib.sha256(encoded).hexdigest()}"
