"""
Permissions API endpoints for validating cloud provider credentials.

Provides endpoints for verifying cloud credentials against required permissions.
Supports AWS, Azure, and GCP credential validation.

Categories:
- "Permissions - Upload": Verify credentials from request body
- "Permissions - Project": Verify credentials from project config
"""
from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict
from typing import Optional

from backend import credentials_checker

router = APIRouter(prefix="/permissions")


# =============================================================================
# Request Models
# =============================================================================

class AWSCredentialsRequest(BaseModel):
    """Request body for AWS credential validation."""
    aws_access_key_id: str
    aws_secret_access_key: str
    aws_region: str = "eu-central-1"
    aws_session_token: Optional[str] = None

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "aws_access_key_id": "AKIAIOSFODNN7EXAMPLE",
            "aws_secret_access_key": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
            "aws_region": "eu-central-1"
        }
    })


class GCPCredentialsRequest(BaseModel):
    """Request body for GCP credential validation."""
    gcp_credentials_file: str
    gcp_project_id: str
    gcp_region: str = "europe-west1"

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "gcp_credentials_file": "/config/gcp_credentials.json",
            "gcp_project_id": "my-project-id",
            "gcp_region": "europe-west1"
        }
    })


class AzureCredentialsRequest(BaseModel):
    """Request body for Azure credential validation."""
    azure_subscription_id: str
    azure_region: str = "westeurope"
    azure_client_id: Optional[str] = None
    azure_client_secret: Optional[str] = None
    azure_tenant_id: Optional[str] = None

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "azure_subscription_id": "12345678-1234-1234-1234-123456789abc",
            "azure_region": "westeurope"
        }
    })


# =============================================================================
# AWS Endpoints
# =============================================================================

@router.get(
    "/verify/aws",
    tags=["Permissions - Project"],
    summary="Verify AWS permissions from project config",
    description=(
        "Validates AWS credentials loaded from the config file. "
        "Checks: credentials present, STS GetCallerIdentity succeeds, "
        "and Pricing API access works."
    ),
    responses={
        200: {
            "description": "Credential check result",
            "content": {
                "application/json": {
                    "example": {
                        "provider": "aws",
                        "status": "valid",
                        "message": "AWS credentials are valid and can access Pricing API",
                        "config_present": True,
                        "credentials_valid": True,
                        "can_fetch_pricing": True,
                        "identity": {
                            "account": "123456789012",
                            "arn": "arn:aws:iam::123456789012:user/example"
                        }
                    }
                }
            }
        }
    }
)
def check_aws_from_config():
    """Check AWS credentials from config file."""
    return credentials_checker.check_aws_credentials_from_config()


@router.post(
    "/verify/aws",
    tags=["Permissions - Upload"],
    summary="Verify AWS permissions from request body",
    description=(
        "Validates AWS credentials provided in the request body. "
        "Does not use the config file."
    )
)
def check_aws_from_body(request: AWSCredentialsRequest):
    """Check AWS credentials from request body."""
    return credentials_checker.check_aws_credentials(request.dict())


# =============================================================================
# GCP Endpoints
# =============================================================================

@router.get(
    "/verify/gcp",
    tags=["Permissions - Project"],
    summary="Verify GCP permissions from project config",
    description=(
        "Validates GCP service account credentials loaded from the config. "
        "Checks: credentials file exists, can load credentials, "
        "and Cloud Billing Catalog API access works."
    ),
    responses={
        200: {
            "description": "Credential check result",
            "content": {
                "application/json": {
                    "example": {
                        "provider": "gcp",
                        "status": "valid",
                        "message": "GCP credentials are valid and can access Cloud Billing Catalog API",
                        "config_present": True,
                        "credentials_valid": True,
                        "can_fetch_pricing": True,
                        "identity": {
                            "project_id": "my-project",
                            "service_account_email": "sa@my-project.iam.gserviceaccount.com"
                        }
                    }
                }
            }
        }
    }
)
def check_gcp_from_config():
    """Check GCP credentials from config file."""
    return credentials_checker.check_gcp_credentials_from_config()


@router.post(
    "/verify/gcp",
    tags=["Permissions - Upload"],
    summary="Verify GCP permissions from request body",
    description=(
        "Validates GCP credentials using the file path provided in the request body."
    )
)
def check_gcp_from_body(request: GCPCredentialsRequest):
    """Check GCP credentials from request body."""
    return credentials_checker.check_gcp_credentials(request.gcp_credentials_file)


# =============================================================================
# Azure Endpoints
# =============================================================================

@router.get(
    "/verify/azure",
    tags=["Permissions - Project"],
    summary="Verify Azure permissions from project config",
    description=(
        "Validates Azure configuration loaded from the config file. "
        "Note: Azure Pricing API is publicly accessible, so credentials "
        "are not strictly required for pricing data. This endpoint validates "
        "that the configuration is properly formatted."
    ),
    responses={
        200: {
            "description": "Credential check result",
            "content": {
                "application/json": {
                    "example": {
                        "provider": "azure",
                        "status": "valid",
                        "message": "Azure configuration is valid. Note: Pricing API is publicly accessible.",
                        "config_present": True,
                        "credentials_valid": True,
                        "can_fetch_pricing": True,
                        "identity": {
                            "subscription_id": "12345678-1234-1234-1234-123456789abc",
                            "region": "westeurope"
                        },
                        "note": "Azure pricing API is publicly accessible - no authentication required"
                    }
                }
            }
        }
    }
)
def check_azure_from_config():
    """Check Azure credentials from config file."""
    return credentials_checker.check_azure_credentials_from_config()


@router.post(
    "/verify/azure",
    tags=["Permissions - Upload"],
    summary="Verify Azure permissions from request body",
    description=(
        "Validates Azure configuration provided in the request body. "
        "Note: Azure Pricing API is publicly accessible."
    )
)
def check_azure_from_body(request: AzureCredentialsRequest):
    """Check Azure credentials from request body."""
    return credentials_checker.check_azure_credentials(request.dict())
