from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from src.models.twin import TwinState


class TwinCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=120)

class TwinUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Optional[str] = Field(default=None, min_length=1, max_length=120)

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
