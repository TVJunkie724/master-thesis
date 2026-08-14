"""Azure Six-layer domain landing and local responsibility tests."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import pytest


SOURCE_ROOT = (
    Path(__file__).resolve().parents[3]
    / "src"
    / "providers"
    / "azure"
    / "azure_functions"
    / "six-layer-domain"
)
SPEC = importlib.util.spec_from_file_location(
    "azure_six_layer_domain",
    SOURCE_ROOT / "function_app.py",
)
assert SPEC is not None and SPEC.loader is not None
runtime = importlib.util.module_from_spec(SPEC)
sys.path.insert(0, str(SOURCE_ROOT))
try:
    SPEC.loader.exec_module(runtime)
finally:
    sys.path.remove(str(SOURCE_ROOT))


def test_runtime_has_six_layer_profile_identity():
    core_spec = importlib.util.spec_from_file_location(
        "azure_six_layer_domain_profile_core",
        SOURCE_ROOT / "core.py",
    )
    assert core_spec is not None and core_spec.loader is not None
    core = importlib.util.module_from_spec(core_spec)
    core_spec.loader.exec_module(core)

    assert core.PROFILE == "six-layer-eventing@1"


def test_remote_event_layer_uses_azure_source_outboxes(monkeypatch):
    telemetry: list[dict[str, object]] = []
    control: list[dict[str, object]] = []
    monkeypatch.setenv("ARCHITECTURE_PROFILE", "six-layer-eventing@1")
    monkeypatch.setenv("V2_EVENT_LAYER_PROVIDER", "aws")
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
    monkeypatch.setenv("V2_EVENT_LAYER_PROVIDER", "azure")
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
        "V2_BRIDGE_EVENT_RECEIVED_ENABLED",
        str(received_enabled).lower(),
    )
    monkeypatch.setenv(
        "V2_BRIDGE_EVENT_PROCESSED_ENABLED",
        str(processed_enabled).lower(),
    )
    name = f"azure_six_layer_domain_{received_enabled}_{processed_enabled}"
    spec = importlib.util.spec_from_file_location(name, SOURCE_ROOT / "function_app.py")
    assert spec is not None and spec.loader is not None
    selected_runtime = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(SOURCE_ROOT))
    try:
        spec.loader.exec_module(selected_runtime)
    finally:
        sys.path.remove(str(SOURCE_ROOT))

    assert hasattr(selected_runtime, "cross_cloud_event_received_bridge") is received_enabled
    assert hasattr(selected_runtime, "cross_cloud_event_processed_bridge") is processed_enabled


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
    monkeypatch.setenv("V2_EVENT_LAYER_PROVIDER", "aws")
    monkeypatch.setenv("V2_HOT_PROVIDER", hot_provider)
    monkeypatch.setenv("V2_L2_PROVIDER", l2_provider)
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
    monkeypatch.setenv("V2_HOT_PROVIDER", "azure")
    monkeypatch.setenv("V2_L2_PROVIDER", "gcp")
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
