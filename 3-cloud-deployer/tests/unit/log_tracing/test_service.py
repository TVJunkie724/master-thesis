from datetime import datetime, timedelta, timezone
import asyncio
from pathlib import Path
from threading import Event
from types import SimpleNamespace

import pytest

from src.log_tracing.registry import TraceNotFound, TraceRegistry
from src.log_tracing.fetchers import ProviderFetchResult
from src.log_tracing.service import LogTraceService


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
        lambda *args: False,
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
        lambda *args: True,
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
        return [
            event
            async for event in service.stream("TRACE-1234ABCD", "factory")
        ]

    events = asyncio.run(collect())
    assert [event["event"] for event in events] == ["error", "done"]
    assert "must-not-leak" not in str(events)
