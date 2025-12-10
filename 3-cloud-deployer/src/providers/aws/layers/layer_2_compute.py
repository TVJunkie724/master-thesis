"""
Layer 2 (Compute) Deployment for AWS.

This module handles deployment and destruction of Layer 2 components:
- Persister IAM Role and Lambda Function
- Event Checker IAM Role and Lambda (optional)
- Lambda Chain Step Function (optional)
- Event Feedback Lambda (optional)

All functions accept provider and config parameters explicitly.
"""

import json
import os
import time
from typing import TYPE_CHECKING
from logger import logger
# util is imported lazily inside functions to avoid circular import
from botocore.exceptions import ClientError
import constants as CONSTANTS
import src.providers.aws.util_aws as util_aws

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
        "config_events": config.events,
        "config_providers": config.providers  # Multi-cloud: provider mapping for dual validation
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

    # Build environment variables
    env_vars = {
        "DIGITAL_TWIN_INFO": json.dumps(_get_digital_twin_info(config)),
        "DYNAMODB_TABLE_NAME": provider.naming.hot_dynamodb_table(),
        "EVENT_CHECKER_LAMBDA_NAME": provider.naming.event_checker_lambda_function(),
        "USE_EVENT_CHECKING": str(config.is_optimization_enabled("useEventChecking")).lower()
    }
    
    # Multi-cloud: Add remote writer URL if L3 is on different cloud
    # NOTE: No fallbacks - missing provider config is a critical error
    l2_provider = config.providers["layer_2_provider"]
    l3_provider = config.providers["layer_3_hot_provider"]
    
    if l3_provider != l2_provider:
        inter_cloud = getattr(config, 'inter_cloud', None) or {}
        connections = inter_cloud.get("connections", {})
        conn_id = f"{l2_provider}_l2_to_{l3_provider}_l3"
        conn = connections.get(conn_id, {})
        url = conn.get("url", "")
        token = conn.get("token", "")
        
        # Validate configuration at deployment time
        if not url or not token:
            raise ValueError(
                f"Multi-cloud config incomplete for {conn_id}: url={bool(url)}, token={bool(token)}. "
                f"Check config_inter_cloud.json."
            )
        
        env_vars["REMOTE_WRITER_URL"] = url
        env_vars["INTER_CLOUD_TOKEN"] = token
        logger.info(f"Multi-cloud mode: Persister will POST to {l3_provider} Writer")

    import src.util as util  # Lazy import to avoid circular dependency
    lambda_client.create_function(
        FunctionName=function_name,
        Runtime="python3.13",
        Role=role_arn,
        Handler="lambda_function.lambda_handler",
        Code={"ZipFile": util.compile_lambda_function(os.path.join(core_lambda_dir, "persister"))},
        Description="L2 Persister: Writes data to storage",
        Timeout=30,  # Increased for remote HTTP calls
        MemorySize=128,
        Publish=True,
        Environment={"Variables": env_vars}
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
# 3.5. Ingestion Lambda (Multi-Cloud Only)
# ==========================================
# Ingestion is deployed when L1 is on a DIFFERENT cloud.
# It receives data FROM remote Connectors via HTTP POST.

def create_ingestion_iam_role(provider: 'AWSProvider') -> None:
    """Creates IAM Role for the Ingestion Lambda (multi-cloud only).
    
    Ingestion needs:
    - Lambda invoke permission (to call local Persister)
    - Basic execution role
    """
    role_name = provider.naming.ingestion_iam_role()
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

    # Attach basic execution policy
    iam_client.attach_role_policy(
        RoleName=role_name,
        PolicyArn=CONSTANTS.AWS_POLICY_LAMBDA_BASIC_EXECUTION
    )
    logger.info(f"Attached Lambda basic execution policy to {role_name}")


def destroy_ingestion_iam_role(provider: 'AWSProvider') -> None:
    """Destroys the Ingestion IAM Role."""
    _destroy_iam_role(provider, provider.naming.ingestion_iam_role())


def create_ingestion_lambda_function(
    provider: 'AWSProvider',
    config: 'ProjectConfig',
    project_path: str
) -> str:
    """Creates the Ingestion Lambda Function with Function URL (multi-cloud only).
    
    Returns the Function URL endpoint for configuration.
    """
    function_name = provider.naming.ingestion_lambda_function()
    role_name = provider.naming.ingestion_iam_role()
    iam_client = provider.clients["iam"]
    lambda_client = provider.clients["lambda"]

    # Get role ARN
    response = iam_client.get_role(RoleName=role_name)
    role_arn = response['Role']['Arn']

    # Get expected token from inter-cloud config
    inter_cloud = getattr(config, 'inter_cloud', None) or {}
    expected_token = inter_cloud.get("expected_token", "")
    
    if not expected_token:
        raise ValueError(
            "Multi-cloud config incomplete: expected_token not set in inter_cloud config. "
            "Check config_inter_cloud.json."
        )

    # Prepare environment variables
    env_vars = {
        "DIGITAL_TWIN_INFO": json.dumps(_get_digital_twin_info(config)),
        "PERSISTER_LAMBDA_NAME": provider.naming.persister_lambda_function(),
        "INTER_CLOUD_TOKEN": expected_token  # Token to validate incoming requests
    }

    core_lambda_dir = os.path.join(project_path, CONSTANTS.AWS_CORE_LAMBDA_DIR_NAME)

    import src.util as util  # Lazy import to avoid circular dependency
    lambda_client.create_function(
        FunctionName=function_name,
        Runtime="python3.13",
        Role=role_arn,
        Handler="lambda_function.lambda_handler",
        Code={"ZipFile": util.compile_lambda_function(os.path.join(core_lambda_dir, "ingestion"))},
        Description="Multi-cloud Ingestion: Receives data from remote Connectors",
        Timeout=30,
        MemorySize=128,
        Publish=True,
        Environment={"Variables": env_vars}
    )
    logger.info(f"Created Lambda function: {function_name}")

    # Create Function URL for HTTP access
    url_response = lambda_client.create_function_url_config(
        FunctionName=function_name,
        AuthType='NONE'  # Auth handled by token validation in Lambda code
    )
    function_url = url_response['FunctionUrl']
    logger.info(f"Created Function URL for {function_name}: {function_url}")

    # Add resource-based policy for public access
    lambda_client.add_permission(
        FunctionName=function_name,
        StatementId='FunctionURLPublicAccess',
        Action='lambda:InvokeFunctionUrl',
        Principal='*',
        FunctionUrlAuthType='NONE'
    )
    logger.info(f"Added public access permission to {function_name}")

    return function_url


def destroy_ingestion_lambda_function(provider: 'AWSProvider') -> None:
    """Destroys the Ingestion Lambda Function and its Function URL."""
    function_name = provider.naming.ingestion_lambda_function()
    lambda_client = provider.clients["lambda"]
    
    try:
        # Delete Function URL first
        try:
            lambda_client.delete_function_url_config(FunctionName=function_name)
            logger.info(f"Deleted Function URL for: {function_name}")
        except ClientError as e:
            if e.response["Error"]["Code"] != "ResourceNotFoundException":
                raise
        
        # Delete the function
        lambda_client.delete_function(FunctionName=function_name)
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

    import src.util as util  # Lazy import to avoid circular dependency
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

    import src.util as util  # Lazy import to avoid circular dependency
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


# ==========================================
# 10. Event Action Deployment (Dynamic)
# ==========================================

def create_processor_iam_role(iot_device, provider: 'AWSProvider') -> None:
    """Create IAM Role for Processor Lambda."""
    if provider is None:
        raise ValueError("provider is required")

    iam_client = provider.clients["iam"]
    role_name = provider.naming.processor_iam_role(iot_device["id"])

    iam_client.create_role(
        RoleName=role_name,
        AssumeRolePolicyDocument=json.dumps(
            {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Principal": {
                            "Service": "lambda.amazonaws.com"
                        },
                        "Action": "sts:AssumeRole"
                    }
                ]
            }
        )
    )

    logger.info(f"Created IAM role: {role_name}")

    policy_arns = [
        CONSTANTS.AWS_POLICY_LAMBDA_BASIC_EXECUTION,
        CONSTANTS.AWS_POLICY_LAMBDA_ROLE
    ]

    for policy_arn in policy_arns:
        iam_client.attach_role_policy(
            RoleName=role_name,
            PolicyArn=policy_arn
        )

        logger.info(f"Attached IAM policy ARN: {policy_arn}")

    logger.info(f"Waiting for propagation...")
    time.sleep(10)


