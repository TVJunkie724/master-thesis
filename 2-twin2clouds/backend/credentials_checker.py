"""
Credential validation logic for all cloud providers.

This module provides functions to validate cloud provider credentials
for accessing pricing APIs (AWS, GCP, Azure).
"""
import os
from typing import Dict, Any, Optional

from backend.aws_twinmaker_pricing_plan import (
    AwsTwinMakerPricingPlanError,
    build_aws_session,
    observe_aws_twinmaker_pricing_plan,
)
from backend.secret_redaction import credential_strings, redact_secret_like_text

# =============================================================================
# Constants
# =============================================================================

REQUIRED_AWS_PERMISSIONS = [
    "pricing:DescribeServices",
    "pricing:GetProducts",
    "pricing:GetAttributeValues",
    "iottwinmaker:GetPricingPlan",
]

REQUIRED_AWS_CONFIG_FIELDS = [
    "aws_access_key_id",
    "aws_secret_access_key",
    "aws_region",
]

REQUIRED_GCP_CONFIG_FIELDS = [
    "gcp_project_id",
    "gcp_region"
]

REQUIRED_AZURE_CONFIG_FIELDS = [
    "azure_subscription_id",
    "azure_region"
]

# =============================================================================
# AWS Credential Validation
# =============================================================================

