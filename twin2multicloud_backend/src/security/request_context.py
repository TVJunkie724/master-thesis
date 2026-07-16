from __future__ import annotations

from contextvars import ContextVar
import logging
import re
import uuid

from starlette.types import ASGIApp, Message, Receive, Scope, Send


REQUEST_ID_HEADER = b"x-request-id"
_REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]{1,64}$")
_request_id: ContextVar[str | None] = ContextVar("request_id", default=None)
logger = logging.getLogger("twin2multicloud.request")


def current_request_id() -> str:
    """Return the request correlation ID inside an active request."""
    return _request_id.get() or str(uuid.uuid4())


def resolve_request_id(scope: Scope) -> str:
    for name, value in scope.get("headers", []):
        if name.lower() != REQUEST_ID_HEADER:
            continue
        try:
            candidate = value.decode("ascii")
        except UnicodeDecodeError:
            break
        if _REQUEST_ID_PATTERN.fullmatch(candidate):
            return candidate
        break
    return str(uuid.uuid4())


class RequestContextMiddleware:
    """Bind one validated request ID and return it on every HTTP response."""

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = resolve_request_id(scope)
        token = _request_id.set(request_id)
        response_status = 500

        async def send_with_request_id(message: Message) -> None:
            nonlocal response_status
            if message["type"] == "http.response.start":
                response_status = message["status"]
                headers = list(message.get("headers", []))
                headers = [(name, value) for name, value in headers if name.lower() != REQUEST_ID_HEADER]
                headers.append((REQUEST_ID_HEADER, request_id.encode("ascii")))
                message["headers"] = headers
            await send(message)

        try:
            await self.app(scope, receive, send_with_request_id)
        except Exception:
            logger.error(
                "request_failed method=%s path=%s status=500 request_id=%s",
                scope.get("method", "UNKNOWN"),
                scope.get("path", ""),
                request_id,
            )
            raise
        else:
            logger.info(
                "request_completed method=%s path=%s status=%s request_id=%s",
                scope.get("method", "UNKNOWN"),
                scope.get("path", ""),
                response_status,
                request_id,
            )
        finally:
            _request_id.reset(token)
