from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ProviderAuthorization:
    auth_url: str
    request_id: str | None = None


@dataclass(frozen=True)
class VerifiedExternalIdentity:
    email: str
    name: str | None
    picture_url: str | None
    subject: str