def destroy_processor_iam_role(iot_device, provider: 'AWSProvider') -> None:
    """Destroy Processor IAM Role."""
    if provider is None:
        raise ValueError("provider is required")

    _destroy_iam_role(provider, provider.naming.processor_iam_role(iot_device["id"]))


def create_processor_lambda_function(iot_device, provider: 'AWSProvider', config: 'ProjectConfig', project_path: str) -> None:
    """Create Processor (or Connector) Lambda Function."""
    if provider is None:
        raise ValueError("provider is required")
    if config is None:
        raise ValueError("config is required")
    if project_path is None:
        raise ValueError("project_path is required")

    # NOTE: No fallbacks - missing provider config is a critical error
    l1_provider = config.providers["layer_1_provider"]
    l2_provider = config.providers["layer_2_provider"]
    # Inter-cloud connection logic
    # config does not expose "inter_cloud" directly usually?
    # ProjectConfig has `inter_cloud` attribute? Yes, usually loaded from config_inter_cloud.json.
    # Assuming config.inter_cloud is accessible or we load it.
    connections = getattr(config, "config_inter_cloud", {}).get("connections", {}) # Using safety getattr + default
    # But ProjectConfig usually merges them. Let's assume passed config object has it.
    # Actually context.config is ProjectConfig wrapper.
    # If not present, default to empty.
    
    connections = config.inter_cloud.get("connections", {}) if hasattr(config, "inter_cloud") and config.inter_cloud else {}

    twin_info = _get_digital_twin_info(config)

    iam_client = provider.clients["iam"]
    lambda_client = provider.clients["lambda"]
    processor_role_name = provider.naming.processor_iam_role(iot_device["id"])
    connector_func_name = provider.naming.connector_lambda_function(iot_device["id"])
    processor_func_name = provider.naming.processor_lambda_function(iot_device["id"])
    persister_func_name = provider.naming.persister_lambda_function()

    base_path = project_path

    # Scenario 1: L2 is Remote (e.g. AWS -> Azure)
    if l2_provider != "aws":
        function_name = connector_func_name
        role_name = processor_role_name
        
        response = iam_client.get_role(RoleName=role_name)
        role_arn = response['Role']['Arn']
        
        # Connection Info
        conn_id = f"{l1_provider}_l1_to_{l2_provider}_l2"
        conn = connections.get(conn_id, {})
        remote_url = conn.get("url", "")
        token = conn.get("token", "")
        
        if not remote_url or not token:
            raise ValueError(
                f"Multi-cloud config incomplete for {conn_id}: url={bool(remote_url)}, token={bool(token)}. "
                f"Check config_inter_cloud.json for connection '{conn_id}'."
            )
        
        import src.util as util
        
        # NOTE: Lambda dir names from constants
        code_bytes = util.compile_lambda_function(os.path.join(base_path, CONSTANTS.LAMBDA_FUNCTIONS_DIR_NAME, "connector"), project_path=project_path)
            
        lambda_client.create_function(
            FunctionName=function_name,
            Runtime="python3.13",
            Role=role_arn,
            Handler="lambda_function.lambda_handler", 
            Code={"ZipFile": code_bytes},
            Description="Connector to Remote L2",
            Timeout=10, 
            MemorySize=128, 
            Publish=True,
            Environment={
                "Variables": {
                    "REMOTE_INGESTION_URL": remote_url,
                    "INTER_CLOUD_TOKEN": token
                }
            }
        )
        logger.info(f"Created Connector Lambda function: {function_name}")
        
    # Scenario 2: L2 is Local (AWS)
    else:
        function_name = processor_func_name
        role_name = processor_role_name
        
        response = iam_client.get_role(RoleName=role_name)
        role_arn = response['Role']['Arn']
        
        import src.util as util
        
        # Check specific device folder first
        custom_rel_path = f"{CONSTANTS.LAMBDA_FUNCTIONS_DIR_NAME}/processors/{iot_device['iotDeviceId']}/process.py"
        if not os.path.exists(os.path.join(base_path, custom_rel_path)):
            # Check default folder
            custom_rel_path = f"{CONSTANTS.LAMBDA_FUNCTIONS_DIR_NAME}/processors/default_processor/process.py"
        
        wrapper_path = os.path.join(base_path, CONSTANTS.LAMBDA_FUNCTIONS_DIR_NAME, "processor_wrapper")
        
        zip_bytes = util.compile_merged_lambda_function(wrapper_path, custom_rel_path, project_path=project_path)

        lambda_client.create_function(
            FunctionName=function_name,
            Runtime="python3.13",
            Role=role_arn,
            Handler="lambda_function.lambda_handler", 
            Code={"ZipFile": zip_bytes},
            Description="Merged Processor (Wrapper + User Logic)",
            Timeout=3,
            MemorySize=128, 
            Publish=True,
            Environment={
                "Variables": {
                    "DIGITAL_TWIN_INFO": json.dumps(twin_info), 
                    "PERSISTER_LAMBDA_NAME": persister_func_name
                }
            }
        )
        logger.info(f"Created Merged Processor Lambda function: {function_name}")


