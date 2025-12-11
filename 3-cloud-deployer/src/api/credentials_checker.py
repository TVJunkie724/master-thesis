"""
AWS Credentials Permission Checker

Validates if provided AWS credentials have the required permissions
for the deployer by listing attached policies and comparing against
a hardcoded list of required actions.

This module is shared by both:
- REST API endpoints (api/credentials.py)
- CLI commands (src/main.py)
"""
import boto3
from botocore.exceptions import ClientError, NoCredentialsError
import json
import sys
import os

# Add src to path for imports when called from API
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

# ==========================================
# Shared Permission Sets (avoid duplication)
# ==========================================
# Define permission sets once, reference in layers that need them

_IAM_ROLE_MANAGEMENT = [
    "iam:CreateRole",
    "iam:DeleteRole",
    "iam:GetRole",
    "iam:AttachRolePolicy",
    "iam:DetachRolePolicy",
    "iam:ListAttachedRolePolicies",
    "iam:ListRolePolicies",
    "iam:DeleteRolePolicy",
    "iam:ListInstanceProfilesForRole",
    "iam:RemoveRoleFromInstanceProfile",
]

_IAM_INLINE_POLICY = [
    "iam:PutRolePolicy",
    "iam:UpdateAssumeRolePolicy",
]

_LAMBDA_BASIC = [
    "lambda:CreateFunction",
    "lambda:DeleteFunction",
    "lambda:GetFunction",
    "lambda:AddPermission",
    "lambda:RemovePermission",
]

_LAMBDA_FUNCTION_URL = [
    "lambda:CreateFunctionUrlConfig",
    "lambda:DeleteFunctionUrlConfig",
    "lambda:GetFunctionUrlConfig",
]

_LAMBDA_CONFIG_UPDATE = [
    "lambda:GetFunctionConfiguration",
    "lambda:UpdateFunctionConfiguration",
]

# Permissions required by the credential checker to inspect its own policies
# These are NOT deployment permissions - they're meta-permissions for self-inspection
SELF_CHECK_PERMISSIONS = {
    "user": [
        "iam:ListUserPolicies",
        "iam:GetUserPolicy",
        "iam:ListAttachedUserPolicies",
        "iam:GetPolicy",
        "iam:GetPolicyVersion",
        "iam:ListGroupsForUser",
        "iam:ListGroupPolicies",
        "iam:GetGroupPolicy",
        "iam:ListAttachedGroupPolicies",
    ],
    "role": [
        "iam:ListRolePolicies",
        "iam:GetRolePolicy",
        "iam:ListAttachedRolePolicies",
        "iam:GetPolicy",
        "iam:GetPolicyVersion",
    ],
}

# ==========================================
# Required AWS Permissions by Layer/Service
# ==========================================
# Each layer lists ONLY unique permissions or references shared sets


