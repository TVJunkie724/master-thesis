from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import Optional

class UserBase(BaseModel):
    email: str
    name: Optional[str] = None

class UserResponse(UserBase):
    model_config = ConfigDict(from_attributes=True)
    
    id: str
    picture_url: Optional[str] = None
    created_at: datetime
    auth_provider: str = "google"
    theme_preference: Optional[str] = "dark"
    google_linked: bool = False
    uibk_linked: bool = False
