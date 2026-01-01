from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import RedirectResponse, Response
from sqlalchemy.orm import Session
from datetime import datetime
import secrets

from src.models.database import get_db
from src.models.user import User
from src.auth.providers.google import GoogleOAuth
from src.auth.providers.saml import UIBKSAMLProvider, is_saml_available
from src.auth.jwt import create_access_token
from src.schemas.auth import TokenResponse
from src.api.dependencies import get_current_user
from src.config import settings

router = APIRouter(prefix="/auth", tags=["auth"])

# In-memory state storage - sufficient for single-instance thesis deployment.
# For production with multiple replicas, use Redis or database-backed storage.
oauth_states: dict[str, str] = {}

# ============================================================================
# Google OAuth Routes
# ============================================================================

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
            google_id=user_info.provider_id,
            auth_provider="google"
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    else:
        user.last_login_at = datetime.utcnow()
        db.commit()
    
    # Generate JWT
    token = create_access_token(user.id)
    
    # Use configurable frontend callback URL
    return RedirectResponse(
        url=f"{settings.FRONTEND_CALLBACK_URL}?token={token}"
    )

# ============================================================================
# UIBK SAML Routes
# ============================================================================

@router.get("/uibk/login")
async def uibk_login(request: Request):
    """
    Initiate UIBK SAML SSO flow.
    
    Redirects user to UIBK Identity Provider for authentication.
    User logs in with UIBK username/password, and IdP sends back
    user attributes (email, name) from the university LDAP directory.
    """
    if not settings.SAML_ENABLED:
        raise HTTPException(status_code=503, detail="UIBK login not available. SAML is not enabled.")
    
    if not is_saml_available():
        raise HTTPException(status_code=503, detail="SAML library not installed")
    
    state = secrets.token_urlsafe(32)
    oauth_states[state] = "pending"
    
    # Build request data for SAML library
    request_data = {
        'https': 'on' if request.url.scheme == 'https' else 'off',
        'http_host': request.url.netloc,
        'script_name': request.url.path,
        'get_data': dict(request.query_params),
    }
    
    provider = UIBKSAMLProvider()
    redirect_url = provider.get_login_url(request_data, relay_state=state)
    
    return {"auth_url": redirect_url}

@router.post("/uibk/callback")
async def uibk_callback(
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Handle UIBK SAML assertion callback (POST binding).
    
    The UIBK IdP POSTs SAML assertion here after successful authentication.
    We validate the assertion, extract user info, and issue a JWT.
    """
    if not settings.SAML_ENABLED:
        raise HTTPException(status_code=503, detail="UIBK login not available")
    
    if not is_saml_available():
        raise HTTPException(status_code=503, detail="SAML library not installed")
    
    form_data = await request.form()
    relay_state = form_data.get("RelayState")
    
    if relay_state not in oauth_states:
        raise HTTPException(status_code=400, detail="Invalid state")
    del oauth_states[relay_state]
    
    # Build request data for SAML library
    request_data = {
        'https': 'on' if request.url.scheme == 'https' else 'off',
        'http_host': request.url.netloc,
        'script_name': request.url.path,
        'get_data': dict(request.query_params),
    }
    
    provider = UIBKSAMLProvider()
    try:
        user_info = await provider.handle_callback(request_data, dict(form_data))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    # Email-based account linking is acceptable for thesis demo.
    # NOTE: In production systems, automatic linking by email could be a security risk
    # if an attacker creates an account with someone else's email first.
    # For this thesis, we accept this trade-off since users are trusted UIBK members.
    user = db.query(User).filter(
        (User.email == user_info.email) | 
        (User.uibk_id == user_info.provider_id)
    ).first()
    
    if not user:
        user = User(
            email=user_info.email,
            name=user_info.name,
            uibk_id=user_info.provider_id,
            auth_provider="uibk"
        )
        db.add(user)
    else:
        # Link UIBK ID if logging in with existing account
        if not user.uibk_id:
            user.uibk_id = user_info.provider_id
        user.last_login_at = datetime.utcnow()
    
    db.commit()
    db.refresh(user)
    
    token = create_access_token(user.id)
    
    # Use configurable frontend URL
    return RedirectResponse(
        url=f"{settings.FRONTEND_CALLBACK_URL}?token={token}"
    )

@router.get("/uibk/metadata")
async def uibk_metadata():
    """
    Serve SP metadata for ACOnet registration.
    
    This endpoint returns XML metadata that must be submitted to ACOnet
    when registering as a Service Provider in the eduID.at federation.
    """
    if not is_saml_available():
        raise HTTPException(status_code=503, detail="SAML library not installed")
    
    provider = UIBKSAMLProvider()
    return Response(
        content=provider.get_metadata(),
        media_type="application/xml"
    )

# ============================================================================
# Common Routes
# ============================================================================

@router.get("/me", response_model=dict)
async def get_me(
    current_user: User = Depends(get_current_user)
):
    """Get current authenticated user."""
    return {
        "id": current_user.id,
        "email": current_user.email,
        "name": current_user.name,
        "picture_url": current_user.picture_url,
        "auth_provider": current_user.auth_provider,
        "uibk_linked": current_user.uibk_id is not None,
        "google_linked": current_user.google_id is not None,
    }

@router.get("/providers")
async def get_available_providers():
    """Get list of available authentication providers."""
    providers = ["google"]  # Always available
    if settings.SAML_ENABLED and is_saml_available():
        providers.append("uibk")
    return {"providers": providers}