REQUIRED_AWS_PERMISSIONS = {
    # Layer 0 is the comprehensive "glue" layer - needs most Lambda/IAM permissions
    # Other layers reference shared sets to avoid duplication
    "layer_0": {
        # Layer 0 (Glue Layer): Multi-cloud HTTP receivers deployed BEFORE Layers 1-5
        # This is the PRIMARY layer for IAM/Lambda permissions
        "iam": _IAM_ROLE_MANAGEMENT + _IAM_INLINE_POLICY,
        "lambda": _LAMBDA_BASIC + _LAMBDA_FUNCTION_URL + _LAMBDA_CONFIG_UPDATE,
    },
    "layer_1": {
        # Layer 1 uses same IAM/Lambda as L0 (no duplication needed in final set)
        # Unique services: IoT Core, STS
        "iot": [
            "iot:CreateThing",
            "iot:DeleteThing",
            "iot:DescribeThing",
            "iot:CreateKeysAndCertificate",
            "iot:CreatePolicy",
            "iot:DeletePolicy",
            "iot:AttachThingPrincipal",
            "iot:DetachThingPrincipal",
            "iot:AttachPolicy",
            "iot:DetachPolicy",
            "iot:UpdateCertificate",
            "iot:DeleteCertificate",
            "iot:ListThingPrincipals",
            "iot:ListAttachedPolicies",
            "iot:ListPolicyVersions",
            "iot:DeletePolicyVersion",
            "iot:CreateTopicRule",
            "iot:DeleteTopicRule",
            "iot:DescribeEndpoint",
        ],
        "sts": [
            "sts:GetCallerIdentity",
        ],
    },
    "layer_2": {
        # Unique service: Step Functions
        "states": [
            "states:CreateStateMachine",
            "states:DeleteStateMachine",
            "states:DescribeStateMachine",
        ],
    },
    "layer_3": {
        # Unique services: DynamoDB, S3, EventBridge
        "dynamodb": [
            "dynamodb:CreateTable",
            "dynamodb:DeleteTable",
            "dynamodb:CreateBackup",
            "dynamodb:DescribeBackup",
        ],
        "s3": [
            "s3:CreateBucket",
            "s3:DeleteBucket",
            "s3:PutBucketCors",
            "s3:GetBucketCors",
            "s3:DeleteBucketCors",
            "s3:ListBucket",
            "s3:DeleteObject",
        ],
        "events": [
            "events:PutRule",
            "events:DeleteRule",
            "events:DescribeRule",
            "events:PutTargets",
            "events:RemoveTargets",
            "events:ListTargetsByRule",
        ],
    },
    "layer_4": {
        # Unique service: IoT TwinMaker
        "iottwinmaker": [
            "iottwinmaker:CreateWorkspace",
            "iottwinmaker:DeleteWorkspace",
            "iottwinmaker:GetWorkspace",
            "iottwinmaker:ListEntities",
            "iottwinmaker:DeleteEntity",
            "iottwinmaker:ListScenes",
            "iottwinmaker:DeleteScene",
            "iottwinmaker:ListComponentTypes",
            "iottwinmaker:DeleteComponentType",
            "iottwinmaker:CreateComponentType",
            "iottwinmaker:GetComponentType",
            "iottwinmaker:UpdateEntity",
            "iottwinmaker:GetEntity",
        ],
    },
    "layer_5": {
        # Unique service: Grafana
        "grafana": [
            "grafana:CreateWorkspace",
            "grafana:DeleteWorkspace",
            "grafana:DescribeWorkspace",
            "grafana:ListWorkspaces",
        ],
    },
}




def _get_all_required_permissions() -> dict:
    """
    Flatten all required permissions into a single dict by service,
    with layer references. Removes duplicates.
    
    Returns:
        Dict like: {"iam": {"actions": set(), "layers": set()}, ...}
    """
    result = {}
    for layer_name, services in REQUIRED_AWS_PERMISSIONS.items():
        for service_name, actions in services.items():
            if service_name not in result:
                result[service_name] = {"actions": set(), "layers": set()}
            result[service_name]["actions"].update(actions)
            if actions:  # Only add layer if it has actions
                result[service_name]["layers"].add(layer_name)
    return result


def _create_session(credentials: dict) -> boto3.Session:
    """Create boto3 session from credentials dict."""
    session_kwargs = {
        "aws_access_key_id": credentials.get("aws_access_key_id"),
        "aws_secret_access_key": credentials.get("aws_secret_access_key"),
        "region_name": credentials.get("aws_region", "us-east-1"),
    }
    
    # Optional session token for temporary credentials
    if credentials.get("aws_session_token"):
        session_kwargs["aws_session_token"] = credentials["aws_session_token"]
    
    return boto3.Session(**session_kwargs)


def _get_caller_identity(sts_client) -> dict:
    """
    Get caller identity to validate credentials and determine principal type.
    
    Returns:
        Dict with account, arn, user_id, and principal_type
    """
    response = sts_client.get_caller_identity()
    arn = response["Arn"]
    
    # Determine principal type from ARN
    if ":user/" in arn:
        principal_type = "user"
    elif ":assumed-role/" in arn:
        principal_type = "assumed-role"
    elif ":role/" in arn:
        principal_type = "role"
    else:
        principal_type = "unknown"
    
    return {
        "account": response["Account"],
        "arn": arn,
        "user_id": response["UserId"],
        "principal_type": principal_type,
    }


