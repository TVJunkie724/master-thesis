"""
Layer 2 (Compute) Deployment for AWS.

This module handles deployment and destruction of Layer 2 components:
- Persister IAM Role and Lambda Function
- Event Checker IAM Role and Lambda (optional)
- Lambda Chain Step Function (optional)
- Event Feedback Lambda (optional)

All functions accept provider and config parameters instead of using globals.
"""

import json
import os
import time
from typing import TYPE_CHECKING
from logger import logger
# util is imported lazily inside functions to avoid circular import
from botocore.exceptions import ClientError
import constants as CONSTANTS

if TYPE_CHECKING:
    from providers.aws.provider import AWSProvider
    from src.core.context import ProjectConfig


# ==========================================
# Helper Functions
# ==========================================

def _get_digital_twin_info(config: 'ProjectConfig') -> dict:
    """Build digital twin info dict for Lambda environment."""
    return {
        "config": {
            "digital_twin_name": config.digital_twin_name,
            "hot_storage_size_in_days": config.hot_storage_size_in_days,
            "cold_storage_size_in_days": config.cold_storage_size_in_days,
            "mode": config.mode,
        },
        "config_iot_devices": config.iot_devices,
        "config_events": config.events
    }


def _destroy_iam_role(provider: 'AWSProvider', role_name: str) -> None:
    """Generic IAM role destruction with policy cleanup."""
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

        iam_client.delete_role(RoleName=role_name)
        logger.info(f"Deleted IAM role: {role_name}")
    except ClientError as e:
        if e.response["Error"]["Code"] != "NoSuchEntity":
            raise


# ==========================================
# 2. Persister IAM Role
# ==========================================

def create_persister_iam_role(provider: 'AWSProvider') -> None:
    """Creates the IAM Role for the L2 Persister Lambda."""
    role_name = provider.naming.persister_iam_role()
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
        CONSTANTS.AWS_POLICY_LAMBDA_ROLE,
        CONSTANTS.AWS_POLICY_DYNAMODB_FULL_ACCESS
    ]
    for policy_arn in policy_arns:
        iam_client.attach_role_policy(RoleName=role_name, PolicyArn=policy_arn)
        logger.info(f"Attached IAM policy ARN: {policy_arn}")

    logger.info("Waiting for propagation...")
    time.sleep(20)


def destroy_persister_iam_role(provider: 'AWSProvider') -> None:
    """Destroys the Persister IAM Role."""
    _destroy_iam_role(provider, provider.naming.persister_iam_role())


# ==========================================
# 3. Persister Lambda Function
# ==========================================

def create_persister_lambda_function(
    provider: 'AWSProvider',
    config: 'ProjectConfig',
    project_path: str
) -> None:
    """Creates the L2 Persister Lambda Function."""
    function_name = provider.naming.persister_lambda_function()
    role_name = provider.naming.persister_iam_role()
    iam_client = provider.clients["iam"]
    lambda_client = provider.clients["lambda"]

    response = iam_client.get_role(RoleName=role_name)
    role_arn = response['Role']['Arn']

    core_lambda_dir = os.path.join(project_path, CONSTANTS.AWS_CORE_LAMBDA_DIR_NAME)

    import util  # Lazy import to avoid circular dependency
    lambda_client.create_function(
        FunctionName=function_name,
        Runtime="python3.13",
        Role=role_arn,
        Handler="lambda_function.lambda_handler",
        Code={"ZipFile": util.compile_lambda_function(os.path.join(core_lambda_dir, "persister"))},
        Description="L2 Persister: Writes data to storage",
        Timeout=3,
        MemorySize=128,
        Publish=True,
        Environment={
            "Variables": {
                "DIGITAL_TWIN_INFO": json.dumps(_get_digital_twin_info(config)),
                "DYNAMODB_TABLE_NAME": provider.naming.hot_dynamodb_table(),
                "EVENT_CHECKER_LAMBDA_NAME": provider.naming.event_checker_lambda_function(),
                "USE_EVENT_CHECKING": str(config.is_optimization_enabled("useEventChecking")).lower()
            }
        }
    )
    logger.info(f"Created Lambda function: {function_name}")


