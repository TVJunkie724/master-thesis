"""Authenticated SSE adapter for canonical deployment stream sessions."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session
from starlette.responses import StreamingResponse

from src.api.dependencies import get_current_user
from src.api.routes.error_models import ERROR_RESPONSES
from src.models.database import get_db
from src.models.user import User
from src.repositories.deployment_repository import DeploymentRepository
from src.repositories.twin_repository import TwinRepository
from src.services.deployment_stream_service import (
    get_session,
    persisted_operation_last_event_id,
    stream_persisted_operation_events,
    stream_session_events,
)

router = APIRouter(prefix="/sse", tags=["sse"])


@router.get(
    "/deploy/{session_id}",
    operation_id="streamDeploymentLogs",
    summary="Stream owner-scoped deployment operation logs",
    description=(
        "Streams deployment, destroy, and verification events from the canonical "
        "Management API session registry. Reconnect with `last_event_id` only "
        "after persisted `/twins/{id}/logs` catch-up."
    ),
    responses={
        401: ERROR_RESPONSES[401],
        404: ERROR_RESPONSES[404],
        422: {"description": "Invalid event cursor"},
    },
)
async def stream_deploy_logs(
    session_id: str,
    request: Request,
    last_event_id: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    session = await get_session(session_id)
    if session is None:
        deployment = DeploymentRepository(db).get_by_session_id(session_id)
        if deployment is None:
            raise HTTPException(
                status_code=404,
                detail="Deployment stream session not found",
            )
        twin = TwinRepository(db).get_active_for_user(
            deployment.twin_id,
            current_user.id,
        )
        if twin is None:
            raise HTTPException(
                status_code=404,
                detail="Deployment stream session not found",
            )
        if last_event_id > persisted_operation_last_event_id(deployment, db):
            raise HTTPException(
                status_code=422,
                detail="Deployment stream cursor is outside persisted history",
            )
        return StreamingResponse(
            stream_persisted_operation_events(deployment, last_event_id, db),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    twin = TwinRepository(db).get_active_for_user(session.twin_id, current_user.id)
    if twin is None:
        # Deliberately use the same response as an unknown session to avoid
        # disclosing another user's active session metadata.
        raise HTTPException(status_code=404, detail="Deployment stream session not found")

    if not session.can_resume_after(last_event_id):
        raise HTTPException(
            status_code=422,
            detail="Deployment stream cursor is outside session history",
        )

    return StreamingResponse(
        stream_session_events(
            session=session,
            request=request,
            last_event_id=last_event_id,
            db=db,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