def _get_attached_permissions(iam_client, caller_identity: dict) -> tuple:
    """
    Get all permissions from attached policies.
    
    Args:
        iam_client: Boto3 IAM client
        caller_identity: Dict from _get_caller_identity()
    
    Returns:
        Tuple of (permissions_set, error_permission or None)
        - If successful: (set of permissions, None)
        - If AccessDenied: (empty set, "iam:ListAttachedUserPolicies" or similar)
    """
    arn = caller_identity["arn"]
    principal_type = caller_identity["principal_type"]
    permissions = set()
    
    try:
        if principal_type == "user":
            # Extract username from ARN: arn:aws:iam::123456789012:user/username
            username = arn.split("/")[-1]
            
            # List inline policies
            try:
                response = iam_client.list_user_policies(UserName=username)
                for policy_name in response.get("PolicyNames", []):
                    policy_doc = iam_client.get_user_policy(UserName=username, PolicyName=policy_name)
                    _extract_permissions(policy_doc["PolicyDocument"], permissions)
            except ClientError as e:
                if e.response["Error"]["Code"] == "AccessDenied":
                    return set(), "iam:ListUserPolicies"
                raise
            
            # List attached managed policies
            try:
                response = iam_client.list_attached_user_policies(UserName=username)
                for policy in response.get("AttachedPolicies", []):
                    _get_policy_permissions(iam_client, policy["PolicyArn"], permissions)
            except ClientError as e:
                if e.response["Error"]["Code"] == "AccessDenied":
                    return set(), "iam:ListAttachedUserPolicies"
                raise
            
            # List group policies
            try:
                groups_response = iam_client.list_groups_for_user(UserName=username)
                for group in groups_response.get("Groups", []):
                    group_name = group["GroupName"]
                    
                    # Group inline policies
                    group_policies = iam_client.list_group_policies(GroupName=group_name)
                    for policy_name in group_policies.get("PolicyNames", []):
                        policy_doc = iam_client.get_group_policy(GroupName=group_name, PolicyName=policy_name)
                        _extract_permissions(policy_doc["PolicyDocument"], permissions)
                    
                    # Group attached policies
                    attached = iam_client.list_attached_group_policies(GroupName=group_name)
                    for policy in attached.get("AttachedPolicies", []):
                        _get_policy_permissions(iam_client, policy["PolicyArn"], permissions)
            except ClientError as e:
                if e.response["Error"]["Code"] == "AccessDenied":
                    return set(), "iam:ListGroupsForUser"
                raise
                
        elif principal_type in ("role", "assumed-role"):
            # Extract role name from ARN
            if principal_type == "assumed-role":
                # arn:aws:sts::123456789012:assumed-role/role-name/session-name
                role_name = arn.split("/")[-2]
            else:
                # arn:aws:iam::123456789012:role/role-name
                role_name = arn.split("/")[-1]
            
            # List inline policies
            try:
                response = iam_client.list_role_policies(RoleName=role_name)
                for policy_name in response.get("PolicyNames", []):
                    policy_doc = iam_client.get_role_policy(RoleName=role_name, PolicyName=policy_name)
                    _extract_permissions(policy_doc["PolicyDocument"], permissions)
            except ClientError as e:
                if e.response["Error"]["Code"] == "AccessDenied":
                    return set(), "iam:ListRolePolicies"
                raise
            
            # List attached managed policies
            try:
                response = iam_client.list_attached_role_policies(RoleName=role_name)
                for policy in response.get("AttachedPolicies", []):
                    _get_policy_permissions(iam_client, policy["PolicyArn"], permissions)
            except ClientError as e:
                if e.response["Error"]["Code"] == "AccessDenied":
                    return set(), "iam:ListAttachedRolePolicies"
                raise
        else:
            return set(), "unknown_principal_type"
            
    except ClientError as e:
        return set(), f"error:{e.response['Error']['Code']}"
    
    return permissions, None


def _get_policy_permissions(iam_client, policy_arn: str, permissions: set):
    """Get permissions from a managed policy and add to the set."""
    try:
        # Get the policy version
        policy = iam_client.get_policy(PolicyArn=policy_arn)
        version_id = policy["Policy"]["DefaultVersionId"]
        
        # Get the policy document
        version = iam_client.get_policy_version(PolicyArn=policy_arn, VersionId=version_id)
        _extract_permissions(version["PolicyVersion"]["Document"], permissions)
    except ClientError:
        # Skip if we can't read the policy
        pass


