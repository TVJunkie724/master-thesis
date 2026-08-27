from __future__ import annotations

from pydantic import BaseModel


class CurrentUserResponse(BaseModel):
    id: str
    email: str
    name: str | None = None
    theme_preference: str
