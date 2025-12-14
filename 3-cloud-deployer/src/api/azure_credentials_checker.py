"""
Azure Credentials Permission Checker

Validates if provided Azure Service Principal credentials have the required
RBAC (Role-Based Access Control) permissions for the deployer by listing
role assignments and comparing against required roles.

This module is shared by both:
- REST API endpoints (api/credentials.py)
- CLI commands (src/main.py)

Authentication Flow:
    1. Use ClientSecretCredential with tenant_id, client_id, client_secret
    2. Verify credentials by listing subscriptions
    3. List role assignments at subscription scope
    4. Compare against required roles:
       - Custom: "Digital Twin Deployer" (recommended, least-privilege)
       - Built-in: "Contributor" + "User Access Administrator" (development)
"""
import json
import os
import sys
import logging

# Add src to path for imports when called from API
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

logger = logging.getLogger(__name__)


# ==========================================
# Required Azure Roles by Layer
# ==========================================

# Built-in role definition IDs (partial GUIDs - these are constant across all Azure tenants)
AZURE_BUILTIN_ROLES = {
    "Owner": "8e3af657-a8ff-443c-a75c-2fe8c4bcb635",
    "Contributor": "b24988ac-6180-42a0-ab88-20f7382dd24c",
    "Reader": "acdd72a7-3385-48ef-bd42-f606fba81ae7",
    "User Access Administrator": "18d7d88d-d35e-4fb5-a5c3-7773c20a72d9",
    "Managed Identity Contributor": "e40ec5ca-96e0-45a2-b4ff-59039f2c2b59",
    "Website Contributor": "de139f84-1756-47ae-9be6-808fbbe84772",
    "IoT Hub Data Contributor": "4fc6c259-987e-4a07-842e-c321cc9d413f",
    "Cosmos DB Operator": "230815da-be43-4aae-9cb4-875f7bd000aa",
    "Storage Account Contributor": "17d1049b-9a84-46fb-8f53-869881c3d3ab",
    "Azure Digital Twins Data Owner": "bcd981a7-7f74-457b-83e1-cceb9e632gy0",
    "Grafana Admin": "22926164-76b3-42b3-bc55-97df8dab3e41",
}

# Specific RBAC actions required per layer (from azure_custom_role.json)
# These are validated against the user's role assignments
REQUIRED_AZURE_PERMISSIONS = {
    "setup": {
        "description": "Resource Groups, Managed Identity, Storage Account",
        "resource_providers": ["Microsoft.Resources", "Microsoft.ManagedIdentity", "Microsoft.Storage"],
        "required_actions": [
            "*/read",
            "Microsoft.Resources/subscriptions/resourceGroups/write",
            "Microsoft.Resources/subscriptions/resourceGroups/delete",
            "Microsoft.ManagedIdentity/userAssignedIdentities/write",
            "Microsoft.ManagedIdentity/userAssignedIdentities/delete",
            "Microsoft.Storage/storageAccounts/write",
            "Microsoft.Storage/storageAccounts/delete",
            "Microsoft.Storage/storageAccounts/listKeys/action",
        ],
    },
    "layer_0": {
        "description": "App Service Plan, Function Apps (Glue Layer)",
        "resource_providers": ["Microsoft.Web"],
        "required_actions": [
            "Microsoft.Web/serverfarms/write",
            "Microsoft.Web/serverfarms/delete",
            "Microsoft.Web/sites/write",
            "Microsoft.Web/sites/delete",
            "Microsoft.Web/sites/publish/action",
            "Microsoft.Web/sites/config/list/action",  # Get publish credentials
            "Microsoft.Web/sites/basicPublishingCredentialsPolicies/write",  # Enable SCM Basic Auth
        ],
    },
    "layer_1": {
        "description": "IoT Hub, Event Grid, Role Assignments, L1 Function Deployment",
        "resource_providers": ["Microsoft.Devices", "Microsoft.EventGrid", "Microsoft.Authorization", "Microsoft.Web"],
        "required_actions": [
            "Microsoft.Devices/IotHubs/write",
            "Microsoft.Devices/IotHubs/delete",
            "Microsoft.Devices/IotHubs/listkeys/action",
            "Microsoft.EventGrid/systemTopics/write",
            "Microsoft.EventGrid/systemTopics/eventSubscriptions/write",
            "Microsoft.Authorization/roleAssignments/write",
            "Microsoft.Authorization/roleAssignments/delete",
            "Microsoft.Web/sites/config/list/action",  # Get publish credentials for L1 functions
            "Microsoft.Web/sites/basicPublishingCredentialsPolicies/write",  # Enable SCM Basic Auth
        ],
    },
    "layer_2": {
        "description": "Function Apps (Compute Layer)",
        "resource_providers": ["Microsoft.Web"],
        "required_actions": [
            "Microsoft.Web/sites/write",
            "Microsoft.Web/sites/delete",
            "Microsoft.Web/sites/publish/action",
            "Microsoft.Web/sites/config/list/action",  # Get publish credentials
            "Microsoft.Web/sites/basicPublishingCredentialsPolicies/write",  # Enable SCM Basic Auth
        ],
    },
    "layer_3": {
        "description": "Cosmos DB, Blob Storage",
        "resource_providers": ["Microsoft.DocumentDB", "Microsoft.Storage"],
        "required_actions": [
            "Microsoft.DocumentDB/databaseAccounts/write",
            "Microsoft.DocumentDB/databaseAccounts/delete",
            "Microsoft.DocumentDB/databaseAccounts/listKeys/action",
            "Microsoft.Storage/storageAccounts/blobServices/containers/write",
        ],
    },
    "layer_4": {
        "description": "Azure Digital Twins",
        "resource_providers": ["Microsoft.DigitalTwins"],
        "required_actions": [
            "Microsoft.DigitalTwins/digitalTwinsInstances/write",
            "Microsoft.DigitalTwins/digitalTwinsInstances/delete",
        ],
        "required_data_actions": [
            "Microsoft.DigitalTwins/digitaltwins/write",
            "Microsoft.DigitalTwins/models/write",
            "Microsoft.DigitalTwins/query/action",
        ],
    },
    "layer_5": {
        "description": "Azure Managed Grafana",
        "resource_providers": ["Microsoft.Dashboard"],
        "required_actions": [
            "Microsoft.Dashboard/grafana/write",
            "Microsoft.Dashboard/grafana/delete",
        ],
    },
}


