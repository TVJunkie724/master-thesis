from __future__ import annotations

import hashlib
import math
import time
from enum import StrEnum
from typing import AsyncIterator

from fastapi import Depends, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from limits import parse
from limits.aio.strategies import MovingWindowRateLimiter
from limits.errors import StorageError
from limits.storage import storage_from_string
from sqlalchemy.orm import Session

from src.api.dependencies import get_current_user
from src.config import settings
from src.models.database import get_db
from src.models.user import User
from src.schemas.credential_security_event import (
    CredentialSecurityAction,
    CredentialSecurityEventDraft,
    CredentialSecurityOutcome,
)
from src.security.request_context import current_request_id
from src.services.credential_security_audit_service import CredentialSecurityAuditService


class CredentialRateClass(StrEnum):
    WRITE = "credential-write"
    VALIDATION = "credential-validation"
    BOOTSTRAP = "credential-bootstrap"


class CredentialRateLimitExceeded(RuntimeError):
    def __init__(self, headers: dict[str, str]):
        super().__init__("Credential endpoint rate limit exceeded")
        self.headers = headers


class CredentialSecurityControlUnavailable(RuntimeError):
    pass


class CredentialRateLimiter:
    """Async moving-window limiter backed by a configured limits storage."""

    def __init__(self, storage_uri: str):
        async_uri = storage_uri if storage_uri.startswith("async+") else f"async+{storage_uri}"
        self._storage = storage_from_string(
            async_uri,
            wrap_exceptions=True,
            implementation="redispy",
        )
        self._limiter = MovingWindowRateLimiter(self._storage)

    async def hit(self, rate: str, rate_class: CredentialRateClass, user_id: str) -> dict[str, str]:
        item = parse(rate)
        actor_key = hashlib.sha256(f"credential-rate:{user_id}".encode()).hexdigest()
        allowed = await self._limiter.hit(item, rate_class.value, actor_key)
        stats = await self._limiter.get_window_stats(item, rate_class.value, actor_key)
        reset_after = max(0, math.ceil(stats.reset_time - time.time()))
        headers = {
            "RateLimit-Limit": str(item.amount),
            "RateLimit-Remaining": str(stats.remaining),
            "RateLimit-Reset": str(reset_after),
        }
        if not allowed:
            headers["Retry-After"] = str(max(1, reset_after))
            raise CredentialRateLimitExceeded(headers)
        return headers

    async def reset(self) -> None:
        await self._storage.reset()


_rate_limiter: CredentialRateLimiter | None = None


def _get_rate_limiter() -> CredentialRateLimiter:
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = CredentialRateLimiter(settings.CREDENTIAL_RATE_LIMIT_STORAGE_URI)
    return _rate_limiter


async def reset_rate_limiter_for_tests() -> None:
    """Clear process-local counters and reconstruct the configured backend."""
    global _rate_limiter
    if _rate_limiter is not None and settings.APP_ENV.value == "test":
        await _rate_limiter.reset()
    _rate_limiter = None


def credential_rate_limit(
    rate_class: CredentialRateClass,
    action: CredentialSecurityAction,
):
    """Authenticate and enforce one operation-class quota as a FastAPI dependency."""

    async def dependency(
        request: Request,
        response: Response,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
    ) -> AsyncIterator[User]:
        request.state.credential_security_action = action
        request.state.credential_security_user_id = current_user.id
        if not settings.CREDENTIAL_RATE_LIMIT_ENABLED:
            try:
                yield current_user
            except Exception as exc:
                _audit_rejection(db, current_user.id, action, exc)
                raise
            return

        rate = {
            CredentialRateClass.WRITE: settings.CREDENTIAL_WRITE_RATE_LIMIT,
            CredentialRateClass.VALIDATION: settings.CREDENTIAL_VALIDATION_RATE_LIMIT,
            CredentialRateClass.BOOTSTRAP: settings.CREDENTIAL_BOOTSTRAP_RATE_LIMIT,
        }[rate_class]
        try:
            headers = await _get_rate_limiter().hit(rate, rate_class, current_user.id)
        except CredentialRateLimitExceeded as exc:
            CredentialSecurityAuditService.commit_standalone(
                db,
                _attempt(current_user.id, action, CredentialSecurityOutcome.RATE_LIMITED, 429),
            )
            raise exc
        except (StorageError, OSError, ConnectionError) as exc:
            CredentialSecurityAuditService.commit_standalone(
                db,
                _attempt(
                    current_user.id,
                    action,
                    CredentialSecurityOutcome.CONTROL_UNAVAILABLE,
                    503,
                ),
            )
            raise CredentialSecurityControlUnavailable(
                "Credential rate-limit storage is unavailable"
            ) from exc

        for name, value in headers.items():
            response.headers[name] = value
        try:
            yield current_user
        except Exception as exc:
            _audit_rejection(db, current_user.id, action, exc)
            raise

    return dependency


def _attempt(
    user_id: str,
    action: CredentialSecurityAction,
    outcome: CredentialSecurityOutcome,
    status: int,
) -> CredentialSecurityEventDraft:
    return CredentialSecurityEventDraft(
        user_id=user_id,
        action=action,
        outcome=outcome,
        resource_type="credential_endpoint",
        http_status=status,
        request_id=current_request_id(),
    )


def _audit_rejection(
    db: Session,
    user_id: str,
    action: CredentialSecurityAction,
    exc: Exception,
) -> None:
    if isinstance(exc, HTTPException):
        status = exc.status_code
    elif isinstance(exc, RequestValidationError):
        status = 422
    else:
        status = 500
    CredentialSecurityAuditService.commit_standalone(
        db,
        _attempt(user_id, action, CredentialSecurityOutcome.REJECTED, status),
    )