def destroy_processor_lambda_function(iot_device, provider: 'AWSProvider') -> None:
    """Destroy Processor (or Connector) Lambda."""
    if provider is None:
        raise ValueError("provider is required")

    lambda_client = provider.clients["lambda"]
    processor_func_name = provider.naming.processor_lambda_function(iot_device["id"])
    connector_func_name = provider.naming.connector_lambda_function(iot_device["id"])

    # Try to delete processor lambda
    try:
        lambda_client.delete_function(FunctionName=processor_func_name)
        logger.info(f"Deleted Lambda function: {processor_func_name}")
    except ClientError as e:
        if e.response["Error"]["Code"] != "ResourceNotFoundException":
            raise

    # Also try to delete connector lambda
    try:
        lambda_client.delete_function(FunctionName=connector_func_name)
        logger.info(f"Deleted Lambda function: {connector_func_name}")
    except ClientError as e:
        if e.response["Error"]["Code"] != "ResourceNotFoundException":
            raise


# ==========================================
# 11. Event Action Deployment (Dynamic)
# ==========================================

def create_event_action_iam_role(
    role_name: str,
    provider: 'AWSProvider'
) -> None:
    """Create IAM role for an event action Lambda."""
    if provider is None:
        raise ValueError("provider is required")

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
    
    policy_arns = [CONSTANTS.AWS_POLICY_LAMBDA_BASIC_EXECUTION]
    
    for policy_arn in policy_arns:
        iam_client.attach_role_policy(RoleName=role_name, PolicyArn=policy_arn)
        logger.info(f"Attached IAM policy ARN: {policy_arn}")