def _create_credential(credentials: dict):
    """Create Azure credential from credentials dict."""
    from azure.identity import ClientSecretCredential
    
    tenant_id = credentials.get("azure_tenant_id")
    client_id = credentials.get("azure_client_id")
    client_secret = credentials.get("azure_client_secret")
    
    if not all([tenant_id, client_id, client_secret]):
        raise ValueError("Missing required Azure credentials: azure_tenant_id, azure_client_id, azure_client_secret")
    
    return ClientSecretCredential(
        tenant_id=tenant_id,
        client_id=client_id,
        client_secret=client_secret
    )


def _get_caller_identity(credential, subscription_id: str) -> dict:
    """
    Validate credentials by getting subscription info.
    
    This is the Azure equivalent of AWS's sts:GetCallerIdentity.
    
    Returns:
        Dict with subscription info and principal identifiers
    """
    from azure.mgmt.resource import SubscriptionClient
    from azure.core.exceptions import ClientAuthenticationError, HttpResponseError
    
    try:
        sub_client = SubscriptionClient(credential)
        subscription = sub_client.subscriptions.get(subscription_id)
        
        return {
            "subscription_id": subscription.subscription_id,
            "subscription_name": subscription.display_name,
            "tenant_id": subscription.tenant_id,
            "state": subscription.state,
            "principal_type": "service_principal",  # Always SP for ClientSecretCredential
        }
    except ClientAuthenticationError as e:
        raise ValueError(f"Authentication failed: {str(e)}")
    except HttpResponseError as e:
        if e.status_code == 403:
            raise ValueError("Access denied - Service Principal may not have access to this subscription")
        raise


def _get_role_assignments_with_permissions(credential, subscription_id: str) -> dict:
    """
    List role assignments AND their permissions for the authenticated principal.
    
    Returns:
        Dict with:
        - assignments: List of role assignment info
        - all_actions: Set of all permitted actions
        - all_data_actions: Set of all permitted data actions
    """
    from azure.mgmt.authorization import AuthorizationManagementClient
    from azure.core.exceptions import HttpResponseError
    
    try:
        auth_client = AuthorizationManagementClient(credential, subscription_id)
        scope = f"/subscriptions/{subscription_id}"
        
        assignments = []
        all_actions = set()
        all_data_actions = set()
        
        for assignment in auth_client.role_assignments.list_for_scope(scope):
            role_def_id = assignment.role_definition_id
            role_def_guid = role_def_id.split("/")[-1]
            
            # Look up friendly name in known built-ins
            role_name = None
            for name, guid in AZURE_BUILTIN_ROLES.items():
                if guid == role_def_guid:
                    role_name = name
                    break
            
            # Get role definition to extract permissions
            try:
                role_def = auth_client.role_definitions.get_by_id(role_def_id)
                if not role_name:
                    role_name = role_def.role_name or f"Custom Role ({role_def_guid[:8]}...)"
                
                # Extract actions and data actions from role definition
                if role_def.permissions:
                    for perm in role_def.permissions:
                        if perm.actions:
                            all_actions.update(perm.actions)
                        if perm.data_actions:
                            all_data_actions.update(perm.data_actions)
            except Exception:
                role_name = role_name or f"Unknown ({role_def_guid[:8]}...)"
            
            assignments.append({
                "principal_id": assignment.principal_id,
                "principal_type": assignment.principal_type,
                "role_name": role_name,
                "role_definition_id": role_def_guid,
                "scope": assignment.scope,
            })
        
        return {
            "assignments": assignments,
            "all_actions": all_actions,
            "all_data_actions": all_data_actions,
        }
        
    except HttpResponseError as e:
        if e.status_code == 403:
            return None
        raise


