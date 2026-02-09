"""
SSE (Server-Sent Events) endpoints for real-time log streaming.

Provides streaming endpoints for deployment/destroy operations with:
- Session state machine (PENDING -> STREAMING -> COMPLETED)
- Thread-safe session access via asyncio.Lock
- Incremental batch persistence
- Reconnection support with Last-Event-Id
"""

import asyncio
import json
import random
from enum import Enum
from datetime import datetime, timedelta
from typing import Dict, Optional, List
from fastapi import APIRouter, HTTPException, Request, Depends
from starlette.responses import StreamingResponse
from sqlalchemy.orm import Session

from src.models import get_db, DeploymentLog
from src.api.routes.error_models import ERROR_RESPONSES

router = APIRouter(prefix="/sse", tags=["sse"])


# =============================================================================
# Session State Machine
# =============================================================================

class SessionState(Enum):
    PENDING = "pending"      # Created, waiting for SSE connection
    STREAMING = "streaming"  # Active bidirectional flow
    COMPLETED = "completed"  # Final event sent, awaiting cleanup


class LogSession:
    """
    Manages a single deployment log streaming session.
    
    Lifecycle:
        PENDING (created) -> STREAMING (client connects) -> COMPLETED (done)
    """
    MAX_BUFFER_SIZE = 500  # Prevent memory exhaustion
    PENDING_TTL = timedelta(seconds=60)
    COMPLETED_TTL = timedelta(seconds=30)
    BATCH_SIZE = 50  # Persist every N logs

    def __init__(self, twin_id: str, session_id: str, operation_type: str = "deploy"):
        self.twin_id = twin_id
        self.session_id = session_id
        self.operation_type = operation_type  # "deploy", "destroy", or "test"
        self.state = SessionState.PENDING
        self.queue: asyncio.Queue = asyncio.Queue()
        self.buffer: List[dict] = []  # Logs before client connects
        self.logs: List[dict] = []  # All logs (for catchup)
        self.unpersisted_logs: List[dict] = []  # Batch for incremental persist
        self.created_at = datetime.utcnow()
        self.last_activity = datetime.utcnow()
        self.event_counter = 0  # For Last-Event-Id support

    def touch(self):
        """Update last activity timestamp."""
        self.last_activity = datetime.utcnow()

    def is_expired(self) -> bool:
        """Check if session exceeded TTL."""
        now = datetime.utcnow()
        if self.state == SessionState.PENDING:
            return now - self.created_at > self.PENDING_TTL
        elif self.state == SessionState.COMPLETED:
            return now - self.last_activity > self.COMPLETED_TTL
        return False  # STREAMING sessions don't expire via TTL

    async def push_log(self, msg: str, level: str = "info") -> int:
        """Push a log event. Returns event ID."""
        self.event_counter += 1
        event = {
            "id": self.event_counter,
            "type": "log",
            "data": msg,
            "level": level,
            "timestamp": datetime.utcnow().isoformat()
        }
        self.logs.append(event)
        self.unpersisted_logs.append(event)
        self.touch()

        if self.state == SessionState.STREAMING:
            await self.queue.put(event)
        else:
            if len(self.buffer) < self.MAX_BUFFER_SIZE:
                self.buffer.append(event)
            # else: drop oldest (prevent memory exhaustion)

        return self.event_counter

    async def push_event(self, event_type: str, data: dict = None) -> int:
        """Push a generic event with custom type (heartbeat, done, etc.).
        
        Unlike push_log(), this sends the event_type as the SSE 'type' field
        rather than embedding it in the data.
        """
        self.event_counter += 1
        event = {
            "id": self.event_counter,
            "type": event_type,
            "data": data or {},
            "timestamp": datetime.utcnow().isoformat()
        }
        self.touch()

        if self.state == SessionState.STREAMING:
            await self.queue.put(event)
        else:
            if len(self.buffer) < self.MAX_BUFFER_SIZE:
                self.buffer.append(event)

        return self.event_counter

    def on_connect(self):
        """Client connected to SSE stream."""
        self.state = SessionState.STREAMING
        self.touch()
        # Flush buffered events
        for event in self.buffer:
            self.queue.put_nowait(event)
        self.buffer.clear()

    def on_complete(self, success: bool, message: str = None, outputs: dict = None):
        """Deployment finished."""
        self.state = SessionState.COMPLETED
        self.event_counter += 1
        final_event = {
            "id": self.event_counter,
            "type": "complete" if success else "error",
            "status": "success" if success else "error",
            "data": message or ("Deployment complete" if success else "Deployment failed"),
            "message": message,
            "outputs": outputs,
            "timestamp": datetime.utcnow().isoformat()
        }
        self.queue.put_nowait(final_event)
        self.touch()

    def should_batch_persist(self) -> bool:
        """Check if we accumulated enough logs for batch persist."""
        return len(self.unpersisted_logs) >= self.BATCH_SIZE

    def get_unpersisted_and_clear(self) -> List[dict]:
        """Get logs to persist and clear the batch buffer."""
        logs = self.unpersisted_logs.copy()
        self.unpersisted_logs.clear()
        return logs


