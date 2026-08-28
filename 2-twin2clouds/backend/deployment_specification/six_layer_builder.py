"""Deterministic ResolvedDeploymentSpecification v2 builder for Six-layer."""

from __future__ import annotations

from decimal import Decimal, ROUND_CEILING
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Mapping
from uuid import UUID

from jsonschema import Draft202012Validator, FormatChecker

from backend.architecture_profiles.diagnostics import ArchitectureResolutionError
from backend.architecture_profiles.six_layer_workload import (
    ResolvedSixLayerWorkload,
)


CONTRACT_ROOT = (
    Path(__file__).resolve().parents[1]
    / "contracts"
    / "generated"
    / "resolved-deployment-specification"
    / "v2"
)
PROVIDERS = ("aws", "azure", "gcp")
REGIONS = {
    "aws": "eu-central-1",
    "azure": "westeurope",
    "gcp": "europe-west1",
}
LOGICAL_COMPONENTS = (
    "component.ingestion",
    "component.processing",
    "component.hot-storage",
    "component.cool-storage",
    "component.archive-storage",
    "component.twin-state",
    "component.visualization",
)
SIX_LAYER_LOGICAL_COMPONENTS = (*LOGICAL_COMPONENTS, "component.eventing")
LOGICAL_TO_LAYER = {
    "component.ingestion": "l1_acquisition",
    "component.processing": "l2_processing",
    "component.hot-storage": "l3_hot",
    "component.cool-storage": "l3_cool",
    "component.archive-storage": "l3_archive",
    "component.twin-state": "l4_twin",
    "component.visualization": "l5_visualization",
}
EVENT_LOGICAL_COMPONENTS = (
    "component.ingestion",
    "component.processing",
    "component.hot-storage",
    "component.twin-state",
)
_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
_AZURE_COSMOS_MIN_AUTOSCALE_RU_PER_GIB = Decimal("10")
_AZURE_COSMOS_AUTOSCALE_RU_INCREMENT = Decimal("1000")
_AZURE_COSMOS_WRITE_RU_PROXY = Decimal("10")
_AZURE_COSMOS_READ_RU_PROXY = Decimal("1")
_GIB_BYTES = Decimal("1073741824")
_EVENT_DELIVERY = {
    "small": {
        "requests": 403406,
        "aws_gib_seconds": "5042.575",
        "azure_execution_seconds": 403406,
        "gcp_vcpu_seconds": "6736.8802",
        "gcp_memory_gib_seconds": "10085.15",
    },
    "medium": {
        "requests": 40904500,
        "aws_gib_seconds": "511306.25",
        "azure_execution_seconds": 40904500,
        "gcp_vcpu_seconds": "683105.15",
        "gcp_memory_gib_seconds": "1022612.5",
    },
    "large": {
        "requests": 621090000,
        "aws_gib_seconds": "7763625",
        "azure_execution_seconds": 621090000,
        "gcp_vcpu_seconds": "51603",
        "gcp_memory_gib_seconds": "77250",
        "gcp_worker_count": 126,
        "gcp_worker_vcpu_seconds": "331128000",
        "gcp_worker_memory_gib_seconds": "165564000",
    },
}
_EVENT_CONTROL = {
    "small": {
        "publishes": 3000,
        "publish_bytes": 5376000,
        "delivery_attempts": 3006,
        "sqs_requests": 9018,
        "azure_operations": 12018,
    },
    "medium": {
        "publishes": 300000,
        "publish_bytes": 537600000,
        "delivery_attempts": 304500,
        "sqs_requests": 913500,
        "azure_operations": 1213500,
    },
    "large": {
        "publishes": 3000000,
        "publish_bytes": 5376000000,
        "delivery_attempts": 3090000,
        "sqs_requests": 9270000,
        "azure_operations": 12270000,
    },
}
_EVENT_FAILURE_STORE_GIB_MONTH = {
    "small": "0.000006733150684931506849315068493",
    "medium": "0.08012449315068493150684931507",
    "large": "9.190750684931506849315068493",
}
_EVENT_LOG_BYTES = {
    "small": 5582848,
    "medium": 946843648,
    "large": 16069632000,
}
_GCP_EVENT_BYTES = {
    "small": (1029376000, 2055434752),
    "medium": (348697600000, 707310464000),
    "large": (13317376000000, 41139617280000),
}


