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
import base64
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
            "Microsoft.Resources/deployments/*",
            "Microsoft.ManagedIdentity/userAssignedIdentities/write",
            "Microsoft.ManagedIdentity/userAssignedIdentities/delete",
            "Microsoft.ManagedIdentity/userAssignedIdentities/assign/action",
            "Microsoft.Storage/storageAccounts/write",
            "Microsoft.Storage/storageAccounts/delete",
            "Microsoft.Storage/storageAccounts/listKeys/action",
        ],
    },
    "observability": {
        "description": "Log Analytics, Application Insights, Diagnostic Settings",
        "resource_providers": ["Microsoft.OperationalInsights", "Microsoft.Insights"],
        "required_actions": [
            "Microsoft.OperationalInsights/workspaces/write",
            "Microsoft.OperationalInsights/workspaces/delete",
            "Microsoft.Insights/components/write",
            "Microsoft.Insights/components/delete",
            "Microsoft.Insights/diagnosticSettings/write",
            "Microsoft.Insights/diagnosticSettings/delete",
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
            "Microsoft.Web/sites/config/write",
            "Microsoft.Web/sites/publish/action",
            "Microsoft.Web/sites/publishxml/action",
            "Microsoft.Web/sites/config/list/action",  # Get publish credentials
            "Microsoft.Web/sites/functions/write",
            "Microsoft.Web/sites/functions/delete",
            "Microsoft.Web/sites/host/listkeys/action",
            "Microsoft.Web/sites/slots/write",
            "Microsoft.Web/sites/slots/delete",
            "Microsoft.Web/sites/basicPublishingCredentialsPolicies/write",  # Enable SCM Basic Auth
            "Microsoft.Web/sites/restart/action",
            "Microsoft.Web/sites/stop/action",
            "Microsoft.Web/sites/start/action",
        ],
    },
    "layer_1": {
        "description": "IoT Hub, Event Grid, Role Assignments, L1 Function Deployment",
        "resource_providers": ["Microsoft.Devices", "Microsoft.EventGrid", "Microsoft.Authorization", "Microsoft.Web"],
        "required_actions": [
            "Microsoft.Devices/IotHubs/write",
            "Microsoft.Devices/IotHubs/delete",
            "Microsoft.Devices/IotHubs/listkeys/action",
            "Microsoft.Devices/IotHubs/IotHubKeys/listkeys/action",  # Get individual key access policies
            "Microsoft.Devices/IotHubs/exportDevices/action",
            "Microsoft.Devices/IotHubs/importDevices/action",
            "Microsoft.Devices/IotHubs/certificates/write",
            "Microsoft.Devices/IotHubs/certificates/delete",
            "Microsoft.Devices/IotHubs/certificates/generateVerificationCode/action",
            "Microsoft.Devices/IotHubs/certificates/verify/action",
            "Microsoft.Devices/provisioningServices/write",
            "Microsoft.Devices/provisioningServices/delete",
            "Microsoft.Devices/provisioningServices/listkeys/action",
            "Microsoft.Devices/register/action",
            "Microsoft.EventGrid/eventSubscriptions/write",
            "Microsoft.EventGrid/eventSubscriptions/delete",
            "Microsoft.EventGrid/systemTopics/write",
            "Microsoft.EventGrid/systemTopics/delete",
            "Microsoft.EventGrid/systemTopics/eventSubscriptions/write",
            "Microsoft.EventGrid/systemTopics/eventSubscriptions/delete",
            "Microsoft.EventGrid/topics/write",
            "Microsoft.EventGrid/topics/delete",
            "Microsoft.Authorization/roleAssignments/write",
            "Microsoft.Authorization/roleAssignments/delete",
            "Microsoft.Web/sites/config/list/action",  # Get publish credentials for L1 functions
            "Microsoft.Web/sites/basicPublishingCredentialsPolicies/write",  # Enable SCM Basic Auth
        ],
    },
    "layer_2": {
        "description": "Function Apps and Logic Apps (Compute Layer)",
        "resource_providers": ["Microsoft.Web", "Microsoft.Logic"],
        "required_actions": [
            "Microsoft.Web/sites/write",
            "Microsoft.Web/sites/delete",
            "Microsoft.Web/sites/publish/action",
            "Microsoft.Web/sites/config/list/action",  # Get publish credentials
            "Microsoft.Web/sites/basicPublishingCredentialsPolicies/write",  # Enable SCM Basic Auth
            "Microsoft.Logic/workflows/write",
            "Microsoft.Logic/workflows/delete",
            "Microsoft.Logic/workflows/triggers/listCallbackUrl/action",
        ],
    },
    "layer_3": {
        "description": "Cosmos DB, Blob Storage",
        "resource_providers": ["Microsoft.DocumentDB", "Microsoft.Storage"],
        "required_actions": [
            "Microsoft.DocumentDB/databaseAccounts/write",
            "Microsoft.DocumentDB/databaseAccounts/delete",
            "Microsoft.DocumentDB/databaseAccounts/read",  # Explicit - */read wildcard not always honored
            "Microsoft.DocumentDB/databaseAccounts/listKeys/action",
            "Microsoft.DocumentDB/databaseAccounts/sqlDatabases/write",
            "Microsoft.DocumentDB/databaseAccounts/sqlDatabases/read",
            "Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers/write",
            "Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers/read",
            "Microsoft.Storage/storageAccounts/blobServices/containers/write",
            "Microsoft.Storage/storageAccounts/blobServices/containers/delete",
            "Microsoft.DocumentDB/databaseAccounts/readMetadata",
            "Microsoft.DocumentDB/databaseAccounts/sqlDatabases/delete",
            "Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers/delete",
        ],
    },
    "layer_4": {
        "description": "Azure Digital Twins",
        "resource_providers": ["Microsoft.DigitalTwins"],
        "required_actions": [
            "Microsoft.DigitalTwins/digitalTwinsInstances/write",
            "Microsoft.DigitalTwins/digitalTwinsInstances/delete",
            "Microsoft.DigitalTwins/digitalTwinsInstances/endpoints/write",
            "Microsoft.DigitalTwins/digitalTwinsInstances/endpoints/delete",
            "Microsoft.DigitalTwins/digitalTwinsInstances/privateEndpointConnections/write",
            "Microsoft.DigitalTwins/digitalTwinsInstances/privateEndpointConnections/delete",
            "Microsoft.DigitalTwins/register/action",
        ],
        "required_data_actions": [
            "Microsoft.DigitalTwins/digitaltwins/read",
            "Microsoft.DigitalTwins/digitaltwins/write",
            "Microsoft.DigitalTwins/digitaltwins/delete",
            "Microsoft.DigitalTwins/digitaltwins/relationships/read",
            "Microsoft.DigitalTwins/digitaltwins/relationships/write",
            "Microsoft.DigitalTwins/digitaltwins/relationships/delete",
            "Microsoft.DigitalTwins/models/read",
            "Microsoft.DigitalTwins/models/write",
            "Microsoft.DigitalTwins/models/delete",
            "Microsoft.DigitalTwins/query/action",
            "Microsoft.DigitalTwins/eventroutes/read",
            "Microsoft.DigitalTwins/eventroutes/write",
            "Microsoft.DigitalTwins/eventroutes/delete",
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


def _decode_jwt_claims(token: str) -> dict:
    """Decode JWT claims without verification for local identity introspection."""
    try:
        payload = token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        return json.loads(base64.urlsafe_b64decode(payload.encode("utf-8")))
    except Exception:
        return {}


def _get_current_principal_claims(credential) -> dict:
    """Return stable principal identifiers from the Azure Resource Manager token."""
    token = credential.get_token("https://management.azure.com/.default").token
    claims = _decode_jwt_claims(token)
    return {
        "principal_id": claims.get("oid") or claims.get("objectid"),
        "application_id": claims.get("appid") or claims.get("azp"),
    }


def _get_caller_identity(credential, subscription_id: str) -> dict:
    """
    Validate credentials by getting subscription info.
    
    This is the Azure equivalent of AWS's sts:GetCallerIdentity.
    
    Returns:
        Dict with subscription info and principal identifiers
    """
    from azure.mgmt.subscription import SubscriptionClient
    from azure.core.exceptions import ClientAuthenticationError, HttpResponseError
    
    try:
        sub_client = SubscriptionClient(credential)
        subscription = sub_client.subscriptions.get(subscription_id)
        
        principal_claims = _get_current_principal_claims(credential)

        return {
            "subscription_id": subscription.subscription_id,
            "subscription_name": subscription.display_name,
            "tenant_id": getattr(credential, '_tenant_id', None),
            "state": subscription.state,
            "principal_type": "service_principal",  # Always SP for ClientSecretCredential
            **principal_claims,
        }
    except ClientAuthenticationError as e:
        raise ValueError(f"Authentication failed: {str(e)}")
    except HttpResponseError as e:
        if e.status_code == 403:
            raise ValueError("Access denied - Service Principal may not have access to this subscription")
        raise


def _check_sp_credential_expiration(tenant_id: str, client_id: str, client_secret: str) -> dict:
    """
    Check if Service Principal credentials are expired or expiring soon.
    
    Uses Microsoft Graph API to check passwordCredentials and keyCredentials
    on the application registration.
    
    Args:
        tenant_id: Azure AD tenant ID
        client_id: Service Principal application (client) ID
        client_secret: Client secret (used for auth to check itself)
    
    Returns:
        Dict with:
        - status: "valid", "expired", "expiring_soon", or "skipped"
        - expiration_date: Date when credential expires (if found)
        - days_until_expiration: Days remaining (if expiring_soon)
        - message: Human-readable status
    """
    try:
        from azure.identity import ClientSecretCredential
        from datetime import datetime, timezone
        import requests
        
        # Get Graph API token
        credential = ClientSecretCredential(
            tenant_id=tenant_id,
            client_id=client_id,
            client_secret=client_secret
        )
        
        try:
            # Get access token for Graph API
            token = credential.get_token("https://graph.microsoft.com/.default")
        except Exception as e:
            # If we can't get a token, the credential is likely expired/invalid
            if "expired" in str(e).lower() or "invalid" in str(e).lower():
                return {
                    "status": "expired",
                    "message": (
                        "Azure Service Principal credentials appear to be expired or invalid.\n"
                        "  • Client secret may have expired\n"
                        "  • Check Azure Portal → App registrations → Certificates & secrets"
                    )
                }
            # For other errors, skip the check gracefully
            return {
                "status": "skipped",
                "reason": f"Could not retrieve Graph token: {str(e)}"
            }
        
        # Query Graph API for application's passwordCredentials
        headers = {"Authorization": f"Bearer {token.token}"}
        
        try:
            # Try to get the application by its client ID
            url = f"https://graph.microsoft.com/v1.0/applications?$filter=appId eq '{client_id}'&$select=passwordCredentials,keyCredentials"
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 403:
                # No permission to read - skip gracefully
                return {
                    "status": "skipped",
                    "reason": "Service Principal lacks permission to read its own application registration (Application.Read.All required)"
                }
            
            if response.status_code != 200:
                return {
                    "status": "skipped",
                    "reason": f"Graph API returned status {response.status_code}"
                }
            
            data = response.json()
            applications = data.get("value", [])
            
            if not applications:
                return {
                    "status": "skipped",
                    "reason": "Application not found in Graph API"
                }
            
            app = applications[0]
            password_creds = app.get("passwordCredentials", [])
            key_creds = app.get("keyCredentials", [])
            
            now = datetime.now(timezone.utc)
            nearest_expiration = None
            
            # Check password credentials (secrets)
            for cred in password_creds:
                end_date_str = cred.get("endDateTime")
                if end_date_str:
                    end_date = datetime.fromisoformat(end_date_str.replace("Z", "+00:00"))
                    if nearest_expiration is None or end_date < nearest_expiration:
                        nearest_expiration = end_date
            
            # Check key credentials (certificates)  
            for cred in key_creds:
                end_date_str = cred.get("endDateTime")
                if end_date_str:
                    end_date = datetime.fromisoformat(end_date_str.replace("Z", "+00:00"))
                    if nearest_expiration is None or end_date < nearest_expiration:
                        nearest_expiration = end_date
            
            if nearest_expiration is None:
                return {
                    "status": "skipped",
                    "reason": "No credential expiration dates found"
                }
            
            days_until_expiration = (nearest_expiration - now).days
            
            if days_until_expiration < 0:
                return {
                    "status": "expired",
                    "expiration_date": nearest_expiration.isoformat(),
                    "message": (
                        f"Azure Service Principal credentials expired {abs(days_until_expiration)} days ago.\n"
                        "Generate new credentials in Azure Portal → App registrations → Certificates & secrets."
                    )
                }
            elif days_until_expiration <= 30:
                return {
                    "status": "expiring_soon",
                    "expiration_date": nearest_expiration.isoformat(),
                    "days_until_expiration": days_until_expiration,
                    "message": f"Azure Service Principal credentials expire in {days_until_expiration} days. Consider rotating soon."
                }
            else:
                return {
                    "status": "valid",
                    "expiration_date": nearest_expiration.isoformat(),
                    "days_until_expiration": days_until_expiration,
                    "message": f"Credentials valid for {days_until_expiration} more days."
                }
                
        except requests.exceptions.RequestException as e:
            return {
                "status": "skipped",
                "reason": f"Graph API request failed: {str(e)}"
            }
            
    except ImportError:
        return {
            "status": "skipped",
            "reason": "requests library not installed"
        }
    except Exception as e:
        return {
            "status": "skipped",
            "reason": f"Unexpected error: {str(e)}"
        }


def _validate_azure_regions(credential, subscription_id: str, regions: dict) -> dict:
    """
    Validate Azure regions are available for the subscription.
    
    Args:
        credential: Authenticated Azure credential
        subscription_id: Azure subscription ID
        regions: Dict of region keys to validate, e.g. {"azure_region": "westeurope", ...}
    
    Returns:
        Dict with validation results per region key
    """
    from azure.mgmt.subscription import SubscriptionClient
    
    result = {}
    try:
        sub_client = SubscriptionClient(credential)
        locations = list(sub_client.subscriptions.list_locations(subscription_id))
        valid_region_names = {loc.name for loc in locations}
        valid_display_names = {loc.display_name.lower(): loc.name for loc in locations}
        
        for key, region in regions.items():
            if not region or not region.strip():
                result[key] = {"valid": False, "error": f"Region not specified for {key}"}
                continue
            
            region_lower = region.lower().strip()
            
            # Check both short name (e.g., "westeurope") and display name (e.g., "West Europe")
            if region_lower in valid_region_names:
                result[key] = {"valid": True, "region": region_lower}
            elif region_lower in valid_display_names:
                result[key] = {"valid": True, "region": valid_display_names[region_lower]}
            else:
                sample_regions = sorted(list(valid_region_names))[:10]
                result[key] = {
                    "valid": False,
                    "error": f"Region '{region}' is not available. Valid regions: {', '.join(sample_regions)}..."
                }
        
        return result
        
    except Exception as e:
        # Return error for all regions if list_locations fails
        for key in regions:
            result[key] = {"valid": False, "error": f"Failed to validate region: {str(e)}"}
        return result


def _get_role_assignments_with_permissions(credential, subscription_id: str, principal_id: str) -> dict:
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
        permission_blocks = []
        
        normalized_principal_id = principal_id.lower()

        for assignment in auth_client.role_assignments.list_for_scope(scope):
            assignment_principal_id = str(assignment.principal_id or "").lower()
            if assignment_principal_id != normalized_principal_id:
                continue

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
                        actions = set(perm.actions or [])
                        not_actions = set(getattr(perm, "not_actions", None) or [])
                        data_actions = set(perm.data_actions or [])
                        not_data_actions = set(getattr(perm, "not_data_actions", None) or [])
                        all_actions.update(actions)
                        all_data_actions.update(data_actions)
                        permission_blocks.append({
                            "role_name": role_name,
                            "actions": actions,
                            "not_actions": not_actions,
                            "data_actions": data_actions,
                            "not_data_actions": not_data_actions,
                        })
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
            "permission_blocks": permission_blocks,
        }
        
    except HttpResponseError as e:
        if e.status_code == 403:
            return None
        raise


# Custom role name for least-privilege access
CUSTOM_ROLE_NAME = "Digital Twin Deployer"


def _action_matches(user_actions: set, required_action: str) -> str:
    """
    Check if user's actions cover the required action.
    
    Handles wildcards like:
    - "*" matches everything (Owner role)
    - "*/read" matches any read action
    - "Microsoft.Web/*" matches all Web actions
    
    Returns:
        "exact" - if the exact permission is present
        "wildcard" - if matched via a wildcard pattern (less reliable)
        "none" - if not matched
    """
    if required_action in user_actions:
        return "exact"
    
    # Check wildcard patterns
    for action in user_actions:
        if action == "*":
            return "wildcard"  # Owner role - matches but may not be reliable
        if action.endswith("/*"):
            prefix = action[:-1]  # Remove "*"
            if required_action.startswith(prefix):
                return "wildcard"
        if action == "*/read" and required_action.endswith("/read"):
            return "wildcard"
        if action == "*/write" and required_action.endswith("/write"):
            return "wildcard"
        if action == "*/delete" and required_action.endswith("/delete"):
            return "wildcard"
        if action == "*/action" and required_action.endswith("/action"):
            return "wildcard"
    
    return "none"


def _action_allowed_by_blocks(permission_blocks: list, required_action: str, data_plane: bool = False) -> str:
    """Evaluate Azure RBAC permission blocks while honoring notActions."""
    actions_key = "data_actions" if data_plane else "actions"
    not_actions_key = "not_data_actions" if data_plane else "not_actions"
    best_match = "none"

    for block in permission_blocks:
        allowed_match = _action_matches(set(block.get(actions_key, set())), required_action)
        if allowed_match == "none":
            continue

        denied_match = _action_matches(set(block.get(not_actions_key, set())), required_action)
        if denied_match != "none":
            continue

        if allowed_match == "exact":
            return "exact"
        best_match = "wildcard"

    return best_match


def _action_allowed(role_info: dict, required_action: str, data_plane: bool = False) -> str:
    """Check whether role assignments allow an action, including Azure notActions."""
    permission_blocks = role_info.get("permission_blocks") or []
    if permission_blocks:
        return _action_allowed_by_blocks(permission_blocks, required_action, data_plane)

    action_set = role_info.get("all_data_actions" if data_plane else "all_actions", set())
    return _action_matches(action_set, required_action)


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
    
    by_layer = {}
    total_layers = len(REQUIRED_AZURE_PERMISSIONS)
    valid_layers = 0
    partial_layers = 0
    
    for layer_name, requirements in REQUIRED_AZURE_PERMISSIONS.items():
        layer_status = "valid"
        missing_actions = []
        present_actions = []
        wildcard_actions = []  # Track permissions only matched via wildcards
        
        # Check required actions (management plane)
        for action in requirements.get("required_actions", []):
            match_type = _action_allowed(role_info, action)
            if match_type == "exact":
                present_actions.append(action)
            elif match_type == "wildcard":
                present_actions.append(action)
                wildcard_actions.append(action)  # Also track as wildcard
            else:
                missing_actions.append(action)
        
        # Check required data actions (data plane)
        for action in requirements.get("required_data_actions", []):
            match_type = _action_allowed(role_info, action, data_plane=True)
            if match_type == "exact":
                present_actions.append(f"[data] {action}")
            elif match_type == "wildcard":
                present_actions.append(f"[data] {action}")
                wildcard_actions.append(f"[data] {action}")
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
            "wildcard_actions": wildcard_actions,  # Permissions matched via wildcards (may not work at runtime)
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
        "region_validation": None,
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

        principal_id = caller_identity.get("principal_id")
        if not principal_id:
            result["status"] = "check_failed"
            result["message"] = (
                "Cannot determine the Azure Service Principal object ID from the ARM token. "
                "Permission validation would be unsafe because subscription role assignments "
                "could not be filtered to the authenticated principal."
            )
            result["can_list_roles"] = False
            return result
        
        # Step 2.5: FAIL-FAST - Check subscription state (catches disabled/deleted subscriptions)
        subscription_state = caller_identity.get("state")
        if subscription_state and subscription_state != "Enabled":
            result["status"] = "invalid"
            result["message"] = (
                f"Azure subscription is '{subscription_state}'. "
                f"Subscription must be 'Enabled' for deployment. "
                f"Check Azure billing status or contact your administrator to reactivate the subscription."
            )
            return result
        
        # Step 2.6: Check SP credential expiration (if Graph API accessible)
        sp_expiration = _check_sp_credential_expiration(
            tenant_id=credentials["azure_tenant_id"],
            client_id=credentials["azure_client_id"],
            client_secret=credentials["azure_client_secret"]
        )
        result["sp_credential_expiration"] = sp_expiration
        
        if sp_expiration.get("status") == "expired":
            result["status"] = "invalid"
            result["message"] = sp_expiration.get("message", "Service Principal credentials have expired")
            return result
        # Note: "expiring_soon" is a warning, not a failure - will be shown but deployment proceeds
        
        # Step 3: Validate regions
        regions_to_validate = {
            "azure_region": credentials.get("azure_region", ""),
            "azure_region_iothub": credentials.get("azure_region_iothub", ""),
            "azure_region_digital_twin": credentials.get("azure_region_digital_twin", ""),
        }
        # Filter out empty regions
        regions_to_validate = {k: v for k, v in regions_to_validate.items() if v and v.strip()}
        
        if regions_to_validate:
            region_results = _validate_azure_regions(credential, subscription_id, regions_to_validate)
            result["region_validation"] = region_results
            
            # Check if any region is invalid
            invalid_regions = [k for k, v in region_results.items() if not v.get("valid")]
            if invalid_regions:
                errors = [region_results[k].get("error", f"Invalid region") for k in invalid_regions]
                result["status"] = "invalid"
                result["message"] = f"Invalid region(s): {'; '.join(errors)}"
                return result
        
        # Step 4: Get role assignments with permissions
        role_info = _get_role_assignments_with_permissions(credential, subscription_id, principal_id)
        
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
        project_name: Project name to read. Required; no global active project fallback.
    
    Returns:
        Same format as check_azure_credentials()
    """
    try:
        from src.core.project_storage import get_project_storage

        if not project_name:
            return {
                "status": "error",
                "message": "Project name is required for request-scoped credential checks.",
                "caller_identity": None,
                "can_list_roles": False,
                "by_layer": {},
                "summary": {"total_layers": 0, "valid_layers": 0, "partial_layers": 0, "invalid_layers": 0},
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
                "can_list_roles": False,
                "by_layer": {},
                "summary": {"total_layers": 0, "valid_layers": 0, "partial_layers": 0, "invalid_layers": 0},
                "project_name": project_name
            }
        
        # Load credentials from config
        config_path = project_dir / "config_credentials.json"
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
