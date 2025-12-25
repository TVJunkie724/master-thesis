from authlib.integrations.httpx_client import AsyncOAuth2Client
from src.auth.providers.base import OAuthProvider, UserInfo
from src.config import settings

class GoogleOAuth(OAuthProvider):
    def __init__(self):
        self.client_id = settings.GOOGLE_CLIENT_ID
        self.client_secret = settings.GOOGLE_CLIENT_SECRET
        self.redirect_uri = settings.GOOGLE_REDIRECT_URI
        
    def get_authorize_url(self, state: str) -> str:
        client = AsyncOAuth2Client(
            client_id=self.client_id,
            redirect_uri=self.redirect_uri,
            scope="openid email profile"
        )
        url, _ = client.create_authorization_url(
            "https://accounts.google.com/o/oauth2/auth",
            state=state
        )
        return url
    
    async def handle_callback(self, code: str) -> UserInfo:
        async with AsyncOAuth2Client(
            client_id=self.client_id,
            client_secret=self.client_secret,
            redirect_uri=self.redirect_uri
        ) as client:
            token = await client.fetch_token(
                "https://oauth2.googleapis.com/token",
                code=code
            )
            
            # Get user info
            resp = await client.get(
                "https://www.googleapis.com/oauth2/v3/userinfo"
            )
            data = resp.json()
            
            return UserInfo(
                email=data["email"],
                name=data.get("name"),
                picture_url=data.get("picture"),
                provider_id=data["sub"]
            )
