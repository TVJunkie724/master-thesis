from fastapi import Depends, HTTPException, Header
from sqlalchemy.orm import Session
from src.models.database import get_db
from src.models.user import User
from src.auth.jwt import verify_token

async def get_current_user(
    authorization: str = Header(...),
    db: Session = Depends(get_db)
) -> User:
    """Extract and validate JWT, return current user."""
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid auth header")
    
    token = authorization.split(" ")[1]
    user_id = verify_token(token)
    
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    
    return user


# DEV BYPASS: For testing without OAuth (DEBUG mode only)
async def get_current_user_dev(
    authorization: str = Header(None),
    db: Session = Depends(get_db)
) -> User:
    """Development-only auth bypass. Uses 'Bearer dev-token' to get first user."""
    from src.config import settings
    
    if settings.DEBUG and authorization == "Bearer dev-token":
        user = db.query(User).first()
        if user:
            return user
        # Create dev user if none exists
        user = User(email="dev@example.com", name="Developer")
        db.add(user)
        db.commit()
        db.refresh(user)
        return user
    
    # Fall back to real auth
    return await get_current_user(authorization, db)