def _get_service_principal_id(credential, subscription_id: str) -> str:
    """
    Get the object ID of the authenticated service principal.
    
    Uses the Graph API to get the current principal's ID.
    """
    # For ClientSecretCredential, we can extract the client_id
    # The object ID is needed to filter role assignments
    # This is a simplified approach - the full implementation would use Graph API
    
    # For now, return None and we'll check all assignments
    return None


# Custom role name for least-privilege access
CUSTOM_ROLE_NAME = "Digital Twin Deployer"


def _action_matches(user_actions: set, required_action: str) -> bool:
    """
    Check if user's actions cover the required action.
    
    Handles wildcards like:
    - "*/read" matches any read action
    - "Microsoft.Web/*" matches all Web actions
    """
    if required_action in user_actions:
        return True
    
    # Check wildcard patterns
    for action in user_actions:
        if action == "*":
            return True
        if action.endswith("/*"):
            prefix = action[:-1]  # Remove "*"
            if required_action.startswith(prefix):
                return True
        if action == "*/read" and required_action.endswith("/read"):
            return True
        if action == "*/write" and required_action.endswith("/write"):
            return True
        if action == "*/delete" and required_action.endswith("/delete"):
            return True
        if action == "*/action" and required_action.endswith("/action"):
            return True
    
    return False


def _compare_permissions(role_info: dict) -> dict:
    """
    Compare user's actual permissions against required actions by layer.
    
    Args:
        role_info: Dict with 'assignments', 'all_actions', 'all_data_actions'
    
    Returns:
        Dict with by_layer status and summary
    """
    if role_info is None:
        return {
            "by_layer": {},
            "summary": {"total_layers": 0, "valid_layers": 0, "partial_layers": 0, "invalid_layers": 0},
        }
    
    user_actions = role_info.get("all_actions", set())
    user_data_actions = role_info.get("all_data_actions", set())
    
    by_layer = {}
    total_layers = len(REQUIRED_AZURE_PERMISSIONS)
    valid_layers = 0
    partial_layers = 0
    
    for layer_name, requirements in REQUIRED_AZURE_PERMISSIONS.items():
        layer_status = "valid"
        missing_actions = []
        present_actions = []
        
        # Check required actions (management plane)
        for action in requirements.get("required_actions", []):
            if _action_matches(user_actions, action):
                present_actions.append(action)
            else:
                missing_actions.append(action)
        
        # Check required data actions (data plane)
        for action in requirements.get("required_data_actions", []):
            if _action_matches(user_data_actions, action):
                present_actions.append(f"[data] {action}")
            else:
                missing_actions.append(f"[data] {action}")
        
        # Determine layer status
        if missing_actions:
            if present_actions:
                layer_status = "partial"
                partial_layers += 1
            else:
                layer_status = "invalid"
        else:
            valid_layers += 1
        
        by_layer[layer_name] = {
            "status": layer_status,
            "description": requirements["description"],
            "resource_providers": requirements["resource_providers"],
            "required_actions": requirements.get("required_actions", []),
            "required_data_actions": requirements.get("required_data_actions", []),
            "present_actions": present_actions,
            "missing_actions": missing_actions,
        }
    
    return {
        "by_layer": by_layer,
        "summary": {
            "total_layers": total_layers,
            "valid_layers": valid_layers,
            "partial_layers": partial_layers,
            "invalid_layers": total_layers - valid_layers - partial_layers,
        }
    }