def _read(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(
            f"Six-layer deployment contract is unavailable: {path}"
        ) from exc
    if not isinstance(value, dict):
        raise RuntimeError(f"Six-layer deployment contract must be an object: {path}")
    return value


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _digest(value: object) -> str:
    return f"sha256:{hashlib.sha256(_canonical_json(value).encode()).hexdigest()}"


@lru_cache(maxsize=1)
def _contract() -> tuple[
    Draft202012Validator,
    dict[str, Any],
    dict[str, Any],
]:
    schema = _read(CONTRACT_ROOT / "schema.json")
    Draft202012Validator.check_schema(schema)
    registry = _read(CONTRACT_ROOT / "component-capacity-registry.json")
    supplied = registry["content_digest"]
    registry["content_digest"] = ""
    if supplied != _digest(registry):
        raise RuntimeError("Six-layer component capacity registry digest drifted")
    registry["content_digest"] = supplied
    fixed = {
        key: definition["const"]
        for key, definition in schema["properties"]["fixed_dimensions"][
            "properties"
        ].items()
    }
    return (
        Draft202012Validator(schema, format_checker=FormatChecker()),
        registry,
        fixed,
    )


def _ceil(value: Decimal) -> int:
    return int(value.to_integral_value(rounding=ROUND_CEILING))


def _decimal_text(value: Decimal) -> str:
    normalized = value.normalize()
    if normalized == normalized.to_integral():
        return str(normalized.quantize(Decimal(1)))
    return format(normalized, "f")


def _azure_cosmos_autoscale_floor(
    hot_payload_gib: object,
    *,
    peak_messages_per_second: Decimal,
    rollup_writes_per_second: Decimal,
    dashboard_queries_per_second: Decimal,
) -> int:
    """Return the frozen storage/operation-driven Large evaluation proxy.

    This is only the minimum provisionable autoscale maximum used to avoid a
    zero-cost offline candidate. Deployment still requires the supervised
    request-charge and autoscale-capacity evidence gates.
    """

    storage_floor = (
        Decimal(str(hot_payload_gib)) * _AZURE_COSMOS_MIN_AUTOSCALE_RU_PER_GIB
    )
    operation_floor = (
        (peak_messages_per_second + rollup_writes_per_second)
        * _AZURE_COSMOS_WRITE_RU_PROXY
        + peak_messages_per_second * _AZURE_COSMOS_READ_RU_PROXY
        + dashboard_queries_per_second * Decimal("720") * _AZURE_COSMOS_READ_RU_PROXY
    )
    required = max(Decimal("1000"), storage_floor, operation_floor)
    increments = (required / _AZURE_COSMOS_AUTOSCALE_RU_INCREMENT).to_integral_value(
        rounding=ROUND_CEILING
    )
    return int(increments * _AZURE_COSMOS_AUTOSCALE_RU_INCREMENT)


def _dimension_classification(dimension_id: str) -> str:
    if dimension_id == "capacity_mode":
        return "deployable_selection"
    if dimension_id in {
        "resource_count",
        "node_count",
        "stream_count",
        "shards_per_stream",
        "timestamp_shards",
        "autoscale_max_ru_per_second",
        "task_count",
    }:
        return "capacity"
    return "usage"


def _dimension_value_type(value: str | int) -> str:
    return "integer" if isinstance(value, int) else "string"


def _dimension_validator(dimension_id: str, value: str | int) -> str:
    if dimension_id == "capacity_mode":
        return "validator.capacity-mode.v1"
    if isinstance(value, int):
        return "validator.non-negative-integer.v1"
    return "validator.non-negative-decimal-string.v1"


def _scenario_capacity(registry: Mapping[str, Any], size: str) -> Mapping[str, Any]:
    return next(item for item in registry["scenario_capacity"] if item["size"] == size)


def _dimension_value(
    component_id: str,
    logical: str,
    dimension_id: str,
    resolved: ResolvedSixLayerWorkload,
    registry: Mapping[str, Any],
    fixed: Mapping[str, Any],
    *,
    azure_large_autoscale_ru_per_second: int | None,
    gcp_event_worker_count: int,
) -> tuple[str | int, str]:
    workload = resolved.workload
    event = resolved.eventing_scenario
    six_layer_event_component = logical == "component.eventing"
    event_delivery = _EVENT_DELIVERY[resolved.size]
    event_control = _EVENT_CONTROL[resolved.size]
    derived = _scenario_capacity(registry, resolved.size)["derived"]
    month_seconds = Decimal("2592000")
    interval_seconds = Decimal(str(workload["deviceSendingIntervalInMinutes"])) * 60
    messages = _ceil(
        Decimal(int(workload["numberOfDevices"])) * month_seconds / interval_seconds
    )
    event_count = int(event["events_per_month"])
    event_attempts = _ceil(
        Decimal(event_count)
        * (
            Decimal("1")
            + Decimal(str(event["retry_share"]))
            + Decimal(str(event["replay_share"]))
        )
    )
    command_executions = _ceil(
        Decimal(event_count)
        * Decimal(str(event["rule_match_share"]))
        * Decimal(str(event["device_command_share_of_matches"]))
    )
    consumer_count = len(event["mandatory_processed_consumers"]) + len(
        event["extra_processed_consumers"]
    )
    dashboard_requests = (
        int(workload["aggregateDashboardRefreshesPerHour"])
        * int(workload["apiCallsPerAggregateDashboardRefresh"])
        * int(workload["dashboardActiveHoursPerDay"])
        * 30
    )
    twin_operations = _ceil(
        (
            Decimal(str(workload["twinStateMaterializationsPerSecond"]))
            + Decimal(str(workload["twinGraphUpdatesPerSecond"]))
        )
        * month_seconds
    ) + int(derived["l4_inspection_reads_per_month"])
    request_count = (
        dashboard_requests
        if "reader" in component_id or logical == "component.visualization"
        else event_attempts
        if any(
            token in component_id
            for token in (
                "event-adapter",
                "sqs",
                "sns",
                "pubsub",
                "event-hubs",
                "kinesis",
            )
        )
        else messages
    )
    event_bytes = event_attempts * int(event["average_event_payload_bytes"])
    canonical_payload_bytes = Decimal(str(derived["canonical_payload_bytes"]))
    rollup_document_count = int(workload["numberOfDevices"]) * int(
        derived["maximum_aggregate_rollup_points"]
    )
    dashboard_point_reads = dashboard_requests * int(
        derived["maximum_aggregate_rollup_points"]
    )
    rollup_storage_gib = (
        Decimal(rollup_document_count) * canonical_payload_bytes / _GIB_BYTES
    )
    twin_storage_gib = (
        Decimal(int(workload["twinEntityCount"])) * canonical_payload_bytes / _GIB_BYTES
    )
    storage_gib = {
        "aws.dynamodb-on-demand-raw": str(derived["hot_payload_gib"]),
        "aws.dynamodb-on-demand-hourly-rollup": _decimal_text(rollup_storage_gib),
        "azure.cosmos-db-nosql-raw-and-rollup": _decimal_text(
            Decimal(str(derived["hot_payload_gib"])) + rollup_storage_gib
        ),
        "gcp.firestore-native-standard-raw-and-rollup": _decimal_text(
            Decimal(str(derived["hot_payload_gib"])) + rollup_storage_gib
        ),
        "gcp.firestore-native-standard-bounded-twin": _decimal_text(twin_storage_gib),
        "gcp.persistent-disk-rwo": str(fixed["gcp_grafana_persistent_disk_gib"]),
        "aws.s3-event-failure-store": _EVENT_FAILURE_STORE_GIB_MONTH[resolved.size],
    }.get(
        component_id,
        {
            "component.hot-storage": str(derived["hot_payload_gib"]),
            "component.cool-storage": str(derived["cool_payload_gib"]),
            "component.archive-storage": str(derived["archive_payload_gib"]),
        }.get(logical, "0"),
    )
    peak_messages_per_second = Decimal(int(workload["numberOfDevices"])) / (
        Decimal(str(workload["deviceSendingIntervalInMinutes"])) * Decimal("60")
    )
    azure_autoscale_floor = (
        _azure_cosmos_autoscale_floor(
            derived["hot_payload_gib"],
            peak_messages_per_second=peak_messages_per_second,
            rollup_writes_per_second=peak_messages_per_second,
            dashboard_queries_per_second=Decimal(
                str(derived["aggregate_dashboard_query_rate_per_second"])
            ),
        )
        if resolved.size == "large" and "cosmos" in component_id
        else 0
    )
    if azure_large_autoscale_ru_per_second is not None and (
        azure_large_autoscale_ru_per_second < azure_autoscale_floor
        or azure_large_autoscale_ru_per_second % 1000 != 0
    ):
        raise ArchitectureResolutionError(
            "ARCH_WORKLOAD_INCOMPATIBLE",
            "azureLargeAutoscaleRuPerSecond",
            "Measured Azure Large autoscale RU/s must be 1,000-RU rounded "
            "and no lower than the frozen storage/operation evaluation floor",
        )
    units = {
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
    }
    if dimension_id == "resource_count":
        count = (
            gcp_event_worker_count
            if component_id == "gcp.cloud-run-worker-pool-fixed-large"
            else {"small": 1, "medium": 3, "large": 12}[resolved.size]
            if "bifromq" in component_id
            else 1
        )
        return count, units[dimension_id]
    if dimension_id == "task_count":
        task_count_key = {
            "aws.ecs-fargate-storage-mover": "aws_storage_tasks",
            "azure.container-apps-scheduled-storage-job": "azure_storage_tasks",
            "gcp.cloud-run-storage-job": "gcp_storage_tasks",
        }.get(component_id)
        if task_count_key is None:
            raise RuntimeError(
                f"No exact storage task-count binding for component: {component_id}"
            )
        return int(derived[task_count_key]), units[dimension_id]
    values: dict[str, str | int] = {
        "stored_gib_month": storage_gib,
        "read_requests": (
            messages + dashboard_point_reads
            if component_id == "aws.dynamodb-on-demand-hourly-rollup"
            else 0
        ),
        "write_requests": (
            messages * 2
            if component_id
            in {
                "aws.dynamodb-on-demand-raw",
                "aws.dynamodb-on-demand-hourly-rollup",
            }
            else 0
        ),
        "request_units": int(
            messages * (_AZURE_COSMOS_WRITE_RU_PROXY * 2 + _AZURE_COSMOS_READ_RU_PROXY)
            + dashboard_point_reads * _AZURE_COSMOS_READ_RU_PROXY
        ),
        "capacity_mode": (
            "autoscale"
            if resolved.size == "large" and "cosmos" in component_id
            else "serverless"
            if "cosmos" in component_id
            else "not_applicable"
        ),
        "autoscale_max_ru_per_second": (
            azure_large_autoscale_ru_per_second
            if azure_large_autoscale_ru_per_second is not None
            else azure_autoscale_floor
        ),
        "document_reads": (
            int(derived["l4_inspection_reads_per_month"])
            if component_id == "gcp.firestore-native-standard-bounded-twin"
            else messages + dashboard_point_reads
        ),
        "document_writes": (
            twin_operations
            if component_id == "gcp.firestore-native-standard-bounded-twin"
            else messages * 2
        ),
        "document_deletes": (
            0
            if component_id == "gcp.firestore-native-standard-bounded-twin"
            else messages + rollup_document_count
        ),
        "timestamp_shards": (
            1
            if component_id == "gcp.firestore-native-standard-bounded-twin"
            else int(derived["firestore_timestamp_shards"])
        ),
        "requests": (
            0
            if component_id == "gcp.cloud-run-worker-pool-fixed-large"
            else int(event_delivery["requests"])
            if component_id
            in {
                "aws.lambda-event-worker",
                "azure.functions-flex-event-worker",
                "gcp.cloud-run-event-service-small-medium",
            }
            else int(event_control["sqs_requests"])
            if six_layer_event_component and component_id == "aws.sqs-fifo"
            else request_count
        ),
        "gib_seconds": (
            str(event_delivery["aws_gib_seconds"])
            if component_id == "aws.lambda-event-worker"
            else str(Decimal(request_count) * Decimal("0.125"))
        ),
        "execution_seconds": (
            int(event_delivery["azure_execution_seconds"])
            if component_id == "azure.functions-flex-event-worker"
            else request_count
        ),
        "vcpu_seconds": (
            str(Decimal(gcp_event_worker_count) * Decimal("2628000"))
            if component_id == "gcp.cloud-run-worker-pool-fixed-large"
            else str(event_delivery["gcp_vcpu_seconds"])
            if component_id == "gcp.cloud-run-event-service-small-medium"
            else request_count
        ),
        "memory_gib_seconds": (
            str(Decimal(gcp_event_worker_count) * Decimal("1314000"))
            if component_id == "gcp.cloud-run-worker-pool-fixed-large"
            else str(event_delivery["gcp_memory_gib_seconds"])
            if component_id == "gcp.cloud-run-event-service-small-medium"
            else str(Decimal(request_count) * Decimal("0.5"))
        ),
        "workspace_count": 1,
        "editor_seats": int(workload["monthlyEditorSeats"]),
        "viewer_seats": int(workload["monthlyViewerSeats"]),
        "node_count": (
            {"small": 1, "medium": 3, "large": 12}[resolved.size]
            if "bifromq" in component_id
            else {"small": 1, "medium": 1, "large": 4}[resolved.size]
            if component_id == "gcp.ordered-mqtt-pubsub-adapter"
            else 1
        ),
        "node_hours": (
            {"small": 730, "medium": 2190, "large": 8760}[resolved.size]
            if "bifromq" in component_id
            else {"small": 730, "medium": 730, "large": 2920}[resolved.size]
            if component_id == "gcp.ordered-mqtt-pubsub-adapter"
            else 730
        ),
        "throughput_unit_hours": {
            "small": 730,
            "medium": 8030,
            "large": 0,
        }[resolved.size],
        "capacity_unit_hours": {
            "small": 0,
            "medium": 0,
            "large": 4380,
        }[resolved.size],
        "stream_count": 2,
        "shards_per_stream": {
            "small": 1,
            "medium": 6,
            "large": 200,
        }[resolved.size],
        "shard_hours": {
            "small": 1460,
            "medium": 8760,
            "large": 292000,
        }[resolved.size],
        "payload_units": event_attempts,
        "publish_bytes": (
            _GCP_EVENT_BYTES[resolved.size][0]
            if component_id == "gcp.pubsub-separated-event-layer-topics"
            else event_bytes
        ),
        "delivery_bytes": (
            _GCP_EVENT_BYTES[resolved.size][1]
            if component_id == "gcp.pubsub-separated-event-layer-topics"
            else _ceil(
                Decimal(int(event_control["delivery_attempts"]))
                * Decimal(int(event_control["publish_bytes"]))
                / Decimal(int(event_control["publishes"]))
            )
            if six_layer_event_component and component_id == "aws.sns-fifo"
            else event_bytes * max(1, consumer_count)
        ),
        "publishes": (
            int(event_control["publishes"])
            if six_layer_event_component and component_id == "aws.sns-fifo"
            else event_attempts
        ),
        "messaging_unit_hours": 730,
        "operations": (
            int(event_control["azure_operations"])
            if six_layer_event_component
            and component_id == "azure.service-bus-standard"
            else event_attempts
        ),
        "log_ingestion_gib": str(
            Decimal(_EVENT_LOG_BYTES[resolved.size]) / _GIB_BYTES
            if logical == "component.eventing"
            else Decimal(messages + event_attempts) * Decimal("256") / _GIB_BYTES
        ),
        "retained_log_gib_month": str(
            Decimal(_EVENT_LOG_BYTES[resolved.size]) / _GIB_BYTES
            if logical == "component.eventing"
            else Decimal(messages + event_attempts) * Decimal("256") / _GIB_BYTES
        ),
        "rule_hours": 730,
        "processed_bytes": (
            dashboard_requests
            * int(fixed["reader_maximum_points"])
            * _ceil(Decimal(str(derived["canonical_payload_bytes"])))
            if component_id == "gcp.grafana-tls-load-balancer"
            else int(Decimal(str(derived["monthly_raw_payload_bytes"])))
        ),
        "connected_devices": int(workload["numberOfDevices"]),
        "messages": (
            command_executions if component_id == "aws.iot-commands" else messages
        ),
        "twin_entities": int(workload["twinEntityCount"]),
        "twin_operations": twin_operations,
        "scheduled_invocations": 8640,
        "workflow_executions": _ceil(
            Decimal(event_count)
            * Decimal(str(event["rule_match_share"]))
            * Decimal(str(event["workflow_start_share_of_matches"]))
        ),
        "workflow_transitions": _ceil(
            Decimal(event_count)
            * Decimal(str(event["rule_match_share"]))
            * Decimal(str(event["workflow_start_share_of_matches"]))
            * Decimal("3")
        ),
    }
    try:
        return values[dimension_id], units[dimension_id]
    except KeyError as exc:
        raise RuntimeError(
            f"Unknown Six-layer capacity dimension: {dimension_id}"
        ) from exc


def _selected_groups(
    assignment: Mapping[str, str],
    registry: Mapping[str, Any],
    *,
    profile_id: str,
    workload_size: str,
) -> list[tuple[str, str, str]]:
    logical_components = (
        SIX_LAYER_LOGICAL_COMPONENTS
        if profile_id == "six-layer-eventing"
        else LOGICAL_COMPONENTS
    )
    if set(assignment) != set(logical_components) or any(
        provider not in PROVIDERS for provider in assignment.values()
    ):
        raise ArchitectureResolutionError(
            "ARCH_WORKLOAD_INCOMPATIBLE",
            "assignment",
            "Architecture assignment must cover every logical component",
        )
    storage_bundle = {
        assignment["component.hot-storage"],
        assignment["component.cool-storage"],
        assignment["component.archive-storage"],
        assignment["component.visualization"],
    }
    if len(storage_bundle) != 1:
        raise ArchitectureResolutionError(
            "ARCH_FUNCTIONAL_INCOMPLETE",
            "assignment",
            "Six-layer PoC requires provider-local L3 storage and L5",
        )
    bundle_index = {item["provider"]: item for item in registry["provider_bundles"]}
    selected: list[tuple[str, str, str]] = []
    seen: set[tuple[str, str]] = set()

    def add(provider: str, logical: str, component_ids: list[str]) -> None:
        for component_id in component_ids:
            key = (provider, component_id)
            if key not in seen:
                seen.add(key)
                selected.append((provider, logical, component_id))

    for logical in LOGICAL_COMPONENTS:
        provider = assignment[logical]
        add(
            provider,
            logical,
            list(bundle_index[provider]["layers"][LOGICAL_TO_LAYER[logical]]),
        )
    if profile_id == "six-layer-eventing":
        eventing_provider = assignment["component.eventing"]
        event_components = list(
            bundle_index[eventing_provider]["six_layer_event_components"]
        )
        if eventing_provider == "azure":
            rejected_tier = (
                "event-hubs-standard-small-medium"
                if workload_size == "large"
                else "event-hubs-dedicated-large"
            )
            event_components = [
                item for item in event_components if rejected_tier not in item
            ]
        elif eventing_provider == "gcp" and workload_size != "large":
            event_components = [
                item
                for item in event_components
                if "worker-pool-fixed-large" not in item
            ]
        add(eventing_provider, "component.eventing", event_components)
        if any(
            assignment[logical] != eventing_provider
            for logical in (
                "component.ingestion",
                "component.processing",
                "component.hot-storage",
            )
        ):
            add(
                eventing_provider,
                "component.eventing",
                [
                    item
                    for item in bundle_index[eventing_provider][
                        "embedded_event_components"
                    ]
                    if "event-adapter" in item
                ],
            )
        for logical in (
            "component.ingestion",
            "component.processing",
            "component.hot-storage",
        ):
            provider = assignment[logical]
            if provider != eventing_provider:
                embedded = list(bundle_index[provider]["embedded_event_components"])
                if (
                    provider == "gcp"
                    and workload_size == "large"
                    and logical in ("component.ingestion", "component.processing")
                ):
                    embedded.append("gcp.cloud-run-worker-pool-fixed-large")
                add(
                    provider,
                    logical,
                    embedded,
                )
    else:
        event_providers = {assignment[item] for item in EVENT_LOGICAL_COMPONENTS}
        for provider in sorted(event_providers):
            owner = next(
                logical
                for logical in EVENT_LOGICAL_COMPONENTS
                if assignment[logical] == provider
            )
            embedded = list(bundle_index[provider]["embedded_event_components"])
            if len(event_providers) == 1:
                embedded = [
                    item for item in embedded if "only-for-reviewed-remote" not in item
                ]
            add(provider, owner, embedded)
    provider_logicals = {
        provider: [
            logical for logical in logical_components if assignment[logical] == provider
        ]
        for provider in PROVIDERS
    }
    for provider, logicals in provider_logicals.items():
        if not logicals:
            continue
        supports = list(bundle_index[provider]["support_components"])
        add(
            provider,
            logicals[0],
            [
                item
                for item in supports
                if any(
                    marker in item
                    for marker in (
                        "cloudwatch",
                        ".monitor",
                        "cloud-monitoring",
                        "cloud-logging",
                        "log-analytics",
                    )
                )
            ],
        )
        if any(
            assignment[logical] == provider
            for logical in ("component.twin-state", "component.visualization")
        ):
            owner = (
                "component.twin-state"
                if assignment["component.twin-state"] == provider
                else "component.visualization"
            )
            add(
                provider,
                owner,
                [
                    item
                    for item in supports
                    if any(
                        marker in item
                        for marker in (
                            "identity-center-layer-access",
                            "entra-layer-access",
                            "direct-iap-layer-access",
                        )
                    )
                ],
            )
        if assignment["component.visualization"] == provider:
            add(
                provider,
                "component.visualization",
                [item for item in supports if "grafana-tls-load-balancer" in item],
            )
    hot = assignment["component.hot-storage"]
    cool = assignment["component.cool-storage"]
    archive = assignment["component.archive-storage"]
    mover_owners = [(hot, "component.hot-storage")]
    if cool != archive:
        mover_owners.append((cool, "component.cool-storage"))
    for provider, logical in mover_owners:
        add(
            provider,
            logical,
            [
                item
                for item in bundle_index[provider]["support_components"]
                if any(
                    marker in item
                    for marker in (
                        "scheduler",
                        "storage-mover",
                        "scheduled-storage-job",
                        "storage-job",
                        "artifact-registry",
                        ".ecr-",
                        ".acr-",
                    )
                )
            ],
        )
    gcp_container_logicals = tuple(
        logical
        for logical in (
            "component.ingestion",
            "component.processing",
            "component.twin-state",
            "component.visualization",
            "component.eventing",
        )
        if logical in assignment
    )
    if any(assignment[logical] == "gcp" for logical in gcp_container_logicals):
        owner = next(
            logical
            for logical in gcp_container_logicals
            if assignment[logical] == "gcp"
        )
        add(
            "gcp",
            owner,
            [
                item
                for item in bundle_index["gcp"]["support_components"]
                if "artifact-registry" in item
            ],
        )
    return selected


def build_six_layer_eventing_v1_deployment_specification(
    *,
    calculation_run_id: str,
    assignment: Mapping[str, str],
    resolved_workload: ResolvedSixLayerWorkload,
    architecture_profile_ref: Mapping[str, str],
    component_catalog_ref: Mapping[str, str],
    workload_contract_digest: str,
    pricing_evidence_digests: Mapping[str, str],
    resolution_status: str = "offline_contract_fixture",
    definition_lifecycle_statuses: Mapping[str, str] | None = None,
    satisfied_live_gate_ids: frozenset[str] = frozenset(),
    azure_large_autoscale_ru_per_second: int | None = None,
    azure_large_autoscale_evidence_digest: str | None = None,
) -> dict[str, Any]:
    """Build one atomic Six-layer Eventing v1 deployment specification."""

    return _build_deployment_specification(
        calculation_run_id=calculation_run_id,
        assignment=assignment,
        resolved_workload=resolved_workload,
        architecture_profile_ref=architecture_profile_ref,
        component_catalog_ref=component_catalog_ref,
        workload_contract_digest=workload_contract_digest,
        pricing_evidence_digests=pricing_evidence_digests,
        resolution_status=resolution_status,
        definition_lifecycle_statuses=definition_lifecycle_statuses,
        satisfied_live_gate_ids=satisfied_live_gate_ids,
        azure_large_autoscale_ru_per_second=azure_large_autoscale_ru_per_second,
        azure_large_autoscale_evidence_digest=azure_large_autoscale_evidence_digest,
    )


def _build_deployment_specification(
    *,
    calculation_run_id: str,
    assignment: Mapping[str, str],
    resolved_workload: ResolvedSixLayerWorkload,
    architecture_profile_ref: Mapping[str, str],
    component_catalog_ref: Mapping[str, str],
    workload_contract_digest: str,
    pricing_evidence_digests: Mapping[str, str],
    resolution_status: str,
    definition_lifecycle_statuses: Mapping[str, str] | None,
    satisfied_live_gate_ids: frozenset[str],
    azure_large_autoscale_ru_per_second: int | None,
    azure_large_autoscale_evidence_digest: str | None,
) -> dict[str, Any]:

    try:
        UUID(calculation_run_id)
    except (TypeError, ValueError, AttributeError) as exc:
        raise ArchitectureResolutionError(
            "ARCH_WORKLOAD_INCOMPATIBLE",
            "calculationRunId",
            "Calculation run ID must be a UUID",
        ) from exc
    validator, registry, fixed = _contract()
    selected_groups = _selected_groups(
        assignment,
        registry,
        profile_id="six-layer-eventing",
        workload_size=resolved_workload.size,
    )
    selected_providers = sorted({provider for provider, _, _ in selected_groups})
    uses_azure_large_autoscale = (
        resolved_workload.size == "large"
        and assignment["component.hot-storage"] == "azure"
    )
    if set(pricing_evidence_digests) != set(selected_providers) or any(
        not isinstance(value, str) or not _DIGEST.fullmatch(value)
        for value in pricing_evidence_digests.values()
    ):
        raise ArchitectureResolutionError(
            "ARCH_PRICING_EVIDENCE_MISSING",
            "pricingEvidence",
            "Every selected provider requires one pinned pricing-evidence digest",
        )
    if (
        (
            azure_large_autoscale_ru_per_second is not None
            and (
                not isinstance(azure_large_autoscale_ru_per_second, int)
                or isinstance(azure_large_autoscale_ru_per_second, bool)
            )
        )
        or (azure_large_autoscale_ru_per_second is None)
        != (azure_large_autoscale_evidence_digest is None)
        or (
            azure_large_autoscale_evidence_digest is not None
            and not _DIGEST.fullmatch(azure_large_autoscale_evidence_digest)
        )
        or (
            azure_large_autoscale_evidence_digest is not None
            and azure_large_autoscale_evidence_digest
            == registry["capacity_evidence_digest"]
        )
        or (
            not uses_azure_large_autoscale
            and azure_large_autoscale_ru_per_second is not None
        )
    ):
        raise ArchitectureResolutionError(
            "ARCH_WORKLOAD_INCOMPATIBLE",
            "azureLargeAutoscaleEvidence",
            "Measured Azure Large autoscale RU/s and its evidence digest must "
            "be supplied together",
        )
    component_index = {item["component_id"]: item for item in registry["components"]}
    gcp_event_worker_count = 0
    if resolved_workload.size == "large":
        eventing_provider = assignment["component.eventing"]
        if eventing_provider == "gcp":
            # Audit and realtime visualization remain Event-Layer-local. L2
            # adds telemetry processing plus rule evaluation; L3 Hot adds
            # historical persistence plus Twin-state projection. Remote
            # telemetry responsibilities add one source-owned bridge worker
            # allocation per distinct received/processed Event topic.
            local_subscription_count = 2
            if assignment["component.processing"] == "gcp":
                local_subscription_count += 2
            if assignment["component.hot-storage"] == "gcp":
                local_subscription_count += 2
            bridge_channel_ids: set[str] = set()
            if assignment["component.processing"] != "gcp":
                bridge_channel_ids.update(
                    {"telemetry.received.v1", "telemetry.processed.v1"}
                )
            if assignment["component.hot-storage"] != "gcp":
                bridge_channel_ids.add("telemetry.processed.v1")
            gcp_event_worker_count = 21 * (
                local_subscription_count + len(bridge_channel_ids)
            )
        else:
            bridge_channel_ids = set()
            if assignment["component.ingestion"] == "gcp":
                bridge_channel_ids.add("telemetry.received.v1")
            if assignment["component.processing"] == "gcp":
                bridge_channel_ids.add("telemetry.processed.v1")
            gcp_event_worker_count = 21 * len(bridge_channel_ids)
    selections = []
    bindings = []
    for provider, logical, component_id in selected_groups:
        component = component_index[component_id]
        selection_id = f"selection.{provider}.{component_id}"
        dimensions = []
        for dimension_id in component["capacity_dimensions"]:
            value, unit = _dimension_value(
                component_id,
                logical,
                dimension_id,
                resolved_workload,
                registry,
                fixed,
                azure_large_autoscale_ru_per_second=(
                    azure_large_autoscale_ru_per_second
                ),
                gcp_event_worker_count=gcp_event_worker_count,
            )
            classification = _dimension_classification(dimension_id)
            dimension = {
                "dimension_id": f"dimension.{provider}.{component_id}.{dimension_id}",
                "classification": classification,
                "value": value,
                "unit": unit,
                "formula_reference": "formula.phase-08-complete-service-bundles",
                "evidence_reference": (
                    azure_large_autoscale_evidence_digest
                    if dimension_id == "autoscale_max_ru_per_second"
                    and resolved_workload.size == "large"
                    and component_id == "azure.cosmos-db-nosql-raw-and-rollup"
                    and azure_large_autoscale_evidence_digest is not None
                    else registry["capacity_evidence_digest"]
                ),
            }
            if (
                component_id == "aws.kinesis-data-streams"
                and dimension_id == "shards_per_stream"
            ):
                dimension["terraform_target"] = "aws_event_kinesis_shards"
            dimensions.append(dimension)
            bindings.append(
                {
                    "binding_id": f"binding.{provider}.{component_id}.{dimension_id}",
                    "source_kind": "deployment_dimension",
                    "source_ref": dimension["dimension_id"],
                    "destination_selection_id": selection_id,
                    "destination_input_id": f"input.{classification}.{dimension_id}",
                    "value_type": _dimension_value_type(value),
                    "sensitivity": "internal",
                    "resolution_stage": "preplan",
                    "validator_id": _dimension_validator(dimension_id, value),
                    "compatibility_version": "1",
                }
            )
        selections.append(
            {
                "selection_id": selection_id,
                "architecture_assignment_id": (
                    f"assignment.{logical.removeprefix('component.')}"
                ),
                "logical_component_id": logical,
                "implementation_component_id": component_id,
                "implementation_component_digest": component["component_digest"],
                "provider": provider,
                "region": REGIONS[provider],
                "required": True,
                "dimensions": dimensions,
            }
        )
    capacity = _scenario_capacity(registry, resolved_workload.size)
    live_blockers = []
    for provider in selected_providers:
        live_blockers.extend(
            f"gate.live-capacity.{provider}.{gate.replace('_', '-')}"
            for gate in capacity["provider_admission"][provider]["live_gates"]
        )
    if assignment["component.twin-state"] == "aws":
        live_blockers.append("gate.live-pricing.aws.twinmaker-account-plan")
    if resolved_workload.size == "large" and gcp_event_worker_count > 0:
        live_blockers.append("gate.live-capacity.gcp.cloud-run-worker-pool-preview")
    missing_azure_large_measurement = uses_azure_large_autoscale and (
        azure_large_autoscale_ru_per_second is None
        or azure_large_autoscale_evidence_digest is None
    )
    if missing_azure_large_measurement:
        live_blockers.append("gate.live-capacity.azure.cosmos-autoscale-ru")
    blockers = sorted(set(live_blockers) - set(satisfied_live_gate_ids))
    if missing_azure_large_measurement:
        blockers = sorted({*blockers, "gate.live-capacity.azure.cosmos-autoscale-ru"})
    required_definition_keys = {
        "profile",
        "catalog",
        *(f"provider:{provider}" for provider in selected_providers),
    }
    definitions_active = (
        definition_lifecycle_statuses is not None
        and set(definition_lifecycle_statuses) == required_definition_keys
        and set(definition_lifecycle_statuses.values()) == {"active"}
    )
    if not definitions_active:
        blockers.append("gate.profile-activation-pending")
        blockers.sort()
    if resolution_status == "deployment_ready" and blockers:
        raise ArchitectureResolutionError(
            "ARCH_NO_ADMISSIBLE_CANDIDATE",
            "capacity",
            "Architecture candidate has unresolved activation or live-capacity gates",
        )
    if resolution_status not in {"offline_contract_fixture", "deployment_ready"}:
        raise ArchitectureResolutionError(
            "ARCH_WORKLOAD_INCOMPATIBLE",
            "resolutionStatus",
            "Architecture deployment resolution status is unsupported",
        )
    specification = {
        "schema_version": "resolved-deployment-specification.v2",
        "calculation_run_id": calculation_run_id,
        "architecture_profile_ref": dict(architecture_profile_ref),
        "optimization_context": {
            "service_decision_ref": dict(registry["package_ref"]),
            "component_catalog_ref": dict(component_catalog_ref),
            "workload_ref": {
                "id": "six-layer-workload",
                "version": "1",
                "digest": workload_contract_digest,
            },
            "eventing_scenario_ref": dict(resolved_workload.eventing_scenario_ref),
            "formula_set_ref": {
                "id": "phase-08-complete-service-bundles",
                "version": "1",
                "digest": registry["pricing_ownership_digest"],
            },
            "pricing_evidence_refs": [
                {
                    "provider": provider,
                    "digest": pricing_evidence_digests[provider],
                }
                for provider in selected_providers
            ],
        },
        "readiness": {
            "status": resolution_status,
            "blocking_gate_ids": blockers,
        },
        "currency": str(resolved_workload.workload["currency"]),
        "fixed_dimensions": fixed,
        "component_selections": selections,
        "bindings": bindings,
        "digest": "",
    }
    specification["digest"] = _digest(
        {key: value for key, value in specification.items() if key != "digest"}
    )
    errors = sorted(
        validator.iter_errors(specification),
        key=lambda error: tuple(str(part) for part in error.absolute_path),
    )
    if errors:
        raise ArchitectureResolutionError(
            "ARCH_RESOLUTION_BUILD_FAILED",
            "resolvedDeploymentSpecification",
            errors[0].message,
        )
    return specification