def check_aws_credentials(credentials: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Validate AWS credentials.
    
    Steps:
    1. Check config/credentials present
    2. Call STS GetCallerIdentity
    3. Test AWS Pricing API operations used by the fetcher
    
    Args:
        credentials: Dictionary with aws_access_key_id, aws_secret_access_key, optional aws_session_token
        
    Returns:
        Dictionary with validation results
    """
    result = {
        "provider": "aws",
        "status": "error",
        "message": "",
        "config_present": False,
        "credentials_valid": False,
        "can_fetch_pricing": False,
        "identity": None,
        "required_permissions": REQUIRED_AWS_PERMISSIONS
    }
    
    # Step 1: Check credentials provided
    if credentials is None:
        result["status"] = "missing"
        result["message"] = "No AWS credentials provided"
        return result
    
    # Check required fields
    missing_fields = [f for f in REQUIRED_AWS_CONFIG_FIELDS if not credentials.get(f)]
    if missing_fields:
        result["status"] = "invalid"
        result["message"] = f"Missing required fields: {', '.join(missing_fields)}"
        return result
    
    result["config_present"] = True
    
    # Step 2: Verify account identity and regional TwinMaker pricing-plan access.
    try:
        session = build_aws_session(credentials, credentials["aws_region"])
        context = observe_aws_twinmaker_pricing_plan(
            credentials,
            credentials["aws_region"],
            configured_account_id=credentials.get("aws_configured_account_id"),
            session=session,
        )
        result["credentials_valid"] = True
        result["identity"] = {
            "account": context["verified_account_id"],
        }
        result["twinmaker_pricing_plan"] = context
    except AwsTwinMakerPricingPlanError as exc:
        result["status"] = "invalid"
        result["message"] = exc.public_message
        result["error_code"] = exc.code
        result["credentials_valid"] = exc.identity_verified
        return result
    except Exception as e:
        result["status"] = "error"
        result["message"] = (
            "Error validating AWS credentials: "
            f"{redact_secret_like_text(e, extra_secrets=credential_strings(credentials))}"
        )
        return result
    
    # Step 3: Test Pricing API access
    try:
        from botocore.exceptions import ClientError

        # Pricing API is only available in us-east-1
        pricing_client = session.client("pricing", region_name="us-east-1")
        
        # Exercise the same Pricing API operations used by the fetcher path.
        pricing_client.describe_services(MaxResults=1)
        pricing_client.get_attribute_values(
            ServiceCode="AmazonEC2",
            AttributeName="location",
            MaxResults=1,
        )
        pricing_client.get_products(ServiceCode="AmazonEC2", MaxResults=1)
        
        result["can_fetch_pricing"] = True
        result["status"] = "valid"
        result["message"] = (
            "AWS credentials can read the Price List API and the regional "
            "TwinMaker pricing plan."
        )
        
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        if error_code == "AccessDeniedException":
            result["status"] = "invalid"
            operation = getattr(e, "operation_name", "Pricing API")
            result["message"] = (
                f"AWS credentials valid but lack Pricing API permission for {operation}. "
                "Required: pricing:DescribeServices, pricing:GetProducts, "
                "pricing:GetAttributeValues"
            )
        else:
            result["status"] = "error"
            result["message"] = f"Error accessing Pricing API: {error_code}"
    except Exception as e:
        result["status"] = "error"
        result["message"] = (
            "Error testing Pricing API access: "
            f"{redact_secret_like_text(e, extra_secrets=credential_strings(credentials))}"
        )
    
    return result


def check_aws_credentials_from_config() -> Dict[str, Any]:
    """
    Load AWS credentials from config and validate.
    
    Returns:
        Dictionary with validation results
    """
    try:
        from backend import config_loader
        credentials = (config_loader.load_credentials_file() or {}).get("aws")
        return check_aws_credentials(credentials)
    except Exception as e:
        return {
            "provider": "aws",
            "status": "error",
            "message": (
                "Error loading AWS credentials from config: "
                f"{redact_secret_like_text(e)}"
            ),
            "config_present": False,
            "credentials_valid": False,
            "can_fetch_pricing": False,
            "identity": None,
            "required_permissions": REQUIRED_AWS_PERMISSIONS
        }


# =============================================================================
# GCP Credential Validation
# =============================================================================

def check_gcp_credentials(credentials_input: Optional[str] = None) -> Dict[str, Any]:
    """
    Validate GCP credentials.
    
    Steps:
    1. Load credentials from file path OR JSON content (using shared utility)
    2. Create CloudCatalogClient and test list_services()
    
    Args:
        credentials_input: Either a file path to GCP service account JSON 
                          OR the raw JSON content string (detected automatically)
        
    Returns:
        Dictionary with validation results
    """
    from backend.gcp_utils import parse_gcp_service_account
    
    result = {
        "provider": "gcp",
        "status": "error",
        "message": "",
        "config_present": False,
        "credentials_valid": False,
        "can_fetch_pricing": False,
        "identity": None
    }
    
    # Step 1: Check credentials provided
    if credentials_input is None:
        result["status"] = "missing"
        result["message"] = "No GCP credentials provided"
        return result
    
    result["config_present"] = True
    
    # Step 2: Parse and validate credentials using shared utility
    try:
        from google.cloud import billing_v1
        
        sa_info, display_info, credentials = parse_gcp_service_account(credentials_input)
        
        result["credentials_valid"] = True
        result["identity"] = {
            "project_id": display_info["project_id"],
            "service_account_email": display_info["client_email"]
        }
        
    except ValueError as e:
        result["status"] = "invalid"
        result["message"] = redact_secret_like_text(
            e,
            extra_secrets=(credentials_input,),
        )
        return result
    except Exception as e:
        result["status"] = "invalid"
        result["message"] = (
            "Error loading GCP credentials: "
            f"{redact_secret_like_text(e, extra_secrets=(credentials_input,))}"
        )
        return result

    
    # Step 3: Test Cloud Billing Catalog API access
    try:
        client = billing_v1.CloudCatalogClient(credentials=credentials)
        
        # List first service to verify access
        request = billing_v1.ListServicesRequest()
        services = client.list_services(request=request)
        
        # Get first service to confirm we can read
        first_service = next(iter(services), None)
        if first_service:
            result["can_fetch_pricing"] = True
            result["status"] = "valid"
            result["message"] = "GCP credentials are valid and can access Cloud Billing Catalog API"
        else:
            result["status"] = "error"
            result["message"] = "GCP credentials valid but no services returned from Billing API"
            
    except Exception as e:
        result["status"] = "error"
        result["message"] = (
            "Error accessing Cloud Billing Catalog API: "
            f"{redact_secret_like_text(e, extra_secrets=(credentials_input,))}"
        )
    
    return result



def check_gcp_credentials_from_config() -> Dict[str, Any]:
    """
    Load GCP credentials from config and validate.
    
    Returns:
        Dictionary with validation results
    """
    try:
        import backend.constants as CONSTANTS
        
        # GCP credentials file is mounted at a specific path in Docker
        credentials_file = CONSTANTS.GCP_CREDENTIALS_FILE_PATH
        
        if not os.path.isfile(credentials_file):
            return {
                "provider": "gcp",
                "status": "missing",
                "message": f"GCP credentials file not found at: {credentials_file}",
                "config_present": False,
                "credentials_valid": False,
                "can_fetch_pricing": False,
                "identity": None
            }
        
        return check_gcp_credentials(credentials_file)
        
    except Exception as e:
        return {
            "provider": "gcp",
            "status": "error",
            "message": (
                "Error loading GCP credentials from config: "
                f"{redact_secret_like_text(e)}"
            ),
            "config_present": False,
            "credentials_valid": False,
            "can_fetch_pricing": False,
            "identity": None
        }


# =============================================================================
# Azure Credential Validation
# =============================================================================

def check_azure_credentials(credentials: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Validate Azure credentials.
    
    Steps:
    1. Check config fields present
    2. Validate credential format
    3. Note: Pricing API is public, but credentials validated for completeness
    
    Args:
        credentials: Dictionary with azure_subscription_id, azure_region, etc.
        
    Returns:
        Dictionary with validation results
    """
    result = {
        "provider": "azure",
        "status": "error",
        "message": "",
        "config_present": False,
        "credentials_valid": False,
        "can_fetch_pricing": True,  # Azure pricing API is public
        "identity": None,
        "note": "Azure pricing API (prices.azure.com) is publicly accessible - no authentication required for pricing data"
    }
    
    # Step 1: Check credentials provided
    if credentials is None:
        result["status"] = "missing"
        result["message"] = "No Azure credentials provided"
        result["can_fetch_pricing"] = True  # Still true - public API
        return result
    
    # Check required fields
    missing_fields = [f for f in REQUIRED_AZURE_CONFIG_FIELDS if not credentials.get(f)]
    if missing_fields:
        result["status"] = "invalid"
        result["message"] = f"Missing required fields: {', '.join(missing_fields)}. Note: Azure credentials are not required for pricing API (public)"
        result["can_fetch_pricing"] = True  # Still true - public API
        return result
    
    result["config_present"] = True
    
    # Step 2: Validate format of subscription ID (basic validation)
    subscription_id = credentials.get("azure_subscription_id", "")
    
    # Azure subscription IDs are UUIDs
    import re
    uuid_pattern = r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$'
    
    if subscription_id and not re.match(uuid_pattern, subscription_id):
        result["status"] = "invalid"
        result["message"] = "Azure subscription_id format is invalid (expected UUID format)"
        result["credentials_valid"] = False
        return result
    
    result["credentials_valid"] = True
    result["identity"] = {
        "subscription_id": subscription_id,
        "region": credentials.get("azure_region")
    }
    result["status"] = "valid"
    result["message"] = "Azure configuration is valid. Note: Pricing API is publicly accessible."
    
    return result


def check_azure_credentials_from_config() -> Dict[str, Any]:
    """
    Load Azure credentials from config and validate.
    
    Returns:
        Dictionary with validation results
    """
    try:
        from backend import config_loader
        credentials = config_loader.load_azure_credentials()
        return check_azure_credentials(credentials)
    except Exception as e:
        return {
            "provider": "azure",
            "status": "error",
            "message": (
                "Error loading Azure credentials from config: "
                f"{redact_secret_like_text(e)}"
            ),
            "config_present": False,
            "credentials_valid": False,
            "can_fetch_pricing": True,  # Still true - public API
            "identity": None,
            "note": "Azure pricing API is publicly accessible - no authentication required"
        }
