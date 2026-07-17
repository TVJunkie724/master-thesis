"""
Canonical provider pricing schema and quality metadata.

Static fallback values are intentionally treated as review-required emergency
values. They keep calculations from crashing, but they are not publishable fresh
provider evidence.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import re
from typing import Any


PRICING_SCHEMA_VERSION = "pricing-provider-schema.v1"
PRICING_CONTRACT_VERSION = "2026.07.17"
SHA256_DIGEST_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")
AWS_REGION_PATTERN = re.compile(r"^[a-z]{2}(?:-gov)?-[a-z0-9-]+-\d+$")

RESERVED_PRICING_KEYS = {
    "__schema__",
    "__quality__",
    "__evidence__",
    "__publication__",
    "__account_pricing_context__",
}

FETCHED = "fetched"
DERIVED = "derived"
CURATED = "curated"
FALLBACK_STATIC = "fallback_static"
FALLBACK_DEFAULT = "fallback_default"
UNSUPPORTED = "unsupported"

PUBLISHABLE = "publishable"
REVIEW_REQUIRED = "review_required"


EXPECTED_PRICING_SCHEMA: dict[str, dict[str, list[str]]] = {
    "aws": {
        "transfer": ["pricing_tiers", "egressPrice"],
        "iotCore": ["pricePerDeviceAndMonth", "priceRulesTriggered", "pricing_tiers"],
        "lambda": ["requestPrice", "durationPrice", "freeRequests", "freeComputeTime"],
        "dynamoDB": ["writePrice", "readPrice", "storagePrice", "freeStorage"],
        "s3InfrequentAccess": [
            "storagePrice",
            "upfrontPrice",
            "requestPrice",
            "dataRetrievalPrice",
            "transferCostFromDynamoDB",
            "transferCostFromCosmosDB",
        ],
        "s3GlacierDeepArchive": [
            "storagePrice",
            "lifecycleAndWritePrice",
            "dataRetrievalPrice",
        ],
        "iotTwinMaker": [
            "usageRates",
            "tieredBundle",
        ],
        "awsManagedGrafana": ["editorPrice", "viewerPrice"],
        "stepFunctions": ["pricePer1kStateTransitions", "pricePerStateTransition"],
        "eventBridge": ["pricePerMillionEvents"],
        "apiGateway": ["pricePerMillionCalls", "dataTransferOutPrice"],
        "scheduler": ["jobPrice"],
    },
    "azure": {
        "transfer": ["pricing_tiers"],
        "iotHub": ["pricing_tiers"],
        "functions": ["requestPrice", "durationPrice", "freeRequests", "freeComputeTime"],
        "cosmosDB": [
            "requestPrice",
            "minimumRequestUnits",
            "RUsPerRead",
            "RUsPerWrite",
            "storagePrice",
        ],
        "blobStorageCool": [
            "storagePrice",
            "upfrontPrice",
            "writePrice",
            "readPrice",
            "dataRetrievalPrice",
            "transferCostFromCosmosDB",
        ],
        "blobStorageArchive": ["storagePrice", "writePrice", "dataRetrievalPrice"],
        "azureDigitalTwins": [
            "pricePerMessage",
            "pricePerOperation",
            "pricePerQueryUnit",
        ],
        "azureManagedGrafana": ["userPrice", "hourlyPrice"],
        "logicApps": ["pricePer1kStateTransitions", "pricePerStateTransition"],
        "eventGrid": ["pricePerMillionEvents"],
        "apiManagement": ["pricePerMillionCalls"],
    },
    "gcp": {
        "transfer": ["pricing_tiers", "egressPrice"],
        "iot": ["pricePerGiB", "pricePerDeviceAndMonth"],
        "functions": ["requestPrice", "durationPrice", "freeRequests", "freeComputeTime"],
        "storage_hot": ["writePrice", "readPrice", "storagePrice", "freeStorage"],
        "storage_cool": [
            "storagePrice",
            "upfrontPrice",
            "requestPrice",
            "dataRetrievalPrice",
        ],
        "storage_archive": [
            "storagePrice",
            "lifecycleAndWritePrice",
            "dataRetrievalPrice",
        ],
        "twinmaker": ["e2MediumPrice", "storagePrice"],
        "grafana": ["e2MediumPrice", "storagePrice"],
        "apiGateway": ["pricePerMillionCalls", "dataTransferOutPrice"],
        "cloudWorkflows": ["stepPrice"],
        "cloudScheduler": ["jobPrice"],
    },
}


PROVIDER_SERVICE_TO_NEUTRAL = {
    "aws": {
        "transfer": "transfer",
        "iotCore": "iot",
        "lambda": "functions",
        "dynamoDB": "storage_hot",
        "s3InfrequentAccess": "storage_cool",
        "s3GlacierDeepArchive": "storage_archive",
        "iotTwinMaker": "twinmaker",
        "awsManagedGrafana": "grafana",
        "stepFunctions": "orchestration",
        "eventBridge": "event_bus",
        "apiGateway": "data_access",
        "scheduler": "scheduler",
    },
    "azure": {
        "transfer": "transfer",
        "iotHub": "iot",
        "functions": "functions",
        "cosmosDB": "storage_hot",
        "blobStorageCool": "storage_cool",
        "blobStorageArchive": "storage_archive",
        "azureDigitalTwins": "twinmaker",
        "azureManagedGrafana": "grafana",
        "logicApps": "orchestration",
        "eventGrid": "event_bus",
        "apiManagement": "data_access",
    },
    "gcp": {
        "transfer": "transfer",
        "iot": "iot",
        "functions": "functions",
        "storage_hot": "storage_hot",
        "storage_cool": "storage_cool",
        "storage_archive": "storage_archive",
        "twinmaker": "twinmaker",
        "grafana": "grafana",
        "apiGateway": "data_access",
        "cloudWorkflows": "orchestration",
        "cloudScheduler": "scheduler",
    },
}


DERIVED_FIELDS = {
    "aws": {
        "s3InfrequentAccess.transferCostFromDynamoDB",
        "s3InfrequentAccess.transferCostFromCosmosDB",
        "stepFunctions.pricePerStateTransition",
        "apiGateway.dataTransferOutPrice",
    },
    "azure": {
        "blobStorageCool.transferCostFromCosmosDB",
        "logicApps.pricePerStateTransition",
    },
    "gcp": {
        "twinmaker.e2MediumPrice",
        "grafana.e2MediumPrice",
        "apiGateway.dataTransferOutPrice",
        "apiGateway.pricePerMillionCalls",
    },
}


DERIVED_FIELD_DEPENDENCIES = {
    "aws": {
        "s3InfrequentAccess.transferCostFromDynamoDB": ("transfer", "egressPrice"),
        "s3InfrequentAccess.transferCostFromCosmosDB": ("transfer", "egressPrice"),
        "stepFunctions.pricePerStateTransition": (
            "orchestration",
            "pricePer1kStateTransitions",
        ),
        "apiGateway.dataTransferOutPrice": ("transfer", "egressPrice"),
    },
    "azure": {
        "blobStorageCool.transferCostFromCosmosDB": ("transfer", "egressPrice"),
        "logicApps.pricePerStateTransition": (
            "orchestration",
            "pricePer1kStateTransitions",
        ),
    },
    "gcp": {
        "twinmaker.e2MediumPrice": (
            "twinmaker",
            ("e2CorePrice", "e2RamPrice"),
        ),
        "grafana.e2MediumPrice": (
            "grafana",
            ("e2CorePrice", "e2RamPrice"),
        ),
        "apiGateway.dataTransferOutPrice": ("transfer", "egressPrice"),
        "apiGateway.pricePerMillionCalls": ("data_access", "pricePerMillionCalls"),
    },
}


CURATED_FIELDS = {
    "aws": {
        "lambda.freeRequests",
        "lambda.freeComputeTime",
        "dynamoDB.freeStorage",
        "s3InfrequentAccess.upfrontPrice",
        "transfer.pricing_tiers",
    },
    "azure": {
        "blobStorageCool.upfrontPrice",
        "cosmosDB.minimumRequestUnits",
        "cosmosDB.RUsPerRead",
        "cosmosDB.RUsPerWrite",
        "functions.freeRequests",
        "functions.freeComputeTime",
    },
    "gcp": {
        "transfer.pricing_tiers",
    },
}


def validate_pricing_payload(provider: str, data: dict[str, Any]) -> dict[str, Any]:
    if not data:
        return _validation_result(provider, "missing", [])

    provider_schema = EXPECTED_PRICING_SCHEMA.get(provider)
    if not provider_schema:
        return _validation_result(provider, "unknown_provider", [])

    payload = strip_pricing_metadata(data)
    missing_keys: list[str] = []
    for service, keys in provider_schema.items():
        service_data = payload.get(service)
        if service_data is None:
            missing_keys.append(f"{service} (missing service)")
            continue
        if not isinstance(service_data, dict):
            missing_keys.append(f"{service} (invalid service)")
            continue
        for key in keys:
            if key not in service_data:
                missing_keys.append(f"{service}.{key}")

    if provider == "aws":
        missing_keys.extend(_validate_aws_twinmaker_contract(payload))
        missing_keys.extend(_validate_aws_snapshot_metadata(data))

    missing_keys = sorted(set(missing_keys))
    status = "incomplete" if missing_keys else "valid"
    quality = data.get("__quality__")
    fallback_fields = list((quality or {}).get("fallback_fields", []))
    unsupported_fields = list((quality or {}).get("unsupported_fields", []))
    quality_status = (
        PUBLISHABLE
        if quality and not fallback_fields and not unsupported_fields
        else REVIEW_REQUIRED
    )
    return _validation_result(
        provider,
        status,
        missing_keys,
        quality_status=quality_status,
        fallback_fields=fallback_fields,
        unsupported_fields=unsupported_fields,
    )


def attach_pricing_metadata(
    provider: str,
    pricing: dict[str, Any],
    fetched: dict[str, dict[str, Any]] | None = None,
    *,
    pricing_region: str | None = None,
) -> dict[str, Any]:
    payload = deepcopy(pricing)
    field_sources = build_field_sources(provider, payload, fetched or {})
    fallback_fields = sorted(
        path
        for path, source in field_sources.items()
        if source in {FALLBACK_STATIC, FALLBACK_DEFAULT}
    )
    unsupported_fields = sorted(
        path for path, source in field_sources.items() if source == UNSUPPORTED
    )
    schema = {
        "schema_version": PRICING_SCHEMA_VERSION,
        "contract_version": PRICING_CONTRACT_VERSION,
        "provider": provider,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    if provider == "aws":
        if (
            not isinstance(pricing_region, str)
            or not AWS_REGION_PATTERN.fullmatch(pricing_region)
        ):
            raise ValueError(
                "A valid pricing_region is required for AWS pricing snapshots."
            )
        schema["pricing_region"] = pricing_region
    payload["__schema__"] = schema
    payload["__quality__"] = {
        "quality_status": (
            REVIEW_REQUIRED if fallback_fields or unsupported_fields else PUBLISHABLE
        ),
        "review_required": bool(fallback_fields or unsupported_fields),
        "field_sources": field_sources,
        "fallback_fields": fallback_fields,
        "unsupported_fields": unsupported_fields,
    }
    evidence = _build_generated_evidence(provider, fetched or {})
    if evidence:
        payload["__evidence__"] = evidence
    if provider == "aws":
        payload["__schema__"]["snapshot_digest"] = (
            canonical_pricing_snapshot_digest(payload)
        )
    return payload


def _build_generated_evidence(
    provider: str,
    fetched: dict[str, dict[str, Any]],
) -> dict[str, Any] | None:
    if provider == "aws":
        twinmaker_evidence = (fetched.get("twinmaker") or {}).get("__evidence__")
        if not twinmaker_evidence:
            return None
        return {
            "schema_version": "pricing-generated-evidence.v1",
            "provider": provider,
            "services": {
                "iotTwinMaker": deepcopy(twinmaker_evidence),
            },
        }
    if provider != "azure":
        return None
    neutral_to_service = {
        neutral: service
        for service, neutral in PROVIDER_SERVICE_TO_NEUTRAL[provider].items()
    }
    fields: dict[str, Any] = {}
    for neutral_service, fetched_values in fetched.items():
        provider_service = neutral_to_service.get(neutral_service)
        if not provider_service or not isinstance(fetched_values, dict):
            continue
        field_evidence = fetched_values.get("__evidence__") or {}
        for field_key, record in field_evidence.items():
            fields[f"{provider_service}.{field_key}"] = record

    transfer_record = fields.get("transfer.pricing_tiers")
    if transfer_record:
        fields["blobStorageCool.transferCostFromCosmosDB"] = {
            "schema_version": "pricing-derived-evidence.v1",
            "source_type": DERIVED,
            "field_path": "blobStorageCool.transferCostFromCosmosDB",
            "depends_on": "transfer.pricing_tiers",
            "derivation": "first positive normalized transfer tier price",
            "normalized_value": next(
                (
                    tier.get("price")
                    for tier in transfer_record.get("normalized_tiers", [])
                    if isinstance(tier.get("price"), (int, float))
                    and tier["price"] > 0
                ),
                None,
            ),
        }
    if not fields:
        return None
    return {
        "schema_version": "pricing-generated-evidence.v1",
        "provider": provider,
        "fields": dict(sorted(fields.items())),
    }


def build_field_sources(
    provider: str,
    pricing: dict[str, Any],
    fetched: dict[str, dict[str, Any]],
) -> dict[str, str]:
    provider_schema = EXPECTED_PRICING_SCHEMA.get(provider, {})
    service_to_neutral = PROVIDER_SERVICE_TO_NEUTRAL.get(provider, {})
    sources: dict[str, str] = {}

    for service, keys in provider_schema.items():
        neutral_service = service_to_neutral.get(service)
        fetched_values = fetched.get(neutral_service, {}) if neutral_service else {}
        for key in keys:
            path = f"{service}.{key}"
            if path in DERIVED_FIELDS.get(provider, set()) and _derived_field_is_fetched(
                provider,
                path,
                fetched,
            ):
                sources[path] = DERIVED
            elif path in CURATED_FIELDS.get(provider, set()):
                sources[path] = CURATED
            elif _source_field_is_fetched(provider, service, key, fetched_values):
                sources[path] = FETCHED
            elif service in pricing and key in pricing.get(service, {}):
                sources[path] = FALLBACK_STATIC
            else:
                sources[path] = UNSUPPORTED
    return dict(sorted(sources.items()))


def strip_pricing_metadata(data: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in data.items() if key not in RESERVED_PRICING_KEYS}


def canonical_pricing_snapshot_digest(data: dict[str, Any]) -> str:
    """Return a stable digest for public pricing data and stable metadata."""

    canonical = deepcopy(data)
    canonical.pop("__account_pricing_context__", None)
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


def _validate_aws_snapshot_metadata(data: dict[str, Any]) -> list[str]:
    schema = data.get("__schema__")
    if schema is None:
        return []
    if not isinstance(schema, dict):
        return ["__schema__ (invalid object)"]

    missing: list[str] = []
    region = schema.get("pricing_region")
    if not isinstance(region, str) or not AWS_REGION_PATTERN.fullmatch(region):
        missing.append("__schema__.pricing_region")

    digest = schema.get("snapshot_digest")
    if not isinstance(digest, str) or not SHA256_DIGEST_PATTERN.fullmatch(digest):
        missing.append("__schema__.snapshot_digest")
    elif digest != canonical_pricing_snapshot_digest(data):
        missing.append("__schema__.snapshot_digest (mismatch)")
    return missing


def _validate_aws_twinmaker_contract(payload: dict[str, Any]) -> list[str]:
    twinmaker = payload.get("iotTwinMaker")
    if not isinstance(twinmaker, dict):
        return []

    missing: list[str] = []
    usage_rates = twinmaker.get("usageRates")
    required_rates = (
        "entityPricePerMonth",
        "queryPrice",
        "unifiedDataAccessApiCallPrice",
    )
    if not isinstance(usage_rates, dict):
        missing.append("iotTwinMaker.usageRates (invalid object)")
    else:
        for key in required_rates:
            if not _is_positive_number(usage_rates.get(key)):
                missing.append(f"iotTwinMaker.usageRates.{key}")

    tiered_bundle = twinmaker.get("tieredBundle")
    tiers = (
        tiered_bundle.get("tiers")
        if isinstance(tiered_bundle, dict)
        else None
    )
    if not isinstance(tiers, list) or len(tiers) != 4:
        return missing + ["iotTwinMaker.tieredBundle.tiers"]

    expected_ranges = (
        ("TIER_1", 1, 1_000),
        ("TIER_2", 1_001, 5_000),
        ("TIER_3", 5_001, 10_000),
        ("TIER_4", 10_001, 20_000),
    )
    previous_queries = -1
    previous_api_calls = -1
    query_overages = set()
    api_overages = set()
    for index, (tier, expected) in enumerate(zip(tiers, expected_ranges)):
        prefix = f"iotTwinMaker.tieredBundle.tiers[{index}]"
        if not isinstance(tier, dict):
            missing.append(f"{prefix} (invalid object)")
            continue
        tier_id, minimum, maximum = expected
        if tier.get("tierId") != tier_id:
            missing.append(f"{prefix}.tierId")
        if tier.get("minimumEntities") != minimum:
            missing.append(f"{prefix}.minimumEntities")
        if tier.get("maximumEntities") != maximum:
            missing.append(f"{prefix}.maximumEntities")
        for key in (
            "monthlyBasePrice",
            "queryOveragePrice",
            "apiCallOveragePrice",
        ):
            if not _is_positive_number(tier.get(key)):
                missing.append(f"{prefix}.{key}")
        included_queries = tier.get("includedQueries")
        included_api_calls = tier.get("includedApiCalls")
        if (
            isinstance(included_queries, bool)
            or not isinstance(included_queries, int)
            or included_queries <= previous_queries
        ):
            missing.append(f"{prefix}.includedQueries")
        else:
            previous_queries = included_queries
        if (
            isinstance(included_api_calls, bool)
            or not isinstance(included_api_calls, int)
            or included_api_calls <= previous_api_calls
        ):
            missing.append(f"{prefix}.includedApiCalls")
        else:
            previous_api_calls = included_api_calls
        if _is_positive_number(tier.get("queryOveragePrice")):
            query_overages.add(float(tier["queryOveragePrice"]))
        if _is_positive_number(tier.get("apiCallOveragePrice")):
            api_overages.add(float(tier["apiCallOveragePrice"]))

    if len(query_overages) != 1:
        missing.append("iotTwinMaker.tieredBundle.queryOveragePrice (inconsistent)")
    if len(api_overages) != 1:
        missing.append("iotTwinMaker.tieredBundle.apiCallOveragePrice (inconsistent)")
    return missing


def _is_positive_number(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and value > 0
    )


def _source_field_is_fetched(
    provider: str,
    service: str,
    key: str,
    fetched_values: dict[str, Any],
) -> bool:
    if key in fetched_values and fetched_values[key] is not None:
        return True
    if provider == "aws" and service == "lambda" and key == "durationPrice":
        return bool(fetched_values.get("durationTiers"))
    if provider == "aws" and service == "iotCore" and key == "pricing_tiers":
        return bool(fetched_values.get("messageTiers"))
    if provider == "gcp" and service in {"twinmaker", "grafana"}:
        if key == "e2MediumPrice":
            return bool(fetched_values.get("e2CorePrice")) and bool(
                fetched_values.get("e2RamPrice")
            )
    return False


def _derived_field_is_fetched(
    provider: str,
    path: str,
    fetched: dict[str, dict[str, Any]],
) -> bool:
    dependency = DERIVED_FIELD_DEPENDENCIES.get(provider, {}).get(path)
    if not dependency:
        return False

    neutral_service, dependency_keys = dependency
    fetched_values = fetched.get(neutral_service, {})
    if isinstance(dependency_keys, tuple):
        return all(fetched_values.get(key) is not None for key in dependency_keys)
    return fetched_values.get(dependency_keys) is not None


def _validation_result(
    provider: str,
    status: str,
    missing_keys: list[str],
    *,
    quality_status: str = PUBLISHABLE,
    fallback_fields: list[str] | None = None,
    unsupported_fields: list[str] | None = None,
) -> dict[str, Any]:
    effective_quality_status = (
        REVIEW_REQUIRED if status != "valid" else quality_status
    )
    return {
        "schema_version": PRICING_SCHEMA_VERSION,
        "contract_version": PRICING_CONTRACT_VERSION,
        "provider": provider,
        "status": status,
        "missing_keys": missing_keys,
        "quality_status": effective_quality_status,
        "review_required": effective_quality_status == REVIEW_REQUIRED,
        "fallback_fields": fallback_fields or [],
        "unsupported_fields": unsupported_fields or [],
    }