def _extract_permissions(policy_document: dict, permissions: set):
    """
    Extract action permissions from a policy document.
    Handles wildcards like * and service:*.
    """
    if isinstance(policy_document, str):
        policy_document = json.loads(policy_document)
    
    statements = policy_document.get("Statement", [])
    if isinstance(statements, dict):
        statements = [statements]
    
    for statement in statements:
        if statement.get("Effect") != "Allow":
            continue
        
        actions = statement.get("Action", [])
        if isinstance(actions, str):
            actions = [actions]
        
        for action in actions:
            if action == "*":
                # Full admin access - add a marker
                permissions.add("*")
            elif action.endswith(":*"):
                # Service wildcard like "s3:*" - add a marker
                permissions.add(action)
            else:
                permissions.add(action)


def _check_permission(permission: str, available: set) -> bool:
    """
    Check if a specific permission is available.
    Handles wildcard matching.
    """
    # Full admin access
    if "*" in available:
        return True
    
    # Exact match
    if permission in available:
        return True
    
    # Service wildcard match (e.g., "s3:*" covers "s3:GetObject")
    service = permission.split(":")[0]
    if f"{service}:*" in available:
        return True
    
    return False


def _compare_permissions(available: set, required: dict) -> dict:
    """
    Compare available permissions against required permissions.
    
    Args:
        available: Set of permissions the credentials have
        required: Dict from _get_all_required_permissions()
    
    Returns:
        Dict with by_layer, by_service, and summary
    """
    by_layer = {}
    by_service = {}
    total_valid = 0
    total_missing = 0
    all_required = set()
    
    # Build by_service first (aggregated view)
    for service_name, data in required.items():
        actions = data["actions"]
        layers = data["layers"]
        
        valid = []
        missing = []
        
        for action in sorted(actions):
            all_required.add(action)
            if _check_permission(action, available):
                valid.append(action)
                total_valid += 1
            else:
                missing.append(action)
                total_missing += 1
        
        by_service[service_name] = {
            "valid": valid,
            "missing": missing,
            "used_in_layers": sorted(layers),
        }
    
    # Build by_layer view
    for layer_name, services in REQUIRED_AWS_PERMISSIONS.items():
        layer_status = "valid"
        layer_services = {}
        
        for service_name, actions in services.items():
            if not actions:
                continue
            
            valid = []
            missing = []
            
            for action in sorted(actions):
                if _check_permission(action, available):
                    valid.append(action)
                else:
                    missing.append(action)
                    layer_status = "partial" if valid else "invalid"
            
            layer_services[service_name] = {
                "valid": valid,
                "missing": missing,
            }
        
        if layer_services:
            by_layer[layer_name] = {
                "status": layer_status if any(s["missing"] for s in layer_services.values()) else "valid",
                "services": layer_services,
            }
    
    return {
        "by_layer": by_layer,
        "by_service": by_service,
        "summary": {
            "total_required": len(all_required),
            "valid": total_valid,
            "missing": total_missing,
        },
    }


