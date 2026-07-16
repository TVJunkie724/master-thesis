from __future__ import annotations

import ipaddress
import json

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from src.security.request_context import current_request_id


HSTS_HEADER = b"strict-transport-security"
HSTS_VALUE = b"max-age=31536000; includeSubDomains"


class ProductionTransportMiddleware:
    """Enforce HTTPS without trusting caller-controlled forwarding headers."""

    def __init__(self, app: ASGIApp, *, require_https: bool, trusted_proxy_cidrs: tuple[str, ...]):
        self.app = app
        self.require_https = require_https
        self.trusted_networks = tuple(
            ipaddress.ip_network(value, strict=False) for value in trusted_proxy_cidrs
        )

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or not self.require_https:
            await self.app(scope, receive, send)
            return

        if not self._is_secure(scope):
            await self._reject(send)
            return

        async def send_with_hsts(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers = [(name, value) for name, value in headers if name.lower() != HSTS_HEADER]
                headers.append((HSTS_HEADER, HSTS_VALUE))
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, send_with_hsts)

    def _is_secure(self, scope: Scope) -> bool:
        if scope.get("scheme") == "https":
            return True
        peer = scope.get("client")
        if not peer or not self._peer_is_trusted(peer[0]):
            return False
        forwarded = self._header(scope, b"x-forwarded-proto")
        return forwarded is not None and forwarded.split(b",", 1)[0].strip().lower() == b"https"

    def _peer_is_trusted(self, peer: str) -> bool:
        try:
            address = ipaddress.ip_address(peer)
        except ValueError:
            return False
        return any(address in network for network in self.trusted_networks)

    @staticmethod
    def _header(scope: Scope, expected: bytes) -> bytes | None:
        for name, value in scope.get("headers", []):
            if name.lower() == expected:
                return value
        return None

    @staticmethod
    async def _reject(send: Send) -> None:
        payload = json.dumps(
            {
                "error_code": "INSECURE_TRANSPORT",
                "message": "HTTPS is required for this API.",
                "fix_suggestion": "Use the configured HTTPS endpoint and trusted edge proxy.",
                "http_status": 400,
                "request_id": current_request_id(),
            }
        ).encode("utf-8")
        await send(
            {
                "type": "http.response.start",
                "status": 400,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(payload)).encode("ascii")),
                ],
            }
        )
        await send({"type": "http.response.body", "body": payload})
