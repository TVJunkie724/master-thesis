"""
API Dependencies - Shared utilities for API endpoints.
"""

from enum import Enum
from typing import Optional
from fastapi import HTTPException
from pydantic import BaseModel

import src.core.state as state




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
    current_project = state.get_active_project()
    if project_name != current_project:
         raise HTTPException(status_code=409, detail=f"SAFETY ERROR: Requested project '{project_name}' does not match active project '{current_project}'. Please switch active project first.")

VALID_PROVIDERS = {"aws", "azure", "google", "gcp"}

def validate_provider(provider: str) -> str:
    """
    Validates and normalizes the provider string.
    Returns normalized provider name or raises HTTPException.
    """
    provider_lower = provider.lower()
    if provider_lower not in VALID_PROVIDERS:
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid provider '{provider}'. Valid providers are: aws, azure, google"
        )
    return provider_lower
