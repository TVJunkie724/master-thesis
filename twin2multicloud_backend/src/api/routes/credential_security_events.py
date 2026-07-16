from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from src.api.dependencies import get_current_user
from src.models.database import get_db
from src.models.user import User
from src.repositories.credential_security_event_repository import (
    CredentialSecurityEventRepository,
)
from src.schemas.credential_security_event import CredentialSecurityEventPage


router = APIRouter(prefix="/credential-security-events", tags=["credential-security-events"])


@router.get(
    "/",
    response_model=CredentialSecurityEventPage,
    operation_id="listCredentialSecurityEvents",
    summary="List the current user's credential security events",
)
async def list_credential_security_events(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CredentialSecurityEventPage:
    items, total = CredentialSecurityEventRepository(db).list_for_user(
        current_user.id,
        limit=limit,
        offset=offset,
    )
    return CredentialSecurityEventPage(items=items, total=total, limit=limit, offset=offset)
