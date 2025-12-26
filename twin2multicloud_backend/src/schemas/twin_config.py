from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class AWSCredentials(BaseModel):
    access_key_id: str = Field(..., min_length=16, max_length=128)
    secret_access_key: str = Field(..., min_length=16)
    region: str = "us-east-1"
    session_token: Optional[str] = None  # For temporary credentials (STS/SSO)

class AzureCredentials(BaseModel):
    subscription_id: str
    client_id: str
    client_secret: str
    tenant_id: str

class GCPCredentials(BaseModel):
    project_id: str
    service_account_json: str  # Full JSON as string

class TwinConfigCreate(BaseModel):
    debug_mode: bool = False
    aws: Optional[AWSCredentials] = None
    azure: Optional[AzureCredentials] = None
    gcp: Optional[GCPCredentials] = None

class TwinConfigUpdate(BaseModel):
    debug_mode: Optional[bool] = None
    aws: Optional[AWSCredentials] = None
    azure: Optional[AzureCredentials] = None
    gcp: Optional[GCPCredentials] = None

class TwinConfigResponse(BaseModel):
    """Response model - NEVER returns actual credentials, only status."""
    id: str
    twin_id: str
    debug_mode: bool
    aws_configured: bool
    aws_validated: bool
    aws_region: Optional[str] = None
    azure_configured: bool
    azure_validated: bool
    gcp_configured: bool
    gcp_validated: bool
    gcp_project_id: Optional[str] = None
    updated_at: datetime
    
    class Config:
        from_attributes = True
    
    @classmethod
    def from_db(cls, config):
        """Convert DB model to response (no secrets exposed)."""
        return cls(
            id=config.id,
            twin_id=config.twin_id,
            debug_mode=config.debug_mode,
            aws_configured=bool(config.aws_access_key_id),
            aws_validated=config.aws_validated,
            aws_region=config.aws_region,
            azure_configured=bool(config.azure_subscription_id),
            azure_validated=config.azure_validated,
            gcp_configured=bool(config.gcp_project_id),
            gcp_validated=config.gcp_validated,
            gcp_project_id=config.gcp_project_id,
            updated_at=config.updated_at
        )

class CredentialValidationResult(BaseModel):
    provider: str  # "aws", "azure", "gcp"
    valid: bool
    message: str
    permissions: Optional[list[str]] = None


class InlineValidationRequest(BaseModel):
    """Request for validating credentials without storing."""
    provider: str  # "aws", "azure", "gcp"
    aws: Optional[AWSCredentials] = None
    azure: Optional[AzureCredentials] = None
    gcp: Optional[GCPCredentials] = None

