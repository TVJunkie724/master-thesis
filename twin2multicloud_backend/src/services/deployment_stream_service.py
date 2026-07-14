"""Deployment SSE session registry and stream event service."""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any

from sqlalchemy.orm import Session

from src.models import DeploymentLog
from src.services.twin_lifecycle_service import TwinLifecycleService

logger = logging.getLogger(__name__)


class SessionState(Enum):
    """Lifecycle states for a log streaming session."""

    PENDING = "pending"
    STREAMING = "streaming"
    COMPLETED = "completed"


@dataclass(frozen=True)
class StreamConnection:
    """One isolated consumer generation plus its deterministic replay snapshot."""

    generation: int
    queue: asyncio.Queue
    replay: tuple[dict[str, Any], ...]
    completed: bool
    replay_gap: bool


class LogSession:
    """Manage one deployment log streaming session."""

    MAX_BUFFER_SIZE = 500
    MAX_REPLAY_SIZE = 500
    MAX_LIVE_QUEUE_SIZE = 500
    PENDING_TTL = timedelta(seconds=60)
    COMPLETED_TTL = timedelta(seconds=30)
    BATCH_SIZE = 50

    def __init__(self, twin_id: str, session_id: str, operation_type: str = "deploy"):
        self.twin_id = twin_id
        self.session_id = session_id
        self.operation_type = operation_type
        self.state = SessionState.PENDING
        self.queue: asyncio.Queue = asyncio.Queue(maxsize=self.MAX_LIVE_QUEUE_SIZE)
        self.buffer: list[dict[str, Any]] = []
        self.logs: list[dict[str, Any]] = []
        self.unpersisted_logs: list[dict[str, Any]] = []
        self.created_at = datetime.utcnow()
        self.last_activity = datetime.utcnow()
        self.event_counter = 0
        self._connection_generation = 0

    def touch(self) -> None:
        self.last_activity = datetime.utcnow()

    def is_expired(self) -> bool:
        now = datetime.utcnow()
        if self.state == SessionState.PENDING:
            return now - self.last_activity > self.PENDING_TTL
        if self.state == SessionState.COMPLETED:
            return now - self.last_activity > self.COMPLETED_TTL
        return False

    async def push_log(self, msg: str, level: str = "info") -> int:
        self.event_counter += 1
        event = {
            "id": self.event_counter,
            "type": "log",
            "data": msg,
            "level": level,
            "timestamp": datetime.utcnow().isoformat(),
        }
        self._remember(event)
        self.unpersisted_logs.append(event)
        self.touch()

        if self.state == SessionState.STREAMING:
            self._enqueue_live(event)
        else:
            self._buffer(event)

        return self.event_counter

    async def push_event(self, event_type: str, data: dict | None = None) -> int:
        self.event_counter += 1
        event = {
            "id": self.event_counter,
            "type": event_type,
            "data": data or {},
            "timestamp": datetime.utcnow().isoformat(),
        }
        self._remember(event)
        self.touch()

        if self.state == SessionState.STREAMING:
            self._enqueue_live(event)
        else:
            self._buffer(event)

        return self.event_counter

    def can_resume_after(self, last_event_id: int) -> bool:
        """Return whether a reconnect cursor belongs to this session history."""
        return 0 <= last_event_id <= self.event_counter

    def open_stream(self, last_event_id: int) -> StreamConnection:
        """Replace any prior consumer and return replay isolated from live events."""
        if not self.can_resume_after(last_event_id):
            raise ValueError("Deployment stream cursor is outside session history")
        self._connection_generation += 1
        self.queue = asyncio.Queue(maxsize=self.MAX_LIVE_QUEUE_SIZE)
        oldest_event_id = self.logs[0]["id"] if self.logs else None
        replay_gap = bool(
            oldest_event_id is not None
            and oldest_event_id > last_event_id + 1
        )
        replay = tuple(
            event.copy()
            for event in self.logs
            if event["id"] > last_event_id
        )
        completed = self.state == SessionState.COMPLETED
        if not completed:
            self.state = SessionState.STREAMING
        self.touch()
        self.buffer.clear()
        return StreamConnection(
            generation=self._connection_generation,
            queue=self.queue,
            replay=replay,
            completed=completed,
            replay_gap=replay_gap,
        )

    def close_stream(self, generation: int) -> None:
        """Reset only the consumer generation that is actually disconnecting."""
        if (
            generation == self._connection_generation
            and self.state == SessionState.STREAMING
        ):
            self.state = SessionState.PENDING
            self.touch()

    def on_complete(
        self,
        success: bool,
        message: str | None = None,
        outputs: dict | None = None,
        operation_id: str | None = None,
        error_code: str | None = None,
    ) -> None:
        was_streaming = self.state == SessionState.STREAMING
        self.state = SessionState.COMPLETED
        self.event_counter += 1
        final_event = {
            "id": self.event_counter,
            "type": "complete" if success else "error",
            "status": "success" if success else "error",
            "data": message or ("Deployment complete" if success else "Deployment failed"),
            "message": message,
            "outputs": outputs,
            "operation_id": operation_id,
            "error_code": error_code,
            "timestamp": datetime.utcnow().isoformat(),
        }
        self._remember(final_event)
        if was_streaming:
            self._enqueue_live(final_event)
        else:
            self._buffer(final_event)
        self.touch()

    def _enqueue_live(self, event: dict[str, Any]) -> None:
        """Bound live delivery; cursor gaps force persisted client catch-up."""
        if self.queue.full():
            self.queue.get_nowait()
        self.queue.put_nowait(event)

    def _remember(self, event: dict[str, Any]) -> None:
        self.logs.append(event)
        if len(self.logs) > self.MAX_REPLAY_SIZE:
            del self.logs[: len(self.logs) - self.MAX_REPLAY_SIZE]

    def _buffer(self, event: dict[str, Any]) -> None:
        self.buffer.append(event)
        if len(self.buffer) > self.MAX_BUFFER_SIZE:
            del self.buffer[: len(self.buffer) - self.MAX_BUFFER_SIZE]

    def should_batch_persist(self) -> bool:
        return len(self.unpersisted_logs) >= self.BATCH_SIZE

    def get_unpersisted_and_clear(self) -> list[dict[str, Any]]:
        logs = self.unpersisted_logs.copy()
        self.unpersisted_logs.clear()
        return logs


