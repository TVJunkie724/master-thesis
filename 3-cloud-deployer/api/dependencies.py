from enum import Enum
from typing import Optional
from fastapi import HTTPException
from pydantic import BaseModel
import globals


class Base64FileRequest(BaseModel):
    file_base64: str
    filename: Optional[str] = None

class ProviderEnum(str, Enum):
    aws = "aws"
    azure = "azure"
    google = "google"

class ConfigType(str, Enum):
    config = "config"
    iot = "iot"
    events = "events"
    hierarchy = "hierarchy"
    credentials = "credentials"
    providers = "providers"
    optimization = "optimization"

def validate_project_context(project_name: str):
    """
    Validates that the requested project name matches the active project.
    """
    if project_name != globals.CURRENT_PROJECT:
         raise HTTPException(status_code=409, detail=f"SAFETY ERROR: Requested project '{project_name}' does not match active project '{globals.CURRENT_PROJECT}'. Please switch active project first.")
