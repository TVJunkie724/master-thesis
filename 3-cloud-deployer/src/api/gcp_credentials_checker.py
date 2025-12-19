"""
GCP Credentials Permission Checker

Validates if provided GCP Service Account credentials have the required
IAM permissions for the deployer.

This module is shared by both:
- REST API endpoints (api/credentials.py)
- CLI commands (src/main.py)

Authentication Flow:
    1. Read Service Account JSON file
    2. Verify credentials by checking project access
    3. Verify required APIs are enabled
    4. Check IAM permissions for the service account
"""
import json
import os
import sys
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


# ==========================================
# Required GCP APIs by Layer
# ==========================================

REQUIRED_GCP_APIS = {
    "setup": {
        "description": "Project Services, IAM, Cloud Storage",
        "apis": [
            "cloudresourcemanager.googleapis.com",
            "iam.googleapis.com",
            "storage.googleapis.com",
        ],
    },
    "layer_1": {
        "description": "Pub/Sub, Eventarc",
        "apis": [
            "pubsub.googleapis.com",
            "eventarc.googleapis.com",
        ],
    },
    "layer_2": {
        "description": "Cloud Functions, Cloud Run, Cloud Build",
        "apis": [
            "cloudfunctions.googleapis.com",
            "run.googleapis.com",
            "cloudbuild.googleapis.com",
        ],
    },
    "layer_3": {
        "description": "Firestore, Cloud Storage, Cloud Scheduler",
        "apis": [
            "firestore.googleapis.com",
            "storage.googleapis.com",
            "cloudscheduler.googleapis.com",
        ],
    },
}

# Required IAM roles for the service account
REQUIRED_GCP_ROLES = [
    "roles/cloudfunctions.developer",
    "roles/pubsub.editor",
    "roles/datastore.user",
    "roles/storage.objectAdmin",
    "roles/run.invoker",
    "roles/cloudscheduler.admin",
    "roles/iam.serviceAccountUser",
]


def _parse_service_account_json(credentials_path: str) -> dict:
    """
    Parse and validate service account JSON file.
    
    Args:
        credentials_path: Path to the service account JSON file
    
    Returns:
        Dict with parsed service account info
    
    Raises:
        ValueError: If file doesn't exist or is invalid
    """
    path = Path(credentials_path)
    
    if not path.exists():
        raise ValueError(f"Service account file not found: {credentials_path}")
    
    try:
        with open(path) as f:
            sa_info = json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in service account file: {e}")
    
    # Validate required fields
    required_fields = ["type", "project_id", "client_email"]
    missing = [f for f in required_fields if f not in sa_info]
    
    if missing:
        raise ValueError(f"Service account JSON missing required fields: {missing}")
    
    if sa_info["type"] != "service_account":
        raise ValueError(f"Invalid credential type: {sa_info['type']}. Expected 'service_account'.")
    
    return {
        "project_id": sa_info["project_id"],
        "client_email": sa_info["client_email"],
        "private_key_id": sa_info.get("private_key_id", "")[:8] + "...",  # Masked
    }


def _check_project_access(project_id: str) -> dict:
    """
    Check if credentials can access the project.
    
    Args:
        project_id: GCP project ID
    
    Returns:
        Dict with project access status
    """
    try:
        from google.cloud import resourcemanager_v3
        
        client = resourcemanager_v3.ProjectsClient()
        project_name = f"projects/{project_id}"
        
        try:
            project = client.get_project(name=project_name)
            return {
                "status": "accessible",
                "project_id": project.project_id,
                "display_name": project.display_name,
                "state": project.state.name,
            }
        except Exception as e:
            if "403" in str(e):
                return {"status": "access_denied", "error": str(e)}
            elif "404" in str(e):
                return {"status": "not_found", "error": str(e)}
            raise
            
    except ImportError:
        return {"status": "sdk_not_installed", "error": "google-cloud-resourcemanager not installed"}
    except Exception as e:
        return {"status": "error", "error": str(e)}


