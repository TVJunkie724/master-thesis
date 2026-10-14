from datetime import datetime, timedelta, timezone
import asyncio
import json
from pathlib import Path
from threading import Event
from types import SimpleNamespace

import pytest

from src.log_tracing.registry import TraceNotFound, TraceRegistry
from src.log_tracing.fetchers import LogEntry, ProviderFetchResult
from src.log_tracing.service import (
    FORWARD_TRACE_CHECKPOINTS,
    TRACE_QUERY_LOOKBACK,
    LogTraceService,
    expected_trace_checkpoints,
)


def _service():
    return LogTraceService(
        TraceRegistry(
            cooldown=timedelta(seconds=30),
            lifetime=timedelta(seconds=120),
        ),
        timeout_seconds=1,
        poll_interval_seconds=1,
    )


def test_service_rejects_non_positive_timing_contracts():
    registry = TraceRegistry(
        cooldown=timedelta(seconds=30),
        lifetime=timedelta(seconds=120),
    )

    with pytest.raises(ValueError, match="timeout"):
        LogTraceService(registry, timeout_seconds=0, poll_interval_seconds=1)
    with pytest.raises(ValueError, match="interval"):
        LogTraceService(registry, timeout_seconds=1, poll_interval_seconds=0)


def _bundle():
    return SimpleNamespace(
        config=SimpleNamespace(
            providers={
                "layer_1_provider": "aws",
                "layer_2_provider": "azure",
                "layer_3_hot_provider": "gcp",
            }
        ),
        credentials={},
        project_path=Path("/tmp/factory"),
    )


def test_start_rolls_back_reservation_when_simulator_fails(monkeypatch):
    service = _service()
    monkeypatch.setattr(
        "src.log_tracing.service.ProjectConfigLoader.load_bundle",
        lambda self, name: _bundle(),
    )
    monkeypatch.setattr(
        "src.log_tracing.service.send_test_message",
        lambda *args, **kwargs: False,
    )

    with pytest.raises(RuntimeError):
        service.start("factory")
    with pytest.raises(TraceNotFound):
        service.validate("TRACE-UNKNOWN1", "factory")


def test_start_issues_trace_only_after_successful_send(monkeypatch):
    service = _service()
    monkeypatch.setattr(
        "src.log_tracing.service.ProjectConfigLoader.load_bundle",
        lambda self, name: _bundle(),
    )
    monkeypatch.setattr(
        "src.log_tracing.service.send_test_message",
        lambda *args, **kwargs: True,
    )

    result = service.start("factory")

    service.validate(result["trace_id"], "factory")
    assert result["providers"] == ["aws", "azure", "gcp"]


def test_provider_query_normalizes_legacy_google_alias():
    from src.log_tracing.service import providers_to_query

    assert providers_to_query(
        {
            "layer_1_provider": "google",
            "layer_2_provider": "gcp",
            "layer_3_hot_provider": "none",
        }
    ) == {"gcp"}


def test_provider_query_includes_all_layers_and_resolved_event_provider():
    from src.log_tracing.service import providers_to_query

    graph = SimpleNamespace(
        nodes=(SimpleNamespace(provider="azure"), SimpleNamespace(provider="aws"))
    )

    assert providers_to_query(
        {
            "layer_1_provider": "aws",
            "layer_2_provider": "aws",
            "layer_3_hot_provider": "aws",
            "layer_4_provider": "gcp",
            "layer_5_provider": "gcp",
        },
        graph,
    ) == {"aws", "azure", "gcp"}


def test_expected_checkpoints_are_scoped_to_active_six_layer_profile():
    graph = SimpleNamespace(profile_ref={"id": "six-layer-eventing", "version": "1"})

    assert expected_trace_checkpoints(graph) == FORWARD_TRACE_CHECKPOINTS
    assert expected_trace_checkpoints(None) == ()


