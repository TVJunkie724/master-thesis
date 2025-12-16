"""
Credentials API Router

Provides endpoints for validating cloud credentials against required permissions.
Supports AWS and Azure credential validation.
"""
from fastapi import APIRouter, Query
from pydantic import BaseModel, Field
from typing import Optional
import json

from api.credentials_checker import check_aws_credentials, check_aws_credentials_from_config
from api.azure_credentials_checker import check_azure_credentials, check_azure_credentials_from_config

router = APIRouter(prefix="/credentials", tags=["Credentials"])


class AWSCredentialsRequest(BaseModel):
    """Request body for AWS credential validation."""
    aws_access_key_id: str = Field(..., description="AWS Access Key ID")
    aws_secret_access_key: str = Field(..., description="AWS Secret Access Key")
    aws_region: str = Field(..., description="AWS Region (e.g., 'eu-central-1')")
    aws_session_token: Optional[str] = Field(
        None, 
        description="Optional AWS Session Token for temporary credentials (from STS)"
    )


class AzureCredentialsRequest(BaseModel):
    """Request body for Azure credential validation."""
    azure_subscription_id: str = Field(..., description="Azure Subscription ID")
    azure_tenant_id: str = Field(..., description="Azure AD Tenant ID")
    azure_client_id: str = Field(..., description="Service Principal Client/Application ID")
    azure_client_secret: str = Field(..., description="Service Principal Client Secret")
    azure_region: str = Field(..., description="Azure Region for general resources (e.g., 'italynorth')")
    azure_region_iothub: str = Field(..., description="Azure Region for IoT Hub (e.g., 'westeurope'), may differ from azure_region")
    azure_region_digital_twin: str = Field(..., description="Azure Region for Digital Twins (e.g., 'westeurope'), must be in ADT supported list")


class CredentialsCheckResponse(BaseModel):
    """Response schema for credential validation."""
    status: str = Field(..., description="Result status: 'valid', 'partial', 'invalid', 'check_failed', or 'error'")
    message: str = Field(..., description="Human-readable result message")
    caller_identity: Optional[dict] = Field(None, description="AWS caller identity if credentials are valid")
    can_list_policies: bool = Field(..., description="Whether the credentials can list their own policies")
    missing_check_permission: Optional[str] = Field(None, description="Permission missing to perform the check (if can_list_policies is False)")
    by_layer: dict = Field(..., description="Permission results organized by deployment layer (layer_1 through layer_5)")
    by_service: dict = Field(..., description="Permission results organized by AWS service with layer references")
    summary: dict = Field(..., description="Summary with total_required, valid, and missing counts")


class AzureCredentialsCheckResponse(BaseModel):
    """Response schema for Azure credential validation."""
    status: str = Field(..., description="Result status: 'valid', 'partial', 'invalid', 'check_failed', or 'error'")
    message: str = Field(..., description="Human-readable result message")
    caller_identity: Optional[dict] = Field(None, description="Azure subscription/principal info")
    can_list_roles: bool = Field(..., description="Whether the credentials can list role assignments")
    by_layer: dict = Field(..., description="Permission results organized by deployment layer")
    summary: dict = Field(..., description="Summary with total_layers, valid_layers, partial_layers, invalid_layers counts")
    recommended_roles: Optional[dict] = Field(None, description="Recommended roles: custom (preferred) and builtin alternatives")


@router.post(
    "/check/aws",
    response_model=CredentialsCheckResponse,
    summary="Validate AWS credentials from request body",
    description=(
        "Validates AWS credentials against all required permissions for the deployer. "
        "Accepts credentials directly in the request body. "
        "Returns categorized results by layer and by service."
    )
)
async def check_aws_from_body(request: AWSCredentialsRequest):
    """
    Validate AWS credentials from request body against all required permissions.
    
    Checks permissions for all 5 deployment layers:
    - **Layer 1**: IoT Core, Lambda (Dispatcher)
    - **Layer 2**: Lambda (Processor), Step Functions
    - **Layer 3**: DynamoDB, S3, EventBridge  
    - **Layer 4**: IoT TwinMaker
    - **Layer 5**: Amazon Managed Grafana
    
    Returns a categorized list of valid and missing permissions.
    """
    return check_aws_credentials(request.model_dump())


@router.get(
    "/check/aws",
    response_model=CredentialsCheckResponse,
    summary="Validate AWS credentials from project config",
    description=(
        "Validates AWS credentials from the project's config_credentials.json file. "
        "Uses the active project if no project name is specified. "
        "Returns categorized results by layer and by service."
    )
)
async def check_aws_from_config(
    project: Optional[str] = Query(
        None, 
        description="Project name to load credentials from. Uses active project if not specified."
    )
):
    """
    Validate AWS credentials from project's config_credentials.json.
    
    Reads the AWS credentials from the specified project's configuration file
    and validates them against all required permissions.
    
    If no project is specified, uses the currently active project.
    """
    return check_aws_credentials_from_config(project)