def _check_enabled_apis(project_id: str) -> dict:
    """
    Check which required APIs are enabled for the project.
    
    Args:
        project_id: GCP project ID
    
    Returns:
        Dict with API status by layer
    """
    try:
        from google.cloud import service_usage_v1
        
        client = service_usage_v1.ServiceUsageClient()
        parent = f"projects/{project_id}"
        
        # Get list of enabled services
        enabled_services = set()
        try:
            request = service_usage_v1.ListServicesRequest(
                parent=parent,
                filter="state:ENABLED",
            )
            for service in client.list_services(request=request):
                # Service name format: projects/{p}/services/{service}
                service_name = service.config.name
                enabled_services.add(service_name)
        except Exception as e:
            return {"status": "check_failed", "error": str(e)}
        
        # Check each layer's requirements
        by_layer = {}
        for layer_name, requirements in REQUIRED_GCP_APIS.items():
            missing_apis = []
            present_apis = []
            
            for api in requirements["apis"]:
                if api in enabled_services:
                    present_apis.append(api)
                else:
                    missing_apis.append(api)
            
            layer_status = "valid" if not missing_apis else ("partial" if present_apis else "invalid")
            
            by_layer[layer_name] = {
                "status": layer_status,
                "description": requirements["description"],
                "present_apis": present_apis,
                "missing_apis": missing_apis,
            }
        
        return {"status": "checked", "by_layer": by_layer}
        
    except ImportError:
        return {"status": "sdk_not_installed", "error": "google-cloud-service-usage not installed"}
    except Exception as e:
        return {"status": "error", "error": str(e)}


def check_gcp_credentials(credentials: dict) -> dict:
    """
    Main entry point. Validates GCP credentials against required permissions.
    
    Args:
        credentials: Dict with gcp_credentials_file, gcp_region, and either
                     gcp_project_id (private) or gcp_billing_account (org)
    
    Returns:
        Dict with status, caller_identity, and permission results
    """
    result = {
        "status": "invalid",
        "message": "",
        "caller_identity": None,
        "project_access": None,
        "api_status": None,
        "required_roles": REQUIRED_GCP_ROLES,
    }
    
    # Validate required fields
    if "gcp_credentials_file" not in credentials:
        result["message"] = "Missing required credential: gcp_credentials_file"
        return result
    
    # Early check: verify credentials file exists
    creds_file_path = Path(credentials["gcp_credentials_file"])
    if not creds_file_path.exists():
        result["message"] = (
            f"GCP credentials file not found: {credentials['gcp_credentials_file']}. "
            f"Please verify the path in config_credentials.json points to a valid service account JSON file."
        )
        return result
    
    if "gcp_region" not in credentials:
        result["message"] = "Missing required credential: gcp_region"
        return result
    
    # Dual-mode validation: either gcp_project_id OR gcp_billing_account required
    has_project_id = credentials.get("gcp_project_id", "").strip()
    has_billing_account = credentials.get("gcp_billing_account", "").strip()
    
    if not has_project_id and not has_billing_account:
        result["message"] = (
            "GCP requires either 'gcp_project_id' (for private accounts with existing project) "
            "or 'gcp_billing_account' (for organization accounts with auto-project creation). "
            "Please provide at least one."
        )
        return result
    
    try:
        # Step 1: Parse and validate service account JSON
        try:
            sa_info = _parse_service_account_json(credentials["gcp_credentials_file"])
            result["caller_identity"] = {
                "project_id": sa_info["project_id"],
                "service_account": sa_info["client_email"],
                "private_key_id": sa_info["private_key_id"],
            }
        except ValueError as e:
            result["message"] = str(e)
            return result
        
        # Use service account's project for permission checks
        project_id = sa_info["project_id"]
        
        # Set GOOGLE_APPLICATION_CREDENTIALS for SDK
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = credentials["gcp_credentials_file"]
        
        # Step 2: Check project access
        project_access = _check_project_access(project_id)
        result["project_access"] = project_access
        
        if project_access["status"] != "accessible":
            if project_access["status"] == "sdk_not_installed":
                result["status"] = "sdk_missing"
                result["message"] = "GCP SDK not installed. Install: pip install google-cloud-resource-manager"
            else:
                result["status"] = "access_denied"
                result["message"] = f"Cannot access project {project_id}: {project_access.get('error', 'Unknown error')}"
            return result
        
        # Step 3: Check enabled APIs
        api_status = _check_enabled_apis(project_id)
        result["api_status"] = api_status
        
        if api_status["status"] == "sdk_not_installed":
            result["status"] = "partial"
            result["message"] = "Credentials valid. API check skipped (google-cloud-service-usage not installed)."
            return result
        
        if api_status["status"] != "checked":
            result["status"] = "partial"
            result["message"] = f"Credentials valid. API check failed: {api_status.get('error', 'Unknown')}"
            return result
        
        # Determine overall status
        all_valid = all(
            layer["status"] == "valid" 
            for layer in api_status.get("by_layer", {}).values()
        )
        
        if all_valid:
            result["status"] = "valid"
            result["message"] = "All required APIs are enabled. Ready for deployment."
        else:
            some_valid = any(
                layer["status"] in ["valid", "partial"]
                for layer in api_status.get("by_layer", {}).values()
            )
            if some_valid:
                result["status"] = "partial"
                result["message"] = "Some required APIs are not enabled. Enable missing APIs in Google Cloud Console."
            else:
                result["status"] = "invalid"
                result["message"] = "Required APIs are not enabled. Enable them in Google Cloud Console."
        
        return result
        
    except Exception as e:
        logger.exception("GCP credential check failed")
        result["status"] = "error"
        result["message"] = f"Unexpected error: {str(e)}"
        return result


