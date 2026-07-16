from unittest.mock import Mock
from urllib.parse import parse_qs, urlparse

import pytest

from src.auth.providers.google import GoogleOAuth, GoogleProviderError
from src.auth.providers.saml import UIBKSAMLProvider
from src.config import settings


def test_google_userinfo_requires_verified_email():
    with pytest.raises(GoogleProviderError, match="not verified"):
        GoogleOAuth._parse_userinfo(
            {
                "sub": "subject",
                "email": "person@example.test",
                "email_verified": False,
            }
        )


def test_google_userinfo_is_normalized_without_provider_payload_leakage():
    identity = GoogleOAuth._parse_userinfo(
        {
            "sub": " subject ",
            "email": "Person@Example.Test ",
            "email_verified": True,
            "name": " Test Person ",
            "picture": "https://images.example.test/person",
        }
    )

    assert identity.subject == "subject"
    assert identity.email == "person@example.test"
    assert identity.name == "Test Person"


def test_google_authorization_uses_pkce_s256(monkeypatch):
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_ID", "client-id")
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_SECRET", "client-secret")
    monkeypatch.setattr(
        settings,
        "GOOGLE_REDIRECT_URI",
        "https://api.example.test/auth/google/callback",
    )

    authorization = GoogleOAuth().get_authorize_url(
        "state-value",
        "pkce-verifier-with-sufficient-entropy-for-this-test",
    )
    query = parse_qs(urlparse(authorization.auth_url).query)

    assert query["state"] == ["state-value"]
    assert query["code_challenge_method"] == ["S256"]
    assert query["code_challenge"][0] != "pkce-verifier-with-sufficient-entropy-for-this-test"


def test_saml_request_metadata_comes_from_registered_acs(monkeypatch):
    monkeypatch.setattr(
        settings,
        "SAML_ACS_URL",
        "https://api.example.test/auth/uibk/callback",
    )

    request_data = UIBKSAMLProvider.request_data(
        query={"safe": "value"},
        post={"SAMLResponse": "opaque"},
    )

    assert request_data["https"] == "on"
    assert request_data["http_host"] == "api.example.test"
    assert request_data["script_name"] == "/auth/uibk/callback"


@pytest.mark.asyncio
async def test_saml_callback_passes_stored_request_id(monkeypatch):
    auth = Mock()
    auth.get_errors.return_value = []
    auth.is_authenticated.return_value = True
    auth.get_attributes.return_value = {
        "mail": ["person@uibk.ac.at"],
        "displayName": ["Test Person"],
    }
    auth.get_nameid.return_value = "subject@uibk.ac.at"
    provider = object.__new__(UIBKSAMLProvider)
    monkeypatch.setattr(provider, "_init_saml_auth", lambda _request: auth)

    identity = await provider.handle_callback(
        {"post_data": {}},
        {"SAMLResponse": "opaque"},
        "request-id-123",
    )

    auth.process_response.assert_called_once_with(request_id="request-id-123")
    assert identity.subject == "subject@uibk.ac.at"


@pytest.mark.asyncio
async def test_saml_errors_are_sanitized(monkeypatch):
    auth = Mock()
    auth.get_errors.return_value = ["private-provider-detail"]
    provider = object.__new__(UIBKSAMLProvider)
    monkeypatch.setattr(provider, "_init_saml_auth", lambda _request: auth)

    with pytest.raises(ValueError) as exc_info:
        await provider.handle_callback({}, {"SAMLResponse": "opaque"}, "request-id")

    assert str(exc_info.value) == "SAML response validation failed"
    assert "private-provider-detail" not in str(exc_info.value)