class SseSessionRegistry:
    """Thread-safe in-memory registry for deployment log sessions."""

    def __init__(self):
        self._sessions: dict[str, LogSession] = {}
        self._lock = asyncio.Lock()
        self._reaper_task: asyncio.Task | None = None

    async def create_session(self, twin_id: str, session_id: str, operation_type: str = "deploy") -> LogSession:
        session = LogSession(twin_id, session_id, operation_type)
        async with self._lock:
            self._sessions[session_id] = session
        return session

    async def get_session(self, session_id: str) -> LogSession | None:
        async with self._lock:
            return self._sessions.get(session_id)

    async def cleanup_session(self, session_id: str) -> None:
        async with self._lock:
            self._sessions.pop(session_id, None)

    async def get_active_sessions_for_twin(self, twin_id: str) -> list[LogSession]:
        async with self._lock:
            return [
                session
                for session in self._sessions.values()
                if session.twin_id == twin_id and session.state != SessionState.COMPLETED
            ]

    async def active_twin_ids(self) -> set[str]:
        async with self._lock:
            return {
                session.twin_id
                for session in self._sessions.values()
                if session.state != SessionState.COMPLETED
            }

    async def collect_expired(self) -> list[LogSession]:
        async with self._lock:
            expired_ids = [sid for sid, session in self._sessions.items() if session.is_expired()]
            return [
                session
                for sid in expired_ids
                if (session := self._sessions.pop(sid, None)) is not None
            ]

    def start_reaper(self) -> None:
        if self._reaper_task is not None:
            return
        try:
            loop = asyncio.get_running_loop()
            self._reaper_task = loop.create_task(_session_reaper(self))
        except RuntimeError:
            pass


async def persist_logs_batch(session: LogSession, logs: list[dict[str, Any]], db: Session) -> None:
    """Persist a batch of log events to the database."""
    if not logs:
        return
    for log in logs:
        db.add(
            DeploymentLog(
                twin_id=session.twin_id,
                session_id=session.session_id,
                event_id=log["id"],
                message=log["data"],
                level=log.get("level", "info"),
                operation_type=session.operation_type,
                timestamp=datetime.fromisoformat(log["timestamp"]) if log.get("timestamp") else datetime.utcnow(),
            )
        )
    db.commit()


