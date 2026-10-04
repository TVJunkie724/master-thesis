"""Azure Six-layer domain landing and local responsibility tests."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
from typing import List, get_type_hints
from unittest.mock import Mock

import azure.functions as func

import pytest


SOURCE_ROOT = (
    Path(__file__).resolve().parents[3]
    / "src"
    / "providers"
    / "azure"
    / "azure_functions"
    / "six-layer-domain"
)


def _load_runtime(module_name: str):
    core_spec = importlib.util.spec_from_file_location(
        f"{module_name}_core",
        SOURCE_ROOT / "core.py",
    )
    assert core_spec is not None and core_spec.loader is not None
    runtime_core = importlib.util.module_from_spec(core_spec)
    core_spec.loader.exec_module(runtime_core)
    spec = importlib.util.spec_from_file_location(
        module_name,
        SOURCE_ROOT / "function_app.py",
    )
    assert spec is not None and spec.loader is not None
    selected_runtime = importlib.util.module_from_spec(spec)
    previous_core = sys.modules.get("core")
    sys.path.insert(0, str(SOURCE_ROOT))
    try:
        sys.modules["core"] = runtime_core
        spec.loader.exec_module(selected_runtime)
    finally:
        sys.path.remove(str(SOURCE_ROOT))
        if previous_core is None:
            sys.modules.pop("core", None)
        else:
            sys.modules["core"] = previous_core
    return selected_runtime


runtime = _load_runtime("azure_six_layer_domain")


def test_event_hub_batch_annotations_are_worker_compatible(monkeypatch):
    # The deployed worker rejects PEP-585 list[T] during indexing even though
    # FunctionApp.get_functions() accepts it. Azure's binding expects typing.List.
    for suffix in ("IOT_PROCESSOR", "REMOTE_TELEMETRY", "BRIDGE_TELEMETRY",
                   "BRIDGE_EVENT_RECEIVED", "BRIDGE_EVENT_PROCESSED"):
        monkeypatch.setenv("SIX_LAYER_" + suffix + "_ENABLED", "true")
    selected = _load_runtime("azure_domain_indexing")
    batches = [f for f in selected.app.get_functions()
               if any(b.type == "eventHubTrigger" for b in f.get_bindings())]
    assert len(batches) == 5
    for function in batches:
        assert get_type_hints(function.get_user_function())["messages"] == List[func.EventHubEvent]


def test_core_scope_does_not_construct_or_publish_a_twin_projection(monkeypatch):
    monkeypatch.setenv("SIX_LAYER_EVALUATION_SCOPE", "core")

    def forbidden(*args, **kwargs):
        pytest.fail("Core must not construct or publish a Twin projection")

    monkeypatch.setattr(runtime, "build_twin_projection", forbidden)
    monkeypatch.setattr(runtime, "_publish_control", forbidden)
    monkeypatch.setattr(runtime, "_materialize_twin_projection", forbidden)
    runtime._project_twin({"payload": {"projection_candidate": True}})


def test_runtime_has_six_layer_profile_identity():
    core_spec = importlib.util.spec_from_file_location(
        "azure_six_layer_domain_profile_core",
        SOURCE_ROOT / "core.py",
    )
    assert core_spec is not None and core_spec.loader is not None
    core = importlib.util.module_from_spec(core_spec)
    core_spec.loader.exec_module(core)

    assert core.PROFILE == "six-layer-eventing@1"


def test_diagnostic_trace_id_is_preserved_for_device_command_delivery():
    event = {
        **_processed_event(),
        "source_sequence": "TRACE-AZURE001",
    }

    assert runtime._diagnostic_trace_id(event) == "TRACE-AZURE001"


def test_remote_event_layer_uses_azure_source_outboxes(monkeypatch):
    telemetry: list[dict[str, object]] = []
    control: list[dict[str, object]] = []
    monkeypatch.setenv("ARCHITECTURE_PROFILE", "six-layer-eventing@1")
    monkeypatch.setenv("SIX_LAYER_EVENT_LAYER_PROVIDER", "aws")
    monkeypatch.setattr(runtime, "_publish_telemetry", telemetry.append)
    monkeypatch.setattr(runtime, "_publish_control", control.append)
    processed = _processed_event()
    matched = runtime.derive_event(
        processed,
        event_type="event.matched.v1",
        producer="component.rule-evaluator",
        payload={
            "device_id": "device-1",
            "rule_id": "rule-1",
            "action": {"type": "lambda", "functionName": "poc-action"},
        },
    )

    runtime._publish_eventing_stream(processed)
    runtime._publish_eventing_control(matched)

    assert telemetry == [processed]
    assert control == [matched]


def test_azure_l2_returns_processed_event_to_selected_event_layer(monkeypatch):
    processed = _processed_event()
    published: list[dict[str, object]] = []
    received = {
        **processed,
        "event_type": "telemetry.received.v1",
        "producer": "component.device-ingress",
    }
    monkeypatch.setenv("ARCHITECTURE_PROFILE", "six-layer-eventing@1")
    monkeypatch.setenv("SIX_LAYER_EVENT_LAYER_PROVIDER", "azure")
    monkeypatch.setattr(runtime, "_invoke_processor_extension", lambda _event: {})
    monkeypatch.setattr(
        runtime,
        "build_processed_event",
        lambda _event, _extension: processed,
    )
    monkeypatch.setattr(runtime, "_publish_eventing_stream", published.append)

    runtime._process_received(received)

    assert published == [processed]


def _processed_event() -> dict[str, object]:
    return {
        "schema_version": "canonical-domain-event.v1",
        "event_id": "event-1",
        "event_type": "telemetry.processed.v1",
        "deployment_id": "deployment-1",
        "source_id": "device-1",
        "source_sequence": "1",
        "occurred_at": "2026-08-14T00:00:00Z",
        "correlation_id": "correlation-1",
        "causation_id": "causation-1",
        "producer": "component.processing",
        "payload": {
            "device_id": "device-1",
            "metric": "temperature",
            "value": 21.5,
        },
    }


@pytest.mark.parametrize(
    ("received_enabled", "processed_enabled"),
    [(True, False), (False, True)],
)
def test_event_bridge_registers_only_the_routed_telemetry_channel(
    monkeypatch,
    received_enabled,
    processed_enabled,
):
    monkeypatch.setenv(
        "SIX_LAYER_BRIDGE_EVENT_RECEIVED_ENABLED",
        str(received_enabled).lower(),
    )
    monkeypatch.setenv(
        "SIX_LAYER_BRIDGE_EVENT_PROCESSED_ENABLED",
        str(processed_enabled).lower(),
    )
    name = f"azure_six_layer_domain_{received_enabled}_{processed_enabled}"
    selected_runtime = _load_runtime(name)

    assert (
        hasattr(selected_runtime, "cross_cloud_event_received_bridge")
        is received_enabled
    )
    assert (
        hasattr(selected_runtime, "cross_cloud_event_processed_bridge")
        is processed_enabled
    )


@pytest.mark.parametrize(
    ("hot_provider", "l2_provider", "expected"),
    [
        ("azure", "aws", ["persist"]),
        ("gcp", "azure", ["rules"]),
        ("azure", "azure", ["persist", "rules"]),
    ],
)
def test_remote_processed_landing_runs_only_azure_responsibilities(
    monkeypatch,
    hot_provider,
    l2_provider,
    expected,
):
    calls: list[str] = []
    monkeypatch.setenv("ARCHITECTURE_PROFILE", "six-layer-eventing@1")
    monkeypatch.setenv("SIX_LAYER_EVENT_LAYER_PROVIDER", "aws")
    monkeypatch.setenv("SIX_LAYER_HOT_PROVIDER", hot_provider)
    monkeypatch.setenv("SIX_LAYER_L2_PROVIDER", l2_provider)
    monkeypatch.setattr(
        runtime,
        "_persist_processed",
        lambda _event: calls.append("persist"),
    )
    monkeypatch.setattr(
        runtime,
        "_evaluate_rules",
        lambda _event: calls.append("rules"),
    )

    runtime._consume(_processed_event())

    assert calls == expected


def test_local_event_layer_processed_roles_remain_provider_scoped(monkeypatch):
    event = _processed_event()
    monkeypatch.setenv("SIX_LAYER_HOT_PROVIDER", "azure")
    monkeypatch.setenv("SIX_LAYER_L2_PROVIDER", "gcp")
    persisted: list[str] = []
    monkeypatch.setattr(
        runtime,
        "_write_raw_and_rollup",
        lambda value: persisted.append(str(value["event_id"])),
    )

    runtime._consume_eventing_delivery("historical-persistence", event)

    assert persisted == ["event-1"]
    with pytest.raises(
        runtime.ContractError,
        match="EVENTING_CONSUMER_PROVIDER_MISMATCH",
    ):
        runtime._consume_eventing_delivery("rule-evaluator", event)


def test_event_layer_rule_control_and_iot_command_preserve_simulator_trace(monkeypatch):
    trace = "TRACE-1234ABCD"
    event = _processed_event()
    event.update(source_sequence=trace, correlation_id=trace)
    event["payload"]["value"] = 42
    monkeypatch.setenv("ARCHITECTURE_PROFILE", "six-layer-eventing@1")
    for layer in ("L1", "L2", "HOT"):
        monkeypatch.setenv("SIX_LAYER_" + layer + "_PROVIDER", "azure")
    monkeypatch.setenv("SIX_LAYER_IOT_HUB_HOSTNAME", "hub.test")
    monkeypatch.setenv("SIX_LAYER_RULES_JSON", json.dumps([{
        "rule_id": "command-check", "condition": "value == INTEGER(42)",
        "action": {"type": "function", "functionName": "poc-command-check",
                   "feedback": {"device_id": "device-1", "payload": "roundtrip-confirmed"}},
    }]))
    queue, outcomes = [], []
    monkeypatch.setattr(runtime, "_publish_eventing_control", queue.append)
    monkeypatch.setattr(runtime, "_post_bound_json", lambda _url, body, **_: runtime._poc_action_result(body))
    monkeypatch.setattr(runtime, "_store_outcome", outcomes.append)
    client = Mock()
    monkeypatch.setattr(runtime, "_iot_command_client", lambda _: client)
    runtime._consume_eventing_delivery("rule-evaluator", event)
    consumed = []
    for _ in range(4):
        assert queue
        item = queue.pop(0)
        consumed.append(item["event_type"])
        runtime._consume_eventing_delivery("control-router", item)
    assert not queue
    assert consumed == ["event.matched.v1", "extension.action.outcome.v1",
                        "device.command.requested.v1", "device.command.outcome.v1"]
    client.send_c2d_message.assert_called_once()
    assert client.send_c2d_message.call_args.args[0] == "device-1"
    assert json.loads(client.send_c2d_message.call_args.args[1]) == {
        "trace_id": trace, "message": "roundtrip-confirmed"}
    assert [item["payload"]["status"] for item in outcomes] == ["SUCCEEDED", "ACCEPTED"]
