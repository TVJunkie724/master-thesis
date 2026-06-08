"""
Canonical provider pricing schema and quality metadata.

Static fallback values are intentionally treated as review-required emergency
values. They keep calculations from crashing, but they are not publishable fresh
provider evidence.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


PRICING_SCHEMA_VERSION = "pricing-provider-schema.v1"
PRICING_CONTRACT_VERSION = "2026.06.08"

RESERVED_PRICING_KEYS = {"__schema__", "__quality__"}

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
            "unifiedDataAccessAPICallsPrice",
            "entityPrice",
            "queryPrice",
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
            "messagePrice",
            "operationPrice",
            "queryPrice",
            "queryUnitTiers",
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
        "transfer.pricing_tiers",
    },
    "azure": {
        "transfer.pricing_tiers",
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
) -> dict[str, Any]:
    payload = dict(pricing)
    field_sources = build_field_sources(provider, payload, fetched or {})
    fallback_fields = sorted(
        path
        for path, source in field_sources.items()
        if source in {FALLBACK_STATIC, FALLBACK_DEFAULT}
    )
    unsupported_fields = sorted(
        path for path, source in field_sources.items() if source == UNSUPPORTED
    )
    payload["__schema__"] = {
        "schema_version": PRICING_SCHEMA_VERSION,
        "contract_version": PRICING_CONTRACT_VERSION,
        "provider": provider,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    payload["__quality__"] = {
        "quality_status": (
            REVIEW_REQUIRED if fallback_fields or unsupported_fields else PUBLISHABLE
        ),
        "review_required": bool(fallback_fields or unsupported_fields),
        "field_sources": field_sources,
        "fallback_fields": fallback_fields,
        "unsupported_fields": unsupported_fields,
    }
    return payload


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
