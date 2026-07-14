"""Tests for deployment SSE stream service boundaries."""

from __future__ import annotations

import json

import pytest

from src.models.deployment_log import DeploymentLog
from src.services.deployment_stream_service import (
    LogSession,
    SessionState,
    SseSessionRegistry,
    _flush_expired_session_logs,
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

    await generator.aclose()

    assert session.state == SessionState.PENDING


@pytest.mark.asyncio
async def test_reconnect_replays_each_event_once_after_cursor(db_session):
    session = LogSession("twin-1", "session-replay", "deploy")
    await session.push_log("already-consumed")
    await session.push_log("missed")

    generator = stream_session_events(
        session=session,
        request=NeverDisconnectedRequest(),
        last_event_id=1,
        db=db_session,
    )
    frame = await anext(generator)
    await generator.aclose()

    payload = json.loads(frame.split("data: ", 1)[1])
    assert payload["id"] == 2
    assert payload["data"] == "missed"
    assert session.state == SessionState.PENDING


def test_new_stream_generation_cannot_be_reset_by_stale_disconnect():
    session = LogSession("twin-1", "session-generation", "deploy")

    first = session.open_stream(0)
    second = session.open_stream(0)
    session.close_stream(first.generation)

    assert first.queue is not second.queue
    assert session.state == SessionState.STREAMING

    session.close_stream(second.generation)
    assert session.state == SessionState.PENDING


def test_stream_rejects_cursor_ahead_of_session_history():
    session = LogSession("twin-1", "session-cursor", "deploy")

    with pytest.raises(ValueError, match="outside session history"):
        session.open_stream(1)


@pytest.mark.asyncio
async def test_replay_buffer_is_bounded_and_requests_persisted_catchup():
    session = LogSession("twin-1", "session-bounded", "deploy")
    for index in range(LogSession.MAX_REPLAY_SIZE + 1):
        await session.push_log(f"log-{index}")

    connection = session.open_stream(0)

    assert len(session.logs) == LogSession.MAX_REPLAY_SIZE
    assert connection.replay_gap is True


@pytest.mark.asyncio
async def test_live_queue_is_bounded_and_exposes_cursor_gap_for_recovery():
    session = LogSession("twin-1", "session-live-bounded", "deploy")
    connection = session.open_stream(0)

    for index in range(LogSession.MAX_LIVE_QUEUE_SIZE + 1):
        await session.push_log(f"log-{index}")

    assert connection.queue.qsize() == LogSession.MAX_LIVE_QUEUE_SIZE
    oldest_retained = connection.queue.get_nowait()
    assert oldest_retained["id"] == 2


@pytest.mark.asyncio
async def test_active_pending_session_ttl_uses_last_activity():
    session = LogSession("twin-1", "session-active", "deploy")
    session.created_at -= session.PENDING_TTL * 2

    await session.push_log("operation is still producing logs")

    assert session.is_expired() is False


@pytest.mark.asyncio
async def test_expired_session_flush_logs_persistence_failure(monkeypatch, caplog):
    session = LogSession("twin-1", "session-failed-flush", "deploy")
    await session.push_log("buffered")

    def fail_get_db():
        raise RuntimeError("database unavailable")

    monkeypatch.setattr("src.models.get_db", fail_get_db)

    with caplog.at_level("WARNING"):
        await _flush_expired_session_logs(session)

    assert "Failed to persist expired deployment session logs" in caplog.text
    assert "session-failed-flush" in caplog.text
