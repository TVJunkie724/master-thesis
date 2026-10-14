"""
Azure Credentials Permission Checker

Validates the one Azure Service Principal used as administrator by the isolated
thesis PoC. It owns resource CRUD, RBAC assignments, and the Microsoft Graph
application permissions required by directed federation.

This module is shared by both:
- REST API endpoints (api/credentials.py)
- CLI commands (src/main.py)

Authentication Flow:
    1. Authenticate the administrator.
    2. Verify the subscription and deployment resource authority.
    3. Verify an Owner assignment at subscription scope.
    4. Verify the required Microsoft Graph app roles.
"""

import base64
import binascii
from fnmatch import fnmatchcase
import json
import os
import logging

from logger import logger
from src.core.observability import redact_sensitive

# ==========================================
# Required Azure Roles by Layer
# ==========================================

# Built-in role definition IDs (partial GUIDs - these are constant across all Azure tenants)
AZURE_BUILTIN_ROLES = {
    "Owner": "8e3af657-a8ff-443c-a75c-2fe8c4bcb635",
    "Contributor": "b24988ac-6180-42a0-ab88-20f7382dd24c",
    "Reader": "acdd72a7-3385-48ef-bd42-f606fba81ae7",
    "User Access Administrator": "18d7d88d-d35e-4fb5-a5c3-7773c20a72d9",
    "Role Based Access Control Administrator": "f58310d9-a9f6-439a-9e8d-f62e7b41a168",
    "Managed Identity Contributor": "e40ec5ca-96e0-45a2-b4ff-59039f2c2b59",
    "Website Contributor": "de139f84-1756-47ae-9be6-808fbbe84772",
    "IoT Hub Data Contributor": "4fc6c259-987e-4a07-842e-c321cc9d413f",
    "Cosmos DB Operator": "230815da-be43-4aae-9cb4-875f7bd000aa",
    "Storage Account Contributor": "17d1049b-9a84-46fb-8f53-869881c3d3ab",
    "Azure Digital Twins Data Owner": "bcd981a7-7f74-457b-83e1-cceb9e632ffe",
    "Azure Digital Twins Data Reader": "d57506d4-4c8d-48b1-8587-93c323f6a5a3",
    "AcrPull": "7f951dda-4ed3-4680-a7ca-43fe172d538d",
    "Azure Event Hubs Data Receiver": "a638d3c7-ab3a-418d-83e6-5f17a39d4fde",
    "Azure Event Hubs Data Sender": "2b629674-e913-4c01-ae53-ef4638d8f975",
    "Azure Service Bus Data Receiver": "4f6d3b9b-027b-4f4c-9142-0e5a2a2247e0",
    "Azure Service Bus Data Sender": "69a216fc-b8fb-44d8-bc22-1f3c2cd27a39",
    "Grafana Admin": "22926164-76b3-42b3-bc55-97df8dab3e41",
    "Grafana Viewer": "60921a7e-fef1-4a43-9b16-a26c52ad4769",
    "IoT Hub Data Reader": "b447c946-2db7-41ec-983d-d8bf3b1c77e3",
    "Storage Blob Data Contributor": "ba92f5b4-2d11-453d-a403-e96b0029c9fe",
}

AZURE_ROLE_ASSIGNMENT_ACTIONS = (
    "Microsoft.Authorization/roleAssignments/write",
    "Microsoft.Authorization/roleAssignments/delete",
)
AZURE_GRAPH_APPLICATION_PERMISSIONS = frozenset(
    {
        "Application.ReadWrite.All",
        "AppRoleAssignment.ReadWrite.All",
    }
)

