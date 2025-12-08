"""
Layer 1 (IoT) Deployment for AWS.

This module handles deployment and destruction of Layer 1 components:
- Dispatcher IAM Role
- Dispatcher Lambda Function  
- IoT Topic Rule

All functions accept provider and config parameters instead of using globals.
"""

import json
import os
import time
from typing import TYPE_CHECKING
from logger import logger
import src.util as util
from botocore.exceptions import ClientError
import src.constants as CONSTANTS

if TYPE_CHECKING:
    from src.providers.aws.provider import AWSProvider
    from src.core.context import ProjectConfig


# ==========================================
# 2. Dispatcher IAM Role
# ==========================================

def create_dispatcher_iam_role(provider: 'AWSProvider') -> None:
    """
    Creates the IAM Role for the L1 Dispatcher Lambda.
    
    Args:
        provider: Initialized AWSProvider with clients and naming
    """
    role_name = provider.naming.dispatcher_iam_role()
    iam_client = provider.clients["iam"]

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

    policy_arns = [
        CONSTANTS.AWS_POLICY_LAMBDA_BASIC_EXECUTION,
        CONSTANTS.AWS_POLICY_LAMBDA_ROLE
    ]

    for policy_arn in policy_arns:
        iam_client.attach_role_policy(RoleName=role_name, PolicyArn=policy_arn)
        logger.info(f"Attached IAM policy ARN: {policy_arn}")

    logger.info("Waiting for propagation...")
    time.sleep(20)


def destroy_dispatcher_iam_role(provider: 'AWSProvider') -> None:
    """
    Destroys the IAM Role for the L1 Dispatcher Lambda.
    
    Args:
        provider: Initialized AWSProvider with clients and naming
    """
    role_name = provider.naming.dispatcher_iam_role()
    iam_client = provider.clients["iam"]

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

        # Delete the role
        iam_client.delete_role(RoleName=role_name)
        logger.info(f"Deleted IAM role: {role_name}")
    except ClientError as e:
        if e.response["Error"]["Code"] != "NoSuchEntity":
            raise


# ==========================================
# 3. Dispatcher Lambda Function
# ==========================================

def create_dispatcher_lambda_function(
    provider: 'AWSProvider',
    config: 'ProjectConfig',
    project_path: str
) -> None:
    """
    Creates the L1 Dispatcher Lambda Function.
    
    Args:
        provider: Initialized AWSProvider with clients and naming
        config: ProjectConfig with digital_twin_name and providers
        project_path: Path to project directory for Lambda source code
    """
    function_name = provider.naming.dispatcher_lambda_function()
    role_name = provider.naming.dispatcher_iam_role()
    iam_client = provider.clients["iam"]
    lambda_client = provider.clients["lambda"]

    response = iam_client.get_role(RoleName=role_name)
    role_arn = response['Role']['Arn']

    # Determine target function suffix based on L2 provider
    l2_provider = config.providers.get("layer_2_provider", "aws")
    target_suffix = "-connector" if l2_provider != "aws" else "-processor"

    # Build digital twin info for Lambda environment
    digital_twin_info = {
        "config": {
            "digital_twin_name": config.digital_twin_name,
            "hot_storage_size_in_days": config.hot_storage_size_in_days,
            "cold_storage_size_in_days": config.cold_storage_size_in_days,
            "mode": config.mode,
        },
        "config_iot_devices": config.iot_devices,
        "config_events": config.events
    }

    # Lambda source path
    core_lambda_dir = os.path.join(project_path, CONSTANTS.AWS_CORE_LAMBDA_DIR_NAME)

    lambda_client.create_function(
        FunctionName=function_name,
        Runtime="python3.13",
        Role=role_arn,
        Handler="lambda_function.lambda_handler",
        Code={"ZipFile": util.compile_lambda_function(os.path.join(core_lambda_dir, "dispatcher"))},
        Description="Core Dispatcher Function for Layer 1 Data Acquisition",
        Timeout=3,
        MemorySize=128,
        Publish=True,
        Environment={
            "Variables": {
                "DIGITAL_TWIN_INFO": json.dumps(digital_twin_info),
                "TARGET_FUNCTION_SUFFIX": target_suffix
            }
        }
    )

    logger.info(f"Created Lambda function: {function_name}")


def destroy_dispatcher_lambda_function(provider: 'AWSProvider') -> None:
    """
    Destroys the L1 Dispatcher Lambda Function.
    
    Args:
        provider: Initialized AWSProvider with clients and naming
    """
    function_name = provider.naming.dispatcher_lambda_function()
    lambda_client = provider.clients["lambda"]

    try:
        lambda_client.delete_function(FunctionName=function_name)
        logger.info(f"Deleted Lambda function: {function_name}")
    except ClientError as e:
        if e.response["Error"]["Code"] != "ResourceNotFoundException":
            raise


# ==========================================
# 4. Dispatcher IoT Rule
# ==========================================

def create_dispatcher_iot_rule(provider: 'AWSProvider', config: 'ProjectConfig') -> None:
    """
    Creates the IoT Topic Rule that triggers the Dispatcher.
    
    Args:
        provider: Initialized AWSProvider with clients and naming
        config: ProjectConfig with digital_twin_name
    """
    rule_name = provider.naming.dispatcher_iot_rule()
    function_name = provider.naming.dispatcher_lambda_function()
    lambda_client = provider.clients["lambda"]
    iot_client = provider.clients["iot"]
    sts_client = provider.clients["sts"]

    sql = f"SELECT * FROM '{config.digital_twin_name}/iot-data'"

    response = lambda_client.get_function(FunctionName=function_name)
    function_arn = response['Configuration']['FunctionArn']

    iot_client.create_topic_rule(
        ruleName=rule_name,
        topicRulePayload={
            "sql": sql,
            "description": "Routes all Digital Twin IoT data to the Dispatcher Lambda",
            "actions": [{"lambda": {"functionArn": function_arn}}],
            "ruleDisabled": False
        }
    )

    logger.info(f"Created IoT rule: {rule_name}")

    region = iot_client.meta.region_name
    account_id = sts_client.get_caller_identity()['Account']

    lambda_client.add_permission(
        FunctionName=function_name,
        StatementId="iot-invoke",
        Action="lambda:InvokeFunction",
        Principal="iot.amazonaws.com",
        SourceArn=f"arn:aws:iot:{region}:{account_id}:rule/{rule_name}"
    )

    logger.info("Added permission to Lambda function so the rule can invoke the function.")


def destroy_dispatcher_iot_rule(provider: 'AWSProvider') -> None:
    """
    Destroys the IoT Topic Rule for the Dispatcher.
    
    Args:
        provider: Initialized AWSProvider with clients and naming
    """
    function_name = provider.naming.dispatcher_lambda_function()
    rule_name = provider.naming.dispatcher_iot_rule()
    lambda_client = provider.clients["lambda"]
    iot_client = provider.clients["iot"]

    try:
        lambda_client.remove_permission(FunctionName=function_name, StatementId="iot-invoke")
        logger.info(f"Removed permission from Lambda function: {rule_name}, {function_name}")
    except lambda_client.exceptions.ResourceNotFoundException:
        pass

    # Check if rule exists before deleting
    try:
        iot_client.get_topic_rule(ruleName=rule_name)
        iot_client.delete_topic_rule(ruleName=rule_name)
        logger.info(f"Deleted IoT Rule: {rule_name}")
    except iot_client.exceptions.ResourceNotFoundException:
        pass