def test_provider_query_has_hard_timeout(monkeypatch):
    service = _service()

    def slow(*args):
        Event().wait(0.05)
        return ProviderFetchResult("aws")

    monkeypatch.setattr(service, "_fetch_provider", slow)

    async def exercise():
        return await service._fetch_with_timeout(
            "aws",
            "TRACE-1234ABCD",
            datetime.now(timezone.utc),
            {},
            {},
            Path("/tmp/factory"),
            timeout=0.001,
        )

    result = asyncio.run(exercise())
    assert result.error == "Provider query timed out"


def test_stream_queries_from_trace_issue_time_with_consistent_lookback(monkeypatch):
    service = _service()
    issued_at = datetime.now(timezone.utc)
    trace_id = "TRACE-1234ABCD"
    service.registry.reserve("factory", issued_at)
    service.registry.issue("factory", trace_id, issued_at)
    monkeypatch.setattr(
        "src.log_tracing.service.ProjectConfigLoader.load_bundle",
        lambda self, name: _bundle(),
    )
    monkeypatch.setattr(
        "src.log_tracing.service.load_terraform_outputs",
        lambda name: {},
    )
    observed = []

    def fetch(provider, trace, started_at, *args):
        observed.append(started_at)
        return ProviderFetchResult(provider)

    monkeypatch.setattr(service, "_fetch_provider", fetch)

    async def collect():
        return [event async for event in service.stream(trace_id, "factory")]

    asyncio.run(collect())

    assert observed
    assert set(observed) == {issued_at - TRACE_QUERY_LOOKBACK}


def test_stream_configuration_failure_still_emits_done(monkeypatch):
    service = _service()
    now = datetime.now(timezone.utc)
    service.registry.reserve("factory", now)
    service.registry.issue("factory", "TRACE-1234ABCD", now)

    def fail(self, name):
        raise RuntimeError("api_key=must-not-leak")

    monkeypatch.setattr(
        "src.log_tracing.service.ProjectConfigLoader.load_bundle",
        fail,
    )

    async def collect():
        return [event async for event in service.stream("TRACE-1234ABCD", "factory")]

    events = asyncio.run(collect())
    assert [event["event"] for event in events] == ["error", "done"]
    assert "must-not-leak" not in str(events)


def test_stream_completes_when_all_forward_checkpoints_are_observed(monkeypatch):
    service = LogTraceService(
        TraceRegistry(
            cooldown=timedelta(seconds=30),
            lifetime=timedelta(seconds=120),
        ),
        timeout_seconds=1,
        poll_interval_seconds=1,
    )
    now = datetime.now(timezone.utc)
    trace_id = "TRACE-1234ABCD"
    service.registry.reserve("factory", now)
    service.registry.issue("factory", trace_id, now)
    graph = SimpleNamespace(
        profile_ref={"id": "six-layer-eventing", "version": "1"},
        nodes=(SimpleNamespace(provider="aws"),),
    )
    bundle = SimpleNamespace(
        config=SimpleNamespace(providers={"layer_1_provider": "aws"}),
        credentials={},
        project_path=Path("/tmp/factory"),
        resolved_deployment_graph=graph,
    )
    monkeypatch.setattr(
        "src.log_tracing.service.ProjectConfigLoader.load_bundle",
        lambda self, name: bundle,
    )
    monkeypatch.setattr(
        "src.log_tracing.service.load_terraform_outputs",
        lambda name: {},
    )
    entries = [
        LogEntry(
            timestamp=now.isoformat(),
            message=f"checkpoint {stage}",
            layer="EVENT" if stage == "event_layer_durable" else "L1",
            provider="aws",
            checkpoint={"trace_id": trace_id, "stage": stage},
        )
        for stage in FORWARD_TRACE_CHECKPOINTS
    ]
    monkeypatch.setattr(
        service,
        "_fetch_provider",
        lambda *args: ProviderFetchResult("aws", entries=entries),
    )

    async def collect():
        return [event async for event in service.stream(trace_id, "factory")]

    events = asyncio.run(collect())
    done = json.loads(events[-1]["data"])
    assert done["status"] == "completed"
    assert done["checkpoint_count"] == len(FORWARD_TRACE_CHECKPOINTS)
    assert done["missing_checkpoints"] == []
    assert done["expected_checkpoints"] == list(FORWARD_TRACE_CHECKPOINTS)
