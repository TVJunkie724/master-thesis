"""Strict contracts for immutable provider pricing catalog snapshots."""

from __future__ import annotations

from copy import deepcopy
from collections.abc import Mapping
from datetime import datetime, timezone
import hashlib
import json
import re
from types import MappingProxyType
from typing import Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_serializer,
    field_validator,
    model_validator,
)

from backend.pricing_schema import canonical_pricing_snapshot_digest


CATALOG_SNAPSHOT_SCHEMA_VERSION = "pricing-catalog-snapshot.v2"
CATALOG_REFERENCE_SCHEMA_VERSION = "pricing-catalog-reference.v1"
CATALOG_CONTEXT_SCHEMA_VERSION = "provider-pricing-catalog-context.v1"
CATALOG_BASELINE_SCHEMA_VERSION = "pricing-catalog-baseline.v1"

Provider = Literal["aws", "azure", "gcp"]
CatalogSource = Literal[
    "provider_api",
    "official_static_documentation",
    "official_calculator_reference",
    "curated_model_constant",
    "reviewed_baseline",
]
ReviewStatus = Literal["reviewed", "review_required"]
PublicationStatus = Literal["published", "candidate"]
CalculationSource = Literal["fresh", "last_known_good", "reviewed_baseline"]

_DIGEST_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")
_SNAPSHOT_ID_PATTERN = re.compile(r"^pcs_[0-9a-f]{64}$")
_REGION_PATTERN = re.compile(r"^[a-z][a-z0-9-]{1,62}$")
_AWS_REGION_PATTERN = re.compile(r"^[a-z]{2}(?:-gov)?-[a-z0-9-]+-\d+$")


def _to_camel(value: str) -> str:
    head, *tail = value.split("_")
    return head + "".join(part.capitalize() for part in tail)


class PricingCatalogContractError(ValueError):
    """Raised when a pricing catalog contract is internally inconsistent."""


class PricingCatalogReference(BaseModel):
    """Immutable identity for one provider-region catalog observation."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        allow_inf_nan=False,
        populate_by_name=True,
        alias_generator=_to_camel,
    )

    schema_version: Literal["pricing-catalog-reference.v1"] = (
        CATALOG_REFERENCE_SCHEMA_VERSION
    )
    snapshot_id: str
    provider: Provider
    pricing_region: str
    provider_schema_version: str = Field(min_length=1, max_length=128)
    contract_version: str = Field(min_length=1, max_length=128)
    registry_version: str = Field(min_length=1, max_length=128)
    mapping_versions: tuple[str, ...]
    fetched_at: datetime
    content_digest: str
    source: CatalogSource
    review_status: ReviewStatus
    publication_status: PublicationStatus
    calculation_source: CalculationSource

    @field_validator("snapshot_id")
    @classmethod
    def validate_snapshot_id(cls, value: str) -> str:
        if not _SNAPSHOT_ID_PATTERN.fullmatch(value):
            raise ValueError("snapshot_id must use the pcs_<sha256> format")
        return value

    @field_validator("pricing_region")
    @classmethod
    def validate_pricing_region(cls, value: str) -> str:
        if not _REGION_PATTERN.fullmatch(value):
            raise ValueError("pricing_region must be canonical")
        return value

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

    @field_validator("content_digest")
    @classmethod
    def validate_content_digest(cls, value: str) -> str:
        if not _DIGEST_PATTERN.fullmatch(value):
            raise ValueError("content_digest must be a lowercase SHA-256 digest")
        return value

    @model_validator(mode="after")
    def validate_cross_fields(self) -> "PricingCatalogReference":
        if self.provider == "aws" and not _AWS_REGION_PATTERN.fullmatch(
            self.pricing_region
        ):
            raise ValueError("AWS pricing_region is invalid")
        if self.publication_status == "published" and self.review_status != "reviewed":
            raise ValueError("Only reviewed references may be published")
        if (
            self.review_status == "review_required"
            and self.publication_status != "candidate"
        ):
            raise ValueError("Review-required references must remain candidates")
        if (self.source == "reviewed_baseline") != (
            self.calculation_source == "reviewed_baseline"
        ):
            raise ValueError(
                "reviewed_baseline source and calculation_source must agree"
            )
        expected_snapshot_id = build_snapshot_id(
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

    def to_storage_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")

    def to_http_dict(self) -> dict[str, Any]:
        return {
            "schemaVersion": self.schema_version,
            "snapshotId": self.snapshot_id,
            "provider": self.provider,
            "pricingRegion": self.pricing_region,
            "providerSchemaVersion": self.provider_schema_version,
            "contractVersion": self.contract_version,
            "registryVersion": self.registry_version,
            "mappingVersions": list(self.mapping_versions),
            "fetchedAt": _utc_iso(self.fetched_at),
            "contentDigest": self.content_digest,
            "source": self.source,
            "reviewStatus": self.review_status,
            "publicationStatus": self.publication_status,
            "calculationSource": self.calculation_source,
        }


class PricingCatalogSnapshot(BaseModel):
    """One immutable pricing payload and its verified identity."""

    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)

    schema_version: Literal["pricing-catalog-snapshot.v2"] = (
        CATALOG_SNAPSHOT_SCHEMA_VERSION
    )
    reference: PricingCatalogReference
    pricing: dict[str, Any]

    @model_validator(mode="after")
    def validate_pricing_digest(self) -> "PricingCatalogSnapshot":
        actual_digest = canonical_pricing_snapshot_digest(self.pricing)
        if actual_digest != self.reference.content_digest:
            raise ValueError("pricing content does not match content_digest")
        return self

    def detached_copy(self) -> "PricingCatalogSnapshot":
        return PricingCatalogSnapshot.model_validate(
            deepcopy(self.model_dump(mode="json"))
        )

    def to_storage_dict(self) -> dict[str, Any]:
        return deepcopy(self.model_dump(mode="json"))


class PricingCatalogContext(BaseModel):
    """Exact three-provider pricing context required by a calculation."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        populate_by_name=True,
        alias_generator=_to_camel,
    )

    schema_version: Literal["provider-pricing-catalog-context.v1"] = (
        CATALOG_CONTEXT_SCHEMA_VERSION
    )
    catalogs: Mapping[Provider, PricingCatalogReference]

    @model_validator(mode="after")
    def validate_provider_map(self) -> "PricingCatalogContext":
        if set(self.catalogs) != {"aws", "azure", "gcp"}:
            raise ValueError("catalogs must contain exactly aws, azure, and gcp")
        for key, reference in self.catalogs.items():
            if key != reference.provider:
                raise ValueError("catalog map key must equal reference provider")
            if reference.review_status != "reviewed":
                raise ValueError("calculation catalogs must be reviewed")
            if reference.publication_status != "published":
                raise ValueError("calculation catalogs must be published")
        object.__setattr__(self, "catalogs", MappingProxyType(dict(self.catalogs)))
        return self

    @field_serializer("catalogs")
    def serialize_catalogs(
        self,
        value: Mapping[Provider, PricingCatalogReference],
    ) -> dict[str, dict[str, Any]]:
        return {
            provider: reference.to_storage_dict()
            for provider, reference in sorted(value.items())
        }

    def to_http_dict(self) -> dict[str, Any]:
        return {
            "schemaVersion": self.schema_version,
            "catalogs": {
                provider: reference.to_http_dict()
                for provider, reference in sorted(self.catalogs.items())
            },
        }


