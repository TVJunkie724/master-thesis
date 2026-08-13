#!/usr/bin/env python3
"""Deterministically calculate the frozen Phase 8 Eventing scenarios."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any, Iterable


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
EVIDENCE_ROOT = REPOSITORY_ROOT / "docs/research/evidence/phase_08_eventing"
SCENARIO_PATH = EVIDENCE_ROOT / "scenario-inputs.json"
DOMAIN_PATH = EVIDENCE_ROOT / "domain-event-flow-contract.json"
PRICE_PATH = EVIDENCE_ROOT / "pricing-model-matrix.json"
FORMULA_PATH = EVIDENCE_ROOT / "formula-and-unit-ledger.json"
CAPABILITY_PATH = EVIDENCE_ROOT / "provider-capability-matrix.json"
SOURCE_PATH = EVIDENCE_ROOT / "source-ledger.json"
BRIDGE_PATH = EVIDENCE_ROOT / "bridge-decision.json"
RESULT_PATH = EVIDENCE_ROOT / "scenario-cost-results.json"

MONEY_QUANTUM = Decimal("0.000000001")
DECIMAL_GB = Decimal(1_000_000_000)
GIB = Decimal(1_073_741_824)
HOURS_PER_MONTH = Decimal(730)
SECONDS_PER_MONTH = Decimal(2_628_000)


def load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle, parse_float=Decimal)


def canonical_json(value: Any) -> bytes:
    def default(item: Any) -> Any:
        if isinstance(item, Decimal):
            return format(item, "f")
        raise TypeError(type(item).__name__)

    return json.dumps(
        value,
        default=default,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def normalized_digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(value)).hexdigest()


def normalize_for_digest(value: Any, parent_key: str = "") -> Any:
    if isinstance(value, dict):
        return {
            key: normalize_for_digest(nested, key)
            for key, nested in sorted(value.items())
        }
    if isinstance(value, list):
        normalized = [normalize_for_digest(nested, parent_key) for nested in value]
        if all(isinstance(item, dict) for item in normalized):
            identity_fields = (
                ("fact_id",),
                ("intent_id",),
                ("bundle_id",),
                ("alternative_id",),
                ("formula_id",),
                ("normalization_rule_id",),
                ("conversion_id",),
                ("source_id",),
                ("provider", "scenario_id"),
                ("source_provider", "destination_provider"),
                ("source_provider",),
                ("destination_provider",),
                ("ingress_provider", "eventing_provider", "processing_provider"),
            )
            for fields in identity_fields:
                if all(all(field in item for field in fields) for item in normalized):
                    return sorted(
                        normalized,
                        key=lambda item: tuple(str(item[field]) for field in fields),
                    )
        if all(isinstance(item, str) for item in normalized) and (
            parent_key.endswith("_ids")
            or parent_key.endswith("_refs")
            or parent_key in {"members", "consumers"}
        ):
            return sorted(normalized)
        return normalized
    return value


def money(value: Decimal) -> str:
    return format(value.quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP), "f")


def decimal_text(value: Decimal) -> str:
    normalized = value.normalize()
    return format(normalized, "f")


def ceil_decimal(value: Decimal) -> int:
    return math.ceil(value)


def intent_map(pricing: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {item["intent_id"]: item for item in pricing["price_intents"]}


def price(intents: dict[str, dict[str, Any]], intent_id: str) -> Decimal:
    return Decimal(str(intents[intent_id]["unit_price_usd"]))


def progressive_cost(
    quantity: Decimal | int,
    intent: dict[str, Any],
) -> Decimal:
    remaining_quantity = Decimal(str(quantity))
    result = Decimal(0)
    schedule = intent["tier_schedule"]
    for tier in schedule:
        lower = Decimal(str(tier["from_quantity"]))
        upper_value = tier["up_to_quantity"]
        unit_price = Decimal(str(tier["unit_price_usd"]))
        if remaining_quantity <= lower:
            continue
        if upper_value == "unbounded":
            tier_quantity = remaining_quantity - lower
        else:
            upper = Decimal(str(upper_value))
            tier_quantity = min(remaining_quantity, upper) - lower
        if tier_quantity > 0:
            result += tier_quantity * unit_price
    return result


def contribution(
    contribution_id: str,
    member: str,
    amount: Decimal,
    intent_ids: list[str],
    formula_ids: list[str],
    quantities: dict[str, Any],
    notes: str,
) -> dict[str, Any]:
    rendered_quantities: dict[str, Any] = {}
    for key, value in quantities.items():
        if isinstance(value, Decimal):
            rendered_quantities[key] = decimal_text(value)
        else:
            rendered_quantities[key] = value
    return {
        "contribution_id": contribution_id,
        "member": member,
        "amount_usd": money(amount),
        "pricing_intent_ids": intent_ids,
        "formula_ids": formula_ids,
        "normalized_quantities": rendered_quantities,
        "notes": notes,
    }


def total_contributions(items: Iterable[dict[str, Any]]) -> Decimal:
    return sum((Decimal(item["amount_usd"]) for item in items), Decimal(0))


def derive_channels(
    scenario: dict[str, Any],
    shared: dict[str, Any],
) -> list[dict[str, Any]]:
    events = scenario["events_per_month"]
    matches = events * Decimal(str(scenario["rule_match_share"]))
    workflows = matches * Decimal(str(scenario["workflow_start_share_of_matches"]))
    commands = matches * Decimal(str(scenario["device_command_share_of_matches"]))
    counts = {
        "telemetry.received.v1": Decimal(events),
        "telemetry.processed.v1": Decimal(events),
        "event.matched.v1": matches,
        "notification.requested.v1": workflows,
        "device.command.requested.v1": commands,
        "extension.action.outcome.v1": matches,
        "notification.workflow.outcome.v1": workflows,
        "device.command.outcome.v1": commands,
    }
    for channel_id, count in counts.items():
        if count != count.to_integral_value():
            raise ValueError(
                f"{scenario['scenario_id']} derives a fractional count for "
                f"{channel_id}: {count}"
            )

    envelope = shared["average_envelope_overhead_bytes"]
    telemetry_bytes = scenario["average_event_payload_bytes"] + envelope
    payload_bytes = {
        "telemetry.received.v1": telemetry_bytes,
        "telemetry.processed.v1": telemetry_bytes,
        "event.matched.v1": shared["average_match_payload_bytes"] + envelope,
        "notification.requested.v1": (
            shared["average_notification_payload_bytes"] + envelope
        ),
        "device.command.requested.v1": (
            shared["average_device_command_payload_bytes"] + envelope
        ),
        "extension.action.outcome.v1": (
            shared["average_outcome_payload_bytes"] + envelope
        ),
        "notification.workflow.outcome.v1": (
            shared["average_outcome_payload_bytes"] + envelope
        ),
        "device.command.outcome.v1": (
            shared["average_outcome_payload_bytes"] + envelope
        ),
    }
    processed_consumers = len(scenario["mandatory_processed_consumers"]) + len(
        scenario["extra_processed_consumers"]
    )
    consumers = {
        "telemetry.received.v1": 1,
        "telemetry.processed.v1": processed_consumers,
        "event.matched.v1": 1,
        "notification.requested.v1": 1,
        "device.command.requested.v1": 1,
        "extension.action.outcome.v1": 1,
        "notification.workflow.outcome.v1": 1,
        "device.command.outcome.v1": 1,
    }
    payload_class = {
        "telemetry.received.v1": "telemetry",
        "telemetry.processed.v1": "telemetry",
        "event.matched.v1": "match",
        "notification.requested.v1": "notification",
        "device.command.requested.v1": "device_command",
        "extension.action.outcome.v1": "outcome",
        "notification.workflow.outcome.v1": "outcome",
        "device.command.outcome.v1": "outcome",
    }

    rows: list[dict[str, Any]] = []
    retry_share = Decimal(str(scenario["retry_share"]))
    dead_letter_share = Decimal(str(scenario["dead_letter_share"]))
    replay_share = Decimal(str(scenario["replay_share"]))
    for channel_id in counts:
        publishes = int(counts[channel_id])
        consumer_count = consumers[channel_id]
        retry_per_consumer = ceil_decimal(Decimal(publishes) * retry_share)
        dead_letter_per_consumer = ceil_decimal(Decimal(publishes) * dead_letter_share)
        replay_publishes = ceil_decimal(Decimal(publishes) * replay_share)
        rows.append(
            {
                "channel_id": channel_id,
                "payload_class": payload_class[channel_id],
                "canonical_bytes_per_event": payload_bytes[channel_id],
                "publish_count": publishes,
                "consumer_count": consumer_count,
                "base_delivery_count": publishes * consumer_count,
                "retry_delivery_count": retry_per_consumer * consumer_count,
                "dead_letter_count": (dead_letter_per_consumer * consumer_count),
                "replay_publish_count": replay_publishes,
                "replay_delivery_count": replay_publishes * consumer_count,
                "delivery_attempt_count": (
                    publishes * consumer_count
                    + retry_per_consumer * consumer_count
                    + replay_publishes * consumer_count
                ),
            }
        )
    return rows


def select_channels(
    channels: list[dict[str, Any]],
    *,
    channel_ids: set[str] | None = None,
    payload_class: str | None = None,
) -> list[dict[str, Any]]:
    selected = channels
    if channel_ids is not None:
        selected = [row for row in selected if row["channel_id"] in channel_ids]
    if payload_class is not None:
        selected = [row for row in selected if row["payload_class"] == payload_class]
    return selected


def bytes_for(
    channels: Iterable[dict[str, Any]],
    count_field: str,
) -> int:
    return sum(row[count_field] * row["canonical_bytes_per_event"] for row in channels)


def count_for(
    channels: Iterable[dict[str, Any]],
    count_field: str,
) -> int:
    return sum(row[count_field] for row in channels)


def observability(
    channels: list[dict[str, Any]],
    shared: dict[str, Any],
    *,
    include_replay: bool = True,
) -> tuple[int, int]:
    telemetry = select_channels(channels, payload_class="telemetry")
    telemetry_publications = count_for(telemetry, "publish_count")
    telemetry_sampled = ceil_decimal(
        Decimal(telemetry_publications)
        * Decimal(str(shared["observability_assumptions"]["telemetry_sample_share"]))
    )
    fully_captured = 0
    for row in channels:
        if row["payload_class"] in {
            "match",
            "notification",
            "device_command",
            "outcome",
        }:
            fully_captured += row["publish_count"]
        fully_captured += row["retry_delivery_count"]
        fully_captured += row["dead_letter_count"]
        if include_replay:
            fully_captured += row["replay_publish_count"]
    records = telemetry_sampled + fully_captured
    return records, (
        records * shared["observability_assumptions"]["average_record_bytes"]
    )


def serverless_compute(
    provider: str,
    components: list[tuple[str, int, int, int]],
    intents: dict[str, dict[str, Any]],
    contribution_prefix: str,
) -> list[dict[str, Any]]:
    invocations = sum(item[1] for item in components)
    if provider == "aws":
        request_id = "intent.aws.lambda.request"
        compute_id = "intent.aws.lambda.compute"
        gb_seconds = sum(
            Decimal(count)
            * Decimal(duration_ms)
            / Decimal(1000)
            * Decimal(memory_mib)
            / Decimal(1024)
            for _, count, duration_ms, memory_mib in components
        )
        member = "AWS Lambda"
        notes = "1-ms duration billing; free grants applied once to this scoped result."
    elif provider == "azure":
        request_id = "intent.azure.functions.execution"
        compute_id = "intent.azure.functions.compute"
        gb_seconds = sum(
            Decimal(count)
            * max(
                Decimal(1),
                Decimal(math.ceil(duration_ms / 100)) / Decimal(10),
            )
            * Decimal(2)
            for _, count, duration_ms, _ in components
        )
        member = "Azure Functions Flex Consumption"
        notes = (
            "On-demand 2-GiB allocation with a 1-second minimum and "
            "100-ms blocks; free grants applied once to this scoped result."
        )
    elif provider == "gcp":
        request_id = "intent.gcp.cloud-run.request"
        cpu_id = "intent.gcp.cloud-run.cpu"
        memory_id = "intent.gcp.cloud-run.memory"
        rounded_seconds = [
            (
                name,
                count,
                Decimal(math.ceil(duration_ms / 100)) / Decimal(10),
                memory_mib,
            )
            for name, count, duration_ms, memory_mib in components
        ]
        cpu_seconds = sum(
            Decimal(count) * duration * Decimal("0.167")
            for _, count, duration, _ in rounded_seconds
        )
        gib_seconds = sum(
            Decimal(count) * duration * Decimal(memory_mib) / Decimal(1024)
            for _, count, duration, memory_mib in rounded_seconds
        )
        request_cost = progressive_cost(invocations, intents[request_id])
        cpu_cost = progressive_cost(cpu_seconds, intents[cpu_id])
        memory_cost = progressive_cost(gib_seconds, intents[memory_id])
        return [
            contribution(
                f"{contribution_prefix}.cloud-run",
                "Google Cloud Run services",
                request_cost + cpu_cost + memory_cost,
                [request_id, cpu_id, memory_id],
                ["formula.gcp.cloud-run-request"],
                {
                    "requests": invocations,
                    "vcpu_seconds": cpu_seconds,
                    "gib_seconds": gib_seconds,
                    "component_invocations": {
                        name: count for name, count, _, _ in components
                    },
                },
                "100-ms request-based billing at 0.167 vCPU and the component memory allocation; free grants applied once.",
            )
        ]
    else:
        raise ValueError(provider)

    request_cost = progressive_cost(invocations, intents[request_id])
    compute_cost = progressive_cost(gb_seconds, intents[compute_id])
    return [
        contribution(
            f"{contribution_prefix}.serverless",
            member,
            request_cost + compute_cost,
            [request_id, compute_id],
            ["formula.compute.serverless"],
            {
                "requests": invocations,
                "gb_seconds": gb_seconds,
                "component_invocations": {
                    name: count for name, count, _, _ in components
                },
            },
            notes,
        )
    ]


def observability_contribution(
    provider: str,
    log_bytes: int,
    intents: dict[str, dict[str, Any]],
    contribution_prefix: str,
) -> dict[str, Any]:
    if provider == "aws":
        ingestion_id = "intent.aws.cloudwatch.ingestion"
        storage_id = "intent.aws.cloudwatch.storage"
        log_gb = Decimal(log_bytes) / DECIMAL_GB
        amount = progressive_cost(log_gb, intents[ingestion_id])
        amount += progressive_cost(log_gb, intents[storage_id])
        ids = [ingestion_id, storage_id]
        formula = "formula.observability.decimal-gb"
        member = "Amazon CloudWatch Logs"
        note = "Thirty-day retained log volume; the separate reviewed free schedules are applied once."
    elif provider == "azure":
        ingestion_id = "intent.azure.monitor.ingestion"
        log_gb = Decimal(log_bytes) / DECIMAL_GB
        amount = progressive_cost(log_gb, intents[ingestion_id])
        ids = [ingestion_id]
        formula = "formula.observability.decimal-gb"
        member = "Azure Monitor Log Analytics"
        note = "Thirty-day retention is inside the reviewed 31-day included period."
    elif provider == "gcp":
        ingestion_id = "intent.gcp.logging.ingestion"
        log_gb = Decimal(log_bytes) / GIB
        amount = progressive_cost(log_gb, intents[ingestion_id])
        ids = [ingestion_id]
        formula = "formula.observability.binary-gib"
        member = "Google Cloud Logging"
        note = "Thirty-day retention is included."
    else:
        raise ValueError(provider)
    return contribution(
        f"{contribution_prefix}.observability",
        member,
        amount,
        ids,
        [formula],
        {"log_bytes": log_bytes, "normalized_log_volume": log_gb},
        note,
    )


def workflow_contribution(
    provider: str,
    executions: int,
    intents: dict[str, dict[str, Any]],
    contribution_prefix: str,
) -> dict[str, Any]:
    if provider == "aws":
        intent_id = "intent.aws.step-functions.transition"
        transitions = executions * 4
        amount = progressive_cost(transitions, intents[intent_id])
        ids = [intent_id]
        member = "AWS Step Functions Standard"
        quantities = {"executions": executions, "state_transitions": transitions}
    elif provider == "azure":
        builtin_id = "intent.azure.logic-apps.builtin"
        connector_id = "intent.azure.logic-apps.connector"
        internal = executions * 3
        external = executions
        amount = progressive_cost(internal, intents[builtin_id])
        amount += progressive_cost(external, intents[connector_id])
        ids = [builtin_id, connector_id]
        member = "Azure Logic Apps Consumption"
        quantities = {
            "executions": executions,
            "internal_actions": internal,
            "external_connector_actions": external,
        }
    elif provider == "gcp":
        internal_id = "intent.gcp.workflows.internal"
        external_id = "intent.gcp.workflows.external"
        internal = executions * 3
        external = executions

        def billed_steps(actual: int, intent_id: str) -> int:
            free = int(intents[intent_id]["free_quantity"])
            return free + max(0, math.ceil((actual - free) / 1000) * 1000)

        billed_internal = billed_steps(internal, internal_id)
        billed_external = billed_steps(external, external_id)
        amount = progressive_cost(billed_internal, intents[internal_id])
        amount += progressive_cost(billed_external, intents[external_id])
        ids = [internal_id, external_id]
        member = "Google Cloud Workflows"
        quantities = {
            "executions": executions,
            "internal_steps": internal,
            "external_steps": external,
            "billed_internal_steps": billed_internal,
            "billed_external_steps": billed_external,
        }
    else:
        raise ValueError(provider)
    return contribution(
        f"{contribution_prefix}.workflow",
        member,
        amount,
        ids,
        ["formula.workflow.four-step"],
        quantities,
        "Three internal orchestration steps and one external notification step per execution.",
    )


def embedded_result(
    provider: str,
    scenario: dict[str, Any],
    shared: dict[str, Any],
    channels: list[dict[str, Any]],
    intents: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    prefix = f"embedded.{provider}.{scenario['scenario_id']}"
    channel_map = {row["channel_id"]: row for row in channels}
    compute = shared["component_compute_assumptions"]

    def delivered(channel_id: str) -> int:
        row = channel_map[channel_id]
        return row["base_delivery_count"] + row["retry_delivery_count"]

    components = [
        (
            "rule_evaluator",
            delivered("telemetry.processed.v1")
            // channel_map["telemetry.processed.v1"]["consumer_count"],
            compute["rule_evaluator"]["duration_ms"],
            compute["rule_evaluator"]["memory_mib"],
        ),
        (
            "extension_action",
            delivered("event.matched.v1"),
            compute["extension_action"]["duration_ms"],
            compute["extension_action"]["memory_mib"],
        ),
        (
            "workflow_adapter",
            delivered("notification.requested.v1"),
            compute["workflow_adapter"]["duration_ms"],
            compute["workflow_adapter"]["memory_mib"],
        ),
        (
            "device_command_adapter",
            delivered("device.command.requested.v1"),
            compute["device_command_adapter"]["duration_ms"],
            compute["device_command_adapter"]["memory_mib"],
        ),
    ]
    items = serverless_compute(provider, components, intents, prefix)
    workflows = channel_map["notification.requested.v1"]["publish_count"]
    commands = channel_map["device.command.requested.v1"]["publish_count"]
    items.append(workflow_contribution(provider, workflows, intents, prefix))

    direct_input_ids = {
        "telemetry.processed.v1",
        "event.matched.v1",
        "notification.requested.v1",
        "device.command.requested.v1",
    }
    direct_rows = select_channels(channels, channel_ids=direct_input_ids)
    direct_dlq = count_for(direct_rows, "dead_letter_count")

    if provider == "aws":
        connection_id = "intent.aws.iot.connection"
        message_id = "intent.aws.iot.message"
        rule_id = "intent.aws.iot.rule"
        action_id = "intent.aws.iot.action"
        command_id = "intent.aws.iot-command.execution"
        connection_minutes = scenario["concurrent_device_connections"] * 30 * 24 * 60
        raw_chunks = math.ceil(scenario["average_event_payload_bytes"] / 5120)
        message_units = scenario["events_per_month"] * raw_chunks + commands
        amount = progressive_cost(connection_minutes, intents[connection_id])
        amount += progressive_cost(message_units, intents[message_id])
        amount += progressive_cost(scenario["events_per_month"], intents[rule_id])
        amount += progressive_cost(scenario["events_per_month"], intents[action_id])
        amount += progressive_cost(commands, intents[command_id])
        items.append(
            contribution(
                f"{prefix}.device-boundary",
                "AWS IoT Core and AWS IoT Commands",
                amount,
                [connection_id, message_id, rule_id, action_id, command_id],
                ["formula.aws.iot-core", "formula.workflow.four-step"],
                {
                    "connection_minutes": connection_minutes,
                    "raw_5kb_message_units": scenario["events_per_month"] * raw_chunks,
                    "command_message_units": commands,
                    "rule_triggers": scenario["events_per_month"],
                    "rule_actions": scenario["events_per_month"],
                    "command_executions": commands,
                },
                "Raw device payload uses 5-KB chunks; the command execution meter remains separate.",
            )
        )
        dlq_id = "intent.aws.sqs-fifo.request"
        items.append(
            contribution(
                f"{prefix}.direct-dlq",
                "Amazon SQS FIFO failure destination",
                progressive_cost(direct_dlq, intents[dlq_id]),
                [dlq_id],
                ["formula.domain.retry-dlq-replay"],
                {"terminal_direct_delivery_failures": direct_dlq},
                "Producer-owned embedded failure destination; no independent Eventing responsibility is created.",
            )
        )
    elif provider == "azure":
        tier_id, units = {
            "eventing-small-v1": ("intent.azure.iot-hub.s1", 1),
            "eventing-medium-v1": ("intent.azure.iot-hub.s2", 3),
            "eventing-large-v1": ("intent.azure.iot-hub.s3", 1),
        }[scenario["scenario_id"]]
        items.append(
            contribution(
                f"{prefix}.device-boundary",
                "Azure IoT Hub",
                Decimal(units) * price(intents, tier_id),
                [tier_id],
                ["formula.azure.iot-hub-fixed"],
                {"units": units, "device_commands": commands},
                "The reviewed fixed tier allocation covers raw ingress and cloud-to-device queues.",
            )
        )
        base_id = "intent.azure.service-bus.base-hour"
        operation_id = "intent.azure.service-bus.operation"
        operations = direct_dlq
        items.append(
            contribution(
                f"{prefix}.direct-dlq",
                "Azure Service Bus Standard failure destination",
                progressive_cost(730, intents[base_id])
                + progressive_cost(operations, intents[operation_id]),
                [base_id, operation_id],
                ["formula.azure.service-bus-standard"],
                {
                    "namespace_hours": 730,
                    "terminal_direct_delivery_operations": operations,
                },
                "Producer-owned embedded DLQ; its fixed namespace cost is visible.",
            )
        )
    elif provider == "gcp":
        embedded_ids = {
            "telemetry.received.v1",
            "device.command.requested.v1",
            "device.command.outcome.v1",
        }
        embedded_rows = select_channels(channels, channel_ids=embedded_ids)
        pubsub_bytes = bytes_for(embedded_rows, "publish_count")
        pubsub_bytes += bytes_for(embedded_rows, "retry_delivery_count")
        pubsub_bytes += bytes_for(embedded_rows, "base_delivery_count")
        dlq_bytes = bytes_for(embedded_rows, "dead_letter_count")
        pubsub_bytes += dlq_bytes
        throughput_id = "intent.gcp.pubsub.throughput"
        retention_id = "intent.gcp.pubsub.retention"
        throughput_gib = Decimal(pubsub_bytes) / GIB
        retained_gib_month = (
            Decimal(bytes_for(embedded_rows, "publish_count") + dlq_bytes)
            / GIB
            * Decimal(scenario["retention_hours"])
            / HOURS_PER_MONTH
        )
        items.append(
            contribution(
                f"{prefix}.pubsub-boundary",
                "Google Cloud Pub/Sub embedded device and command outbox",
                progressive_cost(throughput_gib, intents[throughput_id])
                + progressive_cost(retained_gib_month, intents[retention_id]),
                [throughput_id, retention_id],
                ["formula.gcp.pubsub", "formula.retention.average-storage"],
                {
                    "throughput_bytes": pubsub_bytes,
                    "throughput_gib": throughput_gib,
                    "retained_gib_month": retained_gib_month,
                },
                "Pub/Sub owns the durable command acknowledgement until a correlated device outcome.",
            )
        )
        cluster_id = "intent.gcp.gke.cluster"
        node_id = "intent.gcp.compute.e2-standard-8"
        disk_id = "intent.gcp.pd-balanced"
        rule_id = "intent.gcp.network.forwarding-rule"
        lb_id = "intent.gcp.network.lb-processing"
        software_id = "intent.gcp.bifromq.software"
        command_rows = select_channels(
            channels,
            channel_ids={
                "device.command.requested.v1",
                "device.command.outcome.v1",
            },
        )
        command_bytes = sum(
            (row["publish_count"] + row["retry_delivery_count"])
            * row["canonical_bytes_per_event"]
            for row in command_rows
        )
        device_telemetry_bytes = (
            scenario["events_per_month"]
            * scenario["average_event_payload_bytes"]
        )
        broker_nodes, integration_nodes, integration_clients = {
            "eventing-small-v1": (3, 0, 3),
            "eventing-medium-v1": (3, 0, 6),
            "eventing-large-v1": (12, 4, 300),
        }[scenario["scenario_id"]]
        total_nodes = broker_nodes + integration_nodes
        device_telemetry_gib = Decimal(device_telemetry_bytes) / GIB
        command_gib = Decimal(command_bytes) / GIB
        amount = HOURS_PER_MONTH * price(intents, cluster_id)
        amount += Decimal(total_nodes) * HOURS_PER_MONTH * price(intents, node_id)
        amount += (
            Decimal(total_nodes)
            * Decimal(100)
            * HOURS_PER_MONTH
            * price(intents, disk_id)
        )
        amount += HOURS_PER_MONTH * price(intents, rule_id)
        amount += (device_telemetry_gib + command_gib) * price(intents, lb_id)
        items.append(
            contribution(
                f"{prefix}.mqtt-boundary",
                "Apache BifroMQ 4.0.0-incubating on GKE Standard",
                amount,
                [
                    cluster_id,
                    node_id,
                    disk_id,
                    rule_id,
                    lb_id,
                    software_id,
                ],
                ["formula.gcp.bifromq-gke"],
                {
                    "cluster_hours": 730,
                    "broker_node_count": broker_nodes,
                    "integration_node_count": integration_nodes,
                    "total_nodes": total_nodes,
                    "node_hours": total_nodes * 730,
                    "disk_gib_per_node": 100,
                    "disk_gib_hours": total_nodes * 100 * 730,
                    "forwarding_rule_hours": 730,
                    "integration_clients": integration_clients,
                    "configured_bandwidth_mib_per_second_per_client": 1,
                    "device_telemetry_data_gib": device_telemetry_gib,
                    "command_data_gib": command_gib,
                },
                (
                    "Full bidirectional device boundary with ordered QoS1 "
                    "MQTT-to-Pub/Sub integration; Large uses 12 broker nodes, "
                    "four integration-worker nodes, and 300 configured 1-MiB/s "
                    "clients. Software price is zero; operational labor is "
                    "qualitative and live payload-size testing remains mandatory."
                ),
            )
        )
    else:
        raise ValueError(provider)

    log_records, log_bytes = observability(channels, shared, include_replay=False)
    items.append(observability_contribution(provider, log_bytes, intents, prefix))
    total = total_contributions(items)
    return {
        "bundle_id": f"bundle.{provider}.embedded@1",
        "provider": provider,
        "status": "publishable_bounded_estimate",
        "cost_contributions": items,
        "total_monthly_usd": money(total),
        "normalized_summary": {
            "workflow_executions": workflows,
            "device_commands": commands,
            "direct_retry_compute_invocations": sum(item[1] for item in components),
            "direct_dead_letters": direct_dlq,
            "observability_records": log_records,
        },
        "extra_functionality": (
            ["provider-hosted MQTT boundary"] if provider == "gcp" else []
        ),
        "formula_refs": sorted(
            {formula_id for item in items for formula_id in item["formula_ids"]}
        ),
        "source_refs": sorted(
            {
                intents[intent_id]["source_id"]
                for item in items
                for intent_id in item["pricing_intent_ids"]
            }
        ),
    }


def telemetry_capacity(scenario_id: str, provider: str) -> dict[str, Any]:
    if provider == "aws":
        shards = {
            "eventing-small-v1": 1,
            "eventing-medium-v1": 6,
            "eventing-large-v1": 200,
        }[scenario_id]
        return {"streams": 2, "shards_per_stream": shards}
    if provider == "azure":
        if scenario_id == "eventing-large-v1":
            return {
                "tier": "dedicated",
                "clusters": 1,
                "streams": 2,
                "partitions_per_stream": 200,
            }
        namespaces, throughput_units = {
            "eventing-small-v1": (1, 1),
            "eventing-medium-v1": (1, 11),
        }[scenario_id]
        return {
            "tier": "standard",
            "streams": 2,
            "namespaces": namespaces,
            "throughput_units_per_namespace": throughput_units,
        }
    if provider == "gcp":
        return {"topics": 2}
    raise ValueError(provider)


def azure_dedicated_capacity(
    scenario: dict[str, Any],
    telemetry: list[dict[str, Any]],
    *,
    include_delivery: bool,
) -> dict[str, Any]:
    peak_events_per_second = scenario["peak_events_per_second"]
    peak_ingress_bytes_per_second = sum(
        peak_events_per_second * row["canonical_bytes_per_event"] for row in telemetry
    )
    peak_egress_bytes_per_second = (
        sum(
            peak_events_per_second
            * row["canonical_bytes_per_event"]
            * row["consumer_count"]
            for row in telemetry
        )
        if include_delivery
        else 0
    )
    headroom = Decimal("1.2")
    conservative_ingress_bytes_per_second_per_cu = Decimal(100_000_000)
    conservative_egress_bytes_per_second_per_cu = Decimal(200_000_000)
    ingress_cus = ceil_decimal(
        Decimal(peak_ingress_bytes_per_second)
        * headroom
        / conservative_ingress_bytes_per_second_per_cu
    )
    egress_cus = ceil_decimal(
        Decimal(peak_egress_bytes_per_second)
        * headroom
        / conservative_egress_bytes_per_second_per_cu
    )
    capacity_units = max(1, ingress_cus, egress_cus)
    if capacity_units > 10:
        raise ValueError(
            "Azure Event Hubs Dedicated allocation exceeds the reviewed "
            f"self-service maximum: {capacity_units} CU"
        )
    return {
        "tier": "dedicated",
        "clusters": 1,
        "streams": len(telemetry),
        "partitions_per_stream": 200,
        "peak_ingress_bytes_per_second": peak_ingress_bytes_per_second,
        "peak_egress_bytes_per_second": peak_egress_bytes_per_second,
        "capacity_headroom": headroom,
        "ingress_capacity_units": ingress_cus,
        "egress_capacity_units": egress_cus,
        "capacity_units": capacity_units,
    }


def event_layer_result(
    provider: str,
    scenario: dict[str, Any],
    shared: dict[str, Any],
    channels: list[dict[str, Any]],
    intents: dict[str, dict[str, Any]],
    remote_delivery_channel_ids: set[str] | None = None,
) -> dict[str, Any]:
    prefix = f"event-layer.{provider}.{scenario['scenario_id']}"
    telemetry = select_channels(channels, payload_class="telemetry")
    control = [row for row in channels if row["payload_class"] != "telemetry"]
    items: list[dict[str, Any]] = []
    capacity = telemetry_capacity(scenario["scenario_id"], provider)

    if provider == "aws":
        shard_id = "intent.aws.kinesis.shard-hour"
        put_id = "intent.aws.kinesis.put-unit"
        consumer_id = "intent.aws.kinesis.efo-consumer-hour"
        read_id = "intent.aws.kinesis.efo-read"
        retention_id = "intent.aws.kinesis.extended-retention"
        shards_per_stream = capacity["shards_per_stream"]
        total_shards = shards_per_stream * 2
        put_units = sum(
            row["publish_count"] * math.ceil(row["canonical_bytes_per_event"] / 25600)
            for row in telemetry
        )
        consumer_shard_hours = sum(
            row["consumer_count"] * shards_per_stream * 730 for row in telemetry
        )
        read_gb = Decimal(bytes_for(telemetry, "delivery_attempt_count")) / DECIMAL_GB
        extended_shard_hours = (
            total_shards * 730 if scenario["retention_hours"] > 24 else 0
        )
        kinesis_amount = (
            Decimal(total_shards * 730) * price(intents, shard_id)
            + Decimal(put_units) * price(intents, put_id)
            + Decimal(consumer_shard_hours) * price(intents, consumer_id)
            + read_gb * price(intents, read_id)
            + Decimal(extended_shard_hours) * price(intents, retention_id)
        )
        items.append(
            contribution(
                f"{prefix}.telemetry-log",
                "Amazon Kinesis Data Streams",
                kinesis_amount,
                [shard_id, put_id, consumer_id, read_id, retention_id],
                ["formula.aws.kinesis-provisioned"],
                {
                    **capacity,
                    "total_shard_hours": total_shards * 730,
                    "put_payload_units": put_units,
                    "consumer_shard_hours": consumer_shard_hours,
                    "efo_read_gb": read_gb,
                    "extended_retention_shard_hours": extended_shard_hours,
                },
                "Replay is a retained-stream read and is not double-counted as a new PUT.",
            )
        )
        sns_publish_id = "intent.aws.sns-fifo.publish"
        sns_ingress_id = "intent.aws.sns-fifo.ingress"
        sns_delivery_id = "intent.aws.sns-fifo.delivery"
        sns_egress_id = "intent.aws.sns-fifo.egress"
        archive_processing_id = "intent.aws.sns-fifo.archive-processing"
        archive_storage_id = "intent.aws.sns-fifo.archive-storage"
        sqs_id = "intent.aws.sqs-fifo.request"
        control_publishes = count_for(control, "publish_count")
        control_publish_bytes = bytes_for(control, "publish_count")
        control_deliveries = count_for(control, "delivery_attempt_count")
        control_delivery_bytes = bytes_for(control, "delivery_attempt_count")
        sns_requests = sum(
            row["publish_count"] * math.ceil(row["canonical_bytes_per_event"] / 65536)
            for row in control
        )
        sns_ingress_gb = Decimal(control_publish_bytes) / DECIMAL_GB
        sns_egress_gb = Decimal(control_delivery_bytes) / DECIMAL_GB
        archive_gb_month = (
            sns_ingress_gb * Decimal(scenario["retention_hours"]) / HOURS_PER_MONTH
        )
        sqs_requests = control_deliveries * 3
        control_amount = (
            Decimal(sns_requests) * price(intents, sns_publish_id)
            + sns_ingress_gb * price(intents, sns_ingress_id)
            + Decimal(control_deliveries) * price(intents, sns_delivery_id)
            + sns_egress_gb * price(intents, sns_egress_id)
            + sns_ingress_gb * price(intents, archive_processing_id)
            + archive_gb_month * price(intents, archive_storage_id)
            + progressive_cost(sqs_requests, intents[sqs_id])
        )
        items.append(
            contribution(
                f"{prefix}.control-fanout",
                "Amazon SNS FIFO and SQS FIFO",
                control_amount,
                [
                    sns_publish_id,
                    sns_ingress_id,
                    sns_delivery_id,
                    sns_egress_id,
                    archive_processing_id,
                    archive_storage_id,
                    sqs_id,
                ],
                [
                    "formula.aws.sns-sqs-fifo",
                    "formula.retention.average-storage",
                ],
                {
                    "control_publishes": control_publishes,
                    "sns_64kb_publish_requests": sns_requests,
                    "control_publish_bytes": control_publish_bytes,
                    "control_delivery_attempts": control_deliveries,
                    "sqs_requests": sqs_requests,
                    "archive_gb_month": archive_gb_month,
                },
                "One FIFO queue per named consumer; replay uses the archive and preserves the channel fan-out.",
            )
        )
        s3_put_id = "intent.aws.s3.dlq-put"
        s3_storage_id = "intent.aws.s3.dlq-storage"
        telemetry_dlq = count_for(telemetry, "dead_letter_count")
        telemetry_dlq_bytes = bytes_for(telemetry, "dead_letter_count")
        dlq_gb_month = (
            Decimal(telemetry_dlq_bytes)
            / DECIMAL_GB
            * Decimal(scenario["retention_hours"])
            / HOURS_PER_MONTH
        )
        items.append(
            contribution(
                f"{prefix}.telemetry-dlq",
                "Amazon S3 Standard",
                Decimal(telemetry_dlq) * price(intents, s3_put_id)
                + progressive_cost(dlq_gb_month, intents[s3_storage_id]),
                [s3_put_id, s3_storage_id],
                ["formula.aws.s3-dlq"],
                {
                    "terminal_telemetry_failures": telemetry_dlq,
                    "dead_letter_bytes": telemetry_dlq_bytes,
                    "retained_gb_month": dlq_gb_month,
                },
                "Full-record terminal telemetry failures only; control failures remain in SQS DLQs.",
            )
        )
    elif provider == "azure":
        if scenario["scenario_id"] == "eventing-large-v1":
            capacity = azure_dedicated_capacity(
                scenario,
                telemetry,
                include_delivery=True,
            )
            cu_id = "intent.azure.event-hubs-dedicated.cu-hour"
            cu_hours = capacity["capacity_units"] * 730
            items.append(
                contribution(
                    f"{prefix}.telemetry-log",
                    "Azure Event Hubs Dedicated",
                    Decimal(cu_hours) * price(intents, cu_id),
                    [cu_id],
                    ["formula.azure.event-hubs-dedicated"],
                    {
                        **capacity,
                        "capacity_unit_hours": cu_hours,
                    },
                    "One six-CU cluster carries both telemetry Event Hubs and the explicit dead-letter Event Hub; replay is a checkpoint read.",
                )
            )
        else:
            tu_id = "intent.azure.event-hubs.tu-hour"
            ingress_id = "intent.azure.event-hubs.ingress"
            ingress_units = sum(
                row["publish_count"]
                * math.ceil(row["canonical_bytes_per_event"] / 65536)
                for row in telemetry
            )
            telemetry_dlq_units = sum(
                row["dead_letter_count"]
                * math.ceil(row["canonical_bytes_per_event"] / 65536)
                for row in telemetry
            )
            tu_hours = (
                capacity["namespaces"]
                * capacity["throughput_units_per_namespace"]
                * 730
            )
            amount = Decimal(tu_hours) * price(intents, tu_id)
            amount += Decimal(ingress_units + telemetry_dlq_units) * price(
                intents, ingress_id
            )
            items.append(
                contribution(
                    f"{prefix}.telemetry-log",
                    "Azure Event Hubs Standard",
                    amount,
                    [tu_id, ingress_id],
                    ["formula.azure.event-hubs-standard"],
                    {
                        **capacity,
                        "throughput_unit_hours": tu_hours,
                        "ingress_64kb_units": ingress_units,
                        "dead_letter_64kb_units": telemetry_dlq_units,
                    },
                    "The explicit dead-letter Event Hub shares the selected namespace capacity; replay is a checkpoint read.",
                )
            )
        base_id = "intent.azure.service-bus.base-hour"
        operation_id = "intent.azure.service-bus.operation"
        control_publishes = count_for(control, "publish_count")
        control_deliveries = count_for(control, "delivery_attempt_count")
        operations = control_publishes + control_deliveries * 3
        items.append(
            contribution(
                f"{prefix}.control-fanout",
                "Azure Service Bus Standard",
                progressive_cost(730, intents[base_id])
                + progressive_cost(operations, intents[operation_id]),
                [base_id, operation_id],
                ["formula.azure.service-bus-standard"],
                {
                    "namespace_hours": 730,
                    "control_publish_operations": control_publishes,
                    "delivery_receive_complete_operations": (control_deliveries * 3),
                    "total_operations": operations,
                },
                "Sessions provide per-device order; the namespace's native DLQs own terminal control failures.",
            )
        )
    elif provider == "gcp":
        throughput_id = "intent.gcp.pubsub.throughput"
        retention_id = "intent.gcp.pubsub.retention"
        base_publish_bytes = bytes_for(channels, "publish_count")
        delivery_bytes = bytes_for(channels, "delivery_attempt_count")
        dlq_bytes = bytes_for(channels, "dead_letter_count")
        throughput_bytes = base_publish_bytes + delivery_bytes + dlq_bytes
        throughput_gib = Decimal(throughput_bytes) / GIB
        retained_gib_month = (
            Decimal(base_publish_bytes + dlq_bytes)
            / GIB
            * Decimal(scenario["retention_hours"])
            / HOURS_PER_MONTH
        )
        items.append(
            contribution(
                f"{prefix}.broker",
                "Google Cloud Pub/Sub",
                progressive_cost(throughput_gib, intents[throughput_id])
                + progressive_cost(retained_gib_month, intents[retention_id]),
                [throughput_id, retention_id],
                ["formula.gcp.pubsub", "formula.retention.average-storage"],
                {
                    **capacity,
                    "publish_bytes": base_publish_bytes,
                    "delivery_attempt_bytes": delivery_bytes,
                    "dead_letter_publish_bytes": dlq_bytes,
                    "throughput_gib": throughput_gib,
                    "retained_gib_month": retained_gib_month,
                },
                "Per-request payloads exceed the 1,000-byte minimum; replay redelivers retained messages.",
            )
        )
    else:
        raise ValueError(provider)

    remote_delivery_channel_ids = remote_delivery_channel_ids or set()
    local_adapter_channels = [
        row for row in channels if row["channel_id"] not in remote_delivery_channel_ids
    ]
    adapter_invocations = count_for(local_adapter_channels, "delivery_attempt_count")
    adapter = shared["component_compute_assumptions"]["event_delivery_adapter"]
    if provider == "gcp" and scenario["scenario_id"] == "eventing-large-v1":
        cpu_id = "intent.gcp.cloud-run-worker.cpu"
        memory_id = "intent.gcp.cloud-run-worker.memory"
        local_telemetry = select_channels(
            local_adapter_channels, payload_class="telemetry"
        )
        local_control = [
            row for row in local_adapter_channels if row["payload_class"] != "telemetry"
        ]
        telemetry_subscription_count = sum(
            row["consumer_count"] for row in local_telemetry
        )
        instances = telemetry_subscription_count * 21
        cpu_seconds = Decimal(instances) * SECONDS_PER_MONTH
        memory_seconds = Decimal(instances) * SECONDS_PER_MONTH * Decimal("0.5")
        items.append(
            contribution(
                f"{prefix}.delivery-adapter",
                "Google Cloud Run worker pools",
                progressive_cost(cpu_seconds, intents[cpu_id])
                + progressive_cost(memory_seconds, intents[memory_id]),
                [cpu_id, memory_id],
                ["formula.gcp.cloud-run-worker-pool"],
                {
                    "instances": instances,
                    "streaming_pull_streams": instances,
                    "vcpu_seconds": cpu_seconds,
                    "gib_seconds": memory_seconds,
                    "logical_telemetry_delivery_attempts": count_for(
                        local_telemetry, "delivery_attempt_count"
                    ),
                },
                "Each local telemetry subscription uses 21 one-stream instances; a remote subscription is replaced by its bridge-forwarder.",
            )
        )
        control_invocations = count_for(local_control, "delivery_attempt_count")
        if control_invocations:
            items.extend(
                serverless_compute(
                    provider,
                    [
                        (
                            "event_control_delivery_adapter",
                            control_invocations,
                            adapter["duration_ms"],
                            adapter["memory_mib"],
                        )
                    ],
                    intents,
                    f"{prefix}.control-delivery-adapter",
                )
            )
    else:
        items.extend(
            serverless_compute(
                provider,
                [
                    (
                        "event_delivery_adapter",
                        adapter_invocations,
                        adapter["duration_ms"],
                        adapter["memory_mib"],
                    )
                ],
                intents,
                f"{prefix}.delivery-adapter",
            )
        )

    log_records, log_bytes = observability(channels, shared)
    items.append(observability_contribution(provider, log_bytes, intents, prefix))
    total = total_contributions(items)
    return {
        "bundle_id": f"bundle.{provider}.event-layer@1",
        "provider": provider,
        "status": "publishable_bounded_estimate",
        "cost_contributions": items,
        "total_monthly_usd": money(total),
        "normalized_summary": {
            "base_publishes": count_for(channels, "publish_count"),
            "base_deliveries": count_for(channels, "base_delivery_count"),
            "retry_deliveries": count_for(channels, "retry_delivery_count"),
            "dead_letters": count_for(channels, "dead_letter_count"),
            "replay_publishes": count_for(channels, "replay_publish_count"),
            "replay_deliveries": count_for(channels, "replay_delivery_count"),
            "delivery_adapter_invocations": adapter_invocations,
            "remote_delivery_channels_replaced_by_bridge": len(
                remote_delivery_channel_ids
            ),
            "observability_records": log_records,
        },
        "extra_functionality": [
            "independent fan-out",
            "bounded retention and replay",
            "dead-letter ownership",
            "per-device ordering",
        ],
        "formula_refs": sorted(
            {formula_id for item in items for formula_id in item["formula_ids"]}
        ),
        "source_refs": sorted(
            {
                intents[intent_id]["source_id"]
                for item in items
                for intent_id in item["pricing_intent_ids"]
            }
        ),
    }


def transfer_cost(
    provider: str,
    transfer_bytes: int,
    intents: dict[str, dict[str, Any]],
) -> tuple[str, Decimal, Decimal]:
    intent_id = f"intent.{provider}.transfer.internet-egress"
    unit = GIB if provider == "gcp" else DECIMAL_GB
    quantity = Decimal(transfer_bytes) / unit
    return intent_id, quantity, progressive_cost(quantity, intents[intent_id])


def channel_fixture(
    channels: list[dict[str, Any]],
    channel_ids: set[str] | None = None,
) -> list[dict[str, Any]]:
    selected = (
        channels
        if channel_ids is None
        else select_channels(channels, channel_ids=channel_ids)
    )
    result = []
    for row in selected:
        original_consumers = row["consumer_count"]
        retry_deliveries = row["retry_delivery_count"] // original_consumers
        dead_letters = row["dead_letter_count"] // original_consumers
        replay_deliveries = row["replay_publish_count"]
        result.append(
            dict(
                row,
                consumer_count=1,
                base_delivery_count=row["publish_count"],
                retry_delivery_count=retry_deliveries,
                dead_letter_count=dead_letters,
                replay_delivery_count=replay_deliveries,
                delivery_attempt_count=(
                    row["publish_count"] + retry_deliveries + replay_deliveries
                ),
            )
        )
    return result


def destination_fixture(
    channels: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    result = []
    for row in channels:
        accepted_publishes = row["publish_count"] + row["replay_publish_count"]
        result.append(
            dict(
                row,
                publish_count=accepted_publishes,
                base_delivery_count=accepted_publishes,
                retry_delivery_count=0,
                dead_letter_count=0,
                replay_publish_count=0,
                replay_delivery_count=0,
                delivery_attempt_count=accepted_publishes,
            )
        )
    return result


def bridge_compute_and_transfer(
    source_provider: str,
    scenario: dict[str, Any],
    shared: dict[str, Any],
    channels: list[dict[str, Any]],
    intents: dict[str, dict[str, Any]],
    prefix: str,
) -> list[dict[str, Any]]:
    retry_share = Decimal(str(scenario["retry_share"]))
    replay_share = Decimal(str(scenario["replay_share"]))
    bridge_events = 0
    transfer_bytes = 0
    channel_attempts = []
    for row in channels:
        retries = ceil_decimal(Decimal(row["publish_count"]) * retry_share)
        replays = ceil_decimal(Decimal(row["publish_count"]) * replay_share)
        attempts = row["publish_count"] + retries + replays
        bridge_events += attempts
        transfer_bytes += attempts * row["canonical_bytes_per_event"]
        channel_attempts.append(
            {
                "channel_id": row["channel_id"],
                "payload_class": row["payload_class"],
                "attempts": attempts,
            }
        )
    batch = shared["component_compute_assumptions"]["bridge"]["max_batch_events"]
    bridge = shared["component_compute_assumptions"]["bridge"]
    runtime_quantities: dict[str, Any]
    if source_provider in {"aws", "azure"}:
        invocations = bridge_events
        items = serverless_compute(
            source_provider,
            [
                (
                    "bridge_forwarder",
                    invocations,
                    bridge["duration_ms"],
                    bridge["memory_mib"],
                )
            ],
            intents,
            f"{prefix}.forwarder",
        )
        runtime_quantities = {
            "runtime_mode": "event_source_trigger",
            "cost_batch_assumption": "one_billed_invocation_per_attempt",
            "configured_trigger_batch_max_events": batch,
            "bridge_invocations": invocations,
        }
    elif source_provider == "gcp" and scenario["scenario_id"] == "eventing-large-v1":
        telemetry_channels = [
            row for row in channel_attempts if row["payload_class"] == "telemetry"
        ]
        control_channels = [
            row for row in channel_attempts if row["payload_class"] != "telemetry"
        ]
        instances_per_telemetry_channel = 21
        worker_instances = len(telemetry_channels) * instances_per_telemetry_channel
        items = []
        if worker_instances:
            cpu_id = "intent.gcp.cloud-run-worker.cpu"
            memory_id = "intent.gcp.cloud-run-worker.memory"
            cpu_seconds = Decimal(worker_instances) * SECONDS_PER_MONTH
            memory_seconds = cpu_seconds * Decimal("0.5")
            items.append(
                contribution(
                    f"{prefix}.forwarder.worker-pool",
                    "Google Cloud Run bridge worker pools",
                    progressive_cost(cpu_seconds, intents[cpu_id])
                    + progressive_cost(memory_seconds, intents[memory_id]),
                    [cpu_id, memory_id],
                    ["formula.gcp.cloud-run-worker-pool", "formula.bridge.compute"],
                    {
                        "instances": worker_instances,
                        "instances_per_telemetry_channel": (
                            instances_per_telemetry_channel
                        ),
                        "telemetry_channel_count": len(telemetry_channels),
                        "streaming_pull_streams": worker_instances,
                        "vcpu_seconds": cpu_seconds,
                        "gib_seconds": memory_seconds,
                        "logical_telemetry_attempts": sum(
                            row["attempts"] for row in telemetry_channels
                        ),
                    },
                    "Each telemetry channel uses 21 one-stream StreamingPull workers; no request batching is assumed.",
                )
            )
        control_invocations = sum(row["attempts"] for row in control_channels)
        if control_invocations:
            items.extend(
                serverless_compute(
                    source_provider,
                    [
                        (
                            "bridge_control_forwarder",
                            control_invocations,
                            bridge["duration_ms"],
                            bridge["memory_mib"],
                        )
                    ],
                    intents,
                    f"{prefix}.forwarder.control",
                )
            )
        runtime_quantities = {
            "runtime_mode": "streaming_pull_worker_pool_plus_control_push",
            "cost_batch_assumption": (
                "telemetry_streaming_pull_workers_and_one_control_push_per_attempt"
            ),
            "configured_trigger_batch_max_events": batch,
            "bridge_invocations": control_invocations,
            "worker_instances": worker_instances,
            "instances_per_telemetry_channel": (instances_per_telemetry_channel),
        }
    elif source_provider == "gcp":
        invocations = bridge_events
        items = serverless_compute(
            source_provider,
            [
                (
                    "bridge_forwarder",
                    invocations,
                    bridge["duration_ms"],
                    bridge["memory_mib"],
                )
            ],
            intents,
            f"{prefix}.forwarder",
        )
        runtime_quantities = {
            "runtime_mode": "authenticated_pubsub_push",
            "cost_batch_assumption": "one_push_request_per_attempt",
            "configured_trigger_batch_max_events": batch,
            "bridge_invocations": invocations,
        }
    else:
        raise ValueError(source_provider)

    for item in items:
        if "formula.bridge.compute" not in item["formula_ids"]:
            item["formula_ids"].append("formula.bridge.compute")
    transfer_id, transfer_quantity, amount = transfer_cost(
        source_provider, transfer_bytes, intents
    )
    items.append(
        contribution(
            f"{prefix}.egress",
            f"{source_provider.upper()} internet data transfer",
            amount,
            [transfer_id],
            ["formula.transfer.progressive-egress"],
            {
                "bridge_event_attempts": bridge_events,
                "channel_attempts": channel_attempts,
                **runtime_quantities,
                "transfer_bytes": transfer_bytes,
                "provider_transfer_quantity": transfer_quantity,
            },
            "Source provider owns egress; canonical envelope bytes only, with retry and replay attempts included.",
        )
    )
    return items


def landing_cost(
    provider: str,
    scenario: dict[str, Any],
    channels: list[dict[str, Any]],
    intents: dict[str, dict[str, Any]],
    prefix: str,
    include_delivery: bool,
) -> list[dict[str, Any]]:
    telemetry = select_channels(channels, payload_class="telemetry")
    control = [row for row in channels if row["payload_class"] != "telemetry"]
    items: list[dict[str, Any]] = []
    if telemetry:
        if provider == "aws":
            shards_per_stream = {
                "eventing-small-v1": 1,
                "eventing-medium-v1": 6,
                "eventing-large-v1": 200,
            }[scenario["scenario_id"]]
            shard_id = "intent.aws.kinesis.shard-hour"
            put_id = "intent.aws.kinesis.put-unit"
            consumer_id = "intent.aws.kinesis.efo-consumer-hour"
            read_id = "intent.aws.kinesis.efo-read"
            retention_id = "intent.aws.kinesis.extended-retention"
            stream_count = len(telemetry)
            shard_hours = stream_count * shards_per_stream * 730
            put_units = sum(
                row["publish_count"]
                * math.ceil(row["canonical_bytes_per_event"] / 25600)
                for row in telemetry
            )
            amount = Decimal(shard_hours) * price(intents, shard_id)
            amount += Decimal(put_units) * price(intents, put_id)
            consumer_shard_hours = (
                stream_count * shards_per_stream * 730 if include_delivery else 0
            )
            read_gb = (
                Decimal(bytes_for(telemetry, "delivery_attempt_count")) / DECIMAL_GB
                if include_delivery
                else Decimal(0)
            )
            extended_shard_hours = (
                shard_hours if scenario["retention_hours"] > 24 else 0
            )
            amount += Decimal(consumer_shard_hours) * price(intents, consumer_id)
            amount += read_gb * price(intents, read_id)
            amount += Decimal(extended_shard_hours) * price(intents, retention_id)
            telemetry_intent_ids = [shard_id, put_id, retention_id]
            if include_delivery:
                telemetry_intent_ids.extend([consumer_id, read_id])
            items.append(
                contribution(
                    f"{prefix}.telemetry-landing",
                    "Amazon Kinesis Data Streams landing",
                    amount,
                    telemetry_intent_ids,
                    ["formula.aws.kinesis-provisioned"],
                    {
                        "streams": stream_count,
                        "shards_per_stream": shards_per_stream,
                        "shard_hours": shard_hours,
                        "put_payload_units": put_units,
                        "bridge_consumer_shard_hours": consumer_shard_hours,
                        "bridge_read_gb": read_gb,
                        "extended_retention_shard_hours": extended_shard_hours,
                    },
                    "Destination durable acceptance; downstream consumer compute is outside the bridge result.",
                )
            )
        elif provider == "azure":
            if scenario["scenario_id"] == "eventing-large-v1":
                capacity = azure_dedicated_capacity(
                    scenario,
                    telemetry,
                    include_delivery=include_delivery,
                )
                cu_id = "intent.azure.event-hubs-dedicated.cu-hour"
                cu_hours = capacity["capacity_units"] * 730
                items.append(
                    contribution(
                        f"{prefix}.telemetry-landing",
                        "Azure Event Hubs Dedicated landing",
                        Decimal(cu_hours) * price(intents, cu_id),
                        [cu_id],
                        ["formula.azure.event-hubs-dedicated"],
                        {
                            **capacity,
                            "capacity_unit_hours": cu_hours,
                        },
                        "Destination durable acceptance on a Large-dimensioned Dedicated cluster; downstream consumer compute is outside the bridge result.",
                    )
                )
            else:
                canonical_peak_bytes_per_second = scenario["peak_events_per_second"] * (
                    scenario["average_event_payload_bytes"] + 1024
                )
                required_tu_per_stream = math.ceil(
                    Decimal(str(canonical_peak_bytes_per_second))
                    * Decimal("1.2")
                    / DECIMAL_GB
                    * Decimal(1000)
                )
                required_tu = required_tu_per_stream * len(telemetry)
                namespaces = math.ceil(required_tu / 40)
                tu_per_namespace = math.ceil(required_tu / namespaces)
                tu_id = "intent.azure.event-hubs.tu-hour"
                ingress_id = "intent.azure.event-hubs.ingress"
                ingress_units = sum(
                    row["publish_count"]
                    * math.ceil(row["canonical_bytes_per_event"] / 65536)
                    for row in telemetry
                )
                tu_hours = namespaces * tu_per_namespace * 730
                amount = Decimal(tu_hours) * price(intents, tu_id)
                amount += Decimal(ingress_units) * price(intents, ingress_id)
                items.append(
                    contribution(
                        f"{prefix}.telemetry-landing",
                        "Azure Event Hubs Standard landing",
                        amount,
                        [tu_id, ingress_id],
                        ["formula.azure.event-hubs-standard"],
                        {
                            "streams": len(telemetry),
                            "required_ingress_tu_per_stream": (required_tu_per_stream),
                            "namespaces": namespaces,
                            "throughput_units_per_namespace": tu_per_namespace,
                            "throughput_unit_hours": tu_hours,
                            "ingress_64kb_units": ingress_units,
                        },
                        "Destination durable acceptance; downstream consumer compute is outside the bridge result.",
                    )
                )
        elif provider == "gcp":
            throughput_id = "intent.gcp.pubsub.throughput"
            retention_id = "intent.gcp.pubsub.retention"
            publish_bytes = bytes_for(telemetry, "publish_count")
            delivery_bytes = (
                bytes_for(telemetry, "delivery_attempt_count")
                if include_delivery
                else 0
            )
            throughput_gib = Decimal(publish_bytes + delivery_bytes) / GIB
            retained_gib_month = (
                Decimal(publish_bytes)
                / GIB
                * Decimal(scenario["retention_hours"])
                / HOURS_PER_MONTH
            )
            items.append(
                contribution(
                    f"{prefix}.telemetry-landing",
                    "Google Cloud Pub/Sub telemetry landing",
                    progressive_cost(throughput_gib, intents[throughput_id])
                    + progressive_cost(retained_gib_month, intents[retention_id]),
                    [throughput_id, retention_id],
                    [
                        "formula.gcp.pubsub",
                        "formula.retention.average-storage",
                    ],
                    {
                        "publish_bytes": publish_bytes,
                        "optional_delivery_bytes": delivery_bytes,
                        "throughput_gib": throughput_gib,
                        "retained_gib_month": retained_gib_month,
                    },
                    "Destination durable acceptance; no hidden downstream delivery is charged unless explicitly requested.",
                )
            )
        else:
            raise ValueError(provider)

    if control:
        publishes = count_for(control, "publish_count")
        publish_bytes = bytes_for(control, "publish_count")
        if provider == "aws":
            publish_id = "intent.aws.sns-fifo.publish"
            ingress_id = "intent.aws.sns-fifo.ingress"
            delivery_id = "intent.aws.sns-fifo.delivery"
            egress_id = "intent.aws.sns-fifo.egress"
            archive_processing_id = "intent.aws.sns-fifo.archive-processing"
            archive_storage_id = "intent.aws.sns-fifo.archive-storage"
            sqs_id = "intent.aws.sqs-fifo.request"
            requests = sum(
                row["publish_count"]
                * math.ceil(row["canonical_bytes_per_event"] / 65536)
                for row in control
            )
            delivery_count = (
                count_for(control, "delivery_attempt_count") if include_delivery else 0
            )
            sqs_requests = delivery_count * 3
            publish_gb = Decimal(publish_bytes) / DECIMAL_GB
            archive_gb_month = (
                publish_gb * Decimal(scenario["retention_hours"]) / HOURS_PER_MONTH
            )
            amount = Decimal(requests) * price(intents, publish_id)
            amount += publish_gb * price(intents, ingress_id)
            amount += Decimal(delivery_count) * price(intents, delivery_id)
            amount += (
                publish_gb * price(intents, egress_id)
                if include_delivery
                else Decimal(0)
            )
            amount += publish_gb * price(intents, archive_processing_id)
            amount += archive_gb_month * price(intents, archive_storage_id)
            amount += progressive_cost(sqs_requests, intents[sqs_id])
            ids = [
                publish_id,
                ingress_id,
                delivery_id,
                egress_id,
                archive_processing_id,
                archive_storage_id,
                sqs_id,
            ]
            member = "Amazon SNS/SQS FIFO control landing"
            quantities = {
                "control_publishes": publishes,
                "sns_64kb_requests": requests,
                "publish_bytes": publish_bytes,
                "optional_delivery_count": delivery_count,
                "optional_sqs_requests": sqs_requests,
                "archive_gb_month": archive_gb_month,
            }
            formula = "formula.aws.sns-sqs-fifo"
        elif provider == "azure":
            base_id = "intent.azure.service-bus.base-hour"
            operation_id = "intent.azure.service-bus.operation"
            delivery_count = (
                count_for(control, "delivery_attempt_count") if include_delivery else 0
            )
            operations = publishes + delivery_count * 2
            amount = progressive_cost(730, intents[base_id])
            amount += progressive_cost(operations, intents[operation_id])
            ids = [base_id, operation_id]
            member = "Azure Service Bus Standard control landing"
            quantities = {
                "namespace_hours": 730,
                "control_publishes": publishes,
                "optional_delivery_attempts": delivery_count,
                "operations": operations,
            }
            formula = "formula.azure.service-bus-standard"
        elif provider == "gcp":
            throughput_id = "intent.gcp.pubsub.throughput"
            retention_id = "intent.gcp.pubsub.retention"
            delivery_bytes = (
                bytes_for(control, "delivery_attempt_count") if include_delivery else 0
            )
            throughput_gib = Decimal(publish_bytes + delivery_bytes) / GIB
            retained_gib_month = (
                Decimal(publish_bytes)
                / GIB
                * Decimal(scenario["retention_hours"])
                / HOURS_PER_MONTH
            )
            amount = progressive_cost(throughput_gib, intents[throughput_id])
            amount += progressive_cost(retained_gib_month, intents[retention_id])
            ids = [throughput_id, retention_id]
            member = "Google Cloud Pub/Sub control landing"
            quantities = {
                "publish_bytes": publish_bytes,
                "optional_delivery_bytes": delivery_bytes,
                "throughput_gib": throughput_gib,
                "retained_gib_month": retained_gib_month,
            }
            formula = "formula.gcp.pubsub"
        else:
            raise ValueError(provider)
        items.append(
            contribution(
                f"{prefix}.control-landing",
                member,
                amount,
                ids,
                [formula],
                quantities,
                "Channel-specific durable landing cost; workflow and consumer runtime remain outside the bridge result.",
            )
        )
    return items


def source_outbox_cost(
    provider: str,
    scenario: dict[str, Any],
    channels: list[dict[str, Any]],
    intents: dict[str, dict[str, Any]],
    prefix: str,
) -> list[dict[str, Any]]:
    # The source outbox is the same durable landing shape plus one bridge
    # delivery. It remains producer-owned and does not create a general layer.
    items = landing_cost(
        provider,
        scenario,
        channels,
        intents,
        f"{prefix}.source-outbox",
        include_delivery=True,
    )
    for item in items:
        item["member"] = item["member"].replace(" landing", " source outbox")
        item["notes"] = "Source-owned durable outbox and bridge subscription. " + item[
            "notes"
        ].replace("Destination durable acceptance; ", "")
    return items


def directed_pair_result(
    source_provider: str,
    destination_provider: str,
    scenario: dict[str, Any],
    shared: dict[str, Any],
    channels: list[dict[str, Any]],
    intents: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    fixture = channel_fixture(channels)
    prefix = (
        f"bridge.{source_provider}-to-{destination_provider}.{scenario['scenario_id']}"
    )
    items = source_outbox_cost(source_provider, scenario, fixture, intents, prefix)
    items.extend(
        bridge_compute_and_transfer(
            source_provider,
            scenario,
            shared,
            fixture,
            intents,
            prefix,
        )
    )
    _, bridge_log_bytes = observability(fixture, shared)
    items.append(
        observability_contribution(
            source_provider,
            bridge_log_bytes,
            intents,
            f"{prefix}.bridge",
        )
    )
    items.extend(
        landing_cost(
            destination_provider,
            scenario,
            destination_fixture(fixture),
            intents,
            f"{prefix}.destination",
            include_delivery=False,
        )
    )
    total = total_contributions(items)
    return {
        "route_id": f"route.{source_provider}-to-{destination_provider}.all-domain-channels@1",
        "source_provider": source_provider,
        "destination_provider": destination_provider,
        "status": "publishable_capability_admissible_live_pending",
        "fixture_scope": "one copy of every closed-world domain-event channel; destination fan-out is excluded",
        "cost_contributions": items,
        "total_monthly_usd": money(total),
        "source_refs": sorted(
            {
                intents[intent_id]["source_id"]
                for item in items
                for intent_id in item["pricing_intent_ids"]
            }
        ),
    }


def three_provider_result(
    placement: dict[str, Any],
    scenario: dict[str, Any],
    shared: dict[str, Any],
    channels: list[dict[str, Any]],
    intents: dict[str, dict[str, Any]],
    *,
    include_event_layer_contributions: bool = False,
) -> dict[str, Any]:
    ingress = placement["ingress_provider"]
    eventing = placement["eventing_provider"]
    processing = placement["processing_provider"]
    explicit_hot_storage = "hot_storage_provider" in placement
    hot_storage = placement.get("hot_storage_provider", processing)
    ingress_produced_channel_ids = {
        "telemetry.received.v1",
        "device.command.outcome.v1",
    }
    processing_produced_channel_ids = {
        "telemetry.processed.v1",
        "event.matched.v1",
        "notification.requested.v1",
        "device.command.requested.v1",
        "extension.action.outcome.v1",
        "notification.workflow.outcome.v1",
    }
    ingress_consumed_channel_ids = {"device.command.requested.v1"}
    processing_consumed_channel_ids = {
        "telemetry.received.v1",
        "telemetry.processed.v1",
        "event.matched.v1",
        "notification.requested.v1",
    }
    hot_storage_consumed_channel_ids = {
        "telemetry.processed.v1",
        "extension.action.outcome.v1",
        "notification.workflow.outcome.v1",
        "device.command.outcome.v1",
    }
    all_channel_ids = ingress_produced_channel_ids | processing_produced_channel_ids
    remote_delivery_channel_ids: set[str] = set()
    if processing != eventing:
        remote_delivery_channel_ids |= processing_consumed_channel_ids
    if hot_storage != eventing:
        remote_delivery_channel_ids |= hot_storage_consumed_channel_ids
    if ingress != eventing:
        remote_delivery_channel_ids |= ingress_consumed_channel_ids
    placement_channels = []
    for row in select_channels(channels, channel_ids=all_channel_ids):
        placement_channels.extend(
            channel_fixture([row])
            if row["channel_id"] in remote_delivery_channel_ids
            else [row]
        )
    placement_event_layer = event_layer_result(
        eventing,
        scenario,
        shared,
        placement_channels,
        intents,
        remote_delivery_channel_ids=remote_delivery_channel_ids,
    )
    items: list[dict[str, Any]] = []
    placement_key = f"{ingress}-{eventing}-{processing}"
    if explicit_hot_storage:
        placement_key = f"{placement_key}-{hot_storage}"

    processing_delivery_channel_ids = set(processing_consumed_channel_ids)
    if hot_storage == processing:
        processing_delivery_channel_ids |= hot_storage_consumed_channel_ids
    route_specs = [
        (
            "ingress-to-eventing",
            ingress,
            eventing,
            channel_fixture(channels, ingress_produced_channel_ids),
            True,
            False,
            ("edge.ingestion-to-eventing",),
        ),
        (
            "processing-to-eventing",
            processing,
            eventing,
            channel_fixture(channels, processing_produced_channel_ids),
            True,
            False,
            ("edge.processing-to-eventing",),
        ),
        (
            "eventing-to-processing",
            eventing,
            processing,
            channel_fixture(channels, processing_delivery_channel_ids),
            False,
            True,
            (
                "edge.eventing-to-processing",
                "edge.eventing-to-hot-storage",
            )
            if explicit_hot_storage and hot_storage == processing
            else ("edge.eventing-to-processing",),
        ),
        (
            "eventing-to-ingress",
            eventing,
            ingress,
            channel_fixture(channels, ingress_consumed_channel_ids),
            False,
            True,
            ("edge.eventing-to-ingestion",),
        ),
    ]
    if explicit_hot_storage and hot_storage != processing:
        route_specs.append(
            (
                "eventing-to-hot-storage",
                eventing,
                hot_storage,
                channel_fixture(channels, hot_storage_consumed_channel_ids),
                False,
                True,
                ("edge.eventing-to-hot-storage",),
            )
        )
    route_summaries = []
    bridge_log_bytes_by_provider = {
        "aws": 0,
        "azure": 0,
        "gcp": 0,
    }
    for (
        role,
        source,
        destination,
        fixture,
        add_source_outbox,
        add_destination_landing,
        logical_edge_ids,
    ) in route_specs:
        if source == destination:
            continue
        prefix = f"three-provider.{placement_key}.{scenario['scenario_id']}.{role}"
        route_items: list[dict[str, Any]] = []
        if add_source_outbox:
            route_items.extend(
                source_outbox_cost(source, scenario, fixture, intents, prefix)
            )
        route_items.extend(
            bridge_compute_and_transfer(
                source,
                scenario,
                shared,
                fixture,
                intents,
                prefix,
            )
        )
        _, route_log_bytes = observability(fixture, shared)
        bridge_log_bytes_by_provider[source] += route_log_bytes
        if add_destination_landing:
            route_items.extend(
                landing_cost(
                    destination,
                    scenario,
                    destination_fixture(fixture),
                    intents,
                    f"{prefix}.destination",
                    include_delivery=False,
                )
            )
        route_summaries.append(
            {
                "route_role": role,
                **(
                    {"logical_edge_ids": list(logical_edge_ids)}
                    if explicit_hot_storage
                    else {}
                ),
                "source_provider": source,
                "destination_provider": destination,
                "source_outbox_cost_included": add_source_outbox,
                "destination_landing_cost_included": (add_destination_landing),
                "deduplicated_event_layer_endpoint": (
                    "destination" if not add_destination_landing else "source"
                ),
                "subtotal_usd": money(total_contributions(route_items)),
            }
        )
        items.extend(route_items)

    shared_observability_items: list[dict[str, Any]] = []
    for provider, log_bytes in bridge_log_bytes_by_provider.items():
        if log_bytes:
            shared_observability_items.append(
                observability_contribution(
                    provider,
                    log_bytes,
                    intents,
                    (
                        f"three-provider.{placement_key}."
                        f"{scenario['scenario_id']}.bridge-shared"
                    ),
                )
            )
    items.extend(shared_observability_items)

    event_layer_total = Decimal(placement_event_layer["total_monthly_usd"])
    bridge_total = total_contributions(items)
    result = {
        "placement_id": f"placement.{placement_key}@1",
        "ingress_provider": ingress,
        "eventing_provider": eventing,
        "processing_provider": processing,
        **({"hot_storage_provider": hot_storage} if explicit_hot_storage else {}),
        "status": placement["status"],
        "topology": (
            "single_cloud"
            if len({ingress, eventing, processing, hot_storage}) == 1
            else "two_provider"
            if len({ingress, eventing, processing, hot_storage}) == 2
            else "hub_and_spoke"
        ),
        "event_layer_bundle_ref": (placement_event_layer["bundle_id"]),
        "event_layer_bundle_total_usd": money(event_layer_total),
        "bridge_route_summaries": route_summaries,
        "bridge_shared_observability_usd": money(
            total_contributions(shared_observability_items)
        ),
        "bridge_cost_contributions": items,
        "bridge_addition_total_usd": money(bridge_total),
        "event_scope_total_usd": money(event_layer_total + bridge_total),
        "scope_note": (
            "This is Event-Layer plus deduplicated bridge infrastructure only. All eight domain channels are routed from their component owner through the Eventing provider to one landing copy per remote consumer provider; fan-out among colocated consumers happens after landing. Remote delivery adapters are replaced by bridge forwarders rather than double-counted. Domain-responsibility and full-profile totals remain Phase 8.10."
            if len({ingress, eventing, processing, hot_storage}) == 3
            else "This is Event-Layer plus deduplicated bridge infrastructure only. Each remote domain channel is routed from its component owner through the Eventing provider to one landing copy per remote consumer provider; fan-out among colocated consumers happens after landing. Same-provider edges remain local, and remote delivery adapters are replaced by bridge forwarders rather than double-counted. Domain-responsibility and full-profile totals remain Phase 8.10."
        ),
    }
    if include_event_layer_contributions:
        result["event_layer_cost_contributions"] = placement_event_layer[
            "cost_contributions"
        ]
    return result


def build_result_from_documents(
    scenario_doc: dict[str, Any],
    domain_doc: dict[str, Any],
    pricing_doc: dict[str, Any],
    formula_doc: dict[str, Any],
    capability_doc: dict[str, Any],
    source_doc: dict[str, Any],
    bridge_doc: dict[str, Any],
) -> dict[str, Any]:
    intents = intent_map(pricing_doc)
    shared = scenario_doc["shared_assumptions"]
    scenarios_out = []
    providers = ["aws", "azure", "gcp"]

    for scenario in scenario_doc["scenarios"]:
        channels = derive_channels(scenario, shared)
        embedded = {
            provider: embedded_result(provider, scenario, shared, channels, intents)
            for provider in providers
        }
        event_layer = {
            provider: event_layer_result(provider, scenario, shared, channels, intents)
            for provider in providers
        }
        pair_results = [
            directed_pair_result(
                row["source_provider"],
                row["destination_provider"],
                scenario,
                shared,
                channels,
                intents,
            )
            for row in sorted(
                capability_doc["directed_pair_cases"],
                key=lambda row: (
                    row["source_provider"],
                    row["destination_provider"],
                ),
            )
        ]
        three_provider = [
            three_provider_result(
                row,
                scenario,
                shared,
                channels,
                intents,
            )
            for row in sorted(
                capability_doc["three_provider_cases"],
                key=lambda row: (
                    row["ingress_provider"],
                    row["eventing_provider"],
                    row["processing_provider"],
                ),
            )
        ]
        single_cloud = [
            {
                "provider": row["provider"],
                "event_scope_status": row["event_scope_status"],
                "whole_profile_status": row["whole_profile_status"],
                "embedded_bundle_ref": embedded[row["provider"]]["bundle_id"],
                "embedded_event_cost_usd": embedded[row["provider"]][
                    "total_monthly_usd"
                ],
                "event_layer_bundle_ref": event_layer[row["provider"]]["bundle_id"],
                "event_layer_cost_usd": event_layer[row["provider"]][
                    "total_monthly_usd"
                ],
                "bridge_invocations": 0,
                "cross_cloud_egress_bytes": 0,
                "scope_note": "Separate event-scope subtotals; not a full-profile total or cross-profile ranking.",
            }
            for row in capability_doc["single_cloud_cases"]
        ]
        scenarios_out.append(
            {
                "scenario_id": scenario["scenario_id"],
                "normalized_channels": channels,
                "embedded_bundle_results": [
                    embedded[provider] for provider in providers
                ],
                "event_layer_bundle_results": [
                    event_layer[provider] for provider in providers
                ],
                "single_cloud_results": single_cloud,
                "directed_pair_bridge_results": pair_results,
                "three_provider_results": three_provider,
            }
        )

    body: dict[str, Any] = {
        "$schema": "schemas/scenario-cost-results.schema.json",
        "schema_version": "scenario-cost-results.v1",
        "result_set_id": "phase-08-eventing-cost-results@1",
        "calculation_scope": "embedded domain-event behavior and incremental Event-Layer/bridge costs only; no full-profile ranking",
        "input_digests": {
            "scenario_inputs": normalized_digest(normalize_for_digest(scenario_doc)),
            "domain_event_flow_contract": normalized_digest(
                normalize_for_digest(domain_doc)
            ),
            "pricing_model_matrix": normalized_digest(
                normalize_for_digest(pricing_doc)
            ),
            "formula_and_unit_ledger": normalized_digest(
                normalize_for_digest(formula_doc)
            ),
            "provider_capability_matrix": normalized_digest(
                normalize_for_digest(capability_doc)
            ),
            "source_ledger": normalized_digest(normalize_for_digest(source_doc)),
            "bridge_decision": normalized_digest(normalize_for_digest(bridge_doc)),
        },
        "scenarios": scenarios_out,
    }
    body["result_digest"] = normalized_digest(body)
    return body


def build_result() -> dict[str, Any]:
    return build_result_from_documents(
        load_json(SCENARIO_PATH),
        load_json(DOMAIN_PATH),
        load_json(PRICE_PATH),
        load_json(FORMULA_PATH),
        load_json(CAPABILITY_PATH),
        load_json(SOURCE_PATH),
        load_json(BRIDGE_PATH),
    )


def write_result(value: dict[str, Any]) -> None:
    rendered = (
        json.dumps(
            value,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )
    temporary = RESULT_PATH.with_suffix(".json.tmp")
    temporary.write_text(rendered, encoding="utf-8")
    temporary.replace(RESULT_PATH)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--check",
        action="store_true",
        help="Fail unless the committed result is byte-identical.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    expected = build_result()
    if args.check:
        if not RESULT_PATH.exists():
            print(f"error: missing {RESULT_PATH}")
            return 1
        current = RESULT_PATH.read_text(encoding="utf-8")
        rendered = (
            json.dumps(
                expected,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            + "\n"
        )
        if current != rendered:
            print("error: scenario-cost-results.json is not reproducible")
            return 1
        print(f"verified byte-identical scenario results ({expected['result_digest']})")
        return 0

    write_result(expected)
    print(
        f"wrote {RESULT_PATH.relative_to(REPOSITORY_ROOT)} "
        f"({expected['result_digest']})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
