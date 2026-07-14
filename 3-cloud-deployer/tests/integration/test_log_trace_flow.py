"""Cross-provider log aggregation without live cloud access."""

import asyncio
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from threading import Barrier
from types import SimpleNamespace

from src.log_tracing.fetchers import LogEntry, ProviderFetchResult
from src.log_tracing.registry import TraceRegistry
from src.log_tracing.service import LogTraceService


def test_provider_fetches_run_concurrently_and_results_are_redacted(monkeypatch):
    registry = TraceRegistry(
        cooldown=timedelta(seconds=30),
        lifetime=timedelta(seconds=120),
    )
    now = datetime.now(timezone.utc)
    registry.reserve("factory", now)
    registry.issue("factory", "TRACE-1234ABCD", now)
    service = LogTraceService(
        registry,
        timeout_seconds=0.01,
        poll_interval_seconds=0.01,
    )
    bundle = SimpleNamespace(
        config=SimpleNamespace(
            providers={
                "layer_1_provider": "aws",
                "layer_2_provider": "azure",
                "layer_3_hot_provider": "aws",
            }
        ),
        credentials={},
        project_path=Path("/tmp/factory"),
    )
    monkeypatch.setattr(
        "src.log_tracing.service.ProjectConfigLoader.load_bundle",
        lambda self, name: bundle,
    )
    monkeypatch.setattr(
        "src.log_tracing.service.load_terraform_outputs",
        lambda name: {},
    )
    barrier = Barrier(2, timeout=1)

    def fetch(provider, *args):
        barrier.wait()
        return ProviderFetchResult(
            provider,
            entries=[
                LogEntry(
                    timestamp=f"2026-01-01T00:00:0{provider == 'azure'}Z",
                    message="api_key=must-not-leak",
                    layer="L1",
                    provider=provider,
                    function="dispatcher",
                )
            ],
        )

    monkeypatch.setattr(service, "_fetch_provider", fetch)

    async def collect():
        return [
            event
            async for event in service.stream("TRACE-1234ABCD", "factory")
        ]

    events = asyncio.run(collect())
    log_events = [event for event in events if event["event"] == "log"]
    done = json.loads(events[-1]["data"])
    assert len(log_events) == 2
    assert "must-not-leak" not in json.dumps(log_events)
    assert done["total_logs"] == 2
    assert done["status"] == "completed"
    assert events[-1]["event"] == "done"


def test_provider_failure_produces_partial_terminal_status(monkeypatch):
    registry = TraceRegistry(
        cooldown=timedelta(seconds=30),
        lifetime=timedelta(seconds=120),
    )
    now = datetime.now(timezone.utc)
    registry.reserve("factory", now)
    registry.issue("factory", "TRACE-1234ABCD", now)
    service = LogTraceService(
        registry,
        timeout_seconds=0.001,
        poll_interval_seconds=0.001,
    )
    bundle = SimpleNamespace(
        config=SimpleNamespace(
            providers={
                "layer_1_provider": "aws",
                "layer_2_provider": "aws",
                "layer_3_hot_provider": "aws",
            }
        ),
        credentials={},
        project_path=Path("/tmp/factory"),
    )
    monkeypatch.setattr(
        "src.log_tracing.service.ProjectConfigLoader.load_bundle",
        lambda self, name: bundle,
    )
    monkeypatch.setattr(
        "src.log_tracing.service.load_terraform_outputs",
        lambda name: {},
    )
    monkeypatch.setattr(
        service,
        "_fetch_provider",
        lambda *args: ProviderFetchResult(
            "aws",
            error="api_key=must-not-leak",
        ),
    )

    async def collect():
        return [
            event
            async for event in service.stream("TRACE-1234ABCD", "factory")
        ]

    events = asyncio.run(collect())
    done = json.loads(events[-1]["data"])
    assert any(event["event"] == "error" for event in events)
    assert "must-not-leak" not in json.dumps(events)
    assert done["status"] == "partial"