class PricingCatalogBaselineManifest(BaseModel):
    """Pinned repository baseline references."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["pricing-catalog-baseline.v1"] = (
        CATALOG_BASELINE_SCHEMA_VERSION
    )
    catalogs: Mapping[Provider, PricingCatalogReference]

    @model_validator(mode="after")
    def validate_catalogs(self) -> "PricingCatalogBaselineManifest":
        context = PricingCatalogContext(catalogs=self.catalogs)
        for reference in context.catalogs.values():
            if reference.source != "reviewed_baseline":
                raise ValueError("baseline references must use reviewed_baseline source")
            if reference.calculation_source != "reviewed_baseline":
                raise ValueError(
                    "baseline references must use reviewed_baseline calculation source"
                )
        object.__setattr__(self, "catalogs", MappingProxyType(dict(self.catalogs)))
        return self

    def to_storage_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "catalogs": {
                provider: reference.to_storage_dict()
                for provider, reference in sorted(self.catalogs.items())
            },
        }


def build_pricing_catalog_reference(
    *,
    provider: Provider,
    pricing_region: str,
    pricing: dict[str, Any],
    provider_schema_version: str,
    contract_version: str,
    registry_version: str,
    mapping_versions: tuple[str, ...] | list[str],
    fetched_at: datetime,
    source: CatalogSource,
    review_status: ReviewStatus,
    calculation_source: CalculationSource,
) -> PricingCatalogReference:
    """Construct a reference from canonical identity inputs."""

    normalized_region = canonicalize_pricing_region(provider, pricing_region)
    normalized_mappings = tuple(sorted(set(mapping_versions)))
    normalized_fetched_at = _require_utc(fetched_at)
    content_digest = canonical_pricing_snapshot_digest(pricing)
    snapshot_id = build_snapshot_id(
        provider=provider,
        pricing_region=normalized_region,
        provider_schema_version=provider_schema_version,
        contract_version=contract_version,
        registry_version=registry_version,
        mapping_versions=normalized_mappings,
        fetched_at=normalized_fetched_at,
        content_digest=content_digest,
        source=source,
        review_status=review_status,
    )
    return PricingCatalogReference(
        snapshot_id=snapshot_id,
        provider=provider,
        pricing_region=normalized_region,
        provider_schema_version=provider_schema_version,
        contract_version=contract_version,
        registry_version=registry_version,
        mapping_versions=normalized_mappings,
        fetched_at=normalized_fetched_at,
        content_digest=content_digest,
        source=source,
        review_status=review_status,
        publication_status=(
            "published" if review_status == "reviewed" else "candidate"
        ),
        calculation_source=calculation_source,
    )


def build_snapshot_id(
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
    identity = {
        "provider": provider,
        "pricing_region": pricing_region,
        "provider_schema_version": provider_schema_version,
        "contract_version": contract_version,
        "registry_version": registry_version,
        "mapping_versions": list(mapping_versions),
        "fetched_at": _utc_iso(_require_utc(fetched_at)),
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


def canonicalize_pricing_region(provider: str, region: str) -> str:
    if not isinstance(region, str):
        raise PricingCatalogContractError("pricing region must be a string")
    canonical = region.strip().lower().replace("_", "-").replace(" ", "")
    if not _REGION_PATTERN.fullmatch(canonical):
        raise PricingCatalogContractError("pricing region is not canonical")
    if provider == "aws" and not _AWS_REGION_PATTERN.fullmatch(canonical):
        raise PricingCatalogContractError("AWS pricing region is invalid")
    if provider not in {"aws", "azure", "gcp"}:
        raise PricingCatalogContractError("unsupported pricing provider")
    return canonical


def canonical_json_bytes(payload: dict[str, Any]) -> bytes:
    return (
        json.dumps(
            payload,
            sort_keys=True,
            indent=2,
            ensure_ascii=True,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def _require_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise PricingCatalogContractError("timestamp must be timezone-aware")
    return value.astimezone(timezone.utc)


def _utc_iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
