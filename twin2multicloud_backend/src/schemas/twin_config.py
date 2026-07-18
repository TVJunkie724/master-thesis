import json
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator
from datetime import datetime

from src.schemas.optimizer_calculation import OptimizerCalculationParams


CredentialSource = Literal["cloud_connection"]


class AWSCredentials(BaseModel):
    model_config = ConfigDict(extra="forbid")

    access_key_id: str = Field(..., min_length=16, max_length=128)
    secret_access_key: str = Field(..., min_length=16)
    region: str = Field(default="eu-central-1")
    sso_region: Optional[str] = (
        None  # If SSO is in different region than main resources
    )
    session_token: Optional[str] = (
        None  # OPTIONAL - for temporary credentials (STS/SSO)
    )


class AzureCredentials(BaseModel):
    model_config = ConfigDict(extra="forbid")

    subscription_id: str
    client_id: str
    client_secret: str
    tenant_id: str
    region: str = Field(default="westeurope")
    # IoT Hub and Digital Twins are only available in a subset of Azure
    # regions. These optional overrides fall back to `region` when omitted.
    region_iothub: Optional[str] = None
    region_digital_twin: Optional[str] = None


class GCPCredentials(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_id: Optional[str] = None  # At least one of project_id or billing_account
    billing_account: Optional[str] = None  # NEW - for auto-create project
    service_account_json: Optional[str] = None  # Service account JSON content
    region: str = Field(default="europe-west1")  # NEW

    @model_validator(mode="after")
    def check_project_or_billing(self):
        if not self.project_id and not self.billing_account:
            raise ValueError(
                "At least one of project_id or billing_account is required"
            )
        return self


class TwinConfigCreate(BaseModel):
    debug_mode: bool = False
    aws: Optional[AWSCredentials] = None
    azure: Optional[AzureCredentials] = None
    gcp: Optional[GCPCredentials] = None


class TwinCloudConnectionRefs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    aws: Optional[str] = None
    azure: Optional[str] = None
    gcp: Optional[str] = None


class TwinConfigUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    debug_mode: Optional[bool] = None
    highest_step_reached: Optional[int] = None
    optimizer_params: Optional[OptimizerCalculationParams] = None
    cloud_connections: Optional[TwinCloudConnectionRefs] = None
    aws: Optional[AWSCredentials] = None
    azure: Optional[AzureCredentials] = None
    gcp: Optional[GCPCredentials] = None


class TwinConfigResponse(BaseModel):
    """Response model - NEVER returns actual credentials, only status."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    twin_id: str
    twin_state: Optional[str] = None
    debug_mode: bool
    aws_configured: bool
    aws_validated: bool
    aws_credential_source: Optional[CredentialSource] = None
    aws_cloud_connection_id: Optional[str] = None
    aws_region: Optional[str] = None
    aws_sso_region: Optional[str] = None
    azure_configured: bool
    azure_validated: bool
    azure_credential_source: Optional[CredentialSource] = None
    azure_cloud_connection_id: Optional[str] = None
    azure_region: Optional[str] = None
    azure_region_iothub: Optional[str] = None
    azure_region_digital_twin: Optional[str] = None
    gcp_configured: bool
    gcp_validated: bool
    gcp_credential_source: Optional[CredentialSource] = None
    gcp_cloud_connection_id: Optional[str] = None
    gcp_project_id: Optional[str] = None
    gcp_billing_account_configured: bool = False  # NEW - never expose actual value
    gcp_region: Optional[str] = None  # NEW
    configured_providers: list[str] = Field(default_factory=list)
    credential_sources: dict[str, Optional[CredentialSource]] = Field(
        default_factory=dict
    )
    cloud_connections: dict[str, Optional["BoundCloudConnectionSummary"]] = Field(
        default_factory=dict
    )
    highest_step_reached: int = 0
    optimizer_params: Optional[Any] = (
        None  # CalcParams JSON from OptimizerConfiguration
    )
    optimizer_result: Optional[Any] = (
        None  # CalcResult JSON from OptimizerConfiguration
    )
    updated_at: datetime

    @classmethod
    def from_db(cls, config, optimizer_config=None, twin_state: Optional[str] = None):
        """Convert DB model to response (no secrets exposed)."""
        aws_source = _credential_source(
            cloud_connection=getattr(config, "aws_cloud_connection", None)
        )
        azure_source = _credential_source(
            cloud_connection=getattr(config, "azure_cloud_connection", None)
        )
        gcp_source = _credential_source(
            cloud_connection=getattr(config, "gcp_cloud_connection", None)
        )
        configured_providers = [
            provider
            for provider, source in {
                "aws": aws_source,
                "azure": azure_source,
                "gcp": gcp_source,
            }.items()
            if source is not None
        ]

        return cls(
            id=config.id,
            twin_id=config.twin_id,
            twin_state=twin_state,
            debug_mode=bool(config.debug_mode),
            aws_configured=aws_source is not None,
            aws_validated=bool(config.aws_validated),
            aws_credential_source=aws_source,
            aws_cloud_connection_id=getattr(config, "aws_cloud_connection_id", None),
            aws_region=config.aws_region,
            aws_sso_region=getattr(config, "aws_sso_region", None),
            azure_configured=azure_source is not None,
            azure_validated=bool(config.azure_validated),
            azure_credential_source=azure_source,
            azure_cloud_connection_id=getattr(
                config, "azure_cloud_connection_id", None
            ),
            azure_region=getattr(config, "azure_region", None),
            azure_region_iothub=getattr(config, "azure_region_iothub", None),
            azure_region_digital_twin=getattr(
                config, "azure_region_digital_twin", None
            ),
            gcp_configured=gcp_source is not None,
            gcp_validated=bool(config.gcp_validated),
            gcp_credential_source=gcp_source,
            gcp_cloud_connection_id=getattr(config, "gcp_cloud_connection_id", None),
            gcp_project_id=config.gcp_project_id,
            gcp_billing_account_configured=False,
            gcp_region=getattr(config, "gcp_region", None),  # NEW
            configured_providers=configured_providers,
            credential_sources={
                "aws": aws_source,
                "azure": azure_source,
                "gcp": gcp_source,
            },
            cloud_connections={
                "aws": BoundCloudConnectionSummary.from_db(
                    getattr(config, "aws_cloud_connection", None)
                ),
                "azure": BoundCloudConnectionSummary.from_db(
                    getattr(config, "azure_cloud_connection", None)
                ),
                "gcp": BoundCloudConnectionSummary.from_db(
                    getattr(config, "gcp_cloud_connection", None)
                ),
            },
            highest_step_reached=config.highest_step_reached or 0,
            optimizer_params=_safe_json_loads(optimizer_config.params)
            if optimizer_config and optimizer_config.params
            else None,
            optimizer_result=_safe_json_loads(optimizer_config.result_json)
            if optimizer_config and optimizer_config.result_json
            else None,
            updated_at=config.updated_at,
        )


def _safe_json_loads(s):
    """Safely parse JSON string, returning None on error."""
    if not s:
        return None
    try:
        return json.loads(s)
    except (json.JSONDecodeError, TypeError):
        return None


class BoundCloudConnectionSummary(BaseModel):
    """Secret-safe summary of a CloudConnection bound to a twin."""

    id: str
    provider: str
    display_name: str
    auth_type: str
    validation_status: str
    last_validated_at: Optional[datetime] = None

    @classmethod
    def from_db(cls, connection):
        if connection is None:
            return None
        return cls(
            id=connection.id,
            provider=connection.provider,
            display_name=connection.display_name,
            auth_type=connection.auth_type,
            validation_status=connection.validation_status,
            last_validated_at=connection.last_validated_at,
        )


def _credential_source(*, cloud_connection) -> Optional[CredentialSource]:
    if cloud_connection is not None:
        return "cloud_connection"
    return None


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
