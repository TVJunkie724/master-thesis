from abc import ABC, abstractmethod
from dataclasses import dataclass

@dataclass
class UserInfo:
    email: str
    name: str | None
    picture_url: str | None
    provider_id: str  # e.g., Google user ID

class OAuthProvider(ABC):
    @abstractmethod
    def get_authorize_url(self, state: str) -> str:
        """Return the OAuth authorization URL."""
        ...
    
    @abstractmethod
    async def handle_callback(self, code: str) -> UserInfo:
        """Exchange code for tokens and return user info."""
        ...