# Resource-management actions required by the supported Six-layer graph.
# These are validated against the PoC administrator's role assignments.
REQUIRED_AZURE_PERMISSIONS = {
    "setup": {
        "description": "Resource Groups, Managed Identity, Storage Account",
        "resource_providers": [
            "Microsoft.Resources",
            "Microsoft.ManagedIdentity",
            "Microsoft.Storage",
        ],
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
        "description": "IoT Hub, Event Grid, and L1 Function Deployment",
        "resource_providers": [
            "Microsoft.Devices",
            "Microsoft.EventGrid",
            "Microsoft.Web",
        ],
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
        # These data-plane actions are not ambient subscription prerequisites.
        # The atomic Six-layer graph grants Azure Digital Twins Data Owner to
        # the PoC administrator on the newly created ADT instance through
        # the PoC administrator before seed/readback.
        "provisioned_data_actions": [
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
    """Create one Azure credential without permitting ambient auth fallback."""
    from azure.identity import ClientSecretCredential

    tenant_id = credentials.get("azure_tenant_id")
    client_id = credentials.get("azure_client_id")
    client_secret = credentials.get("azure_client_secret")

    if not all([tenant_id, client_id, client_secret]):
        raise ValueError("Missing required Azure administrator credentials")

    return ClientSecretCredential(
        tenant_id=tenant_id, client_id=client_id, client_secret=client_secret
    )


def _decode_jwt_claims(token: str) -> dict:
    """Decode JWT claims without verification for local identity introspection."""
    try:
        payload = token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        return json.loads(base64.urlsafe_b64decode(payload.encode("utf-8")))
    except (
        IndexError,
        UnicodeDecodeError,
        binascii.Error,
        json.JSONDecodeError,
        TypeError,
    ):
        return {}


def _get_current_principal_claims(credential) -> dict:
    """Return stable principal identifiers from the Azure Resource Manager token."""
    token = credential.get_token("https://management.azure.com/.default").token
    claims = _decode_jwt_claims(token)
    return {
        "principal_id": claims.get("oid") or claims.get("objectid"),
        "application_id": claims.get("appid") or claims.get("azp"),
    }


def _check_microsoft_graph_authority(credential) -> dict:
    """Validate the required Graph application roles carried by the app token."""

    try:
        token = credential.get_token("https://graph.microsoft.com/.default").token
    except Exception as exc:
        return {
            "status": "authentication_failed",
            "message": "Microsoft Graph authentication failed for the Azure administrator.",
            "reason": redact_sensitive(exc),
            "missing_permissions": sorted(AZURE_GRAPH_APPLICATION_PERMISSIONS),
            "unexpected_permissions": [],
        }

    claims = _decode_jwt_claims(token)
    raw_roles = claims.get("roles")
    granted = (
        {str(role) for role in raw_roles if isinstance(role, str) and role.strip()}
        if isinstance(raw_roles, list)
        else set()
    )
    missing = sorted(AZURE_GRAPH_APPLICATION_PERMISSIONS - granted)
    if missing:
        return {
            "status": "consent_required",
            "message": "Microsoft Graph application permissions are incomplete.",
            "missing_permissions": missing,
            "unexpected_permissions": [],
        }
    return {
        "status": "ready",
        "message": "The required Microsoft Graph application permissions are consented.",
        "missing_permissions": [],
        "unexpected_permissions": [],
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
            "tenant_id": getattr(credential, "_tenant_id", None),
            "state": subscription.state,
            "principal_type": "service_principal",  # Always SP for ClientSecretCredential
            **principal_claims,
        }
    except ClientAuthenticationError as exc:
        raise ValueError(f"Authentication failed: {redact_sensitive(exc)}") from exc
    except HttpResponseError as e:
        if e.status_code == 403:
            raise ValueError(
                "Access denied - Service Principal may not have access to this subscription"
            )
        raise


def _check_sp_credential_expiration(
    tenant_id: str, client_id: str, client_secret: str
) -> dict:
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
            tenant_id=tenant_id, client_id=client_id, client_secret=client_secret
        )

        try:
            # Get access token for Graph API
            token = credential.get_token("https://graph.microsoft.com/.default")
        except Exception as exc:
            # If we can't get a token, the credential is likely expired/invalid
            error_text = str(exc).lower()
            if "expired" in error_text or "invalid" in error_text:
                return {
                    "status": "expired",
                    "graph_authority": {
                        "status": "authentication_failed",
                        "message": "Microsoft Graph authentication failed with the supplied client credential.",
                    },
                    "message": (
                        "Azure Service Principal credentials appear to be expired or invalid.\n"
                        "  • Client secret may have expired\n"
                        "  • Check Azure Portal → App registrations → Certificates & secrets"
                    ),
                }
            # For other errors, skip the check gracefully
            return {
                "status": "skipped",
                "graph_authority": {
                    "status": "check_failed",
                    "message": "Microsoft Graph token acquisition could not be verified.",
                },
                "reason": f"Could not retrieve Graph token: {redact_sensitive(exc)}",
            }

        # Query Graph API for application's passwordCredentials
        headers = {"Authorization": f"Bearer {token.token}"}

        try:
            # Try to get the application by its client ID
            url = f"https://graph.microsoft.com/v1.0/applications?$filter=appId eq '{client_id}'&$select=passwordCredentials,keyCredentials"
            response = requests.get(url, headers=headers, timeout=10)

            if response.status_code in {401, 403}:
                return {
                    "status": "skipped",
                    "graph_authority": {
                        "status": "consent_required",
                        "message": (
                            "Microsoft Graph denied application inspection; tenant admin consent "
                            "for the documented application permissions is required."
                        ),
                    },
                    "reason": "Microsoft Graph application authority is not granted.",
                }

            if response.status_code != 200:
                return {
                    "status": "skipped",
                    "graph_authority": {
                        "status": "transient"
                        if response.status_code >= 500
                        else "check_failed",
                        "message": f"Microsoft Graph returned HTTP {response.status_code}.",
                    },
                    "reason": f"Graph API returned status {response.status_code}",
                }

            data = response.json()
            applications = data.get("value", [])

            if not applications:
                return {
                    "status": "skipped",
                    "graph_authority": {
                        "status": "ready",
                        "message": "Microsoft Graph application-read authority was verified.",
                    },
                    "reason": "Application not found in Graph API",
                }

            app = applications[0]
            password_creds = app.get("passwordCredentials", [])

            now = datetime.now(timezone.utc)
            active_expirations = []
            for cred in password_creds:
                end_date_str = cred.get("endDateTime")
                if not end_date_str:
                    continue
                end_date = datetime.fromisoformat(end_date_str.replace("Z", "+00:00"))
                if end_date >= now:
                    active_expirations.append(end_date)

            # A token was successfully issued with the submitted client secret.
            # Graph returns the whole application's credential inventory without
            # revealing which password credential matched that secret. Historical
            # expired entries therefore cannot prove that the submitted secret is
            # expired and must not fail an otherwise authenticated connection.
            if not active_expirations:
                return {
                    "status": "valid",
                    "graph_authority": {
                        "status": "ready",
                        "message": "Microsoft Graph application-read authority was verified.",
                    },
                    "reason": (
                        "The submitted client secret authenticated successfully; "
                        "Graph exposed no matching active expiration metadata."
                    ),
                }

            nearest_expiration = min(active_expirations)
            days_until_expiration = (nearest_expiration - now).days
            if days_until_expiration <= 30:
                return {
                    "status": "expiring_soon",
                    "graph_authority": {
                        "status": "ready",
                        "message": "Microsoft Graph application-read authority was verified.",
                    },
                    "expiration_date": nearest_expiration.isoformat(),
                    "days_until_expiration": days_until_expiration,
                    "message": f"Azure Service Principal credentials expire in {days_until_expiration} days. Consider rotating soon.",
                }
            else:
                return {
                    "status": "valid",
                    "graph_authority": {
                        "status": "ready",
                        "message": "Microsoft Graph application-read authority was verified.",
                    },
                    "expiration_date": nearest_expiration.isoformat(),
                    "days_until_expiration": days_until_expiration,
                    "message": f"Credentials valid for {days_until_expiration} more days.",
                }

        except requests.exceptions.RequestException as exc:
            return {
                "status": "skipped",
                "graph_authority": {
                    "status": "transient",
                    "message": "Microsoft Graph could not be reached for the authority check.",
                },
                "reason": f"Graph API request failed: {redact_sensitive(exc)}",
            }

    except ImportError:
        return {
            "status": "skipped",
            "graph_authority": {
                "status": "unsupported",
                "message": "Microsoft Graph inspection dependencies are unavailable.",
            },
            "reason": "requests library not installed",
        }
    except Exception as exc:
        return {
            "status": "skipped",
            "graph_authority": {
                "status": "check_failed",
                "message": "Microsoft Graph authority inspection failed unexpectedly.",
            },
            "reason": f"Unexpected error: {redact_sensitive(exc)}",
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
                result[key] = {
                    "valid": False,
                    "error": f"Region not specified for {key}",
                }
                continue

            region_lower = region.lower().strip()

            # Check both short name (e.g., "westeurope") and display name (e.g., "West Europe")
            if region_lower in valid_region_names:
                result[key] = {"valid": True, "region": region_lower}
            elif region_lower in valid_display_names:
                result[key] = {
                    "valid": True,
                    "region": valid_display_names[region_lower],
                }
            else:
                sample_regions = sorted(list(valid_region_names))[:10]
                result[key] = {
                    "valid": False,
                    "error": f"Region '{region}' is not available. Valid regions: {', '.join(sample_regions)}...",
                }

        return result

    except Exception as exc:
        # Return error for all regions if list_locations fails
        for key in regions:
            result[key] = {
                "valid": False,
                "error": f"Failed to validate region: {redact_sensitive(exc)}",
            }
        return result


def _get_role_assignments_with_permissions(
    credential, subscription_id: str, principal_id: str
) -> dict:
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
                    role_name = (
                        role_def.role_name or f"Custom Role ({role_def_guid[:8]}...)"
                    )

                # Extract actions and data actions from role definition
                if role_def.permissions:
                    for perm in role_def.permissions:
                        actions = set(perm.actions or [])
                        not_actions = set(getattr(perm, "not_actions", None) or [])
                        data_actions = set(perm.data_actions or [])
                        not_data_actions = set(
                            getattr(perm, "not_data_actions", None) or []
                        )
                        all_actions.update(actions)
                        all_data_actions.update(data_actions)
                        permission_blocks.append(
                            {
                                "role_name": role_name,
                                "role_definition_id": role_def_guid,
                                "actions": actions,
                                "not_actions": not_actions,
                                "data_actions": data_actions,
                                "not_data_actions": not_data_actions,
                            }
                        )
            except Exception:
                role_name = role_name or f"Unknown ({role_def_guid[:8]}...)"

            assignments.append(
                {
                    "principal_id": assignment.principal_id,
                    "principal_type": assignment.principal_type,
                    "role_name": role_name,
                    "role_definition_id": role_def_guid,
                    "scope": assignment.scope,
                    "condition": getattr(assignment, "condition", None),
                    "condition_version": getattr(assignment, "condition_version", None),
                }
            )

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
    normalized_required = required_action.casefold()
    normalized_actions = {str(action).casefold() for action in user_actions}
    if normalized_required in normalized_actions:
        return "exact"

    # Azure role definitions can place wildcards in any action segment, for
    # example ``Microsoft.Authorization/*/Write`` in Contributor.notActions.
    # Match them case-insensitively because Azure resource-provider operations
    # are case-insensitive.
    for action in normalized_actions:
        if "*" in action and fnmatchcase(normalized_required, action):
            return "wildcard"

    return "none"


def _action_allowed_by_blocks(
    permission_blocks: list, required_action: str, data_plane: bool = False
) -> str:
    """Evaluate Azure RBAC permission blocks while honoring notActions."""
    actions_key = "data_actions" if data_plane else "actions"
    not_actions_key = "not_data_actions" if data_plane else "not_actions"
    best_match = "none"

    for block in permission_blocks:
        allowed_match = _action_matches(
            set(block.get(actions_key, set())), required_action
        )
        if allowed_match == "none":
            continue

        denied_match = _action_matches(
            set(block.get(not_actions_key, set())), required_action
        )
        if denied_match != "none":
            continue

        if allowed_match == "exact":
            return "exact"
        best_match = "wildcard"

    return best_match


def _action_allowed(
    role_info: dict, required_action: str, data_plane: bool = False
) -> str:
    """Check whether role assignments allow an action, including Azure notActions."""
    permission_blocks = role_info.get("permission_blocks") or []
    if permission_blocks:
        return _action_allowed_by_blocks(permission_blocks, required_action, data_plane)

    action_set = role_info.get(
        "all_data_actions" if data_plane else "all_actions", set()
    )
    return _action_matches(action_set, required_action)


def _validate_administrator_authority(role_info: dict) -> dict:
    """Validate the deliberately broad administrator used by this thesis PoC."""

    comparison = _compare_permissions(role_info)
    assignments = list(role_info.get("assignments") or [])
    owner_role_id = AZURE_BUILTIN_ROLES["Owner"].casefold()
    has_owner_assignment = any(
        str(assignment.get("role_definition_id") or "").casefold()
        == owner_role_id
        for assignment in assignments
    )
    missing_assignment_actions = [
        action
        for action in AZURE_ROLE_ASSIGNMENT_ACTIONS
        if _action_allowed(role_info, action) == "none"
    ]
    complete = (
        comparison["summary"]["valid_layers"]
        == comparison["summary"]["total_layers"]
    )
    ready = has_owner_assignment and complete and not missing_assignment_actions
    return {
        "status": "ready" if ready else "invalid",
        "message": (
            "Azure thesis-PoC administrator has subscription Owner authority."
            if ready
            else "Azure thesis-PoC administrator requires subscription Owner authority."
        ),
        "owner_assignment_found": has_owner_assignment,
        "missing_actions": missing_assignment_actions,
        "comparison": comparison,
    }


def _compare_permissions(
    role_info: dict,
    required_permissions: dict | None = None,
) -> dict:
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
            "summary": {
                "total_layers": 0,
                "valid_layers": 0,
                "partial_layers": 0,
                "invalid_layers": 0,
            },
        }

    permission_contract = (
        REQUIRED_AZURE_PERMISSIONS
        if required_permissions is None
        else required_permissions
    )
    by_layer = {}
    total_layers = len(permission_contract)
    valid_layers = 0
    partial_layers = 0

    for layer_name, requirements in permission_contract.items():
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
            "provisioned_data_actions": requirements.get(
                "provisioned_data_actions", []
            ),
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
        },
    }


