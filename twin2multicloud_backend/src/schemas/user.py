from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class UserBase(BaseModel):
    email: str
    name: Optional[str] = None

class UserResponse(UserBase):
    id: str
    picture_url: Optional[str] = None
    created_at: datetime
    
    class Config:
        from_attributes = True
