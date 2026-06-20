"""Tests for deployment SSE stream service boundaries."""

from __future__ import annotations

import json

import pytest

from src.models.deployment_log import DeploymentLog
from src.services.deployment_stream_service import (
    LogSession,
    SessionState,
    SseSessionRegistry,
    persist_logs_batch,
    stream_session_events,
)


class NeverDisconnectedRequest:
    async def is_disconnected(self):
        return False


@pytest.mark.asyncio
async def test_registry_tracks_active_sessions_and_ignores_completed():
    registry = SseSessionRegistry()

    running = await registry.create_session("twin-1", "session-running", "deploy")
    completed = await registry.create_session("twin-1", "session-complete", "deploy")
    completed.on_complete(success=True, message="done")

    active = await registry.get_active_sessions_for_twin("twin-1")

    assert active == [running]


@pytest.mark.asyncio
async def test_log_session_stores_final_event_for_reconnect_replay(db_session):
    session = LogSession("twin-1", "session-1", "deploy")
    session.on_complete(success=True, message="done", outputs={"endpoint": "ok"})

    generator = stream_session_events(
        session=session,
        request=NeverDisconnectedRequest(),
        last_event_id=0,
        db=db_session,
    )

    frame = await anext(generator)

    payload = json.loads(frame.split("data: ", 1)[1])
    assert payload["type"] == "complete"
    assert payload["message"] == "done"
    assert payload["outputs"] == {"endpoint": "ok"}


@pytest.mark.asyncio
async def test_persist_logs_batch_writes_deployment_logs(db_session):
    session = LogSession("twin-1", "session-1", "deploy")
    await session.push_log("hello", level="info")

    await persist_logs_batch(session, session.get_unpersisted_and_clear(), db_session)

    logs = db_session.query(DeploymentLog).all()
    assert len(logs) == 1
    assert logs[0].twin_id == "twin-1"
    assert logs[0].session_id == "session-1"
    assert logs[0].message == "hello"
    assert logs[0].level == "info"


@pytest.mark.asyncio
async def test_stream_session_events_resets_running_session_to_pending_on_disconnect(db_session):
    class DisconnectAfterFirstFrame:
        def __init__(self):
            self.calls = 0

        async def is_disconnected(self):
            self.calls += 1
            return self.calls > 1

    session = LogSession("twin-1", "session-1", "deploy")
    await session.push_log("buffered")
    generator = stream_session_events(
        session=session,
        request=DisconnectAfterFirstFrame(),
        last_event_id=0,
        db=db_session,
    )

    frame = await anext(generator)
    assert "buffered" in frame

    try:
        await anext(generator)
    except StopAsyncIteration:
        pass

    assert session.state == SessionState.PENDING
