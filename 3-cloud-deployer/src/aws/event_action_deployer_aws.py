"""
AWS Event Action Deployer - Lambda Actions for Events.

This module handles deployment of Lambda functions that are triggered by events.
Each event can have an associated Lambda action (function) that is auto-deployed.

Migration Status:
    - Supports both legacy (globals-based) and new (provider-based) calling patterns.
    - Provider parameter is optional for backward compatibility.
"""

import json
import os
import time
from typing import TYPE_CHECKING, Optional
from logger import logger
from botocore.exceptions import ClientError
import constants as CONSTANTS

if TYPE_CHECKING:
    from src.providers.aws.provider import AWSProvider
    from src.core.context import DeploymentContext


def _get_legacy_context():
    """Get clients and config from globals for legacy compatibility."""
    import globals
    import aws.globals_aws as globals_aws
    
    return {
        "iam_client": globals_aws.aws_iam_client,
        "lambda_client": globals_aws.aws_lambda_client,
        "events": globals.config_events,
        "digital_twin_info": globals.digital_twin_info(),
        "project_path": globals.get_project_upload_path(),
    }


def create_iam_role(
    role_name: str,
    provider: Optional['AWSProvider'] = None
) -> None:
    """Create IAM role for an event action Lambda.
    
    Args:
        role_name: Name for the IAM role
        provider: Optional AWSProvider. If None, uses globals.
    """
    if provider:
        iam_client = provider.clients["iam"]
    else:
        iam_client = _get_legacy_context()["iam_client"]
    
    iam_client.create_role(
        RoleName=role_name,
        AssumeRolePolicyDocument=json.dumps({
            "Version": "2012-10-17",
            "Statement": [{
                "Effect": "Allow",
                "Principal": {"Service": "lambda.amazonaws.com"},
                "Action": "sts:AssumeRole"
            }]
        })
    )
    logger.info(f"Created IAM role: {role_name}")
    
    policy_arns = [CONSTANTS.AWS_POLICY_LAMBDA_BASIC_EXECUTION]
    
    for policy_arn in policy_arns:
        iam_client.attach_role_policy(RoleName=role_name, PolicyArn=policy_arn)
        logger.info(f"Attached IAM policy ARN: {policy_arn}")


def destroy_iam_role(
    role_name: str,
    provider: Optional['AWSProvider'] = None
) -> None:
    """Destroy IAM role for an event action Lambda.
    
    Args:
        role_name: Name of the IAM role to delete
        provider: Optional AWSProvider. If None, uses globals.
    """
    if provider:
        iam_client = provider.clients["iam"]
    else:
        iam_client = _get_legacy_context()["iam_client"]
    
    try:
        # Detach managed policies
        response = iam_client.list_attached_role_policies(RoleName=role_name)
        for policy in response["AttachedPolicies"]:
            iam_client.detach_role_policy(RoleName=role_name, PolicyArn=policy["PolicyArn"])
        
        # Delete inline policies
        response = iam_client.list_role_policies(RoleName=role_name)
        for policy_name in response["PolicyNames"]:
            iam_client.delete_role_policy(RoleName=role_name, PolicyName=policy_name)
        
        # Remove from instance profiles
        response = iam_client.list_instance_profiles_for_role(RoleName=role_name)
        for profile in response["InstanceProfiles"]:
            iam_client.remove_role_from_instance_profile(
                InstanceProfileName=profile["InstanceProfileName"],
                RoleName=role_name
            )
        
        iam_client.delete_role(RoleName=role_name)
        logger.info(f"Deleted IAM role: {role_name}")
    except ClientError as e:
        if e.response["Error"]["Code"] != "NoSuchEntity":
            raise


def info_iam_role(
    role_name: str,
    provider: Optional['AWSProvider'] = None
) -> None:
    """Print status of an IAM role.
    
    Args:
        role_name: Name of the IAM role
        provider: Optional AWSProvider. If None, uses globals.
    """
    import aws.util_aws as util_aws
    
    if provider:
        iam_client = provider.clients["iam"]
    else:
        iam_client = _get_legacy_context()["iam_client"]
    
    try:
        iam_client.get_role(RoleName=role_name)
        logger.info(f"✅ IAM Role exists: {role_name} {util_aws.link_to_iam_role(role_name)}")
    except ClientError as e:
        if e.response["Error"]["Code"] == "NoSuchEntity":
            logger.info(f"❌ IAM Role missing: {role_name}")
        else:
            raise


