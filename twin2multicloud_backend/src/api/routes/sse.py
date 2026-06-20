"""
SSE (Server-Sent Events) endpoints for real-time log streaming.

Provides streaming endpoints for deployment/destroy operations with:
- Session state machine (PENDING -> STREAMING -> COMPLETED)
- Thread-safe session access via asyncio.Lock
- Incremental batch persistence
- Reconnection support with Last-Event-Id
"""

from fastapi import APIRouter, HTTPException, Request, Depends
from starlette.responses import StreamingResponse
from sqlalchemy.orm import Session

from src.models import get_db
from src.api.routes.error_models import ERROR_RESPONSES
from src.services.deployment_stream_service import (
    LogSession,
    SessionState,
    cleanup_session,
    create_session,
    get_active_sessions_for_twin,
    get_session,
    persist_logs_batch,
    start_reaper,
    stream_session_events,
)

router = APIRouter(prefix="/sse", tags=["sse"])


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

    return StreamingResponse(
        stream_session_events(session, request, last_event_id, db),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        }
    )


# Start reaper on module import (will be activated when event loop starts)
start_reaper()