# ==========================================
# Azure Credentials Endpoints
# ==========================================

@router.post(
    "/check/azure",
    response_model=AzureCredentialsCheckResponse,
    summary="Validate Azure credentials from request body",
    description=(
        "Validates Azure Service Principal credentials against required RBAC roles. "
        "Checks if Contributor and User Access Administrator roles are assigned. "
        "Returns categorized results by deployment layer."
    )
)
async def check_azure_from_body(request: AzureCredentialsRequest):
    """
    Validate Azure Service Principal credentials from request body.
    
    Checks RBAC role assignments for all deployment layers:
    - **Setup**: Resource Groups, Managed Identity, Storage
    - **Layer 0**: App Service Plan, Function Apps
    - **Layer 1**: IoT Hub, Event Grid, Role Assignments
    - **Layer 2**: Function Apps (Compute)
    - **Layer 3**: Cosmos DB, Blob Storage
    - **Layer 4**: Azure Digital Twins
    - **Layer 5**: Azure Managed Grafana
    
    Returns status and missing roles by layer.
    """
    return check_azure_credentials(request.model_dump())


@router.get(
    "/check/azure",
    response_model=AzureCredentialsCheckResponse,
    summary="Validate Azure credentials from project config",
    description=(
        "Validates Azure credentials from the project's config_credentials.json file. "
        "Uses the active project if no project name is specified. "
        "Returns categorized results by layer."
    )
)
async def check_azure_from_config(
    project: Optional[str] = Query(
        None, 
        description="Project name to load credentials from. Uses active project if not specified."
    )
):
    """
    Validate Azure credentials from project's config_credentials.json.
    
    Reads the Azure credentials from the specified project's configuration file
    and validates them against required RBAC role assignments.
    
    If no project is specified, uses the currently active project.
    """
    return check_azure_credentials_from_config(project)


# ==========================================
# GCP Credentials Endpoints
# ==========================================

# Import GCP checker (at the top, import was added separately)
from api.gcp_credentials_checker import check_gcp_credentials, check_gcp_credentials_from_config


class GCPCredentialsRequest(BaseModel):
    """Request body for GCP credential validation."""
    gcp_project_id: Optional[str] = Field(None, description="GCP Project ID (optional if billing_account provided)")
    gcp_billing_account: Optional[str] = Field(None, description="GCP Billing Account (for project creation)")
    gcp_credentials_file: str = Field(..., description="Path to Service Account JSON key file")
    gcp_region: str = Field(..., description="GCP Region (e.g., 'europe-west1')")


class GCPCredentialsCheckResponse(BaseModel):
    """Response schema for GCP credential validation."""
    status: str = Field(..., description="Result status: 'valid', 'partial', 'invalid', 'sdk_missing', or 'error'")
    message: str = Field(..., description="Human-readable result message")
    caller_identity: Optional[dict] = Field(None, description="GCP service account info")
    project_access: Optional[dict] = Field(None, description="Project access status")
    api_status: Optional[dict] = Field(None, description="API enablement status by layer")
    required_roles: list = Field(..., description="List of required IAM roles")


@router.post(
    "/check/gcp",
    response_model=GCPCredentialsCheckResponse,
    summary="Validate GCP credentials from request body",
    description=(
        "Validates GCP Service Account credentials against required permissions. "
        "Checks project access and API enablement status. "
        "Returns status and missing APIs by layer."
    )
)
async def check_gcp_from_body(request: GCPCredentialsRequest):
    """
    Validate GCP Service Account credentials from request body.
    
    Checks permissions for L1-L3 deployment layers:
    - **L1**: Pub/Sub, Eventarc
    - **L2**: Cloud Functions, Cloud Run, Cloud Build
    - **L3**: Firestore, Cloud Storage, Cloud Scheduler
    
    Note: L4/L5 not available - GCP lacks managed Digital Twin and Grafana services.
    
    Returns status and missing APIs.
    """
    return check_gcp_credentials(request.model_dump())


@router.get(
    "/check/gcp",
    response_model=GCPCredentialsCheckResponse,
    summary="Validate GCP credentials from project config",
    description=(
        "Validates GCP credentials from the project's config_credentials.json file. "
        "Uses the active project if no project name is specified. "
        "Returns status and API enablement results."
    )
)
async def check_gcp_from_config(
    project: Optional[str] = Query(
        None, 
        description="Project name to load credentials from. Uses active project if not specified."
    )
):
    """
    Validate GCP credentials from project's config_credentials.json.
    
    Reads the GCP credentials from the specified project's configuration file
    and validates them against required permissions.
    
    If no project is specified, uses the currently active project.
    """
    return check_gcp_credentials_from_config(project)

