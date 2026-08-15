from __future__ import annotations

import hashlib
import math
import time

from fastapi import Response
from limits import parse
from limits.aio.strategies import MovingWindowRateLimiter
from limits.errors import StorageError
from limits.storage import storage_from_string

from src.config import settings


class UserFunctionRateLimitExceeded(RuntimeError):
    def __init__(self, headers: dict[str, str]) -> None:
        super().__init__("User-function source download rate limit exceeded")
        self.headers = headers


class UserFunctionSecurityControlUnavailable(RuntimeError):
    pass


class UserFunctionRateLimiter:
    """Shared moving-window limiter for sensitive extension source reads."""

    def __init__(self, storage_uri: str) -> None:
        async_uri = storage_uri if storage_uri.startswith("async+") else f"async+{storage_uri}"
        self._storage = storage_from_string(
            async_uri,
            wrap_exceptions=True,
            implementation="redispy",
        )
        self._limiter = MovingWindowRateLimiter(self._storage)

    async def hit(self, rate: str, user_id: str) -> dict[str, str]:
        item = parse(rate)
        actor_key = hashlib.sha256(
            f"user-function-source-rate:{user_id}".encode()
        ).hexdigest()
        allowed = await self._limiter.hit(
            item,
            "user-function-source-download",
            actor_key,
        )
        stats = await self._limiter.get_window_stats(
            item,
            "user-function-source-download",
            actor_key,
        )
        reset_after = max(0, math.ceil(stats.reset_time - time.time()))
        headers = {
            "RateLimit-Limit": str(item.amount),
            "RateLimit-Remaining": str(stats.remaining),
            "RateLimit-Reset": str(reset_after),
        }
        if not allowed:
            headers["Retry-After"] = str(max(1, reset_after))
            raise UserFunctionRateLimitExceeded(headers)
        return headers

    async def reset(self) -> None:
        await self._storage.reset()


_limiter: UserFunctionRateLimiter | None = None


def _get_limiter() -> UserFunctionRateLimiter:
    global _limiter
    if _limiter is None:
        _limiter = UserFunctionRateLimiter(settings.user_function_rate_limit_storage_uri)
    return _limiter


async def enforce_user_function_source_rate_limit(
    response: Response,
    user_id: str,
) -> None:
    if not settings.USER_FUNCTION_RATE_LIMIT_ENABLED:
        return
    try:
        headers = await _get_limiter().hit(
            settings.USER_FUNCTION_SOURCE_DOWNLOAD_RATE_LIMIT,
            user_id,
        )
    except UserFunctionRateLimitExceeded:
        raise
    except (StorageError, OSError, ConnectionError) as exc:
        raise UserFunctionSecurityControlUnavailable(
            "User-function rate-limit storage is unavailable"
        ) from exc
    for name, value in headers.items():
        response.headers[name] = value


async def reset_user_function_rate_limiter_for_tests() -> None:
    global _limiter
    if _limiter is not None and settings.APP_ENV.value == "test":
        await _limiter.reset()
    _limiter = None
