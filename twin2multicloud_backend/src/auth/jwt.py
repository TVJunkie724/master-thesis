from dataclasses import dataclass
from datetime import datetime, timezone

from jose import jwt, JWTError

from src.config import settings


@dataclass(frozen=True)
class AuthTokenClaims:
    user_id: str
    session_id: str


def parse_bearer_token(authorization: str | None) -> str | None:
    """Return one strict bearer credential or ``None`` for malformed input."""
    if authorization is None or not authorization.startswith("Bearer "):
        return None
    token = authorization.removeprefix("Bearer ")
    if not token or any(char.isspace() or ord(char) == 127 for char in token):
        return None
    return token


def create_access_token(user_id: str, session_id: str, expires_at: datetime) -> str:
    issued_at = datetime.now(timezone.utc)
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    payload = {
        "sub": user_id,
        "jti": session_id,
        "iss": settings.JWT_ISSUER,
        "aud": settings.JWT_AUDIENCE,
        "exp": expires_at,
        "iat": issued_at,
        "nbf": issued_at,
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def verify_token(token: str) -> AuthTokenClaims | None:
    """Return validated subject/session claims or ``None`` for any invalid JWT."""
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
            issuer=settings.JWT_ISSUER,
            audience=settings.JWT_AUDIENCE,
        )
        user_id = payload.get("sub")
        session_id = payload.get("jti")
        if not isinstance(user_id, str) or not user_id:
            return None
        if not isinstance(session_id, str) or not session_id:
            return None
        return AuthTokenClaims(user_id=user_id, session_id=session_id)
    except JWTError:
        return None
