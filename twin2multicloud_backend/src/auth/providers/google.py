from __future__ import annotations

from collections.abc import Callable
from typing import Any

from authlib.integrations.httpx_client import AsyncOAuth2Client

from src.auth.providers.base import ProviderAuthorization, VerifiedExternalIdentity
from src.config import settings


class GoogleProviderError(RuntimeError):
    """Sanitized Google OAuth boundary error."""


class GoogleOAuth:
    AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
    TOKEN_URL = "https://oauth2.googleapis.com/token"  # nosec B105
    USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"

    def __init__(
        self,
        client_factory: Callable[..., AsyncOAuth2Client] = AsyncOAuth2Client,
    ) -> None:
        self._client_factory = client_factory

    def get_authorize_url(self, state: str, code_verifier: str) -> ProviderAuthorization:
        self._require_configuration()
        client = self._client_factory(
            client_id=settings.GOOGLE_CLIENT_ID,
            redirect_uri=settings.GOOGLE_REDIRECT_URI,
            scope="openid email profile",
            code_challenge_method="S256",
        )
        url, _ = client.create_authorization_url(
            self.AUTHORIZE_URL,
            state=state,
            code_verifier=code_verifier,
            access_type="online",
            prompt="select_account",
        )
        return ProviderAuthorization(auth_url=url)

    async def handle_callback(
        self,
        code: str,
        code_verifier: str,
    ) -> VerifiedExternalIdentity:
        self._require_configuration()
        try:
            async with self._client_factory(
                client_id=settings.GOOGLE_CLIENT_ID,
                client_secret=settings.GOOGLE_CLIENT_SECRET,
                redirect_uri=settings.GOOGLE_REDIRECT_URI,
                code_challenge_method="S256",
                timeout=15.0,
            ) as client:
                await client.fetch_token(
                    self.TOKEN_URL,
                    code=code,
                    code_verifier=code_verifier,
                )
                response = await client.get(self.USERINFO_URL)
                response.raise_for_status()
                data = response.json()
        except Exception as exc:
            raise GoogleProviderError("Google authentication could not be verified") from exc

        return self._parse_userinfo(data)

    @staticmethod
    def _parse_userinfo(data: Any) -> VerifiedExternalIdentity:
        if not isinstance(data, dict):
            raise GoogleProviderError("Google user information was invalid")
        subject = data.get("sub")
        email = data.get("email")
        if not isinstance(subject, str) or not subject.strip():
            raise GoogleProviderError("Google user information was incomplete")
        if not isinstance(email, str) or "@" not in email:
            raise GoogleProviderError("Google user information was incomplete")
        if data.get("email_verified") is not True:
            raise GoogleProviderError("Google email address is not verified")
        name = data.get("name")
        picture = data.get("picture")
        return VerifiedExternalIdentity(
            email=email.strip().lower(),
            name=name.strip() if isinstance(name, str) and name.strip() else None,
            picture_url=picture if isinstance(picture, str) and picture else None,
            subject=subject.strip(),
        )

    @staticmethod
    def _require_configuration() -> None:
        if not settings.google_auth_enabled:
            raise GoogleProviderError("Google authentication is not configured")
