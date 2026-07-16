from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.security.request_context import RequestContextMiddleware
from src.security.transport import ProductionTransportMiddleware


def _app(*, require_https: bool, trusted_proxy_cidrs: tuple[str, ...] = ()) -> FastAPI:
    app = FastAPI()

    @app.get("/probe")
    async def probe():
        return {"ok": True}

    app.add_middleware(
        ProductionTransportMiddleware,
        require_https=require_https,
        trusted_proxy_cidrs=trusted_proxy_cidrs,
    )
    app.add_middleware(RequestContextMiddleware)
    return app


def test_direct_https_is_accepted_with_hsts_and_preserved_request_id():
    client = TestClient(_app(require_https=True), base_url="https://api.example.test")

    response = client.get("/probe", headers={"X-Request-ID": "safe-request.123"})

    assert response.status_code == 200
    assert response.headers["strict-transport-security"] == (
        "max-age=31536000; includeSubDomains"
    )
    assert response.headers["x-request-id"] == "safe-request.123"


def test_plain_http_and_untrusted_forwarded_proto_are_rejected_without_redirect():
    client = TestClient(_app(require_https=True), base_url="http://api.example.test")

    response = client.get("/probe", headers={"X-Forwarded-Proto": "https"})

    assert response.status_code == 400
    assert response.history == []
    assert response.json()["error_code"] == "INSECURE_TRANSPORT"
    assert response.headers["x-request-id"] == response.json()["request_id"]


def test_trusted_proxy_forwarded_https_is_accepted():
    client = TestClient(
        _app(require_https=True, trusted_proxy_cidrs=("10.0.0.0/8",)),
        base_url="http://api.example.test",
        client=("10.2.3.4", 50000),
    )

    response = client.get("/probe", headers={"X-Forwarded-Proto": "https"})

    assert response.status_code == 200
    assert "strict-transport-security" in response.headers


def test_malformed_request_id_is_replaced():
    client = TestClient(_app(require_https=False))

    response = client.get("/probe", headers={"X-Request-ID": "contains spaces and secrets"})

    assert response.status_code == 200
    assert response.headers["x-request-id"] != "contains spaces and secrets"
    assert len(response.headers["x-request-id"]) == 36