def create_lambda_function(
    function_name: str,
    provider: Optional['AWSProvider'] = None,
    project_path: str = None,
    digital_twin_info: dict = None
) -> None:
    """Create Lambda function for an event action.
    
    Args:
        function_name: Name for the Lambda function
        provider: Optional AWSProvider. If None, uses globals.
        project_path: Path to project directory. Required if provider is set.
        digital_twin_info: Digital twin configuration. Required if provider is set.
    """
    import util
    
    if provider:
        iam_client = provider.clients["iam"]
        lambda_client = provider.clients["lambda"]
    else:
        ctx = _get_legacy_context()
        iam_client = ctx["iam_client"]
        lambda_client = ctx["lambda_client"]
        project_path = ctx["project_path"]
        digital_twin_info = ctx["digital_twin_info"]
    
    role_name = function_name
    response = iam_client.get_role(RoleName=role_name)
    role_arn = response['Role']['Arn']
    
    lambda_dir = os.path.join(project_path, CONSTANTS.EVENT_ACTIONS_DIR_NAME, function_name)
    
    lambda_client.create_function(
        FunctionName=function_name,
        Runtime="python3.13",
        Role=role_arn,
        Handler="lambda_function.lambda_handler",
        Code={"ZipFile": util.compile_lambda_function(lambda_dir)},
        Description="Event action Lambda function",
        Timeout=3,
        MemorySize=128,
        Publish=True,
        Environment={
            "Variables": {
                "DIGITAL_TWIN_INFO": json.dumps(digital_twin_info)
            }
        }
    )
    logger.info(f"Created Lambda function: {function_name}")


def destroy_lambda_function(
    function_name: str,
    provider: Optional['AWSProvider'] = None
) -> None:
    """Destroy Lambda function for an event action.
    
    Args:
        function_name: Name of the Lambda function to delete
        provider: Optional AWSProvider. If None, uses globals.
    """
    if provider:
        lambda_client = provider.clients["lambda"]
    else:
        lambda_client = _get_legacy_context()["lambda_client"]
    
    try:
        lambda_client.delete_function(FunctionName=function_name)
        logger.info(f"Deleted Lambda function: {function_name}")
    except ClientError as e:
        if e.response["Error"]["Code"] != "ResourceNotFoundException":
            raise


def info_lambda_function(
    function_name: str,
    provider: Optional['AWSProvider'] = None
) -> None:
    """Print status of a Lambda function.
    
    Args:
        function_name: Name of the Lambda function
        provider: Optional AWSProvider. If None, uses globals.
    """
    import aws.util_aws as util_aws
    
    if provider:
        lambda_client = provider.clients["lambda"]
    else:
        lambda_client = _get_legacy_context()["lambda_client"]
    
    try:
        lambda_client.get_function(FunctionName=function_name)
        logger.info(f"✅ Lambda Function exists: {function_name} {util_aws.link_to_lambda_function(function_name)}")
    except ClientError as e:
        if e.response["Error"]["Code"] == "ResourceNotFoundException":
            logger.info(f"❌ Lambda Function missing: {function_name}")
        else:
            raise


# ==========================================
# High-level deployment functions
# ==========================================

def deploy_lambda_actions(
    provider: Optional['AWSProvider'] = None,
    events: list = None,
    project_path: str = None,
    digital_twin_info: dict = None
) -> None:
    """Deploy all Lambda actions defined in events config.
    
    Args:
        provider: Optional AWSProvider. If None, uses globals.
        events: List of event configurations. If None, reads from globals.
        project_path: Path to project directory.
        digital_twin_info: Digital twin configuration.
    """
    if events is None:
        import globals
        events = globals.config_events
    
    for event in events:
        action = event.get("action", {})
        if action.get("type") == "lambda" and action.get("autoDeploy", True):
            function_name = action["functionName"]
            create_iam_role(function_name, provider)
            
            logger.info("Waiting for propagation...")
            time.sleep(20)
            
            create_lambda_function(function_name, provider, project_path, digital_twin_info)


def destroy_lambda_actions(
    provider: Optional['AWSProvider'] = None,
    events: list = None
) -> None:
    """Destroy all Lambda actions defined in events config.
    
    Args:
        provider: Optional AWSProvider. If None, uses globals.
        events: List of event configurations. If None, reads from globals.
    """
    if events is None:
        import globals
        events = globals.config_events
    
    for event in events:
        action = event.get("action", {})
        if action.get("type") == "lambda" and action.get("autoDeploy", True):
            function_name = action["functionName"]
            destroy_lambda_function(function_name, provider)
            destroy_iam_role(function_name, provider)


def info_lambda_actions(
    provider: Optional['AWSProvider'] = None,
    events: list = None
) -> None:
    """Print status of all Lambda actions defined in events config.
    
    Args:
        provider: Optional AWSProvider. If None, uses globals.
        events: List of event configurations. If None, reads from globals.
    """
    if events is None:
        import globals
        events = globals.config_events
    
    for event in events:
        action = event.get("action", {})
        if action.get("type") == "lambda" and action.get("autoDeploy", True):
            function_name = action["functionName"]
            info_iam_role(function_name, provider)
            info_lambda_function(function_name, provider)
