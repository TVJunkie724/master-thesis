"""Authentication dependency for the local single-user thesis PoC."""

import secrets

from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from src.config import settings
from src.models.database import get_db
from src.models.user import User


async def get_current_user(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> User:
    """Resolve the sole PoC user after checking the configured bearer."""
    expected = f"Bearer {settings.POC_AUTH_TOKEN}"
    if authorization is None or not secrets.compare_digest(authorization, expected):
        raise HTTPException(status_code=401, detail="Invalid PoC bearer token")

    user = db.query(User).filter(User.email == settings.POC_USER_EMAIL).first()
    if user is not None:
        return user

    user = User(
        email=settings.POC_USER_EMAIL,
        name=settings.POC_USER_NAME,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user
