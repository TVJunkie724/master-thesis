import secrets
from datetime import datetime, timezone

from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session
from src.models.database import get_db
from src.models.user import User
from src.models.authentication import AuthSession
from src.auth.jwt import parse_bearer_token, verify_token
from src.config import settings

async def _get_current_user_real(
    authorization: str | None = Header(None),
    db: Session = Depends(get_db)
) -> User:
    """Extract and validate JWT, return current user."""
    token = parse_bearer_token(authorization)
    if token is None:
        raise HTTPException(status_code=401, detail="Invalid auth header")

    claims = verify_token(token)
    
    if not claims:
        raise HTTPException(status_code=401, detail="Invalid token")

    now = datetime.now(timezone.utc)
    session = db.query(AuthSession).filter(
        AuthSession.id == claims.session_id,
        AuthSession.user_id == claims.user_id,
        AuthSession.revoked_at.is_(None),
        AuthSession.expires_at > now,
    ).first()
    if session is None:
        raise HTTPException(status_code=401, detail="Invalid token")

    user = db.query(User).filter(User.id == claims.user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    
    return user


async def _get_current_user_dev(
    authorization: str = Header(None),
    db: Session = Depends(get_db)
) -> User:
    """Resolve the configured local/test identity for an explicit dev token."""
    expected = f"Bearer {settings.DEV_AUTH_TOKEN}"
    if authorization and secrets.compare_digest(authorization, expected):
        user = db.query(User).first()
        if user:
            return user
        # Create dev user if none exists
        user = User(email="dev@example.com", name="Developer")
        db.add(user)
        db.commit()
        db.refresh(user)
        return user
    
    # Fall back to real auth
    return await _get_current_user_real(authorization, db)


async def get_current_user(
    authorization: str | None = Header(None),
    db: Session = Depends(get_db),
) -> User:
    """Authenticate a request, with an explicit non-production dev capability."""
    if settings.DEV_AUTH_ENABLED:
        return await _get_current_user_dev(authorization, db)
    return await _get_current_user_real(authorization, db)
