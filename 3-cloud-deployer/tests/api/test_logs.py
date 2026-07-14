"""Log tracing API boundary tests."""

import asyncio

import pytest
from fastapi import HTTPException

from src.api import logs


def test_generate_trace_id_uses_stable_safe_format():
    first = logs.generate_trace_id()
    second = logs.generate_trace_id()

    assert first.startswith("TRACE-")
    assert len(first) == 14
    assert first != second
    assert first.removeprefix("TRACE-").isalnum()


def test_provider_query_set_is_deduplicated(monkeypatch):
    bundle = type(
        "Bundle",
        (),
        {
            "config": type(
                "Config",
                (),
                {
                    "providers": {
                        "layer_1_provider": "aws",
                        "layer_2_provider": "aws",
                        "layer_3_hot_provider": "gcp",
                    }
                },
            )()
        },
    )()
    monkeypatch.setattr(
        "src.core.config_loader.ProjectConfigLoader.load_bundle",
        lambda self, name: bundle,
    )

    assert logs.get_providers_to_query("factory") == {"aws", "gcp"}


def test_missing_project_is_rejected(monkeypatch, tmp_path):
    monkeypatch.setattr(
        logs,
        "resolve_project_context_path",
        lambda name: tmp_path / "missing",
    )

    with pytest.raises(HTTPException) as exc_info:
        logs._require_project("factory")

    assert exc_info.value.status_code == 404


def test_start_endpoint_runs_blocking_start_in_worker(monkeypatch, tmp_path):
    monkeypatch.setattr(
        logs,
        "resolve_project_context_path",
        lambda name: tmp_path,
    )
    monkeypatch.setattr(
        logs.trace_service,
        "start",
        lambda name: {"trace_id": "TRACE-1234ABCD"},
    )

    result = asyncio.run(logs.start_log_trace(project_name="factory"))

    assert result == {"trace_id": "TRACE-1234ABCD"}


def test_trace_constants_remain_bounded():
    assert logs.RATE_LIMIT_SECONDS == 30
    assert logs.TRACE_TIMEOUT_SECONDS == 90
    assert logs.POLL_INTERVAL_SECONDS == 2
    assert logs.trace_registry.max_traces == 1024
