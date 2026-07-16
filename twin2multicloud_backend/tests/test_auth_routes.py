from urllib.parse import parse_qs, urlparse

from src.auth.providers.base import ProviderAuthorization, VerifiedExternalIdentity
from src.auth.providers.google import GoogleOAuth
from src.config import settings


def test_provider_capabilities_are_disabled_without_configuration(client):
    response = client.get("/auth/providers")

    assert response.status_code == 200
    assert response.json() == {
        "providers": [
            {
                "provider": "uibk",
                "display_name": "UIBK",
                "enabled": False,
                "unavailable_reason": "not_enabled",
            },
            {
                "provider": "google",
                "display_name": "Google",
                "enabled": False,
                "unavailable_reason": "not_configured",
            },
        ]
    }


def test_disabled_provider_returns_structured_error(client):
    response = client.post("/auth/providers/google/login")

    assert response.status_code == 503
    assert response.json()["error_code"] == "AUTH_PROVIDER_UNAVAILABLE"
    assert "request_id" in response.json()


def test_google_browser_flow_exchanges_once_without_token_in_callback(
    client,
    monkeypatch,
):
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_ID", "client-id")
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_SECRET", "client-secret")
    monkeypatch.setattr(
        settings,
        "GOOGLE_REDIRECT_URI",
        "http://localhost:5005/auth/google/callback",
    )

    def authorize(_self, state, _verifier):
        return ProviderAuthorization(
            auth_url=f"https://accounts.example.test/authorize?state={state}"
        )

    async def callback(_self, _code, _verifier):
        return VerifiedExternalIdentity(
            email="person@example.test",
            name="Test Person",
            picture_url=None,
            subject="google-subject",
        )

    monkeypatch.setattr(GoogleOAuth, "get_authorize_url", authorize)
    monkeypatch.setattr(GoogleOAuth, "handle_callback", callback)

    started = client.post("/auth/providers/google/login")
    assert started.status_code == 201
    payload = started.json()
    state = parse_qs(urlparse(payload["auth_url"]).query)["state"][0]
    assert "access_token" not in payload

    provider_callback = client.get(
        "/auth/google/callback",
        params={"state": state, "code": "authorization-code"},
    )
    assert provider_callback.status_code == 200
    assert "Sign-in complete" in provider_callback.text
    assert "token" not in provider_callback.headers.get("location", "").lower()
    assert provider_callback.headers["cache-control"] == "no-store"

    exchanged = client.post(
        "/auth/session/exchange",
        json={
            "transaction_id": payload["transaction_id"],
            "poll_verifier": payload["poll_verifier"],
        },
    )
    assert exchanged.status_code == 200
    session = exchanged.json()
    assert session["status"] == "authenticated"
    assert session["user"]["google_linked"] is True
    token = session["access_token"]

    me = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["email"] == "person@example.test"

    malformed = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {token} extra"},
    )
    assert malformed.status_code == 401

    replay = client.post(
        "/auth/session/exchange",
        json={
            "transaction_id": payload["transaction_id"],
            "poll_verifier": payload["poll_verifier"],
        },
    )
    assert replay.status_code == 409
    assert replay.json()["error_code"] == "AUTH_TRANSACTION_REPLAYED"

    logout = client.post("/auth/logout", headers={"Authorization": f"Bearer {token}"})
    assert logout.status_code == 200
    assert client.get("/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401


def test_pending_login_can_be_cancelled_and_not_exchanged(client, monkeypatch):
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_ID", "client-id")
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_SECRET", "client-secret")
    monkeypatch.setattr(
        settings,
        "GOOGLE_REDIRECT_URI",
        "http://localhost:5005/auth/google/callback",
    )
    monkeypatch.setattr(
        GoogleOAuth,
        "get_authorize_url",
        lambda _self, state, _verifier: ProviderAuthorization(
            auth_url=f"https://accounts.example.test/authorize?state={state}"
        ),
    )
    started = client.post("/auth/providers/google/login").json()
    command = {
        "transaction_id": started["transaction_id"],
        "poll_verifier": started["poll_verifier"],
    }

    pending = client.post("/auth/session/exchange", json=command)
    assert pending.status_code == 202
    assert pending.json() == {
        "status": "pending",
        "access_token": None,
        "token_type": None,
        "expires_in": None,
        "user": None,
    }

    assert client.post("/auth/session/cancel", json=command).status_code == 200
    inactive = client.post("/auth/session/exchange", json=command)
    assert inactive.status_code == 410
    assert inactive.json()["error_code"] == "AUTH_TRANSACTION_INACTIVE"


def test_session_exchange_rejects_non_uuid_transaction_id(client):
    response = client.post(
        "/auth/session/exchange",
        json={
            "transaction_id": "not-a-canonical-uuid-value-000000000",
            "poll_verifier": "poll-verifier-with-at-least-thirty-two-characters",
        },
    )

    assert response.status_code == 422


def test_login_initiation_is_rate_limited_with_structured_error(client, monkeypatch):
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_ID", "client-id")
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_SECRET", "client-secret")
    monkeypatch.setattr(
        settings,
        "GOOGLE_REDIRECT_URI",
        "http://localhost:5005/auth/google/callback",
    )
    monkeypatch.setattr(settings, "AUTH_LOGIN_RATE_LIMIT", "1/minute")
    monkeypatch.setattr(
        GoogleOAuth,
        "get_authorize_url",
        lambda _self, state, _verifier: ProviderAuthorization(
            auth_url=f"https://accounts.example.test/authorize?state={state}"
        ),
    )

    assert client.post("/auth/providers/google/login").status_code == 201
    limited = client.post("/auth/providers/google/login")

    assert limited.status_code == 429
    assert limited.json()["error_code"] == "RATE_LIMITED"
    assert int(limited.headers["Retry-After"]) >= 1
