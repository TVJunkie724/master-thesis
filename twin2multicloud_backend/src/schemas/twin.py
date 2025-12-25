from pydantic import BaseModel
from datetime import datetime
from typing import Optional
from src.models.twin import TwinState

class TwinCreate(BaseModel):
    name: str

class TwinUpdate(BaseModel):
    name: Optional[str] = None
    state: Optional[TwinState] = None

class TwinResponse(BaseModel):
    id: str
    name: str
    state: TwinState
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True
