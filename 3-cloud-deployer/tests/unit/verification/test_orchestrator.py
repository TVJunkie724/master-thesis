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


def test_phase_one_failure_skips_each_remaining_phase_once():
    subject = DataFlowVerificationOrchestrator(_context(), lambda *args, **kwargs: False)

    events = asyncio.run(_collect(subject))

    phases = [_payload(event) for event in events if _event_name(event) == "phase"]
    skipped = [phase["phase"] for phase in phases if phase["status"] == "skip"]
    done = _payload(events[-1])
    assert skipped == [2, 3, 4]
    assert done["fail_count"] == 1
    assert done["skip_count"] == 3


def test_phase_four_result_is_independent_from_phase_three_failure(monkeypatch):
    providers = {
        "layer_1_provider": "aws",
        "layer_2_provider": "aws",
        "layer_3_hot_provider": "aws",
        "layer_4_provider": "aws",
    }
    outputs = {
        "aws_l3_hot_reader_url": "https://example.test/hot-reader",
        "aws_twinmaker_workspace_id": "workspace",
    }
    context = _context(
        providers=providers,
        terraform_outputs=outputs,
        optimization={"useEventChecking": True},
    )
    monkeypatch.setattr(
        orchestrator_module.probes,
        "poll_hot_reader",
        lambda *args, **kwargs: ProbeResult(
            success=True,
            evidence={"record_count": 1},
        ),
    )
    monkeypatch.setattr(
        orchestrator_module.probes,
        "check_twinmaker_entity",
        lambda *args, **kwargs: ProbeResult(success=False, error="not found"),
    )
    monkeypatch.setattr(
        orchestrator_module.probes,
        "check_cloud_logs",
        lambda *args, **kwargs: ProbeResult(success=True),
    )
    subject = DataFlowVerificationOrchestrator(context, lambda *args, **kwargs: True)

    events = asyncio.run(_collect(subject))

    phases = [_payload(event) for event in events if _event_name(event) == "phase"]
    terminal = {(phase["phase"], phase["status"]) for phase in phases}
    done = _payload(events[-1])
    assert (3, "fail") in terminal
    assert (4, "pass") in terminal
    assert done["pass_count"] == 3
    assert done["fail_count"] == 1


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


def test_event_checker_probe_uses_trace_specific_marker(monkeypatch):
    captured = {}
    context = _context(optimization={"useEventChecking": True})

    def check_cloud_logs(provider, pattern, *args, **kwargs):
        captured.update(provider=provider, pattern=pattern)
        return ProbeResult(success=True)

    monkeypatch.setattr(
        orchestrator_module.probes,
        "check_cloud_logs",
        check_cloud_logs,
    )
    subject = DataFlowVerificationOrchestrator(context, lambda *args, **kwargs: True)

    async def collect_phase():
        return [
            event
            async for event in subject._phase_event_flow("VERIFY-1234ABCD")
        ]

    asyncio.run(collect_phase())
    assert captured == {
        "provider": "aws",
        "pattern": "T2MC_EVENT_CHECKER_RECEIVED trace_id=VERIFY-1234ABCD",
    }
