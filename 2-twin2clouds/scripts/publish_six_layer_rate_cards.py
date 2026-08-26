"""Publish reviewed Six-layer rate cards into immutable baselines.

The architecture adapter owns formulas only. This publisher combines the
already reviewed provider baseline values with the explicit supplemental
public-price observations in ``six_layer_rate_card_sources.v1.json`` and
writes new immutable snapshot identities. Existing snapshots are retained.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Mapping
from urllib.parse import urlparse

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.pricing_catalog_models import (  # noqa: E402
    PricingCatalogBaselineManifest,
    PricingCatalogSnapshot,
    build_pricing_catalog_reference,
    canonical_json_bytes,
)
from backend.calculation_v2.components.azure.iot_hub import (  # noqa: E402
    AzureIoTHubCalculator,
)
from backend.pricing_schema import canonical_pricing_snapshot_digest  # noqa: E402


BASELINE_ROOT = ROOT / "json" / "pricing_catalog_baselines"
BASELINE_PATH = BASELINE_ROOT / "baseline.json"
HISTORY_ROOT = BASELINE_ROOT / "history"
SOURCE_PATH = ROOT / "pricing_registry" / "six_layer_rate_card_sources.v1.json"
SCHEMA_PATH = ROOT / "pricing_registry" / "six_layer_rate_card.schema.json"
CAPACITY_REGISTRY_PATH = (
    ROOT
    / "backend"
    / "contracts"
    / "generated"
    / "resolved-deployment-specification"
    / "v2"
    / "component-capacity-registry.json"
)
WORKLOAD_ROOT = (
    ROOT / "backend" / "contracts" / "generated" / "six-layer-workload" / "v1"
)
FORMULA_REF = "formula.phase-08-complete-service-bundles"
RATE_CARD_KEY = "sixLayer"
RATE_CARD_SCHEMA_VERSION = "six-layer-rate-card.v1"
ROUTE_CLASSES = (
    "domain_event_cross_cloud",
    "twin_projection_cross_cloud",
    "storage_hot_to_cool_cross_cloud",
    "storage_cool_to_archive_cross_cloud",
)
PROVIDER_REGIONS = {
    "aws": "eu-central-1",
    "azure": "westeurope",
    "gcp": "europe-west1",
}
SOURCE_HOSTS = {
    "aws": {"aws.amazon.com", "pricing.us-east-1.amazonaws.com"},
    "azure": {"prices.azure.com"},
    "gcp": {"cloud.google.com"},
}
SOURCE_RATE_KEYS = {
    "aws": {
        "iotCommandExecution",
        "iotCommandFreeExecutions",
        "sqsFifoRequestTier1",
        "sqsFifoRequestTier2",
        "sqsFifoRequestTier3",
        "snsFifoPublishRequest",
        "snsFifoPublishPayloadPerByte",
        "snsFifoDeliveryPayloadPerByte",
        "kinesisShardHour",
        "kinesisPayloadUnit",
        "cloudWatchLogIngestionPerGib",
        "cloudWatchRetentionPerGibMonth",
        "fargateStorageMoverPerConcurrentTaskMonth",
        "ecrBoundedImageStoragePerRepositoryMonth",
    },
    "azure": {
        "serviceBusStandardBasePerHour",
        "serviceBusIncludedOperations",
        "serviceBusOperationsTier1",
        "serviceBusOperationsTier2",
        "serviceBusOperationsTier3",
        "eventHubsStandardThroughputUnitHour",
        "eventHubsDedicatedCapacityUnitHour",
        "logAnalyticsIngestionPerGib",
        "logAnalyticsRetentionPerGibMonth",
        "containerAppsVcpuSecond",
        "containerAppsMemoryGibSecond",
        "containerAppsStorageMoverPerConcurrentTaskMonth",
        "acrBasicPerRepositoryMonth",
        "cosmosServerlessPerMillionRu",
        "cosmosAutoscalePer100MaxRuHour",
    },
    "gcp": {
        "cloudRunRequest",
        "cloudRunVcpuSecond",
        "cloudRunMemoryGibSecond",
        "pubsubPerByte",
        "cloudLoggingIngestionPerGib",
        "cloudLoggingRetentionPerGibMonth",
        "loadBalancerRuleHour",
        "loadBalancerProcessedByte",
        "persistentDiskPerGibMonth",
        "firestoreDelete",
        "cloudRunStorageMoverPerConcurrentTaskMonth",
        "artifactRegistryBoundedImageStoragePerRepositoryMonth",
    },
}

UNITS = {
    "resource_count": "count",
    "stored_gib_month": "GiB-month",
    "read_requests": "requests/month",
    "write_requests": "requests/month",
    "request_units": "RU/month",
    "capacity_mode": "enum",
    "autoscale_max_ru_per_second": "RU/s",
    "document_reads": "operations/month",
    "document_writes": "operations/month",
    "document_deletes": "operations/month",
    "timestamp_shards": "count",
    "requests": "requests/month",
    "gib_seconds": "GiB-s/month",
    "execution_seconds": "seconds/month",
    "vcpu_seconds": "vCPU-s/month",
    "memory_gib_seconds": "GiB-s/month",
    "workspace_count": "count",
    "editor_seats": "seats/month",
    "viewer_seats": "seats/month",
    "node_count": "count",
    "node_hours": "hours/month",
    "throughput_unit_hours": "TU-hours/month",
    "capacity_unit_hours": "CU-hours/month",
    "stream_count": "count",
    "shards_per_stream": "count",
    "shard_hours": "shard-hours/month",
    "payload_units": "units/month",
    "publish_bytes": "bytes/month",
    "delivery_bytes": "bytes/month",
    "publishes": "requests/month",
    "messaging_unit_hours": "MU-hours/month",
    "operations": "operations/month",
    "log_ingestion_gib": "GiB/month",
    "retained_log_gib_month": "GiB-month",
    "rule_hours": "hours/month",
    "processed_bytes": "bytes/month",
    "connected_devices": "count",
    "messages": "messages/month",
    "twin_entities": "count",
    "twin_operations": "operations/month",
    "scheduled_invocations": "invocations/month",
    "workflow_executions": "executions/month",
    "workflow_transitions": "transitions/month",
    "task_count": "count",
    "cross_cloud_egress_bytes": "bytes/month",
}


def _read(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return value


def _canonical(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _digest(value: object) -> str:
    return f"sha256:{hashlib.sha256(_canonical(value)).hexdigest()}"


def _timestamp(value: object, field: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field} must be an ISO-8601 timestamp") from exc
    if parsed.utcoffset() is None:
        raise ValueError(f"{field} must be timezone-aware")
    return parsed


def _validate_source_manifest(source: Mapping[str, Any]) -> datetime:
    if (
        set(source)
        != {
            "schemaVersion",
            "reviewedAt",
            "currencyConversions",
            "currencySource",
            "providers",
        }
        or source["schemaVersion"] != "six-layer-rate-card-sources.v1"
    ):
        raise ValueError("Six-layer source-manifest identity is invalid")
    reviewed_at = _timestamp(source["reviewedAt"], "reviewedAt")
    conversions = source["currencyConversions"]
    if not isinstance(conversions, Mapping) or set(conversions) != {"USD", "EUR"}:
        raise ValueError("Source manifest must pin exactly USD and EUR")
    if _decimal(conversions["USD"]) != 1 or _decimal(conversions["EUR"]) <= 0:
        raise ValueError("Source-manifest currency conversions are invalid")
    currency_source = source["currencySource"]
    if not isinstance(currency_source, Mapping) or set(currency_source) != {
        "sourceId",
        "url",
        "observedAt",
        "providerUpdatedAt",
    }:
        raise ValueError("Currency source evidence is incomplete")
    if urlparse(str(currency_source["url"])).hostname != "open.er-api.com":
        raise ValueError("Currency source must use the reviewed public endpoint")
    observed_at = _timestamp(currency_source["observedAt"], "currencySource.observedAt")
    provider_updated_at = _timestamp(
        currency_source["providerUpdatedAt"],
        "currencySource.providerUpdatedAt",
    )
    if provider_updated_at > observed_at or observed_at > reviewed_at:
        raise ValueError("Currency evidence timestamps are inconsistent")
    providers = source["providers"]
    if not isinstance(providers, Mapping) or set(providers) != set(PROVIDER_REGIONS):
        raise ValueError("Source manifest must cover exactly AWS, Azure, and GCP")
    for provider, expected_region in PROVIDER_REGIONS.items():
        payload = providers[provider]
        if not isinstance(payload, Mapping) or set(payload) != {
            "region",
            "sources",
            "rates",
        }:
            raise ValueError(f"{provider} source evidence is incomplete")
        if payload["region"] != expected_region:
            raise ValueError(f"{provider} source region is not canonical")
        sources = payload["sources"]
        if not isinstance(sources, list) or not sources:
            raise ValueError(f"{provider} must have public source evidence")
        source_ids = set()
        for entry in sources:
            if not isinstance(entry, Mapping) or set(entry) != {"sourceId", "url"}:
                raise ValueError(f"{provider} source entry is invalid")
            source_id = str(entry["sourceId"])
            host = urlparse(str(entry["url"])).hostname
            if (
                not source_id
                or source_id in source_ids
                or host not in SOURCE_HOSTS[provider]
            ):
                raise ValueError(f"{provider} source identity or host is invalid")
            source_ids.add(source_id)
        rates = payload["rates"]
        if not isinstance(rates, Mapping) or set(rates) != SOURCE_RATE_KEYS[provider]:
            raise ValueError(f"{provider} supplemental rate set is incomplete")
        if any(_decimal(value) < 0 for value in rates.values()):
            raise ValueError(f"{provider} supplemental rates must be non-negative")
    return reviewed_at


def _decimal(value: object) -> Decimal:
    return Decimal(str(value))


def _decimal_text(value: object) -> str:
    decimal = _decimal(value).normalize()
    if decimal == decimal.to_integral():
        return str(decimal.quantize(Decimal(1)))
    return format(decimal, "f")


def _meter(
    dimension: str,
    price: object,
    *,
    billing_increment: object = "1",
    free_quantity: object = "0",
    minimum_charge: object = "0",
    tiers: list[dict[str, str | None]] | None = None,
) -> dict[str, Any]:
    return {
        "dimension": dimension,
        "unit": UNITS[dimension],
        "billingIncrement": _decimal_text(billing_increment),
        "freeQuantity": _decimal_text(free_quantity),
        "minimumCharge": _decimal_text(minimum_charge),
        "tiers": tiers or [{"upTo": None, "pricePerUnit": _decimal_text(price)}],
    }


def _variant(
    dimensions: tuple[str, ...],
    meters: list[dict[str, Any]],
    *,
    selectors: Mapping[str, str | int] | None = None,
) -> dict[str, Any]:
    billed = {str(item["dimension"]) for item in meters}
    return {
        "selectors": dict(selectors or {}),
        "meters": meters,
        "nonBillableDimensions": {
            dimension: "not_a_separate_meter_in_the_reviewed_poc_rate_card"
            for dimension in dimensions
            if dimension not in billed
        },
    }


def _legacy(pricing: Mapping[str, Any], *path: str) -> Decimal:
    value: Any = pricing
    for part in path:
        value = value[part]
    return _decimal(value)


def _lambda_meters(pricing: Mapping[str, Any]) -> list[dict[str, Any]]:
    values = pricing["lambda"]
    return [
        _meter("requests", values["requestPrice"]),
        _meter("gib_seconds", values["durationPrice"]),
    ]


def _azure_function_meters(pricing: Mapping[str, Any]) -> list[dict[str, Any]]:
    values = pricing["functions"]
    return [
        _meter("requests", values["requestPrice"]),
        _meter(
            "execution_seconds",
            _decimal(values["durationPrice"]) * Decimal("0.25"),
        ),
    ]


def _cloud_run_meters(rates: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [
        _meter("requests", rates["cloudRunRequest"]),
        _meter("vcpu_seconds", rates["cloudRunVcpuSecond"]),
        _meter("memory_gib_seconds", rates["cloudRunMemoryGibSecond"]),
    ]


def _aws_component(
    component_id: str,
    dimensions: tuple[str, ...],
    pricing: Mapping[str, Any],
    rates: Mapping[str, Any],
) -> list[dict[str, Any]]:
    if component_id == "aws.iot-core":
        tiers = []
        for tier in pricing["iotCore"]["pricing_tiers"].values():
            raw_limit = tier["limit"]
            tiers.append(
                {
                    "upTo": None if raw_limit == "Infinity" else str(raw_limit),
                    "pricePerUnit": _decimal_text(tier["price"]),
                }
            )
        meters = [
            _meter("connected_devices", pricing["iotCore"]["pricePerDeviceAndMonth"]),
            _meter("messages", "0", tiers=tiers),
        ]
    elif component_id == "aws.iot-commands":
        meters = [
            _meter(
                "messages",
                rates["iotCommandExecution"],
                free_quantity=rates["iotCommandFreeExecutions"],
            )
        ]
    elif component_id.startswith("aws.lambda"):
        meters = _lambda_meters(pricing)
    elif component_id == "aws.step-functions-standard":
        meters = [
            _meter(
                "workflow_transitions",
                pricing["stepFunctions"]["pricePerStateTransition"],
            )
        ]
    elif component_id.startswith("aws.dynamodb-on-demand-"):
        meters = [
            _meter("read_requests", pricing["dynamoDB"]["readPrice"]),
            _meter("write_requests", pricing["dynamoDB"]["writePrice"]),
            _meter("stored_gib_month", pricing["dynamoDB"]["storagePrice"]),
        ]
    elif component_id == "aws.s3-standard-ia":
        meters = [
            _meter("stored_gib_month", pricing["s3InfrequentAccess"]["storagePrice"])
        ]
    elif component_id in {"aws.s3-glacier-deep-archive", "aws.s3-event-failure-store"}:
        source = (
            pricing["s3GlacierDeepArchive"]
            if component_id == "aws.s3-glacier-deep-archive"
            else pricing["s3InfrequentAccess"]
        )
        meters = [_meter("stored_gib_month", source["storagePrice"])]
    elif component_id == "aws.iot-twinmaker-standard":
        usage = pricing["iotTwinMaker"]["usageRates"]
        meters = [
            _meter("twin_entities", usage["entityPricePerMonth"]),
            _meter("twin_operations", usage["unifiedDataAccessApiCallPrice"]),
        ]
    elif component_id == "aws.amazon-managed-grafana-12":
        meters = [
            _meter("editor_seats", pricing["awsManagedGrafana"]["editorPrice"]),
            _meter("viewer_seats", pricing["awsManagedGrafana"]["viewerPrice"]),
        ]
    elif component_id == "aws.sqs-fifo":
        meters = [
            _meter(
                "requests",
                "0",
                tiers=[
                    {
                        "upTo": "100000000000",
                        "pricePerUnit": rates["sqsFifoRequestTier1"],
                    },
                    {
                        "upTo": "200000000000",
                        "pricePerUnit": rates["sqsFifoRequestTier2"],
                    },
                    {"upTo": None, "pricePerUnit": rates["sqsFifoRequestTier3"]},
                ],
            )
        ]
    elif component_id in {
        "aws.sns-fifo",
        "aws.sns-fifo-only-for-reviewed-remote-control-edge",
    }:
        catalog = _read(WORKLOAD_ROOT / "eventing-scenario-catalog.json")
        variants = []
        for scenario in catalog["scenarios"]:
            publishes = int(
                (
                    _decimal(scenario["events_per_month"])
                    * (
                        Decimal("1")
                        + _decimal(scenario["retry_share"])
                        + _decimal(scenario["replay_share"])
                    )
                ).to_integral_value(rounding="ROUND_CEILING")
            )
            publish_price = _decimal(rates["snsFifoPublishRequest"]) + (
                _decimal(scenario["average_event_payload_bytes"])
                * _decimal(rates["snsFifoPublishPayloadPerByte"])
            )
            variants.append(
                _variant(
                    dimensions,
                    [
                        _meter("publishes", publish_price),
                        _meter(
                            "delivery_bytes",
                            rates["snsFifoDeliveryPayloadPerByte"],
                        ),
                    ],
                    selectors={"publishes": publishes},
                )
            )
        return variants
    elif component_id in {
        "aws.kinesis-data-streams",
        "aws.kinesis-only-for-reviewed-remote-telemetry-edge",
    }:
        meters = [
            _meter("shard_hours", rates["kinesisShardHour"]),
            _meter("payload_units", rates["kinesisPayloadUnit"]),
        ]
    elif component_id == "aws.cloudwatch":
        meters = [
            _meter("log_ingestion_gib", rates["cloudWatchLogIngestionPerGib"]),
            _meter("retained_log_gib_month", rates["cloudWatchRetentionPerGibMonth"]),
        ]
    elif component_id == "aws.eventbridge-scheduler":
        meters = [_meter("scheduled_invocations", pricing["scheduler"]["jobPrice"])]
    elif component_id == "aws.ecs-fargate-storage-mover":
        meters = [
            _meter("task_count", rates["fargateStorageMoverPerConcurrentTaskMonth"])
        ]
    elif component_id == "aws.ecr-if-container-selected":
        meters = [
            _meter("resource_count", rates["ecrBoundedImageStoragePerRepositoryMonth"])
        ]
    else:
        meters = []
    return [_variant(dimensions, meters)]


def _azure_component(
    component_id: str,
    dimensions: tuple[str, ...],
    pricing: Mapping[str, Any],
    rates: Mapping[str, Any],
) -> list[dict[str, Any]]:
    if component_id == "azure.iot-hub":
        calculator = AzureIoTHubCalculator()
        variants = []
        for size in ("small", "medium", "large"):
            workload = _read(WORKLOAD_ROOT / "fixtures" / "valid" / f"core-{size}.json")
            messages = (
                _decimal(workload["numberOfDevices"])
                * Decimal("2592000")
                / (_decimal(workload["deviceSendingIntervalInMinutes"]) * Decimal("60"))
            ).to_integral_value(rounding="ROUND_CEILING")
            selection = calculator.calculate_selection(
                messages_per_month=int(messages),
                pricing={"azure": dict(pricing)},
                average_message_size_kb=float(workload["averageSizeOfMessageInKb"]),
            )
            variants.append(
                _variant(
                    dimensions,
                    [
                        _meter(
                            "messages",
                            "0",
                            minimum_charge=selection.total_cost,
                        )
                    ],
                    selectors={"messages": int(messages)},
                )
            )
        return variants
    elif component_id.startswith("azure.functions-flex"):
        meters = _azure_function_meters(pricing)
    elif component_id == "azure.logic-apps-consumption":
        meters = [
            _meter(
                "workflow_transitions",
                pricing["logicApps"]["pricePerStateTransition"],
            )
        ]
    elif component_id == "azure.cosmos-db-nosql-raw-and-rollup":
        storage = _meter("stored_gib_month", pricing["cosmosDB"]["storagePrice"])
        serverless = _variant(
            dimensions,
            [
                _meter(
                    "request_units",
                    _decimal(rates["cosmosServerlessPerMillionRu"])
                    / Decimal("1000000"),
                ),
                storage,
            ],
            selectors={"capacity_mode": "serverless"},
        )
        autoscale = _variant(
            dimensions,
            [
                _meter(
                    "autoscale_max_ru_per_second",
                    _decimal(rates["cosmosAutoscalePer100MaxRuHour"])
                    * Decimal("730")
                    / Decimal("100"),
                ),
                storage,
            ],
            selectors={"capacity_mode": "autoscale"},
        )
        return [serverless, autoscale]
    elif component_id == "azure.blob-cool":
        meters = [
            _meter("stored_gib_month", pricing["blobStorageCool"]["storagePrice"])
        ]
    elif component_id == "azure.blob-archive":
        meters = [
            _meter("stored_gib_month", pricing["blobStorageArchive"]["storagePrice"])
        ]
    elif component_id == "azure.digital-twins":
        meters = [
            _meter("twin_operations", pricing["azureDigitalTwins"]["pricePerOperation"])
        ]
    elif component_id == "azure.managed-grafana-12-standard":
        meters = [
            _meter(
                "workspace_count",
                _decimal(pricing["azureManagedGrafana"]["hourlyPrice"])
                * Decimal("730"),
            ),
            _meter("editor_seats", pricing["azureManagedGrafana"]["userPrice"]),
            _meter("viewer_seats", pricing["azureManagedGrafana"]["userPrice"]),
        ]
    elif component_id == "azure.service-bus-standard":
        meters = [
            _meter("messaging_unit_hours", rates["serviceBusStandardBasePerHour"]),
            _meter(
                "operations",
                "0",
                free_quantity=rates["serviceBusIncludedOperations"],
                tiers=[
                    {
                        "upTo": "87000000",
                        "pricePerUnit": rates["serviceBusOperationsTier1"],
                    },
                    {
                        "upTo": "2487000000",
                        "pricePerUnit": rates["serviceBusOperationsTier2"],
                    },
                    {"upTo": None, "pricePerUnit": rates["serviceBusOperationsTier3"]},
                ],
            ),
        ]
    elif component_id in {
        "azure.event-hubs-standard-small-medium",
        "azure.event-hubs-only-for-reviewed-remote-telemetry-edge",
    }:
        meters = [
            _meter(
                "throughput_unit_hours", rates["eventHubsStandardThroughputUnitHour"]
            ),
            _meter("capacity_unit_hours", rates["eventHubsDedicatedCapacityUnitHour"]),
        ]
    elif component_id == "azure.event-hubs-dedicated-large":
        meters = [
            _meter("capacity_unit_hours", rates["eventHubsDedicatedCapacityUnitHour"])
        ]
    elif component_id == "azure.log-analytics-shared-workspace":
        meters = [
            _meter("log_ingestion_gib", rates["logAnalyticsIngestionPerGib"]),
            _meter("retained_log_gib_month", rates["logAnalyticsRetentionPerGibMonth"]),
        ]
    elif component_id == "azure.container-apps-scheduled-storage-job":
        meters = [
            _meter(
                "task_count", rates["containerAppsStorageMoverPerConcurrentTaskMonth"]
            )
        ]
    elif component_id == "azure.acr-basic-if-container-selected":
        meters = [_meter("resource_count", rates["acrBasicPerRepositoryMonth"])]
    else:
        meters = []
    return [_variant(dimensions, meters)]


def _gcp_component(
    component_id: str,
    dimensions: tuple[str, ...],
    pricing: Mapping[str, Any],
    rates: Mapping[str, Any],
) -> list[dict[str, Any]]:
    if component_id == "apache.bifromq-4.0.0-incubating-on-gke-standard":
        meters = [_meter("node_hours", pricing["grafana"]["e2MediumPrice"])]
    elif component_id == "gcp.ordered-mqtt-pubsub-adapter":
        meters = [_meter("node_hours", pricing["grafana"]["e2MediumPrice"])]
    elif component_id in {
        "gcp.pubsub-separated-embedded-topics",
        "gcp.pubsub-separated-event-layer-topics",
    }:
        meters = [
            _meter("publish_bytes", rates["pubsubPerByte"]),
            _meter("delivery_bytes", rates["pubsubPerByte"]),
        ]
    elif component_id in {
        "gcp.cloud-run-service",
        "gcp.cloud-run-event-adapter",
        "gcp.cloud-run-event-service-small-medium",
        "gcp.cloud-run-worker-pool-fixed-large",
        "gcp.cloud-run-iap-twin-explorer",
        "gcp.cloud-run-raw-history-reader",
        "gcp.cloud-run-twin-api-materializer",
    }:
        meters = _cloud_run_meters(rates)
    elif component_id == "gcp.workflows":
        meters = [
            _meter("workflow_transitions", pricing["cloudWorkflows"]["stepPrice"])
        ]
    elif component_id in {
        "gcp.firestore-native-standard-raw-and-rollup",
        "gcp.firestore-native-standard-bounded-twin",
    }:
        meters = [
            _meter("document_reads", pricing["storage_hot"]["readPrice"]),
            _meter("document_writes", pricing["storage_hot"]["writePrice"]),
            _meter("document_deletes", rates["firestoreDelete"]),
            _meter("stored_gib_month", pricing["storage_hot"]["storagePrice"]),
        ]
    elif component_id == "gcp.cloud-storage-nearline":
        meters = [_meter("stored_gib_month", pricing["storage_cool"]["storagePrice"])]
    elif component_id == "gcp.cloud-storage-archive":
        meters = [
            _meter("stored_gib_month", pricing["storage_archive"]["storagePrice"])
        ]
    elif component_id == "grafana.oss-12-on-gke":
        meters = [_meter("node_hours", pricing["grafana"]["e2MediumPrice"])]
    elif component_id == "gcp.persistent-disk-rwo":
        meters = [_meter("stored_gib_month", rates["persistentDiskPerGibMonth"])]
    elif component_id in {
        "gcp.external-load-balancer",
        "gcp.grafana-tls-load-balancer",
    }:
        meters = [
            _meter("rule_hours", rates["loadBalancerRuleHour"]),
            _meter("processed_bytes", rates["loadBalancerProcessedByte"]),
        ]
    elif component_id == "gcp.cloud-scheduler":
        meters = [
            _meter(
                "scheduled_invocations",
                "0",
                minimum_charge=pricing["cloudScheduler"]["jobPrice"],
            )
        ]
    elif component_id == "gcp.cloud-run-storage-job":
        meters = [
            _meter("task_count", rates["cloudRunStorageMoverPerConcurrentTaskMonth"])
        ]
    elif component_id == "gcp.cloud-logging":
        meters = [
            _meter("log_ingestion_gib", rates["cloudLoggingIngestionPerGib"]),
            _meter("retained_log_gib_month", rates["cloudLoggingRetentionPerGibMonth"]),
        ]
    elif component_id == "gcp.artifact-registry-if-container-selected":
        meters = [
            _meter(
                "resource_count",
                rates["artifactRegistryBoundedImageStoragePerRepositoryMonth"],
            )
        ]
    else:
        meters = []
    return [_variant(dimensions, meters)]


def _route_rates(pricing: Mapping[str, Any]) -> dict[str, Any]:
    transfer = pricing["transfer"]
    bytes_per_unit = _decimal(transfer["bytes_per_billing_unit"])
    tiers = []
    for tier in transfer["pricing_tiers"]:
        upper = tier["end_quantity"]
        tiers.append(
            {
                "upTo": None
                if upper is None
                else _decimal_text(_decimal(upper) * bytes_per_unit),
                "pricePerUnit": _decimal_text(
                    _decimal(tier["unit_price"]) / bytes_per_unit
                ),
            }
        )
    source = {
        "selectors": {},
        "meters": [
            {
                **_meter(
                    "cross_cloud_egress_bytes",
                    "0",
                    billing_increment=bytes_per_unit,
                    tiers=tiers,
                ),
                "unit": "bytes/month",
            }
        ],
        "nonBillableDimensions": {
            "source_runtime": "priced_by_the_selected_source_adapter_component"
        },
    }
    destination = {
        "selectors": {},
        "meters": [],
        "nonBillableDimensions": {
            "destination_operations": "priced_by_the_selected_destination_broker_component"
        },
    }
    return {
        route_class: {
            "sourceVariants": [deepcopy(source)],
            "destinationVariants": [deepcopy(destination)],
        }
        for route_class in ROUTE_CLASSES
    }


def _build_card(
    provider: str,
    pricing: Mapping[str, Any],
    source: Mapping[str, Any],
    components: list[Mapping[str, Any]],
) -> dict[str, Any]:
    rates = source["providers"][provider]["rates"]
    component_rates = {}
    for component in components:
        if component["provider"] != provider:
            continue
        component_id = str(component["component_id"])
        dimensions = tuple(str(item) for item in component["capacity_dimensions"])
        unknown = set(dimensions) - set(UNITS)
        if unknown:
            raise ValueError(
                f"Unknown dimensions for {component_id}: {sorted(unknown)}"
            )
        if provider == "aws":
            variants = _aws_component(component_id, dimensions, pricing, rates)
        elif provider == "azure":
            variants = _azure_component(component_id, dimensions, pricing, rates)
        else:
            variants = _gcp_component(component_id, dimensions, pricing, rates)
        component_rates[component_id] = {"variants": variants}
    return {
        "schemaVersion": RATE_CARD_SCHEMA_VERSION,
        "baseCurrency": "USD",
        "currencyConversions": dict(source["currencyConversions"]),
        "formulaReference": FORMULA_REF,
        "componentRates": dict(sorted(component_rates.items())),
        "routeRates": _route_rates(pricing),
    }


def _source_snapshot(reference: Mapping[str, Any]) -> tuple[Path, dict[str, Any]]:
    path = (
        BASELINE_ROOT
        / str(reference["provider"])
        / str(reference["pricing_region"])
        / "snapshots"
        / f"{reference['snapshot_id']}.json"
    )
    snapshot = _read(path)
    pricing = deepcopy(snapshot["pricing"])
    pricing.pop(RATE_CARD_KEY, None)
    evidence = pricing.get("__evidence__")
    if isinstance(evidence, dict):
        evidence.pop(RATE_CARD_KEY, None)
    return path, pricing


def _expected_publication() -> tuple[
    PricingCatalogBaselineManifest, dict[str, PricingCatalogSnapshot]
]:
    baseline = _read(BASELINE_PATH)
    source = _read(SOURCE_PATH)
    reviewed_at = _validate_source_manifest(source)
    registry = _read(CAPACITY_REGISTRY_PATH)
    schema = _read(SCHEMA_PATH)
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)
    snapshots: dict[str, PricingCatalogSnapshot] = {}
    references = {}
    for provider in ("aws", "azure", "gcp"):
        prior_reference = baseline["catalogs"][provider]
        _, pricing = _source_snapshot(prior_reference)
        card = _build_card(provider, pricing, source, registry["components"])
        errors = sorted(
            validator.iter_errors(card), key=lambda item: list(item.absolute_path)
        )
        if errors:
            raise ValueError(f"Invalid {provider} rate card: {errors[0].message}")
        pricing[RATE_CARD_KEY] = card
        evidence = pricing.setdefault("__evidence__", {})
        evidence[RATE_CARD_KEY] = {
            "schema_version": "six-layer-rate-card-evidence.v1",
            "source_manifest": SOURCE_PATH.name,
            "source_manifest_digest": _digest(source),
            "rate_card_digest": _digest(card),
            "reviewed_at": source["reviewedAt"],
            "sources": source["providers"][provider]["sources"],
            "currency_source": source["currencySource"],
        }
        pricing["__schema__"]["generated_at"] = source["reviewedAt"]
        pricing["__schema__"]["baseline_provenance"] = (
            "phase_08_reviewed_rate_card_overlay"
        )
        pricing["__schema__"]["snapshot_digest"] = canonical_pricing_snapshot_digest(
            pricing
        )
        reference = build_pricing_catalog_reference(
            provider=provider,
            pricing_region=prior_reference["pricing_region"],
            pricing=pricing,
            provider_schema_version=prior_reference["provider_schema_version"],
            contract_version=prior_reference["contract_version"],
            registry_version=prior_reference["registry_version"],
            mapping_versions=tuple(prior_reference["mapping_versions"]),
            fetched_at=reviewed_at,
            source="reviewed_baseline",
            review_status="reviewed",
            calculation_source="reviewed_baseline",
        )
        references[provider] = reference
        snapshots[provider] = PricingCatalogSnapshot(
            reference=reference, pricing=pricing
        )
    return PricingCatalogBaselineManifest(catalogs=references), snapshots


def _archive_current_manifest(current: bytes) -> None:
    """Retain the exact predecessor required by safe runtime migration."""

    payload = _read(BASELINE_PATH)
    PricingCatalogBaselineManifest.model_validate(payload)
    canonical = canonical_json_bytes(payload)
    if current != canonical:
        raise ValueError("Current pricing baseline is not canonical JSON")
    HISTORY_ROOT.mkdir(parents=True, exist_ok=True)
    for candidate in HISTORY_ROOT.glob("baseline-*.json"):
        if candidate.read_bytes() == canonical:
            return
    suffix = hashlib.sha256(canonical).hexdigest()[:12]
    target = HISTORY_ROOT / f"baseline-pre-six-layer-{suffix}.json"
    if target.exists() and target.read_bytes() != canonical:
        raise ValueError("Pricing baseline history identity collision")
    target.write_bytes(canonical)


def publish(*, write: bool) -> None:
    manifest, snapshots = _expected_publication()
    expected_manifest = canonical_json_bytes(manifest.to_storage_dict())
    if not write:
        if BASELINE_PATH.read_bytes() != expected_manifest:
            raise SystemExit("Six-layer pricing baseline is stale; run with --write")
        for provider, snapshot in snapshots.items():
            reference = snapshot.reference
            target = (
                BASELINE_ROOT
                / provider
                / reference.pricing_region
                / "snapshots"
                / f"{reference.snapshot_id}.json"
            )
            if not target.is_file() or target.read_bytes() != canonical_json_bytes(
                snapshot.to_storage_dict()
            ):
                raise SystemExit(f"Six-layer pricing snapshot is stale: {provider}")
        print("Six-layer immutable rate cards: OK")
        return
    current_manifest = BASELINE_PATH.read_bytes()
    if current_manifest != expected_manifest:
        _archive_current_manifest(current_manifest)
    BASELINE_PATH.write_bytes(expected_manifest)
    for provider, snapshot in snapshots.items():
        reference = snapshot.reference
        target = (
            BASELINE_ROOT
            / provider
            / reference.pricing_region
            / "snapshots"
            / f"{reference.snapshot_id}.json"
        )
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(canonical_json_bytes(snapshot.to_storage_dict()))
        print(f"published {provider} {reference.snapshot_id}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    publish(write=args.write)


if __name__ == "__main__":
    main()