# =============================================================================
# Session Manager with Thread Safety
# =============================================================================

_sessions: Dict[str, LogSession] = {}
_sessions_lock = asyncio.Lock()
_reaper_task: Optional[asyncio.Task] = None


async def _persist_logs_batch(session: LogSession, logs: List[dict], db: Session):
    """Persist a batch of logs to database."""
    if not logs:
        return
    for log in logs:
        db.add(DeploymentLog(
            twin_id=session.twin_id,
            session_id=session.session_id,
            event_id=log["id"],
            message=log["data"],
            level=log.get("level", "info"),
            operation_type=session.operation_type,
            timestamp=datetime.fromisoformat(log["timestamp"]) if log.get("timestamp") else datetime.utcnow()
        ))
    db.commit()



async def _recover_stuck_twins():
    """Recover twins stuck in deploying/destroying for >30 min with no active session."""
    import logging
    from src.models import get_db
    from src.models.twin import DigitalTwin, TwinState

    logger = logging.getLogger(__name__)
    threshold = datetime.utcnow() - timedelta(minutes=30)

    # Snapshot active twin IDs under lock
    async with _sessions_lock:
        active_twin_ids = {s.twin_id for s in _sessions.values()
                          if s.state != SessionState.COMPLETED}

    # Query stuck twins outside lock (avoids holding lock during DB I/O)
    try:
        db_gen = get_db()
        db = next(db_gen)
        stuck = db.query(DigitalTwin).filter(
            DigitalTwin.state.in_([TwinState.DEPLOYING, TwinState.DESTROYING]),
            DigitalTwin.updated_at < threshold,
        ).all()

        for twin in stuck:
            if twin.id not in active_twin_ids:
                logger.warning(
                    f"Recovering stuck twin {twin.id} from {twin.state} → error"
                )
                twin.state = TwinState.ERROR
                twin.last_error = "Operation timed out after 30 minutes (auto-recovered)"
        db.commit()
        db.close()
    except Exception as e:
        logger.warning(f"Failed to query stuck twins: {e}")


async def _session_reaper():
    """Background task that cleans expired sessions every 10 seconds."""
    from src.models import get_db
    import logging
    _reaper_logger = logging.getLogger(__name__)
    _stuck_check_counter = 0
    while True:
        await asyncio.sleep(10)
        async with _sessions_lock:
            expired = [sid for sid, s in _sessions.items() if s.is_expired()]
            for sid in expired:
                session = _sessions.pop(sid, None)
                if session and session.unpersisted_logs:
                    # Get a fresh DB session for cleanup
                    try:
                        db_gen = get_db()
                        db = next(db_gen)
                        await _persist_logs_batch(session, session.unpersisted_logs, db)
                        db.close()
                    except Exception:
                        pass  # Best effort

        # Check for stuck deployments every ~5 minutes (30 iterations × 10s)
        _stuck_check_counter += 1
        if _stuck_check_counter >= 30:
            _stuck_check_counter = 0
            try:
                await _recover_stuck_twins()
            except Exception as e:
                _reaper_logger.warning(f"Stuck twin recovery failed: {e}")


def start_reaper():
    """Start the session reaper background task."""
    global _reaper_task
    if _reaper_task is None:
        try:
            loop = asyncio.get_running_loop()
            _reaper_task = loop.create_task(_session_reaper())
        except RuntimeError:
            pass  # No running loop yet, will be started later


async def create_session(twin_id: str, session_id: str, operation_type: str = "deploy") -> LogSession:
    """Create a new log session (thread-safe)."""
    session = LogSession(twin_id, session_id, operation_type)
    async with _sessions_lock:
        _sessions[session_id] = session
    return session


async def get_session(session_id: str) -> Optional[LogSession]:
    """Get session by ID (thread-safe)."""
    async with _sessions_lock:
        return _sessions.get(session_id)


