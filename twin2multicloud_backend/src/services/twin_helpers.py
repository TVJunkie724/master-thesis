# src/services/twin_helpers.py
"""
Shared twin-related helpers extracted from route handlers.

This module consolidates the get_user_twin helper that was duplicated across:
- config.py
- deployer.py  
- optimizer.py
- optimizer_config.py
"""

from fastapi import HTTPException
from sqlalchemy.orm import Session

from src.models.twin import DigitalTwin, TwinState
from src.models.user import User


async def get_user_twin(twin_id: str, user: User, db: Session) -> DigitalTwin:
    """
    Verify twin ownership and return the twin.
    
    Args:
        twin_id: UUID of the twin to retrieve
        user: Current authenticated user
        db: Database session
        
    Returns:
        DigitalTwin: The requested twin if owned by user
        
    Raises:
        HTTPException: 404 if twin not found or not owned by user
    """
    twin = db.query(DigitalTwin).filter(
        DigitalTwin.id == twin_id,
        DigitalTwin.user_id == user.id,
        DigitalTwin.state != TwinState.INACTIVE,
    ).first()
    if not twin:
        raise HTTPException(status_code=404, detail="Twin not found")
    return twin