def destroy_persister_lambda_function(provider: 'AWSProvider') -> None:
    """Destroys the Persister Lambda Function."""
    function_name = provider.naming.persister_lambda_function()
    try:
        provider.clients["lambda"].delete_function(FunctionName=function_name)
        logger.info(f"Deleted Lambda function: {function_name}")
    except ClientError as e:
        if e.response["Error"]["Code"] != "ResourceNotFoundException":
            raise


# ==========================================
# 4. Event Checker IAM Role
# ==========================================

def create_event_checker_iam_role(provider: 'AWSProvider') -> None:
    """Creates the IAM Role for the L2 Event Checker Lambda."""
    role_name = provider.naming.event_checker_iam_role()
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
        CONSTANTS.AWS_POLICY_LAMBDA_ROLE,
        CONSTANTS.AWS_POLICY_DYNAMODB_FULL_ACCESS,
        CONSTANTS.AWS_POLICY_LAMBDA_READ_ONLY,
        CONSTANTS.AWS_POLICY_STEP_FUNCTIONS_FULL_ACCESS
    ]
    for policy_arn in policy_arns:
        iam_client.attach_role_policy(RoleName=role_name, PolicyArn=policy_arn)
        logger.info(f"Attached IAM policy ARN: {policy_arn}")

    # Inline Policy for TwinMaker Access
    iam_client.put_role_policy(
        RoleName=role_name,
        PolicyName="TwinmakerAccess",
        PolicyDocument=json.dumps({
            "Version": "2012-10-17",
            "Statement": [
                {"Effect": "Allow", "Action": "iottwinmaker:ListWorkspaces", "Resource": "*"},
                {"Effect": "Allow", "Action": ["iottwinmaker:*"], "Resource": "*"},
                {"Effect": "Allow", "Action": ["dynamodb:*"], "Resource": "*"},
                {"Effect": "Allow", "Action": ["s3:*"], "Resource": "*"}
            ]
        })
    )
    logger.info("Attached inline IAM policy: TwinmakerAccess")
    logger.info("Waiting for propagation...")
    time.sleep(20)


def destroy_event_checker_iam_role(provider: 'AWSProvider') -> None:
    """Destroys the Event Checker IAM Role."""
    _destroy_iam_role(provider, provider.naming.event_checker_iam_role())


# ==========================================
# 5. Event Checker Lambda Function
# ==========================================

def create_event_checker_lambda_function(
    provider: 'AWSProvider',
    config: 'ProjectConfig',
    project_path: str
) -> None:
    """Creates the L2 Event Checker Lambda Function."""
    function_name = provider.naming.event_checker_lambda_function()
    role_name = provider.naming.event_checker_iam_role()
    iam_client = provider.clients["iam"]
    lambda_client = provider.clients["lambda"]
    sts_client = provider.clients["sts"]

    response = iam_client.get_role(RoleName=role_name)
    role_arn = response['Role']['Arn']

    # Get Lambda Chain ARN if enabled
    lambda_chain_arn = "NONE"
    if config.is_optimization_enabled("triggerNotificationWorkflow") and config.is_optimization_enabled("useEventChecking"):
        region = lambda_client.meta.region_name
        account_id = sts_client.get_caller_identity()['Account']
        lambda_chain_name = provider.naming.lambda_chain_step_function()
        lambda_chain_arn = f"arn:aws:states:{region}:{account_id}:stateMachine:{lambda_chain_name}"

    # Get Event Feedback ARN if enabled
    event_feedback_arn = "NONE"
    if config.is_optimization_enabled("returnFeedbackToDevice") and config.is_optimization_enabled("useEventChecking"):
        try:
            response = lambda_client.get_function(FunctionName=provider.naming.event_feedback_lambda_function())
            event_feedback_arn = response["Configuration"]["FunctionArn"]
        except Exception as e:
            logger.warning(f"Could not retrieve Event Feedback Lambda ARN: {e}")
            event_feedback_arn = "UNKNOWN"

    core_lambda_dir = os.path.join(project_path, CONSTANTS.AWS_CORE_LAMBDA_DIR_NAME)

    import util  # Lazy import to avoid circular dependency
    lambda_client.create_function(
        FunctionName=function_name,
        Runtime="python3.13",
        Role=role_arn,
        Handler="lambda_function.lambda_handler",
        Code={"ZipFile": util.compile_lambda_function(os.path.join(core_lambda_dir, "event-checker"))},
        Description="L2 Event Checker: Evaluates data against rules",
        Timeout=3,
        MemorySize=128,
        Publish=True,
        Environment={
            "Variables": {
                "DIGITAL_TWIN_INFO": json.dumps(_get_digital_twin_info(config)),
                "TWINMAKER_WORKSPACE_NAME": provider.naming.twinmaker_workspace(),
                "LAMBDA_CHAIN_STEP_FUNCTION_ARN": lambda_chain_arn,
                "EVENT_FEEDBACK_LAMBDA_FUNCTION_ARN": event_feedback_arn,
                "USE_STEP_FUNCTIONS": str(config.is_optimization_enabled("triggerNotificationWorkflow")).lower(),
                "USE_FEEDBACK": str(config.is_optimization_enabled("returnFeedbackToDevice")).lower()
            }
        }
    )
    logger.info(f"Created Lambda function: {function_name}")