def check_gcp_credentials_from_config(project_name: Optional[str] = None) -> dict:
    """
    Validate credentials from the project's config_credentials.json.
    
    Args:
        project_name: Optional project name. Uses active project if not specified.
    
    Returns:
        Same format as check_gcp_credentials()
    """
    try:
        import src.core.state as state
        
        # Determine project path
        if project_name:
            project_dir = os.path.join(state.get_project_upload_path(), project_name)
            if not os.path.exists(project_dir):
                return {
                    "status": "error",
                    "message": f"Invalid project: Project '{project_name}' does not exist.",
                    "caller_identity": None,
                    "project_access": None,
                    "api_status": None,
                    "project_name": project_name
                }
        else:
            project_name = state.get_active_project()
            project_dir = os.path.join(state.get_project_upload_path(), project_name)
        
        # Load credentials from config
        config_path = os.path.join(project_dir, "config_credentials.json")
        if not os.path.exists(config_path):
            return {
                "status": "error",
                "message": "No config_credentials.json found in project.",
                "caller_identity": None,
                "project_access": None,
                "api_status": None,
                "project_name": project_name
            }
        
        try:
            with open(config_path, 'r') as f:
                config_credentials = json.load(f)
        except json.JSONDecodeError:
            return {
                "status": "error",
                "message": "Invalid JSON in config_credentials.json",
                "caller_identity": None,
                "project_access": None,
                "api_status": None,
                "project_name": project_name
            }
        
        gcp_creds = config_credentials.get("gcp", {})
        
        if not gcp_creds:
            return {
                "status": "error",
                "message": "No GCP credentials found in config_credentials.json",
                "caller_identity": None,
                "project_access": None,
                "api_status": None,
                "project_name": project_name
            }
        
        # Resolve gcp_credentials_file relative to project directory if needed
        if "gcp_credentials_file" in gcp_creds:
            creds_path = gcp_creds["gcp_credentials_file"]
            # If not an absolute path, resolve relative to project directory
            if not os.path.isabs(creds_path):
                gcp_creds["gcp_credentials_file"] = os.path.join(project_dir, creds_path)
        
        # Check the credentials
        result = check_gcp_credentials(gcp_creds)
        result["project_name"] = project_name
        return result
        
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to load credentials from config: {str(e)}",
            "caller_identity": None,
            "project_access": None,
            "api_status": None,
            "project_name": project_name
        }


# Export for use by API and CLI
__all__ = [
    "check_gcp_credentials",
    "check_gcp_credentials_from_config",
    "REQUIRED_GCP_APIS",
    "REQUIRED_GCP_ROLES",
]
