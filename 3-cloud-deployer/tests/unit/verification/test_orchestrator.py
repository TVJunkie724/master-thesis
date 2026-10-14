import asyncio
import json
from pathlib import Path

from src.verification import orchestrator as orchestrator_module
from src.verification.contracts import (
    PhaseEmission,
    PhaseOutcome,
    ProbeResult,
    VerificationContext,
)
from src.verification.orchestrator import DataFlowVerificationOrchestrator


def _context(**overrides) -> VerificationContext:
    values = {
        "project_name": "test-twin",
        "project_path": Path("/tmp/test-twin"),
        "providers": {
            "layer_1_provider": "aws",
            "layer_2_provider": "aws",
            "layer_3_hot_provider": "aws",
        },
        "terraform_outputs": {
            "aws_l3_hot_reader_url": "https://example.test/hot-reader",
        },
        "optimization": {},
        "credentials": {},
        "events": [],
    }
    values.update(overrides)
    return VerificationContext(**values)


async def _collect(orchestrator, payload=None) -> list[str]:
    return [
        event
        async for event in orchestrator.stream(
            payload or {"iotDeviceId": "device-1", "temperature": 21}
        )
    ]


def _payload(event: str) -> dict:
    line = next(line for line in event.splitlines() if line.startswith("data: "))
    return json.loads(line.removeprefix("data: "))


def _event_name(event: str) -> str:
    return event.splitlines()[0].removeprefix("event: ")


def test_phase_one_failure_skips_each_remaining_required_phase_once():
    subject = DataFlowVerificationOrchestrator(
        _context(), lambda *args, **kwargs: False
    )

    events = asyncio.run(_collect(subject))

    phases = [_payload(event) for event in events if _event_name(event) == "phase"]
    skipped = [phase["phase"] for phase in phases if phase["status"] == "skip"]
    done = _payload(events[-1])
    assert skipped == [2, 3]
    assert done["fail_count"] == 1
    assert done["skip_count"] == 2


def test_twin_projection_failure_is_terminal_evidence(monkeypatch):
    providers = {
        "layer_1_provider": "aws",
        "layer_2_provider": "aws",
        "layer_3_hot_provider": "aws",
        "layer_4_provider": "aws",
    }
    outputs = {
        "aws_component_twin_state_output": {"workspace_id": "workspace"},
    }
    context = _context(
        providers=providers,
        terraform_outputs=outputs,
        optimization={"useEventChecking": True},
    )
    monkeypatch.setattr(
        orchestrator_module.probes,
        "check_hot_storage_trace",
        lambda *args, **kwargs: ProbeResult(
            success=True,
            evidence={"record_count": 1},
        ),
    )
    monkeypatch.setattr(
        orchestrator_module.probes,
        "check_twinmaker_projection",
        lambda *args, **kwargs: ProbeResult(success=False, error="not found"),
    )
    subject = DataFlowVerificationOrchestrator(context, lambda *args, **kwargs: True)

    events = asyncio.run(_collect(subject))

    phases = [_payload(event) for event in events if _event_name(event) == "phase"]
    terminal = {(phase["phase"], phase["status"]) for phase in phases}
    done = _payload(events[-1])
    assert (3, "fail") in terminal
    assert done["pass_count"] == 2
    assert done["fail_count"] == 1


def test_roundtrip_forces_traceable_twin_projection(monkeypatch):
    captured = {}
    context = _context(
        providers={
            "layer_1_provider": "aws",
            "layer_2_provider": "aws",
            "layer_3_hot_provider": "aws",
        }
    )

    def send_message(*args, **kwargs):
        captured.update(kwargs["payload_override"])
        return True

    monkeypatch.setattr(
        orchestrator_module.probes,
        "check_hot_storage_trace",
        lambda *args, **kwargs: ProbeResult(success=True, evidence={"record_count": 1}),
    )
    subject = DataFlowVerificationOrchestrator(context, send_message)

    events = asyncio.run(
        _collect(subject, {"iotDeviceId": "device-1", "temperature": 23.5})
    )

    done = _payload(events[-1])
    assert captured["projection_candidate"] is True
    assert captured["source_sequence"] == captured["trace_id"]
    assert captured["metric"] == "value"
    assert captured["value"] == 23.5
    assert captured["twin_id"] == "device-1"
    assert done["schema_version"] == "telemetry-verification.v1"
    assert done["trace_id"] == captured["trace_id"]


