from __future__ import annotations

from enum import StrEnum
import hashlib
import ipaddress
import math
import time

from fastapi import Request, Response
from limits import parse
from limits.aio.strategies import MovingWindowRateLimiter
from limits.errors import StorageError
from limits.storage import storage_from_string

from src.config import settings


class AuthRateClass(StrEnum):
    LOGIN = "auth-login"
    EXCHANGE = "auth-exchange"


class AuthRateLimitExceeded(RuntimeError):
    def __init__(self, headers: dict[str, str]) -> None:
        super().__init__("Authentication endpoint rate limit exceeded")
        self.headers = headers


class AuthSecurityControlUnavailable(RuntimeError):
    pass


class AuthRateLimiter:
    def __init__(self, storage_uri: str) -> None:
        async_uri = storage_uri if storage_uri.startswith("async+") else f"async+{storage_uri}"
        storage = storage_from_string(
            async_uri,
            wrap_exceptions=True,
            implementation="redispy",
        )
        self._storage = storage
        self._limiter = MovingWindowRateLimiter(storage)

    async def hit(self, rate: str, rate_class: AuthRateClass, actor: str) -> dict[str, str]:
        item = parse(rate)
        actor_key = hashlib.sha256(f"auth-rate:{actor}".encode()).hexdigest()
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
            raise AuthRateLimitExceeded(headers)
        return headers

    async def reset(self) -> None:
        await self._storage.reset()


_limiter: AuthRateLimiter | None = None


async def enforce_auth_rate_limit(
    request: Request,
    response: Response,
    rate_class: AuthRateClass,
) -> None:
    if not settings.AUTH_RATE_LIMIT_ENABLED:
        return
    rate = (
        settings.AUTH_LOGIN_RATE_LIMIT
        if rate_class is AuthRateClass.LOGIN
        else settings.AUTH_EXCHANGE_RATE_LIMIT
    )
    try:
        headers = await _get_limiter().hit(rate, rate_class, _client_actor(request))
    except AuthRateLimitExceeded:
        raise
    except (StorageError, OSError, ConnectionError) as exc:
        raise AuthSecurityControlUnavailable(
            "Authentication rate-limit storage is unavailable"
        ) from exc
    for name, value in headers.items():
        response.headers[name] = value


def _get_limiter() -> AuthRateLimiter:
    global _limiter
    if _limiter is None:
        _limiter = AuthRateLimiter(settings.auth_rate_limit_storage_uri)
    return _limiter


async def reset_auth_rate_limiter_for_tests() -> None:
    global _limiter
    if _limiter is not None and settings.APP_ENV.value == "test":
        await _limiter.reset()
    _limiter = None


def _client_actor(request: Request) -> str:
    peer = request.client.host if request.client else "unknown"
    if _peer_is_trusted(peer):
        forwarded = request.headers.get("x-forwarded-for", "").split(",", 1)[0].strip()
        try:
            if forwarded:
                return str(ipaddress.ip_address(forwarded))
        except ValueError:
            pass
    try:
        return str(ipaddress.ip_address(peer))
    except ValueError:
        return "unknown"


def _peer_is_trusted(peer: str) -> bool:
    try:
        address = ipaddress.ip_address(peer)
    except ValueError:
        return False
    return any(
        address in ipaddress.ip_network(network, strict=False)
        for network in settings.trusted_proxy_cidrs
    )