def destroy_event_checker_lambda_function(provider: 'AWSProvider') -> None:
    """Destroys the Event Checker Lambda Function."""
    function_name = provider.naming.event_checker_lambda_function()
    try:
        provider.clients["lambda"].delete_function(FunctionName=function_name)
        logger.info(f"Deleted Lambda function: {function_name}")
    except ClientError as e:
        if e.response["Error"]["Code"] != "ResourceNotFoundException":
            raise


# ==========================================
# 6. Lambda Chain (Step Function) Role
# ==========================================

def create_lambda_chain_iam_role(provider: 'AWSProvider') -> None:
    """Creates the IAM Role for the Step Function State Machine."""
    role_name = provider.naming.lambda_chain_iam_role()
    iam_client = provider.clients["iam"]

    iam_client.create_role(
        RoleName=role_name,
        AssumeRolePolicyDocument=json.dumps({
            "Version": "2012-10-17",
            "Statement": [{
                "Effect": "Allow",
                "Principal": {"Service": "states.amazonaws.com"},
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


def destroy_lambda_chain_iam_role(provider: 'AWSProvider') -> None:
    """Destroys the Lambda Chain IAM Role."""
    _destroy_iam_role(provider, provider.naming.lambda_chain_iam_role())


# ==========================================
# 7. Lambda Chain (Step Function)
# ==========================================

def create_lambda_chain_step_function(provider: 'AWSProvider', upload_path: str) -> None:
    """Creates the Step Function State Machine."""
    sf_name = provider.naming.lambda_chain_step_function()
    role_name = provider.naming.lambda_chain_iam_role()
    iam_client = provider.clients["iam"]
    sf_client = provider.clients["stepfunctions"]

    response = iam_client.get_role(RoleName=role_name)
    role_arn = response["Role"]["Arn"]

    # Read definition from file
    sf_dir = os.path.join(upload_path, CONSTANTS.STATE_MACHINES_DIR_NAME)
    sf_def_path = os.path.join(sf_dir, CONSTANTS.AWS_STATE_MACHINE_FILE)

    if not os.path.exists(sf_def_path):
        sf_def_path = os.path.join(upload_path, CONSTANTS.AWS_STATE_MACHINE_FILE)

    if not os.path.exists(sf_def_path):
        raise FileNotFoundError(
            f"State machine definition not found. Please ensure '{CONSTANTS.AWS_STATE_MACHINE_FILE}' "
            f"exists in the '{CONSTANTS.STATE_MACHINES_DIR_NAME}/' folder."
        )

    with open(sf_def_path, 'r') as f:
        definition = f.read()

    sf_client.create_state_machine(name=sf_name, roleArn=role_arn, definition=definition)
    logger.info(f"Created Step Function: {sf_name}")


def destroy_lambda_chain_step_function(provider: 'AWSProvider') -> None:
    """Destroys the Lambda Chain Step Function."""
    sf_name = provider.naming.lambda_chain_step_function()
    lambda_client = provider.clients["lambda"]
    sts_client = provider.clients["sts"]
    sf_client = provider.clients["stepfunctions"]

    region = lambda_client.meta.region_name
    account_id = sts_client.get_caller_identity()['Account']
    sf_arn = f"arn:aws:states:{region}:{account_id}:stateMachine:{sf_name}"

    try:
        sf_client.describe_state_machine(stateMachineArn=sf_arn)
    except ClientError as e:
        if e.response["Error"]["Code"] == "StateMachineDoesNotExist":
            return

    sf_client.delete_state_machine(stateMachineArn=sf_arn)
    logger.info(f"Deletion of Step Function initiated: {sf_name}")

    while True:
        try:
            sf_client.describe_state_machine(stateMachineArn=sf_arn)
            time.sleep(2)
        except ClientError as e:
            if e.response["Error"]["Code"] == "StateMachineDoesNotExist":
                break
            raise

    logger.info(f"Deleted Step Function: {sf_name}")


# ==========================================
# 8. Event Feedback IAM Role
# ==========================================

def create_event_feedback_iam_role(provider: 'AWSProvider') -> None:
    """Creates the IAM Role for the Event Feedback Lambda."""
    role_name = provider.naming.event_feedback_iam_role()
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
        CONSTANTS.AWS_POLICY_IOT_DATA_ACCESS
    ]
    for policy_arn in policy_arns:
        iam_client.attach_role_policy(RoleName=role_name, PolicyArn=policy_arn)
        logger.info(f"Attached IAM policy ARN: {policy_arn}")

    logger.info("Waiting for propagation...")
    time.sleep(20)


def destroy_event_feedback_iam_role(provider: 'AWSProvider') -> None:
    """Destroys the Event Feedback IAM Role."""
    _destroy_iam_role(provider, provider.naming.event_feedback_iam_role())


# ==========================================
# 9. Event Feedback Lambda Function
# ==========================================

def create_event_feedback_lambda_function(
    provider: 'AWSProvider',
    config: 'ProjectConfig',
    upload_path: str
) -> None:
    """Creates the Event Feedback Lambda Function."""
    function_name = provider.naming.event_feedback_lambda_function()
    role_name = provider.naming.event_feedback_iam_role()
    iam_client = provider.clients["iam"]
    lambda_client = provider.clients["lambda"]

    response = iam_client.get_role(RoleName=role_name)
    role_arn = response["Role"]["Arn"]

    lambda_dir = os.path.join(upload_path, CONSTANTS.LAMBDA_FUNCTIONS_DIR_NAME, "event-feedback")

    import util  # Lazy import to avoid circular dependency
    lambda_client.create_function(
        FunctionName=function_name,
        Runtime="python3.13",
        Role=role_arn,
        Handler="lambda_function.lambda_handler",
        Code={"ZipFile": util.compile_lambda_function(lambda_dir)},
        Description="User Defined Event Feedback Function",
        Timeout=3,
        MemorySize=128,
        Publish=True,
        Environment={
            "Variables": {
                "DIGITAL_TWIN_INFO": json.dumps(_get_digital_twin_info(config))
            }
        }
    )
    logger.info(f"Created Lambda function: {function_name}")


def destroy_event_feedback_lambda_function(provider: 'AWSProvider') -> None:
    """Destroys the Event Feedback Lambda Function."""
    function_name = provider.naming.event_feedback_lambda_function()
    try:
        provider.clients["lambda"].delete_function(FunctionName=function_name)
        logger.info(f"Deleted Lambda function: {function_name}")
    except ClientError as e:
        if e.response["Error"]["Code"] != "ResourceNotFoundException":
            raise
