import asyncio
import json

import pytest
from pydantic import ValidationError

from src.api.verify import DataFlowRequest, _safe_event_stream


def test_request_requires_non_empty_device_id():
    with pytest.raises(ValidationError, match="iotDeviceId"):
        DataFlowRequest(payload={"temperature": 20})


def test_request_enforces_portable_message_size_limit():
    with pytest.raises(ValidationError, match="128 KiB"):
        DataFlowRequest(
            payload={"iotDeviceId": "device-1", "value": "x" * (128 * 1024)}
        )


def test_safe_stream_does_not_expose_runtime_exception():
    class FailingOrchestrator:
        async def stream(self, payload):
            del payload
            if False:
                yield ""
            raise RuntimeError("api_key=must-not-leak")

    async def collect():
        return [event async for event in _safe_event_stream(FailingOrchestrator(), {})]

    events = asyncio.run(collect())
    serialized = json.dumps(events)
    assert "must-not-leak" not in serialized
    assert "internal error" in serialized
    done_line = next(
        line for line in events[-1].splitlines() if line.startswith("data: ")
    )
    assert json.loads(done_line.removeprefix("data: "))["fail_count"] == 1


def test_safe_stream_preserves_completed_phase_counts_on_failure():
    class PartiallyFailingOrchestrator:
        async def stream(self, payload):
            del payload
            yield 'event: phase\ndata: {"phase":1,"name":"Delivery","status":"pass"}\n\n'
            yield 'event: phase\ndata: {"phase":2,"name":"Storage","status":"running"}\n\n'
            raise RuntimeError("boom")

    async def collect():
        return [
            event
            async for event in _safe_event_stream(PartiallyFailingOrchestrator(), {})
        ]

    events = asyncio.run(collect())
    done_line = next(
        line for line in events[-1].splitlines() if line.startswith("data: ")
    )
    done = json.loads(done_line.removeprefix("data: "))
    assert done["pass_count"] == 1
    assert done["fail_count"] == 1
    assert done["failed_phase"] == "Phase 2 - Storage"