def destroy_event_action_iam_role(
    role_name: str,
    provider: 'AWSProvider'
) -> None:
    """Destroy IAM role for an event action Lambda."""
    _destroy_iam_role(provider, role_name)


def info_event_action_iam_role(
    role_name: str,
    provider: 'AWSProvider'
) -> None:
    """Print status of an IAM role."""
    iam_client = provider.clients["iam"]
    try:
        iam_client.get_role(RoleName=role_name)
        logger.info(f"✅ IAM Role exists: {role_name} {_links().link_to_iam_role(role_name, region=provider.region)}")
    except ClientError as e:
        if e.response["Error"]["Code"] == "NoSuchEntity":
            logger.info(f"❌ IAM Role missing: {role_name}")
        else:
            raise


def create_event_action_lambda_function(
    function_name: str,
    provider: 'AWSProvider',
    project_path: str,
    digital_twin_info: dict
) -> None:
    """Create Lambda function for an event action."""
    import src.util as util
    
    iam_client = provider.clients["iam"]
    lambda_client = provider.clients["lambda"]
    
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


def destroy_event_action_lambda_function(
    function_name: str,
    provider: 'AWSProvider'
) -> None:
    """Destroy Lambda function for an event action."""
    lambda_client = provider.clients["lambda"]
    try:
        lambda_client.delete_function(FunctionName=function_name)
        logger.info(f"Deleted Lambda function: {function_name}")
    except ClientError as e:
        if e.response["Error"]["Code"] != "ResourceNotFoundException":
            raise


def info_event_action_lambda_function(
    function_name: str,
    provider: 'AWSProvider'
) -> None:
    """Print status of a Lambda function."""
    lambda_client = provider.clients["lambda"]
    try:
        lambda_client.get_function(FunctionName=function_name)
        logger.info(f"✅ Lambda Function exists: {function_name} {_links().link_to_lambda_function(function_name, region=provider.region)}")
    except ClientError as e:
        if e.response["Error"]["Code"] == "ResourceNotFoundException":
            logger.info(f"❌ Lambda Function missing: {function_name}")
        else:
            raise


