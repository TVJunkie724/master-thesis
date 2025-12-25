from pydantic import BaseModel

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

class AuthUrlResponse(BaseModel):
    auth_url: str