async def recover_stuck_twins(registry: SseSessionRegistry) -> None:
    """Recover twins stuck in deploying/destroying for more than 30 minutes."""
    from src.models import get_db
    from src.models.twin import DigitalTwin, TwinState

    threshold = datetime.utcnow() - timedelta(minutes=30)
    active_twin_ids = await registry.active_twin_ids()

    try:
        db_gen = get_db()
        db = next(db_gen)
        stuck = (
            db.query(DigitalTwin)
            .filter(
                DigitalTwin.state.in_([TwinState.DEPLOYING, TwinState.DESTROYING]),
                DigitalTwin.updated_at < threshold,
            )
            .all()
        )

        for twin in stuck:
            if twin.id not in active_twin_ids:
                logger.warning("Recovering stuck twin %s from %s to error", twin.id, twin.state)
                timeout_error = "Operation timed out after 30 minutes (auto-recovered)"
                if twin.state == TwinState.DESTROYING:
                    TwinLifecycleService.fail_destroy(twin, timeout_error)
                else:
                    TwinLifecycleService.fail_deploy(twin, timeout_error)
        db.commit()
        db.close()
    except Exception as exc:
        logger.warning("Failed to query stuck twins: %s", exc)


async def _session_reaper(registry: SseSessionRegistry) -> None:
    stuck_check_counter = 0
    while True:
        await asyncio.sleep(10)
        expired_sessions = await registry.collect_expired()
        for session in expired_sessions:
            await _flush_expired_session_logs(session)

        stuck_check_counter += 1
        if stuck_check_counter >= 30:
            stuck_check_counter = 0
            try:
                await recover_stuck_twins(registry)
            except Exception as exc:
                logger.warning("Stuck twin recovery failed: %s", exc)


async def _flush_expired_session_logs(session: LogSession) -> None:
    """Persist logs for an expired session and log failures for diagnostics."""
    if not session.unpersisted_logs:
        return

    try:
        from src.models import get_db

        db_gen = get_db()
        db = next(db_gen)
        await persist_logs_batch(session, session.unpersisted_logs, db)
        db.close()
    except Exception as exc:
        logger.warning(
            "Failed to persist expired deployment session logs for session %s: %s",
            session.session_id,
            exc,
        )


async def stream_session_events(session: LogSession, request, last_event_id: int, db: Session):
    """Yield SSE frames for a session with replay, heartbeat, and persistence."""
    connection = session.open_stream(last_event_id)
    try:
        if connection.replay_gap:
            event = {
                "id": last_event_id,
                "type": "catchup_required",
                "data": "Persisted deployment log catch-up is required.",
            }
            yield _sse_frame(event)
            return

        for event in connection.replay:
            yield _sse_frame(event)
            if event.get("type") in {"complete", "error"}:
                return

        if connection.completed:
            return

        while True:
            if await request.is_disconnected():
                break

            try:
                event = await asyncio.wait_for(connection.queue.get(), timeout=30)
                yield _sse_frame(event)

                if session.should_batch_persist():
                    logs = session.get_unpersisted_and_clear()
                    await persist_logs_batch(session, logs, db)

                if event.get("type") in ["complete", "error"]:
                    break

            except asyncio.TimeoutError:
                yield ": heartbeat\n\n"
                session.touch()

    finally:
        if session.unpersisted_logs:
            await persist_logs_batch(session, session.get_unpersisted_and_clear(), db)
        session.close_stream(connection.generation)


def _sse_frame(event: dict[str, Any]) -> str:
    return f"id: {event.get('id', 0)}\ndata: {json.dumps(event)}\n\n"


registry = SseSessionRegistry()


async def create_session(twin_id: str, session_id: str, operation_type: str = "deploy") -> LogSession:
    return await registry.create_session(twin_id, session_id, operation_type)


async def get_session(session_id: str) -> LogSession | None:
    return await registry.get_session(session_id)


async def cleanup_session(session_id: str) -> None:
    await registry.cleanup_session(session_id)


async def get_active_sessions_for_twin(twin_id: str) -> list[LogSession]:
    return await registry.get_active_sessions_for_twin(twin_id)


def start_reaper() -> None:
    registry.start_reaper()
