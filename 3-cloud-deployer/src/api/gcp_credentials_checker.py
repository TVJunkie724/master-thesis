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
        "description": "Cloud Functions, Cloud Run, Cloud Build, Workflows",
        "apis": [
            "cloudfunctions.googleapis.com",
            "run.googleapis.com",
            "cloudbuild.googleapis.com",
            "workflows.googleapis.com",
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

REQUIRED_GCP_PERMISSIONS = {
    "setup": {
        "description": "Project access, IAM, service accounts, API enablement, source bucket",
        "permissions": [
            "resourcemanager.projects.get",
            "resourcemanager.projects.getIamPolicy",
            "resourcemanager.projects.setIamPolicy",
            "iam.serviceAccounts.create",
            "iam.serviceAccounts.delete",
            "iam.serviceAccounts.get",
            "iam.serviceAccounts.list",
            "iam.serviceAccounts.actAs",
            "iam.serviceAccountKeys.create",
            "iam.serviceAccountKeys.delete",
            "iam.roles.create",
            "iam.roles.delete",
            "iam.roles.get",
            "iam.roles.list",
            "iam.roles.update",
            "serviceusage.services.enable",
            "serviceusage.services.disable",
            "serviceusage.services.get",
            "serviceusage.services.list",
            "storage.buckets.create",
            "storage.buckets.delete",
            "storage.buckets.get",
            "storage.buckets.list",
            "storage.buckets.update",
            "storage.objects.create",
            "storage.objects.delete",
            "storage.objects.get",
            "storage.objects.list",
            "storage.objects.update",
        ],
    },
    "layer_1": {
        "description": "Pub/Sub and Eventarc triggers",
        "permissions": [
            "pubsub.topics.create",
            "pubsub.topics.delete",
            "pubsub.topics.get",
            "pubsub.topics.getIamPolicy",
            "pubsub.topics.list",
            "pubsub.topics.publish",
            "pubsub.topics.setIamPolicy",
            "pubsub.subscriptions.create",
            "pubsub.subscriptions.delete",
            "pubsub.subscriptions.get",
            "pubsub.subscriptions.list",
            "eventarc.triggers.create",
            "eventarc.triggers.delete",
            "eventarc.triggers.get",
            "eventarc.triggers.list",
            "eventarc.triggers.update",
        ],
    },
    "layer_2": {
        "description": "Cloud Functions Gen2, Cloud Run invoker bindings, Cloud Build, Workflows",
        "permissions": [
            "cloudfunctions.functions.create",
            "cloudfunctions.functions.delete",
            "cloudfunctions.functions.get",
            "cloudfunctions.functions.list",
            "cloudfunctions.functions.update",
            "cloudfunctions.functions.sourceCodeSet",
            "cloudfunctions.operations.get",
            "cloudfunctions.operations.list",
            "run.services.create",
            "run.services.delete",
            "run.services.get",
            "run.services.list",
            "run.services.update",
            "run.services.setIamPolicy",
            "run.services.getIamPolicy",
            "run.operations.get",
            "run.operations.list",
            "cloudbuild.builds.create",
            "cloudbuild.builds.get",
            "cloudbuild.builds.list",
            "workflows.workflows.create",
            "workflows.workflows.delete",
            "workflows.workflows.get",
            "workflows.workflows.list",
            "workflows.workflows.update",
            "workflows.operations.get",
            "workflows.operations.list",
        ],
    },
    "layer_3": {
        "description": "Firestore, storage buckets/objects, Cloud Scheduler",
        "permissions": [
            "datastore.databases.create",
            "datastore.databases.delete",
            "datastore.databases.get",
            "datastore.databases.list",
            "datastore.entities.create",
            "datastore.entities.delete",
            "datastore.entities.get",
            "datastore.entities.list",
            "datastore.entities.update",
            "datastore.indexes.create",
            "datastore.indexes.delete",
            "datastore.indexes.get",
            "datastore.indexes.list",
            "cloudscheduler.jobs.create",
            "cloudscheduler.jobs.delete",
            "cloudscheduler.jobs.get",
            "cloudscheduler.jobs.list",
            "cloudscheduler.jobs.update",
        ],
    },
}


GCP_RESOURCE_SCOPED_PERMISSION_PREFIXES = (
    "storage.objects.",
)
GCP_RESOURCE_SCOPED_PERMISSIONS = {
    "pubsub.topics.getIamPolicy",
    "pubsub.topics.setIamPolicy",
    "storage.buckets.delete",
    "storage.buckets.get",
    "storage.buckets.update",
}


def _parse_service_account_json(credentials_input: str) -> tuple:
    """
    Parse and validate service account JSON from file path OR raw JSON content.
    
    This is a thin wrapper around the shared parse_gcp_service_account() utility.
    Maintains the same interface for backward compatibility with existing callers.
    
    Args:
        credentials_input: Either a file path to the service account JSON file
                          OR the raw JSON content string (detected automatically)
    
    Returns:
        Tuple of (display_info, sa_info, credentials) where:
        - display_info: Dict with project_id, client_email, and masked private_key_id
        - sa_info: The complete SA info dict
        - credentials: google.oauth2.service_account.Credentials for SDK clients
    
    Raises:
        ValueError: If input is invalid or missing required fields
    """
    from src.utils.gcp_utils import parse_gcp_service_account
    
    # Shared utility returns (sa_info, display_info, credentials)
    # We reorder to (display_info, sa_info, credentials) for backward compatibility
    sa_info, display_info, credentials = parse_gcp_service_account(credentials_input)
    return display_info, sa_info, credentials



def _check_project_access(project_id: str, credentials=None) -> dict:
    """
    Check if credentials can access the project.
    
    Args:
        project_id: GCP project ID
        credentials: Optional google.oauth2 credentials object. If None, uses default.
    
    Returns:
        Dict with project access status
    """
    try:
        from google.cloud import resourcemanager_v3
        
        client = resourcemanager_v3.ProjectsClient(credentials=credentials)
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
            error_str = str(e)
            if "403" in error_str:
                return {
                    "status": "access_denied", 
                    "error": (
                        "Access denied to GCP project. This can happen if:\n"
                        "  • Service account key has been disabled in IAM\n"
                        "  • Service account has been deleted\n"
                        "  • Service account lacks permission to access this project\n"
                        "  • Project ID is incorrect\n"
                        "Check: Google Cloud Console → IAM & Admin → Service Accounts"
                    )
                }
            elif "404" in error_str:
                return {
                    "status": "not_found", 
                    "error": (
                        f"GCP project '{project_id}' not found. This can happen if:\n"
                        "  • Project ID is incorrect (check for typos)\n"
                        "  • Project has been deleted\n"
                        "  • Service account belongs to a different project\n"
                        "Verify your project ID in Google Cloud Console."
                    )
                }
            raise
            
    except ImportError:
        return {"status": "sdk_not_installed", "error": "google-cloud-resourcemanager not installed"}
    except Exception as e:
        return {"status": "error", "error": str(e)}



def _validate_gcp_region(project_id: str, region: str, credentials=None) -> dict:
    """
    Validate GCP region exists for the project.
    
    Args:
        project_id: GCP project ID
        region: Region to validate (e.g., 'europe-west1')
        credentials: Optional google.oauth2 credentials object. If None, uses default.
    
    Returns:
        Dict with 'valid' bool and either 'region' or 'error'
    """
    try:
        from google.cloud import compute_v1
        
        client = compute_v1.RegionsClient(credentials=credentials)
        regions = list(client.list(project=project_id))
        valid_region_names = {r.name for r in regions}
        
        if region in valid_region_names:
            return {"valid": True, "region": region}
        
        sample_regions = sorted(list(valid_region_names))[:10]
        return {
            "valid": False,
            "error": f"Region '{region}' is not valid. Available regions: {', '.join(sample_regions)}..."
        }
        
    except ImportError:
        # SDK not installed - skip validation but warn
        return {
            "valid": True,
            "skipped": True,
            "warning": "google-cloud-compute not installed, region validation skipped"
        }
    except Exception as e:
        return {"valid": False, "error": f"Failed to validate region: {str(e)}"}  



def _check_enabled_apis(project_id: str, credentials=None) -> dict:
    """
    Check which required APIs are enabled for the project.
    
    Args:
        project_id: GCP project ID
        credentials: Optional google.oauth2 credentials object. If None, uses default.
    
    Returns:
        Dict with API status by layer
    """
    try:
        from google.cloud import service_usage_v1
        
        client = service_usage_v1.ServiceUsageClient(credentials=credentials)
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


def _get_all_required_gcp_permissions() -> set[str]:
    """Flatten the versioned GCP permission contract into one set."""
    return {
        permission
        for group in REQUIRED_GCP_PERMISSIONS.values()
        for permission in group["permissions"]
    }


def _is_resource_scoped_gcp_permission(permission: str) -> bool:
    """Return true for permissions that cannot be checked reliably on a project."""
    return (
        permission in GCP_RESOURCE_SCOPED_PERMISSIONS
        or any(permission.startswith(prefix) for prefix in GCP_RESOURCE_SCOPED_PERMISSION_PREFIXES)
    )


def _get_project_testable_gcp_permissions() -> set[str]:
    """Return required permissions that are safe to test against projects/{id}."""
    return {
        permission
        for permission in _get_all_required_gcp_permissions()
        if not _is_resource_scoped_gcp_permission(permission)
    }


def _get_resource_scoped_gcp_permissions() -> set[str]:
    """Return required permissions deferred to resource/provider validation."""
    return {
        permission
        for permission in _get_all_required_gcp_permissions()
        if _is_resource_scoped_gcp_permission(permission)
    }


def _compare_gcp_permissions(granted_permissions: set[str], required_by_layer: dict | None = None) -> dict:
    """Compare granted permissions from testIamPermissions with the contract."""
    permission_contract = required_by_layer or REQUIRED_GCP_PERMISSIONS
    by_layer = {}
    total_required = 0
    total_valid = 0
    total_missing = 0

    for layer_name, requirements in permission_contract.items():
        required = set(requirements["permissions"])
        valid = sorted(required & granted_permissions)
        missing = sorted(required - granted_permissions)

        total_required += len(required)
        total_valid += len(valid)
        total_missing += len(missing)

        by_layer[layer_name] = {
            "status": "valid" if not missing else ("partial" if valid else "invalid"),
            "description": requirements["description"],
            "valid": valid,
            "missing": missing,
        }

    return {
        "by_layer": by_layer,
        "summary": {
            "total_required": total_required,
            "valid": total_valid,
            "missing": total_missing,
        },
    }


def _filter_gcp_permission_contract(permissions_to_include: set[str]) -> dict:
    """Return the permission contract with only selected permissions per layer."""
    filtered = {}
    for layer_name, requirements in REQUIRED_GCP_PERMISSIONS.items():
        permissions = [
            permission
            for permission in requirements["permissions"]
            if permission in permissions_to_include
        ]
        if permissions:
            filtered[layer_name] = {
                "description": requirements["description"],
                "permissions": permissions,
            }
    return filtered


def _check_iam_permissions(project_id: str, credentials=None) -> dict:
    """
    Check granted GCP IAM permissions against the explicit deployment contract.

    Uses Cloud Resource Manager testIamPermissions on the project resource for
    project-level permissions. Future resource-scoped permissions are reported
    separately because checking them on projects/{id} can produce false negatives.
    """
    try:
        from google.cloud import resourcemanager_v3

        client = resourcemanager_v3.ProjectsClient(credentials=credentials)
        project_testable_permissions = sorted(_get_project_testable_gcp_permissions())
        deferred_permissions = sorted(_get_resource_scoped_gcp_permissions())
        response = client.test_iam_permissions(
            resource=f"projects/{project_id}",
            permissions=project_testable_permissions,
        )
        granted_permissions = set(response.permissions)
        comparison = _compare_gcp_permissions(
            granted_permissions,
            _filter_gcp_permission_contract(set(project_testable_permissions)),
        )

        return {
            "status": "checked",
            "resource": f"projects/{project_id}",
            "granted_permissions": sorted(granted_permissions),
            "required_permissions": project_testable_permissions,
            "deferred_permissions": deferred_permissions,
            "deferred_reason": (
                "These permissions are resource-scoped and are not hard-failed by "
                "project-level testIamPermissions before deployment resources exist."
            ),
            **comparison,
        }
    except ImportError:
        return {
            "status": "sdk_not_installed",
            "error": "google-cloud-resourcemanager not installed",
        }
    except Exception as e:
        return {"status": "check_failed", "error": str(e)}



def _check_billing_enabled(project_id: str, credentials=None) -> dict:
    """
    Check if billing is enabled for the GCP project.
    
    A project without billing cannot deploy any paid resources.
    This catches billing issues early before Terraform fails.
    
    Args:
        project_id: GCP project ID
        credentials: Optional google.oauth2 credentials object. If None, uses default.
    
    Returns:
        Dict with billing_enabled status
    """
    try:
        from google.cloud import billing_v1
        
        client = billing_v1.CloudBillingClient(credentials=credentials)
        name = f"projects/{project_id}"
        
        try:
            billing_info = client.get_project_billing_info(name=name)
            return {
                "status": "checked",
                "billing_enabled": billing_info.billing_enabled,
                "billing_account": billing_info.billing_account_name if billing_info.billing_enabled else None,
            }
        except Exception as e:
            if "403" in str(e):
                # Permission denied - can't check billing, skip gracefully
                return {
                    "status": "skipped",
                    "reason": "Permission denied to check billing info",
                    "billing_enabled": None,  # Unknown
                }
            raise
            
    except ImportError:
        return {
            "status": "skipped",
            "reason": "google-cloud-billing not installed",
            "billing_enabled": None,  # Unknown
        }
    except Exception as e:
        return {"status": "error", "error": str(e), "billing_enabled": None}


def _resolve_gcp_validation_project_id(credentials: dict, service_account_project_id: str) -> tuple[str, str]:
    """Resolve the project that credential preflight can safely validate."""
    explicit_project_id = credentials.get("gcp_project_id", "")
    if isinstance(explicit_project_id, str) and explicit_project_id.strip():
        return explicit_project_id.strip(), "existing_project"
    return service_account_project_id, "bootstrap_service_account_project"



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
        "region_validation": None,
        "project_access": None,
        "api_status": None,
        "permission_status": None,
        "validation_project": None,
        "required_roles": REQUIRED_GCP_ROLES,
        "required_permissions": REQUIRED_GCP_PERMISSIONS,
    }
    
    # Validate required fields
    if "gcp_credentials_file" not in credentials:
        result["message"] = "Missing required credential: gcp_credentials_file"
        return result
    
    # Note: Early file existence check removed - _parse_service_account_json handles both file paths AND JSON content
    
    if "gcp_region" not in credentials:
        result["message"] = "Missing required credential: gcp_region"
        return result
    
    # Dual-mode validation: either gcp_project_id OR gcp_billing_account required
    has_project_id = credentials.get("gcp_project_id", "").strip() if credentials.get("gcp_project_id") else ""
    has_billing_account = credentials.get("gcp_billing_account", "").strip() if credentials.get("gcp_billing_account") else ""
    
    if not has_project_id and not has_billing_account:
        result["message"] = (
            "GCP requires either 'gcp_project_id' (for private accounts with existing project) "
            "or 'gcp_billing_account' (for organization accounts with auto-project creation). "
            "Please provide at least one."
        )
        return result
    
    try:
        # Step 1: Parse and validate service account JSON (handles both file path and JSON content)
        # Returns credentials object for thread-safe SDK usage
        try:
            sa_info, full_sa_info, gcp_credentials = _parse_service_account_json(credentials["gcp_credentials_file"])
            result["caller_identity"] = {
                "project_id": sa_info["project_id"],
                "service_account": sa_info["client_email"],
                "private_key_id": sa_info["private_key_id"],
            }
        except ValueError as e:
            result["message"] = str(e)
            return result
        
        # Use the explicit deployment target in private account mode. In
        # organization/bootstrap mode, the final project may not exist yet, so the
        # service account project is used only as a bootstrap validation target.
        project_id, validation_mode = _resolve_gcp_validation_project_id(
            credentials,
            service_account_project_id=sa_info["project_id"],
        )
        result["validation_project"] = {
            "project_id": project_id,
            "mode": validation_mode,
            "service_account_project_id": sa_info["project_id"],
        }
        
        # NOTE: We pass explicit credentials to all SDK clients instead of using
        # GOOGLE_APPLICATION_CREDENTIALS environment variable. This is:
        # - Thread-safe (no race conditions with concurrent requests)
        # - Production-ready (no temp files, no global state mutations)
        
        # Step 2: Check project access
        project_access = _check_project_access(project_id, credentials=gcp_credentials)
        result["project_access"] = project_access
        
        if project_access["status"] != "accessible":
            if project_access["status"] == "sdk_not_installed":
                result["status"] = "sdk_missing"
                result["message"] = "GCP SDK not installed. Install: pip install google-cloud-resource-manager"
            else:
                result["status"] = "access_denied"
                result["message"] = f"Cannot access project {project_id}: {project_access.get('error', 'Unknown error')}"
            return result
        
        # Step 2.5: FAIL-FAST - Check project state (catches deleted/pending deletion projects)
        project_state = project_access.get("state")
        if project_state and project_state not in ["ACTIVE", None]:
            result["status"] = "invalid"
            result["message"] = (
                f"GCP project is '{project_state}'. "
                f"Project must be 'ACTIVE' for deployment. "
                f"Check Google Cloud Console for project status or create a new project."
            )
            return result
        
        # Step 2.6: Check billing is enabled
        billing_status = _check_billing_enabled(project_id, credentials=gcp_credentials)
        result["billing_status"] = billing_status
        
        if billing_status.get("status") == "checked" and not billing_status.get("billing_enabled"):
            result["status"] = "invalid"
            result["message"] = (
                f"GCP project '{project_id}' does not have billing enabled. "
                f"Enable billing in Google Cloud Console to deploy resources."
            )
            return result
        
        # Step 3: Validate region
        region = credentials.get("gcp_region", "")
        if region:
            region_result = _validate_gcp_region(project_id, region, credentials=gcp_credentials)
            result["region_validation"] = {"gcp_region": region_result}
            
            if not region_result.get("valid") and not region_result.get("skipped"):
                result["status"] = "invalid"
                result["message"] = region_result.get("error", f"Invalid region: {region}")
                return result
        
        # Step 4: Check enabled APIs
        api_status = _check_enabled_apis(project_id, credentials=gcp_credentials)
        result["api_status"] = api_status
        
        if api_status["status"] == "sdk_not_installed":
            result["status"] = "partial"
            result["message"] = "Credentials valid. API check skipped (google-cloud-service-usage not installed)."
            return result
        
        if api_status["status"] != "checked":
            result["status"] = "partial"
            result["message"] = f"Credentials valid. API check failed: {api_status.get('error', 'Unknown')}"
            return result

        # Step 5: Check effective IAM permissions without mutating cloud resources
        permission_status = _check_iam_permissions(project_id, credentials=gcp_credentials)
        result["permission_status"] = permission_status

        if permission_status["status"] != "checked":
            result["status"] = "partial"
            result["message"] = (
                "Credentials valid. Permission check failed: "
                f"{permission_status.get('error', 'Unknown')}"
            )
            return result

        missing_permissions = permission_status.get("summary", {}).get("missing", 0)
        if missing_permissions:
            result["status"] = "partial"
            result["message"] = (
                f"Some required GCP permissions are missing: "
                f"{missing_permissions} of {permission_status['summary']['total_required']}."
            )
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
        project_name: Project name to read. Required; no global active project fallback.
    
    Returns:
        Same format as check_gcp_credentials()
    """
    try:
        from src.core.project_storage import get_project_storage

        if not project_name:
            return {
                "status": "error",
                "message": "Project name is required for request-scoped credential checks.",
                "caller_identity": None,
                "project_access": None,
                "api_status": None,
                "required_roles": REQUIRED_GCP_ROLES,
                "required_permissions": REQUIRED_GCP_PERMISSIONS,
                "project_name": None,
            }

        storage = get_project_storage()
        
        # Determine project path
        project_dir = storage.context(project_name).project_path
        if not project_dir.exists():
            return {
                "status": "error",
                "message": f"Invalid project: Project '{project_name}' does not exist.",
                "caller_identity": None,
                "project_access": None,
                "api_status": None,
                "required_roles": REQUIRED_GCP_ROLES,
                "required_permissions": REQUIRED_GCP_PERMISSIONS,
                "project_name": project_name
            }
        
        # Load credentials from config
        config_path = project_dir / "config_credentials.json"
        if not os.path.exists(config_path):
            return {
                "status": "error",
                "message": "No config_credentials.json found in project.",
                "caller_identity": None,
                "project_access": None,
                "api_status": None,
                "required_roles": REQUIRED_GCP_ROLES,
                "required_permissions": REQUIRED_GCP_PERMISSIONS,
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
                "required_roles": REQUIRED_GCP_ROLES,
                "required_permissions": REQUIRED_GCP_PERMISSIONS,
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
                "required_roles": REQUIRED_GCP_ROLES,
                "required_permissions": REQUIRED_GCP_PERMISSIONS,
                "project_name": project_name
            }
        
        # Resolve gcp_credentials_file relative to project directory if needed
        if "gcp_credentials_file" in gcp_creds:
            creds_path = gcp_creds["gcp_credentials_file"]
            # If not an absolute path, resolve relative to project directory
            if not os.path.isabs(creds_path):
                gcp_creds["gcp_credentials_file"] = str(project_dir / creds_path)
        
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
            "required_roles": REQUIRED_GCP_ROLES,
            "required_permissions": REQUIRED_GCP_PERMISSIONS,
            "project_name": project_name
        }


# Export for use by API and CLI
__all__ = [
    "check_gcp_credentials",
    "check_gcp_credentials_from_config",
    "REQUIRED_GCP_APIS",
    "REQUIRED_GCP_ROLES",
    "REQUIRED_GCP_PERMISSIONS",
    "_check_iam_permissions",
    "_compare_gcp_permissions",
    "_get_all_required_gcp_permissions",
]