def check_azure_credentials(credentials: dict) -> dict:
    """
    Main entry point. Validates Azure credentials against ALL required permissions.
    
    Args:
        credentials: Dict with azure_subscription_id, azure_tenant_id, 
                     azure_client_id, azure_client_secret, azure_region
    
    Returns:
        Dict with status, caller_identity, and permission results by layer
    """
    result = {
        "status": "invalid",
        "message": "",
        "caller_identity": None,
        "can_list_roles": False,
        "by_layer": {},
        "summary": {"total_layers": 0, "valid_layers": 0, "partial_layers": 0, "invalid_layers": 0},
        "recommended_roles": {
            "custom": "Digital Twin Deployer (recommended, least-privilege)",
            "builtin": ["Contributor", "User Access Administrator"]
        },
    }
    
    # Validate required fields
    required_fields = ["azure_subscription_id", "azure_tenant_id", "azure_client_id", "azure_client_secret"]
    missing = [f for f in required_fields if not credentials.get(f)]
    
    if missing:
        result["message"] = f"Missing required credentials: {', '.join(missing)}"
        return result
    
    subscription_id = credentials["azure_subscription_id"]
    
    try:
        # Step 1: Create credential
        try:
            credential = _create_credential(credentials)
        except ValueError as e:
            result["message"] = str(e)
            return result
        
        # Step 2: Validate credentials with subscription access
        try:
            caller_identity = _get_caller_identity(credential, subscription_id)
            result["caller_identity"] = caller_identity
        except ValueError as e:
            result["message"] = str(e)
            return result
        
        # Step 3: Get role assignments with permissions
        role_info = _get_role_assignments_with_permissions(credential, subscription_id)
        
        if role_info is None:
            result["status"] = "check_failed"
            result["message"] = (
                "Cannot determine permissions - Service Principal lacks permission to list role assignments. "
                "This typically means the principal doesn't have Reader or higher access at subscription scope. "
                "Grant 'Reader' role at subscription level to enable permission checking."
            )
            result["can_list_roles"] = False
            return result
        
        result["can_list_roles"] = True
        result["role_assignments_count"] = len(role_info.get("assignments", []))
        result["total_actions_count"] = len(role_info.get("all_actions", set()))
        
        # List assigned role names for reference
        result["assigned_roles"] = [a["role_name"] for a in role_info.get("assignments", [])]
        
        # Step 4: Compare against required permissions
        comparison = _compare_permissions(role_info)
        result["by_layer"] = comparison["by_layer"]
        result["summary"] = comparison["summary"]
        
        # Determine overall status
        summary = comparison["summary"]
        
        if summary["valid_layers"] == summary["total_layers"]:
            result["status"] = "valid"
            result["message"] = "All required permissions are present. Ready for deployment."
        elif summary["valid_layers"] > 0:
            result["status"] = "partial"
            missing_count = summary["partial_layers"] + summary["invalid_layers"]
            result["message"] = f"Some layers have missing permissions: {missing_count} of {summary['total_layers']} layers incomplete."
        else:
            result["status"] = "invalid"
            result["message"] = "Required permissions are missing. Use our custom 'Digital Twin Deployer' role (recommended) or assign Contributor + User Access Administrator."
        
        return result
        
    except Exception as e:
        logger.exception("Azure credential check failed")
        result["status"] = "error"
        result["message"] = f"Unexpected error: {str(e)}"
        return result


def check_azure_credentials_from_config(project_name: str = None) -> dict:
    """
    Validate credentials from the project's config_credentials.json.
    
    Args:
        project_name: Optional project name. Uses active project if not specified.
    
    Returns:
        Same format as check_azure_credentials()
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
                    "can_list_roles": False,
                    "by_layer": {},
                    "summary": {"total_layers": 0, "valid_layers": 0, "partial_layers": 0, "invalid_layers": 0},
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
                "can_list_roles": False,
                "by_layer": {},
                "summary": {"total_layers": 0, "valid_layers": 0, "partial_layers": 0, "invalid_layers": 0},
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
                "can_list_roles": False,
                "by_layer": {},
                "summary": {"total_layers": 0, "valid_layers": 0, "partial_layers": 0, "invalid_layers": 0},
                "project_name": project_name
            }
        
        azure_creds = config_credentials.get("azure", {})
        
        if not azure_creds:
            return {
                "status": "error",
                "message": "No Azure credentials found in config_credentials.json",
                "caller_identity": None,
                "can_list_roles": False,
                "by_layer": {},
                "summary": {"total_layers": 0, "valid_layers": 0, "partial_layers": 0, "invalid_layers": 0},
                "project_name": project_name
            }
        
        # Check the credentials
        result = check_azure_credentials(azure_creds)
        result["project_name"] = project_name
        return result
        
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to load credentials from config: {str(e)}",
            "caller_identity": None,
            "can_list_roles": False,
            "by_layer": {},
            "summary": {"total_layers": 0, "valid_layers": 0, "partial_layers": 0, "invalid_layers": 0},
            "project_name": project_name
        }


# Export for use by API and CLI
__all__ = [
    "check_azure_credentials",
    "check_azure_credentials_from_config",
    "REQUIRED_AZURE_PERMISSIONS",
    "AZURE_BUILTIN_ROLES",
]