def test_phase_run_forwards_event_before_phase_completes():
    release = asyncio.Event()

    async def source():
        yield PhaseEmission(event="first")
        await release.wait()
        yield PhaseEmission(outcome=PhaseOutcome(status="pass", passed=1))

    async def exercise():
        run = orchestrator_module._PhaseRun(source())
        events = run.events()
        first = await anext(events)
        assert run.outcome is None
        release.set()
        remaining = [event async for event in events]
        return first, remaining, run.require_outcome()

    first, remaining, outcome = asyncio.run(exercise())
    assert first == "first"
    assert remaining == []
    assert outcome.status == "pass"


def test_aws_projection_uses_canonical_output_bundle_and_trace(monkeypatch):
    captured = {}
    context = _context(
        providers={"layer_4_provider": "aws"},
        terraform_outputs={
            "aws_component_twin_state_output": {"workspace_id": "workspace-1"},
            "aws_region": "eu-central-1",
        },
        credentials={"aws": {"aws_access_key_id": "test"}},
    )
    subject = DataFlowVerificationOrchestrator(context, lambda *args, **kwargs: True)

    def projection(*args, **kwargs):
        captured.update(args=args, kwargs=kwargs)
        return ProbeResult(success=True)

    monkeypatch.setattr(
        orchestrator_module.probes,
        "check_twinmaker_projection",
        projection,
    )

    result = subject._probe_digital_twin(
        "aws",
        "device-1",
        "VERIFY-1234ABCD",
        "value",
        23.5,
        orchestrator_module.datetime.now(orchestrator_module.timezone.utc),
    )

    assert result.success is True
    assert captured["args"][:5] == (
        "workspace-1",
        "device-1",
        "value",
        23.5,
        "VERIFY-1234ABCD",
    )
    assert captured["kwargs"]["aws_region"] == "eu-central-1"


def test_azure_projection_uses_canonical_output_bundle_and_trace(monkeypatch):
    captured = {}
    context = _context(
        providers={"layer_4_provider": "azure"},
        terraform_outputs={
            "azure_component_twin_state_output": {
                "endpoint": "https://twins.example.test"
            }
        },
        credentials={"azure": {"azure_client_id": "test"}},
    )
    subject = DataFlowVerificationOrchestrator(context, lambda *args, **kwargs: True)

    def projection(*args, **kwargs):
        captured.update(args=args, kwargs=kwargs)
        return ProbeResult(success=True)

    monkeypatch.setattr(orchestrator_module.probes, "check_adt_twin", projection)

    result = subject._probe_digital_twin(
        "azure",
        "device-1",
        "VERIFY-1234ABCD",
        "value",
        23.5,
        orchestrator_module.datetime.now(orchestrator_module.timezone.utc),
    )

    assert result.success is True
    assert captured["args"][:3] == (
        "https://twins.example.test",
        {"azure_client_id": "test"},
        "device-1",
    )
    assert captured["kwargs"]["expected_source_sequence"] == "VERIFY-1234ABCD"


def test_gcp_projection_uses_trace_and_project_context(monkeypatch):
    captured = {}
    context = _context(
        project_path=Path("/tmp/project"),
        providers={"layer_4_provider": "gcp"},
        terraform_outputs={
            "gcp_component_twin_state_output": {"service": "Twin Explorer"}
        },
        credentials={"gcp": {"gcp_project_id": "project-1"}},
    )
    subject = DataFlowVerificationOrchestrator(context, lambda *args, **kwargs: True)

    def projection(*args, **kwargs):
        captured.update(args=args, kwargs=kwargs)
        return ProbeResult(success=True)

    monkeypatch.setattr(
        orchestrator_module.probes,
        "check_gcp_twin_projection",
        projection,
    )

    result = subject._probe_digital_twin(
        "gcp",
        "device-1",
        "VERIFY-1234ABCD",
        "value",
        23.5,
        orchestrator_module.datetime.now(orchestrator_module.timezone.utc),
    )

    assert result.success is True
    assert captured["args"][:2] == ("device-1", "VERIFY-1234ABCD")
    assert captured["args"][3] == {"gcp_project_id": "project-1"}
    assert captured["args"][4] == Path("/tmp/project")