def deploy_lambda_actions(
    provider: 'AWSProvider',
    config: 'ProjectConfig',
    project_path: str
) -> None:
    """Deploy all Lambda actions defined in events config."""
    if not config.events:
        return
    
    digital_twin_info = _get_digital_twin_info(config)
    
    for event in config.events:
        action = event.get("action", {})
        if action.get("type") == "lambda" and action.get("autoDeploy", True):
            function_name = action["functionName"]
            create_event_action_iam_role(function_name, provider)
            
            logger.info("Waiting for propagation...")
            time.sleep(20)
            
            create_event_action_lambda_function(function_name, provider, project_path, digital_twin_info)


def destroy_lambda_actions(
    provider: 'AWSProvider',
    config: 'ProjectConfig'
) -> None:
    """Destroy all Lambda actions defined in events config."""
    if not config.events:
        return
    
    for event in config.events:
        action = event.get("action", {})
        if action.get("type") == "lambda" and action.get("autoDeploy", True):
            function_name = action["functionName"]
            destroy_event_action_lambda_function(function_name, provider)
            destroy_event_action_iam_role(function_name, provider)


def info_lambda_actions(
    provider: 'AWSProvider',
    events: list
) -> None:
    """Print status of all Lambda actions defined in events config."""
    if events is None:
        return
    
    for event in events:
        action = event.get("action", {})
        if action.get("type") == "lambda" and action.get("autoDeploy", True):
            function_name = action["functionName"]
            info_event_action_iam_role(function_name, provider)
            info_event_action_lambda_function(function_name, provider)


# ==========================================
# 11. Info / Status Checks
# ==========================================

def _links():
    return util_aws

def check_persister_iam_role(provider: 'AWSProvider'):
    role_name = provider.naming.persister_iam_role()
    client = provider.clients["iam"]
    try:
        client.get_role(RoleName=role_name)
        logger.info(f"✅ Persister IAM Role exists: {_links().link_to_iam_role(role_name, region=provider.region)}")
    except ClientError as e:
        if e.response["Error"]["Code"] == "NoSuchEntity":
            logger.error(f"❌ Persister IAM Role missing: {role_name}")
        else:
            raise

def check_persister_lambda_function(provider: 'AWSProvider'):
    function_name = provider.naming.persister_lambda_function()
    client = provider.clients["lambda"]
    try:
        client.get_function(FunctionName=function_name)
        logger.info(f"✅ Persister Lambda Function exists: {_links().link_to_lambda_function(function_name, region=provider.region)}")
    except ClientError as e:
        if e.response["Error"]["Code"] == "ResourceNotFoundException":
            logger.error(f"❌ Persister Lambda Function missing: {function_name}")
        else:
            raise

def check_event_checker_iam_role(provider: 'AWSProvider'):
    role_name = provider.naming.event_checker_iam_role()
    client = provider.clients["iam"]
    try:
        client.get_role(RoleName=role_name)
        logger.info(f"✅ Event Checker IAM Role exists: {_links().link_to_iam_role(role_name, region=provider.region)}")
    except ClientError as e:
        if e.response["Error"]["Code"] == "NoSuchEntity":
            logger.error(f"❌ Event Checker IAM Role missing: {role_name}")
        else:
            raise

def check_event_checker_lambda_function(provider: 'AWSProvider'):
    function_name = provider.naming.event_checker_lambda_function()
    client = provider.clients["lambda"]
    try:
        client.get_function(FunctionName=function_name)
        logger.info(f"✅ Event Checker Lambda Function exists: {_links().link_to_lambda_function(function_name, region=provider.region)}")
    except ClientError as e:
        if e.response["Error"]["Code"] == "ResourceNotFoundException":
            logger.error(f"❌ Event Checker Lambda Function missing: {function_name}")
        else:
            raise

def check_lambda_chain_iam_role(provider: 'AWSProvider'):
    role_name = provider.naming.lambda_chain_iam_role()
    client = provider.clients["iam"]
    try:
        client.get_role(RoleName=role_name)
        logger.info(f"✅ Lambda-Chain IAM Role exists: {_links().link_to_iam_role(role_name, region=provider.region)}")
    except ClientError as e:
        if e.response["Error"]["Code"] == "NoSuchEntity":
            logger.error(f"❌ Lambda-Chain IAM Role missing: {role_name}")
        else:
            raise

