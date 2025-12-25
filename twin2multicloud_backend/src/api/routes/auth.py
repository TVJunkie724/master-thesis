from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
import secrets

from src.models.database import get_db
from src.models.user import User
from src.auth.providers.google import GoogleOAuth
from src.auth.jwt import create_access_token
from src.schemas.auth import TokenResponse
from src.api.dependencies import get_current_user

router = APIRouter(prefix="/auth", tags=["auth"])

# In-memory state storage (use Redis in production)
oauth_states: dict[str, str] = {}

@router.get("/google/login")
async def google_login():
    """Initiate Google OAuth flow."""
    state = secrets.token_urlsafe(32)
    oauth_states[state] = "pending"
    
    provider = GoogleOAuth()
    auth_url = provider.get_authorize_url(state)
    
    return {"auth_url": auth_url}

@router.get("/google/callback")
async def google_callback(
    code: str = Query(...),
    state: str = Query(...),
    db: Session = Depends(get_db)
):
    """Handle Google OAuth callback."""
    # Verify state
    if state not in oauth_states:
        raise HTTPException(status_code=400, detail="Invalid state")
    del oauth_states[state]
    
    # Exchange code for user info
    provider = GoogleOAuth()
    user_info = await provider.handle_callback(code)
    
    # Find or create user
    user = db.query(User).filter(User.email == user_info.email).first()
    if not user:
        user = User(
            email=user_info.email,
            name=user_info.name,
            picture_url=user_info.picture_url,
            google_id=user_info.provider_id
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    
    # Generate JWT
    token = create_access_token(user.id)
    
    # Redirect to frontend with token
    # In production, use a more secure method
    return RedirectResponse(
        url=f"http://localhost:8080/auth/callback?token={token}"
    )

@router.get("/me", response_model=dict)
async def get_me(
    current_user: User = Depends(get_current_user)
):
    """Get current authenticated user."""
    return {
        "id": current_user.id,
        "email": current_user.email,
        "name": current_user.name,
        "picture_url": current_user.picture_url
    }