async def cleanup_session(session_id: str):
    """Remove session from memory (thread-safe)."""
    async with _sessions_lock:
        _sessions.pop(session_id, None)


async def get_active_sessions_for_twin(twin_id: str) -> List[LogSession]:
    """Get all non-completed sessions for a twin (for concurrent deploy check)."""
    async with _sessions_lock:
        return [s for s in _sessions.values() 
                if s.twin_id == twin_id and s.state != SessionState.COMPLETED]


# =============================================================================
# Legacy API (for backward compatibility with existing code)
# =============================================================================

def get_log_queue(session_id: str) -> asyncio.Queue:
    """Get or create a log queue for a session (legacy API)."""
    if session_id not in _sessions:
        # Create a minimal session for legacy compatibility
        session = LogSession("legacy", session_id, "deploy")
        _sessions[session_id] = session
    return _sessions[session_id].queue


async def push_log(session_id: str, log: str):
    """Push a log message to a session's queue (legacy API)."""
    session = await get_session(session_id)
    if session:
        await session.push_log(log)


async def push_complete(session_id: str, status: str, message: str, outputs: dict = None):
    """Push completion message to a session's queue (legacy API)."""
    session = await get_session(session_id)
    if session:
        session.on_complete(success=(status != "error"), message=message, outputs=outputs)


# =============================================================================
# SSE Endpoint
# =============================================================================

@router.get(
    "/deploy/{session_id}",
    operation_id="streamDeploymentLogs",
    summary="SSE endpoint for real-time deployment log streaming",
    description=(
        "**Purpose:** Stream real-time deployment/destroy logs via Server-Sent Events.\\n\\n"
        "**When to call:** After POST to /deploy or /destroy returns session_id.\\n\\n"
        "**Connection:** Open as EventSource in browser/HTTP client.\\n\\n"
        "**SSE event types:**\\n"
        "- `log`: Line of output {id, data, level, timestamp}\\n"
        "- `heartbeat`: Keep-alive (via SSE comment)\\n"
        "- `complete`: Success {status, message, outputs}\\n"
        "- `error`: Failure {status, message}\\n\\n"
        "**Reconnection:** Pass `last_event_id` query param to resume from event ID.\\n\\n"
        "**Timeout:** Heartbeats sent every 30s to keep connection alive."
    ),
    responses={
        404: ERROR_RESPONSES[404],
    }
)
async def stream_deploy_logs(
    session_id: str,
    request: Request,
    last_event_id: int = 0,
    db: Session = Depends(get_db)
):
    """
    SSE endpoint for streaming deployment logs.
    
    Connect to this endpoint after starting a deployment to receive
    real-time log updates. Supports reconnection via last_event_id.
    
    Args:
        session_id: The deployment session ID
        last_event_id: Resume from this event ID (for reconnection)
    
    Events:
    - {"id": N, "type": "log", "data": "Log message...", "level": "info|error"}
    - {"id": N, "type": "complete|error", "status": "success|error", "message": "..."}
    """
    session = await get_session(session_id)
    if not session:
        raise HTTPException(404, "Session not found or expired")

    async def event_generator():
        try:
            # Mark session as streaming
            session.on_connect()

            # Send any missed events (for reconnection)
            if last_event_id > 0:
                missed = [e for e in session.logs if e["id"] > last_event_id]
                for event in missed:
                    yield f"id: {event['id']}\ndata: {json.dumps(event)}\n\n"

            # Stream live events
            while True:
                # Check if client disconnected
                if await request.is_disconnected():
                    break

                try:
                    event = await asyncio.wait_for(session.queue.get(), timeout=30)
                    yield f"id: {event.get('id', 0)}\ndata: {json.dumps(event)}\n\n"

                    # Incremental persistence check
                    if session.should_batch_persist():
                        logs = session.get_unpersisted_and_clear()
                        await _persist_logs_batch(session, logs, db)

                    # Terminal events
                    if event.get("type") in ["complete", "error"]:
                        break

                except asyncio.TimeoutError:
                    # Heartbeat to keep connection alive
                    yield f": heartbeat\n\n"
                    session.touch()

        finally:
            # Final persistence of any remaining logs
            if session.unpersisted_logs:
                await _persist_logs_batch(session, session.get_unpersisted_and_clear(), db)
            # Don't cleanup immediately - leave for reaper in case of reconnect
            session.state = SessionState.COMPLETED

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        }
    )


# Start reaper on module import (will be activated when event loop starts)
start_reaper()