def check_lambda_chain_step_function(provider: 'AWSProvider'):
    sf_name = provider.naming.lambda_chain_step_function()
    client = provider.clients["stepfunctions"]
    region = provider.region
    # Get account ID from STS client
    account_id = provider.clients["sts"].get_caller_identity()['Account']
    sf_arn = f"arn:aws:states:{region}:{account_id}:stateMachine:{sf_name}"

    try:
        client.describe_state_machine(stateMachineArn=sf_arn)
        logger.info(f"✅ Lambda-Chain Step Function exists: {_links().link_to_step_function(sf_arn, region=provider.region)}")
    except ClientError as e:
        if e.response["Error"]["Code"] == "StateMachineDoesNotExist":
            logger.error(f"❌ Lambda-Chain Step Function missing: {sf_name}")
        else:
             raise

def check_event_feedback_iam_role(provider: 'AWSProvider'):
    role_name = provider.naming.event_feedback_iam_role()
    client = provider.clients["iam"]
    try:
        client.get_role(RoleName=role_name)
        logger.info(f"✅ Event-Feedback IAM Role exists: {_links().link_to_iam_role(role_name, region=provider.region)}")
    except ClientError as e:
        if e.response["Error"]["Code"] == "NoSuchEntity":
            logger.error(f"❌ Event-Feedback IAM Role missing: {role_name}")
        else:
            raise

def check_event_feedback_lambda_function(provider: 'AWSProvider'):
    function_name = provider.naming.event_feedback_lambda_function()
    client = provider.clients["lambda"]
    try:
        client.get_function(FunctionName=function_name)
        logger.info(f"✅ Event-Feedback Lambda Function exists: {_links().link_to_lambda_function(function_name, region=provider.region)}")
    except ClientError as e:
        if e.response["Error"]["Code"] == "ResourceNotFoundException":
            logger.error(f"❌ Event-Feedback Lambda Function missing: {function_name}")
        else:
            raise

def check_processor_iam_role(iot_device, provider: 'AWSProvider'):
    role_name = provider.naming.processor_iam_role(iot_device.get('name', 'unknown'))
    client = provider.clients["iam"]
    try:
        client.get_role(RoleName=role_name)
        logger.info(f"✅ Processor {role_name} IAM Role exists: {_links().link_to_iam_role(role_name, region=provider.region)}")
    except ClientError as e:
        if e.response["Error"]["Code"] == "NoSuchEntity":
            logger.error(f"❌ Processor {role_name} IAM Role missing: {role_name}")
        else:
            raise

def check_processor_lambda_function(iot_device, provider: 'AWSProvider'):
    function_name = provider.naming.processor_lambda_function(iot_device.get('name', 'unknown'))
    client = provider.clients["lambda"]
    try:
        client.get_function(FunctionName=function_name)
        logger.info(f"✅ Processor {function_name} Lambda Function exists: {_links().link_to_lambda_function(function_name, region=provider.region)}")
    except ClientError as e:
        if e.response["Error"]["Code"] == "ResourceNotFoundException":
            logger.error(f"❌ Processor {function_name} Lambda Function missing: {function_name}")
        else:
            raise


def info_l2(context: 'DeploymentContext', provider: 'AWSProvider') -> None:
    """Check status of all L2 components."""
    # Persister
    check_persister_iam_role(provider)
    check_persister_lambda_function(provider)
    
    # Processors
    if context.config.iot_devices:
        for device in context.config.iot_devices:
            check_processor_iam_role(device, provider)
            check_processor_lambda_function(device, provider)
    
    # Event Checker (Optional)
    if context.config.is_optimization_enabled("useEventChecking"):
        check_event_checker_iam_role(provider)
        check_event_checker_lambda_function(provider)
        
        if context.config.is_optimization_enabled("triggerNotificationWorkflow"):
            check_lambda_chain_iam_role(provider)
            check_lambda_chain_step_function(provider)
            
        if context.config.is_optimization_enabled("returnFeedbackToDevice"):
            check_event_feedback_iam_role(provider)
            check_event_feedback_lambda_function(provider)
            
    # Event Actions
    if context.config.events:
        info_lambda_actions(provider, context.config.events)