def check_azure_credentials(credentials: dict) -> dict:
    """Validate the single-administrator Azure thesis-PoC contract."""

    result = {
        "status": "invalid",
        "message": "",
        "caller_identity": None,
        "region_validation": None,
        "microsoft_graph_authority": None,
        "administrator_authority": None,
        "can_list_roles": False,
        "by_layer": {},
        "summary": {
            "total_layers": 0,
            "valid_layers": 0,
            "partial_layers": 0,
            "invalid_layers": 0,
        },
        "recommended_roles": {"administrator": "Owner"},
    }

    required_fields = [
        "azure_subscription_id",
        "azure_tenant_id",
        "azure_client_id",
        "azure_client_secret",
    ]
    missing = [f for f in required_fields if not credentials.get(f)]
    if missing:
        result["message"] = f"Missing required credentials: {', '.join(missing)}"
        return result
    subscription_id = credentials["azure_subscription_id"]

    try:
        try:
            administrator_credential = _create_credential(credentials)
        except ValueError as exc:
            result["message"] = redact_sensitive(exc)
            return result

        try:
            administrator_identity = _get_caller_identity(
                administrator_credential,
                subscription_id,
            )
        except ValueError as exc:
            result["message"] = redact_sensitive(exc)
            return result

        administrator_principal_id = administrator_identity.get("principal_id")
        if not administrator_principal_id:
            result["status"] = "check_failed"
            result["message"] = (
                "Cannot determine the Azure administrator object ID from the ARM token; "
                "permission validation cannot safely filter role assignments."
            )
            return result

        subscription_state = str(administrator_identity.get("state") or "")
        if subscription_state and subscription_state != "Enabled":
            result["message"] = "Azure subscription is not enabled."
            result["subscription_state"] = subscription_state
            return result

        result["caller_identity"] = {
            "subscription_state": administrator_identity.get("state"),
            "principal_type": "service_principal",
            "administrator_authenticated": True,
        }

        graph_authority = _check_microsoft_graph_authority(administrator_credential)
        result["microsoft_graph_authority"] = graph_authority

        sp_expiration = _check_sp_credential_expiration(
            tenant_id=credentials["azure_tenant_id"],
            client_id=credentials["azure_client_id"],
            client_secret=credentials["azure_client_secret"],
        )
        result["sp_credential_expiration"] = {
            key: value
            for key, value in sp_expiration.items()
            if key != "graph_authority"
        }
        if sp_expiration.get("status") == "expired":
            result["message"] = sp_expiration.get(
                "message", "Azure administrator credentials have expired"
            )
            return result

        regions_to_validate = {
            "azure_region": credentials.get("azure_region", ""),
            "azure_region_iothub": credentials.get("azure_region_iothub", ""),
            "azure_region_digital_twin": credentials.get(
                "azure_region_digital_twin", ""
            ),
        }
        regions_to_validate = {
            k: v for k, v in regions_to_validate.items() if v and v.strip()
        }
        if regions_to_validate:
            region_results = _validate_azure_regions(
                administrator_credential,
                subscription_id,
                regions_to_validate,
            )
            result["region_validation"] = region_results
            invalid_regions = [
                k for k, v in region_results.items() if not v.get("valid")
            ]
            if invalid_regions:
                result["message"] = "One or more Azure regions are unavailable."
                return result

        administrator_roles = _get_role_assignments_with_permissions(
            administrator_credential,
            subscription_id,
            administrator_principal_id,
        )
        if administrator_roles is None:
            result["status"] = "check_failed"
            result["message"] = (
                "Azure role assignments cannot be inspected for the PoC administrator."
            )
            return result

        result["can_list_roles"] = True
        administrator_authority = _validate_administrator_authority(
            administrator_roles
        )
        result["administrator_authority"] = administrator_authority
        comparison = administrator_authority["comparison"]
        result["by_layer"] = comparison["by_layer"]
        result["summary"] = comparison["summary"]

        if (
            administrator_authority["status"] == "ready"
            and graph_authority["status"] == "ready"
        ):
            result["status"] = "valid"
            result["message"] = (
                "Azure thesis-PoC administrator and Microsoft Graph authority are ready."
            )
        elif comparison["summary"]["valid_layers"] > 0:
            result["status"] = "partial"
            result["message"] = (
                "Azure administrator authority requires repair before deployment."
            )
        else:
            result["message"] = "Azure administrator is not ready for deployment."

        return result

    except Exception as exc:
        logger.error(
            "Azure credential check failed: %s",
            redact_sensitive(exc),
            exc_info=logger.isEnabledFor(logging.DEBUG),
        )
        result["status"] = "error"
        result["message"] = (
            "Azure credential validation failed unexpectedly. Check logs."
        )
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
                "summary": {
                    "total_layers": 0,
                    "valid_layers": 0,
                    "partial_layers": 0,
                    "invalid_layers": 0,
                },
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
                "summary": {
                    "total_layers": 0,
                    "valid_layers": 0,
                    "partial_layers": 0,
                    "invalid_layers": 0,
                },
                "project_name": project_name,
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
                "summary": {
                    "total_layers": 0,
                    "valid_layers": 0,
                    "partial_layers": 0,
                    "invalid_layers": 0,
                },
                "project_name": project_name,
            }

        try:
            with open(config_path, "r") as f:
                config_credentials = json.load(f)
        except json.JSONDecodeError:
            return {
                "status": "error",
                "message": "Invalid JSON in config_credentials.json",
                "caller_identity": None,
                "can_list_roles": False,
                "by_layer": {},
                "summary": {
                    "total_layers": 0,
                    "valid_layers": 0,
                    "partial_layers": 0,
                    "invalid_layers": 0,
                },
                "project_name": project_name,
            }

        azure_creds = config_credentials.get("azure", {})

        if not azure_creds:
            return {
                "status": "error",
                "message": "No Azure credentials found in config_credentials.json",
                "caller_identity": None,
                "can_list_roles": False,
                "by_layer": {},
                "summary": {
                    "total_layers": 0,
                    "valid_layers": 0,
                    "partial_layers": 0,
                    "invalid_layers": 0,
                },
                "project_name": project_name,
            }

        # Check the credentials
        result = check_azure_credentials(azure_creds)
        result["project_name"] = project_name
        return result

    except Exception as exc:
        logger.error(
            "Failed to load Azure credentials for project %s: %s",
            project_name,
            redact_sensitive(exc),
            exc_info=logger.isEnabledFor(logging.DEBUG),
        )
        return {
            "status": "error",
            "message": "Failed to load Azure credentials from project configuration.",
            "caller_identity": None,
            "can_list_roles": False,
            "by_layer": {},
            "summary": {
                "total_layers": 0,
                "valid_layers": 0,
                "partial_layers": 0,
                "invalid_layers": 0,
            },
            "project_name": project_name,
        }


# Export for use by API and CLI
__all__ = [
    "check_azure_credentials",
    "check_azure_credentials_from_config",
    "REQUIRED_AZURE_PERMISSIONS",
    "AZURE_BUILTIN_ROLES",
]