def check_aws_credentials(credentials: dict) -> dict:
    """
    Main entry point. Validates AWS credentials against ALL required permissions.
    
    Args:
        credentials: Dict with aws_access_key_id, aws_secret_access_key, aws_region, 
                     and optionally aws_session_token
    
    Returns:
        Dict with status, caller_identity, and permission results by layer and service
    """
    result = {
        "status": "invalid",
        "message": "",
        "caller_identity": None,
        "can_list_policies": False,
        "missing_check_permission": None,
        "by_layer": {},
        "by_service": {},
        "summary": {"total_required": 0, "valid": 0, "missing": 0},
    }
    
    # Validate required fields
    if not credentials.get("aws_access_key_id") or not credentials.get("aws_secret_access_key"):
        result["message"] = "Missing required credentials: aws_access_key_id and aws_secret_access_key"
        return result
    
    try:
        # Create session
        session = _create_session(credentials)
        sts_client = session.client("sts")
        iam_client = session.client("iam")
        
        # Step 1: Validate credentials with GetCallerIdentity
        try:
            caller_identity = _get_caller_identity(sts_client)
            result["caller_identity"] = caller_identity
        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            if error_code in ("InvalidClientTokenId", "SignatureDoesNotMatch"):
                result["message"] = "Invalid credentials: access key or secret key is incorrect"
            elif error_code == "ExpiredToken":
                result["message"] = "Credentials have expired (session token may be expired)"
            else:
                result["message"] = f"Failed to validate credentials: {error_code}"
            return result
        except NoCredentialsError:
            result["message"] = "No credentials provided"
            return result
        
        # Step 2: Get permissions from attached policies
        available_permissions, check_error = _get_attached_permissions(iam_client, caller_identity)
        
        if check_error:
            principal_type = caller_identity["principal_type"]
            # Determine which permissions are needed based on principal type
            if principal_type in ("role", "assumed-role"):
                needed_permissions = SELF_CHECK_PERMISSIONS["role"]
            else:
                needed_permissions = SELF_CHECK_PERMISSIONS["user"]
            
            result["status"] = "check_failed"
            result["message"] = (
                f"Cannot determine permissions - credentials lack '{check_error}' to inspect their own policies. "
                f"Add the self-check permissions to your IAM policy, or use our ready-to-use policy from the docs."
            )
            result["missing_check_permission"] = check_error
            result["can_list_policies"] = False
            result["self_check_help"] = {
                "principal_type": principal_type,
                "required_permissions": needed_permissions,
                "policy_json_url": "/docs/references/aws_deployer_policy.json",
                "docs_url": "/docs/docs-credentials-setup.html#aws-setup",
                "hint": f"Your IAM {principal_type} needs permissions to read its own attached policies."
            }
            return result

        
        result["can_list_policies"] = True
        
        # Step 3: Compare against required permissions
        required = _get_all_required_permissions()
        comparison = _compare_permissions(available_permissions, required)
        
        result["by_layer"] = comparison["by_layer"]
        result["by_service"] = comparison["by_service"]
        result["summary"] = comparison["summary"]
        
        # Determine overall status
        if comparison["summary"]["missing"] == 0:
            result["status"] = "valid"
            result["message"] = "All required permissions are present."
        elif comparison["summary"]["valid"] > 0:
            result["status"] = "partial"
            result["message"] = f"Some permissions are missing: {comparison['summary']['missing']} of {comparison['summary']['total_required']}"
        else:
            result["status"] = "invalid"
            result["message"] = "No required permissions are present."
        
        return result
        
    except Exception as e:
        result["status"] = "error"
        result["message"] = f"Unexpected error: {str(e)}"
        return result


def check_aws_credentials_from_config(project_name: str = None) -> dict:
    """
    Validate credentials from the project's config_credentials.json.
    
    Args:
        project_name: Optional project name. Uses active project if not specified.
    
    Returns:
        Same format as check_aws_credentials()
    """
    try:
        import src.core.state as state
        
        # Determine project path
        if project_name:
            # Validate project exists
            project_dir = os.path.join(state.get_project_upload_path(), project_name)
            if not os.path.exists(project_dir):
                return {
                    "status": "error",
                    "message": f"Invalid project: Project '{project_name}' does not exist.",
                    "caller_identity": None,
                    "can_list_policies": False,
                    "missing_check_permission": None,
                    "by_layer": {},
                    "by_service": {},
                    "summary": {"total_required": 0, "valid": 0, "missing": 0},
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
                "can_list_policies": False,
                "missing_check_permission": None,
                "by_layer": {},
                "by_service": {},
                "summary": {"total_required": 0, "valid": 0, "missing": 0},
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
                "can_list_policies": False,
                "missing_check_permission": None,
                "by_layer": {},
                "by_service": {},
                "summary": {"total_required": 0, "valid": 0, "missing": 0},
                "project_name": project_name
            }
        
        aws_creds = config_credentials.get("aws", {})
        
        if not aws_creds:
            return {
                "status": "error",
                "message": "No AWS credentials found in config_credentials.json",
                "caller_identity": None,
                "can_list_policies": False,
                "missing_check_permission": None,
                "by_layer": {},
                "by_service": {},
                "summary": {"total_required": 0, "valid": 0, "missing": 0},
                "project_name": project_name
            }
        
        # Check the credentials
        return check_aws_credentials(aws_creds)
        
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to load credentials from config: {str(e)}",
            "caller_identity": None,
            "can_list_policies": False,
            "missing_check_permission": None,
            "by_layer": {},
            "by_service": {},
            "summary": {"total_required": 0, "valid": 0, "missing": 0},
            "project_name": project_name
        }


# Export for use by API and CLI
__all__ = [
    "check_aws_credentials",
    "check_aws_credentials_from_config",
    "REQUIRED_AWS_PERMISSIONS",
]
