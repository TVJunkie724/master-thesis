from pydantic import BaseModel, ConfigDict, Field, model_validator
from typing import Optional
from datetime import datetime


class AWSCredentials(BaseModel):
    access_key_id: str = Field(..., min_length=16, max_length=128)
    secret_access_key: str = Field(..., min_length=16)
    region: str = Field(default="eu-central-1")
    session_token: Optional[str] = None  # OPTIONAL - for temporary credentials (STS/SSO)


class AzureCredentials(BaseModel):
    subscription_id: str
    client_id: str
    client_secret: str
    tenant_id: str
    region: str = Field(default="westeurope")  # NEW


class GCPCredentials(BaseModel):
    project_id: Optional[str] = None  # At least one of project_id or billing_account
    billing_account: Optional[str] = None  # NEW - for auto-create project
    service_account_json: Optional[str] = None  # Service account JSON content
    region: str = Field(default="europe-west1")  # NEW
    
    @model_validator(mode='after')
    def check_project_or_billing(self):
        if not self.project_id and not self.billing_account:
            raise ValueError('At least one of project_id or billing_account is required')
        return self


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
    model_config = ConfigDict(from_attributes=True)
    
    id: str
    twin_id: str
    debug_mode: bool
    aws_configured: bool
    aws_validated: bool
    aws_region: Optional[str] = None
    azure_configured: bool
    azure_validated: bool
    azure_region: Optional[str] = None  # NEW
    gcp_configured: bool
    gcp_validated: bool
    gcp_project_id: Optional[str] = None
    gcp_billing_account_configured: bool = False  # NEW - never expose actual value
    gcp_region: Optional[str] = None  # NEW
    updated_at: datetime
    
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
            azure_region=getattr(config, 'azure_region', None),  # NEW
            gcp_configured=bool(config.gcp_project_id or config.gcp_service_account_json),
            gcp_validated=config.gcp_validated,
            gcp_project_id=config.gcp_project_id,
            gcp_billing_account_configured=bool(getattr(config, 'gcp_billing_account', None)),  # NEW
            gcp_region=getattr(config, 'gcp_region', None),  # NEW
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
