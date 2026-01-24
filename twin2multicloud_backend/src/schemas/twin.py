from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import Optional
from src.models.twin import TwinState

class TwinCreate(BaseModel):
    name: str

class TwinUpdate(BaseModel):
    name: Optional[str] = None
    state: Optional[TwinState] = None

class TwinResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: str
    name: str
    state: TwinState
    created_at: datetime
    updated_at: datetime
    deployed_at: Optional[datetime] = None
    destroyed_at: Optional[datetime] = None
    last_error: Optional[str] = None
