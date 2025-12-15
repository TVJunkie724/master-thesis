"""
Layer 3 (Storage) Deployment for AWS.

This module handles deployment and destruction of Layer 3 components:
- Hot Storage: DynamoDB + Hot Reader Lambdas
- Cold Storage: S3 + Hot-to-Cold Mover
- Archive Storage: S3 + Cold-to-Archive Mover
- API Gateway (optional, for cross-cloud access)

All functions accept provider and config parameters explicitly.
"""

import json
import os
import time
from datetime import datetime, timezone
from typing import TYPE_CHECKING
from logger import logger
# util is imported lazily inside functions to avoid circular import
import src.providers.aws.util_aws as util_aws
from botocore.exceptions import ClientError
import constants as CONSTANTS
from src.providers.aws.layers.tagging_helpers import tag_iam_role, get_tags_list, tag_s3_bucket

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
        response = iam_client.list_attached_role_policies(RoleName=role_name)
        for policy in response["AttachedPolicies"]:
            iam_client.detach_role_policy(RoleName=role_name, PolicyArn=policy["PolicyArn"])

        response = iam_client.list_role_policies(RoleName=role_name)
        for policy_name in response["PolicyNames"]:
            iam_client.delete_role_policy(RoleName=role_name, PolicyName=policy_name)

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


def _destroy_lambda(provider: 'AWSProvider', function_name: str) -> None:
    """Generic Lambda function destruction."""
    try:
        provider.clients["lambda"].delete_function(FunctionName=function_name)
        logger.info(f"Deleted Lambda function: {function_name}")
    except ClientError as e:
        if e.response["Error"]["Code"] != "ResourceNotFoundException":
            raise


# ==========================================
# 1.5. Writer Lambda (Multi-Cloud Only)
# ==========================================
# Writer is deployed when L2 is on a DIFFERENT cloud.
# It receives data FROM remote Persisters via HTTP POST.

def create_hot_writer_iam_role(provider: 'AWSProvider') -> None:
    """Creates IAM Role for the Writer Lambda (multi-cloud only).
    
    Writer needs:
    - DynamoDB write access
    - Basic execution role
    """
    role_name = provider.naming.hot_writer_iam_role()
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

    # Add inline policy for DynamoDB access
    table_name = provider.naming.hot_dynamodb_table()
    iam_client.put_role_policy(
        RoleName=role_name,
        PolicyName="DynamoDBWriteAccess",
        PolicyDocument=json.dumps({
            "Version": "2012-10-17",
            "Statement": [{
                "Effect": "Allow",
                "Action": [
                    "dynamodb:PutItem",
                    "dynamodb:UpdateItem",
                    "dynamodb:BatchWriteItem"
                ],
                "Resource": f"arn:aws:dynamodb:*:*:table/{table_name}"
            }]
        })
    )
    logger.info(f"Added DynamoDB write policy to {role_name}")
    
    # Tag the IAM role for resource grouping
    tag_iam_role(provider, role_name, "L3")


def destroy_hot_writer_iam_role(provider: 'AWSProvider') -> None:
    """Destroys the Writer IAM Role."""
    _destroy_iam_role(provider, provider.naming.hot_writer_iam_role())


def create_hot_writer_lambda_function(
    provider: 'AWSProvider',
    config: 'ProjectConfig',
    project_path: str
) -> str:
    """Creates the Writer Lambda Function with Function URL (multi-cloud only).
    
    Returns the Function URL endpoint for configuration.
    """
    function_name = provider.naming.hot_writer_lambda_function()
    role_name = provider.naming.hot_writer_iam_role()
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
        "DYNAMODB_TABLE_NAME": provider.naming.hot_dynamodb_table(),
        "INTER_CLOUD_TOKEN": expected_token  # Token to validate incoming requests
    }

    core_lambda_dir = os.path.join(project_path, CONSTANTS.AWS_CORE_LAMBDA_DIR_NAME)

    import src.util as util  # Lazy import to avoid circular dependency
    lambda_client.create_function(
        FunctionName=function_name,
        Runtime="python3.13",
        Role=role_arn,
        Handler="lambda_function.lambda_handler",
        Code={"ZipFile": util.compile_lambda_function(os.path.join(core_lambda_dir, "hot-writer"))},
        Description="Multi-cloud Writer: Receives data from remote Persisters",
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


def destroy_hot_writer_lambda_function(provider: 'AWSProvider') -> None:
    """Destroys the Writer Lambda Function and its Function URL."""
    function_name = provider.naming.hot_writer_lambda_function()
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
# 1.6. Cold Writer Lambda (Multi-Cloud Only)
# ==========================================
# Cold Writer is deployed when L3 Hot is on a DIFFERENT cloud than L3 Cold.
# It receives chunked data FROM remote Hot-to-Cold Movers via HTTP POST.

def create_cold_writer_iam_role(provider: 'AWSProvider') -> None:
    """Creates IAM Role for the Cold Writer Lambda (multi-cloud only).
    
    Cold Writer needs:
    - S3 write access to Cold bucket
    - Basic execution role
    """
    role_name = provider.naming.cold_writer_iam_role()
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

    # Add inline policy for S3 Cold bucket write access
    bucket_name = provider.naming.cold_s3_bucket()
    iam_client.put_role_policy(
        RoleName=role_name,
        PolicyName="S3ColdWriteAccess",
        PolicyDocument=json.dumps({
            "Version": "2012-10-17",
            "Statement": [{
                "Effect": "Allow",
                "Action": [
                    "s3:PutObject"
                ],
                "Resource": f"arn:aws:s3:::{bucket_name}/*"
            }]
        })
    )
    logger.info(f"Added S3 Cold write policy to {role_name}")


def destroy_cold_writer_iam_role(provider: 'AWSProvider') -> None:
    """Destroys the Cold Writer IAM Role."""
    role_name = provider.naming.cold_writer_iam_role()
    _destroy_iam_role(provider, role_name)


def create_cold_writer_lambda_function(
    provider: 'AWSProvider',
    config: 'ProjectConfig',
    project_path: str,
    expected_token: str
) -> str:
    """Creates the Cold Writer Lambda Function with Function URL.
    
    Returns:
        The Function URL for the Cold Writer.
    """
    function_name = provider.naming.cold_writer_lambda_function()
    role_name = provider.naming.cold_writer_iam_role()
    bucket_name = provider.naming.cold_s3_bucket()
    lambda_client = provider.clients["lambda"]
    iam_client = provider.clients["iam"]

    # Get role ARN
    role_arn = iam_client.get_role(RoleName=role_name)["Role"]["Arn"]

    # Create Lambda function
    lambda_dir = os.path.join(project_path, CONSTANTS.LAMBDA_FUNCTIONS_DIR_NAME, "cold-writer")
    zip_buffer = util_aws.create_lambda_zip(lambda_dir)

    lambda_client.create_function(
        FunctionName=function_name,
        Runtime="python3.12",
        Role=role_arn,
        Handler="lambda_function.lambda_handler",
        Code={"ZipFile": zip_buffer.read()},
        Timeout=60,
        MemorySize=256,
        Environment={
            "Variables": {
                "COLD_S3_BUCKET_NAME": bucket_name,
                "INTER_CLOUD_TOKEN": expected_token,
            }
        }
    )
    logger.info(f"Created Cold Writer Lambda: {function_name}")
    time.sleep(5)  # Wait for Lambda to be ready

    # Create Function URL (AuthType: NONE, validation in Lambda code)
    url_response = lambda_client.create_function_url_config(
        FunctionName=function_name,
        AuthType='NONE'
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


def destroy_cold_writer_lambda_function(provider: 'AWSProvider') -> None:
    """Destroys the Cold Writer Lambda Function and its Function URL."""
    function_name = provider.naming.cold_writer_lambda_function()
    lambda_client = provider.clients["lambda"]
    
    try:
        try:
            lambda_client.delete_function_url_config(FunctionName=function_name)
            logger.info(f"Deleted Function URL for: {function_name}")
        except ClientError as e:
            if e.response["Error"]["Code"] != "ResourceNotFoundException":
                raise
        
        lambda_client.delete_function(FunctionName=function_name)
        logger.info(f"Deleted Lambda function: {function_name}")
    except ClientError as e:
        if e.response["Error"]["Code"] != "ResourceNotFoundException":
            raise


# ==========================================
# 1.7. Archive Writer Lambda (Multi-Cloud Only)
# ==========================================
# Archive Writer is deployed when L3 Cold is on a DIFFERENT cloud than L3 Archive.
# It receives data FROM remote Cold-to-Archive Movers via HTTP POST.

def create_archive_writer_iam_role(provider: 'AWSProvider') -> None:
    """Creates IAM Role for the Archive Writer Lambda (multi-cloud only).
    
    Archive Writer needs:
    - S3 write access to Archive bucket
    - Basic execution role
    """
    role_name = provider.naming.archive_writer_iam_role()
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

    iam_client.attach_role_policy(
        RoleName=role_name,
        PolicyArn=CONSTANTS.AWS_POLICY_LAMBDA_BASIC_EXECUTION
    )
    logger.info(f"Attached Lambda basic execution policy to {role_name}")

    # Add inline policy for S3 Archive bucket write access
    bucket_name = provider.naming.archive_s3_bucket()
    iam_client.put_role_policy(
        RoleName=role_name,
        PolicyName="S3ArchiveWriteAccess",
        PolicyDocument=json.dumps({
            "Version": "2012-10-17",
            "Statement": [{
                "Effect": "Allow",
                "Action": [
                    "s3:PutObject"
                ],
                "Resource": f"arn:aws:s3:::{bucket_name}/*"
            }]
        })
    )
    logger.info(f"Added S3 Archive write policy to {role_name}")


def destroy_archive_writer_iam_role(provider: 'AWSProvider') -> None:
    """Destroys the Archive Writer IAM Role."""
    role_name = provider.naming.archive_writer_iam_role()
    _destroy_iam_role(provider, role_name)


def create_archive_writer_lambda_function(
    provider: 'AWSProvider',
    config: 'ProjectConfig',
    project_path: str,
    expected_token: str
) -> str:
    """Creates the Archive Writer Lambda Function with Function URL.
    
    Returns:
        The Function URL for the Archive Writer.
    """
    function_name = provider.naming.archive_writer_lambda_function()
    role_name = provider.naming.archive_writer_iam_role()
    bucket_name = provider.naming.archive_s3_bucket()
    lambda_client = provider.clients["lambda"]
    iam_client = provider.clients["iam"]

    role_arn = iam_client.get_role(RoleName=role_name)["Role"]["Arn"]

    lambda_dir = os.path.join(project_path, CONSTANTS.LAMBDA_FUNCTIONS_DIR_NAME, "archive-writer")
    zip_buffer = util_aws.create_lambda_zip(lambda_dir)

    lambda_client.create_function(
        FunctionName=function_name,
        Runtime="python3.12",
        Role=role_arn,
        Handler="lambda_function.lambda_handler",
        Code={"ZipFile": zip_buffer.read()},
        Timeout=60,
        MemorySize=256,
        Environment={
            "Variables": {
                "ARCHIVE_S3_BUCKET_NAME": bucket_name,
                "INTER_CLOUD_TOKEN": expected_token,
            }
        }
    )
    logger.info(f"Created Archive Writer Lambda: {function_name}")
    time.sleep(5)

    url_response = lambda_client.create_function_url_config(
        FunctionName=function_name,
        AuthType='NONE'
    )
    function_url = url_response['FunctionUrl']
    logger.info(f"Created Function URL for {function_name}: {function_url}")

    lambda_client.add_permission(
        FunctionName=function_name,
        StatementId='FunctionURLPublicAccess',
        Action='lambda:InvokeFunctionUrl',
        Principal='*',
        FunctionUrlAuthType='NONE'
    )
    logger.info(f"Added public access permission to {function_name}")

    return function_url


def destroy_archive_writer_lambda_function(provider: 'AWSProvider') -> None:
    """Destroys the Archive Writer Lambda Function and its Function URL."""
    function_name = provider.naming.archive_writer_lambda_function()
    lambda_client = provider.clients["lambda"]
    
    try:
        try:
            lambda_client.delete_function_url_config(FunctionName=function_name)
            logger.info(f"Deleted Function URL for: {function_name}")
        except ClientError as e:
            if e.response["Error"]["Code"] != "ResourceNotFoundException":
                raise
        
        lambda_client.delete_function(FunctionName=function_name)
        logger.info(f"Deleted Lambda function: {function_name}")
    except ClientError as e:
        if e.response["Error"]["Code"] != "ResourceNotFoundException":
            raise


# ==========================================
# 2. Hot Storage (DynamoDB)
# ==========================================

def create_hot_dynamodb_table(provider: 'AWSProvider') -> None:
    """Creates the DynamoDB table for Hot Storage."""
    table_name = provider.naming.hot_dynamodb_table()
    dynamodb_client = provider.clients["dynamodb"]

    dynamodb_client.create_table(
        TableName=table_name,
        KeySchema=[
            {"AttributeName": "device_id", "KeyType": "HASH"},
            {"AttributeName": "timestamp", "KeyType": "RANGE"}
        ],
        AttributeDefinitions=[
            {"AttributeName": "device_id", "AttributeType": "S"},
            {"AttributeName": "timestamp", "AttributeType": "S"}
        ],
        BillingMode="PAY_PER_REQUEST",
        Tags=[{"Key": k, "Value": v} for k, v in provider.naming.get_common_tags("L3").items()]
    )
    logger.info(f"Created DynamoDB table: {table_name}")

    waiter = dynamodb_client.get_waiter('table_exists')
    waiter.wait(TableName=table_name)
    logger.info(f"DynamoDB table is now active: {table_name}")


def destroy_hot_dynamodb_table(provider: 'AWSProvider') -> None:
    """Destroys the Hot Storage DynamoDB table."""
    table_name = provider.naming.hot_dynamodb_table()
    dynamodb_client = provider.clients["dynamodb"]

    try:
        dynamodb_client.describe_table(TableName=table_name)
    except ClientError as e:
        if e.response["Error"]["Code"] == "ResourceNotFoundException":
            return
        raise

    dynamodb_client.delete_table(TableName=table_name)
    logger.info(f"Deletion of DynamoDB table initiated: {table_name}")

    waiter = dynamodb_client.get_waiter('table_not_exists')
    waiter.wait(TableName=table_name)
    logger.info(f"DynamoDB table deleted: {table_name}")


# ==========================================
# 3. Hot-Cold Mover
# ==========================================

def create_hot_cold_mover_iam_role(provider: 'AWSProvider') -> None:
    """Creates IAM Role for the Hot-to-Cold Data Mover."""
    role_name = provider.naming.hot_cold_mover_iam_role()
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
        CONSTANTS.AWS_POLICY_S3_FULL_ACCESS,
        CONSTANTS.AWS_POLICY_DYNAMODB_FULL_ACCESS
    ]
    for policy_arn in policy_arns:
        iam_client.attach_role_policy(RoleName=role_name, PolicyArn=policy_arn)
        logger.info(f"Attached IAM policy ARN: {policy_arn}")
    
    # Tag the IAM role for resource grouping
    tag_iam_role(provider, role_name, "L3")

    logger.info("Waiting for propagation...")
    time.sleep(20)


def destroy_hot_cold_mover_iam_role(provider: 'AWSProvider') -> None:
    _destroy_iam_role(provider, provider.naming.hot_cold_mover_iam_role())


def create_hot_cold_mover_lambda_function(provider: 'AWSProvider', config: 'ProjectConfig', project_path: str) -> None:
    """Creates the Hot-to-Cold Data Mover Lambda.
    
    If L3 Cold is on a different cloud than L3 Hot, injects multi-cloud
    environment variables (REMOTE_COLD_WRITER_URL, INTER_CLOUD_TOKEN)
    for cross-cloud data transfer.
    """
    function_name = provider.naming.hot_cold_mover_lambda_function()
    role_name = provider.naming.hot_cold_mover_iam_role()
    iam_client = provider.clients["iam"]
    lambda_client = provider.clients["lambda"]

    response = iam_client.get_role(RoleName=role_name)
    role_arn = response['Role']['Arn']

    core_lambda_dir = os.path.join(project_path, CONSTANTS.AWS_CORE_LAMBDA_DIR_NAME)

    # Build environment variables
    env_vars = {
        "DIGITAL_TWIN_INFO": json.dumps(_get_digital_twin_info(config)),
        "DYNAMODB_TABLE_NAME": provider.naming.hot_dynamodb_table(),
        "COLD_S3_BUCKET_NAME": provider.naming.cold_s3_bucket()
    }
    
    # Multi-cloud: Inject remote Cold Writer URL if L3 Cold is on different cloud
    # NOTE: Using direct access [] - missing keys should raise KeyError (fail-fast)
    l3_hot = config.providers["layer_3_hot_provider"]
    l3_cold = config.providers["layer_3_cold_provider"]
    
    if l3_hot != l3_cold:
        conn_id = f"{l3_hot}_l3hot_to_{l3_cold}_l3cold"
        connections = getattr(config, 'inter_cloud', {}).get("connections", {}) if hasattr(config, 'inter_cloud') else {}
        conn = connections.get(conn_id, {})
        
        url = conn.get("url", "")
        token = conn.get("token", "")
        
        if not url or not token:
            raise ValueError(
                f"Multi-cloud config incomplete for {conn_id}: url={bool(url)}, token={bool(token)}. "
                f"Ensure config_inter_cloud.json contains connection '{conn_id}' with 'url' and 'token'."
            )
        
        env_vars["REMOTE_COLD_WRITER_URL"] = url
        env_vars["INTER_CLOUD_TOKEN"] = token
        logger.info(f"[Hot-Cold Mover] Multi-cloud mode: Will POST to {l3_cold} Cold Writer")

    import util  # Lazy import to avoid circular dependency
    lambda_client.create_function(
        FunctionName=function_name,
        Runtime="python3.13",
        Role=role_arn,
        Handler="lambda_function.lambda_handler",
        Code={"ZipFile": util.compile_lambda_function(os.path.join(core_lambda_dir, "hot-to-cold-mover"))},
        Description="L3 Hot-to-Cold Mover: Moves old data to S3",
        Timeout=60,
        MemorySize=256,
        Publish=True,
        Environment={"Variables": env_vars}
    )
    logger.info(f"Created Lambda function: {function_name}")


def destroy_hot_cold_mover_lambda_function(provider: 'AWSProvider') -> None:
    _destroy_lambda(provider, provider.naming.hot_cold_mover_lambda_function())


def create_hot_cold_mover_event_rule(provider: 'AWSProvider') -> None:
    """Creates the EventBridge Rule to schedule the Hot-to-Cold Mover."""
    rule_name = provider.naming.hot_cold_mover_event_rule()
    function_name = provider.naming.hot_cold_mover_lambda_function()
    events_client = provider.clients["events"]
    lambda_client = provider.clients["lambda"]

    events_client.put_rule(
        Name=rule_name,
        ScheduleExpression=CONSTANTS.AWS_HOT_COLD_SCHEDULE,
        State="ENABLED",
        Description="Triggers the Hot-to-Cold Data Mover Lambda on a schedule"
    )
    logger.info(f"Created EventBridge rule: {rule_name}")

    response = lambda_client.get_function(FunctionName=function_name)
    function_arn = response['Configuration']['FunctionArn']

    events_client.put_targets(
        Rule=rule_name,
        Targets=[{"Id": "HotColdMoverTarget", "Arn": function_arn}]
    )

    try:
        lambda_client.add_permission(
            FunctionName=function_name,
            StatementId="eventbridge-invoke",
            Action="lambda:InvokeFunction",
            Principal="events.amazonaws.com"
        )
    except ClientError as e:
        if e.response["Error"]["Code"] != "ResourceConflictException":
            raise

    logger.info(f"Linked EventBridge rule to Lambda: {function_name}")


def destroy_hot_cold_mover_event_rule(provider: 'AWSProvider') -> None:
    """Destroys the Hot-Cold Mover EventBridge Rule."""
    rule_name = provider.naming.hot_cold_mover_event_rule()
    function_name = provider.naming.hot_cold_mover_lambda_function()
    events_client = provider.clients["events"]
    lambda_client = provider.clients["lambda"]

    try:
        lambda_client.remove_permission(FunctionName=function_name, StatementId="eventbridge-invoke")
    except ClientError:
        pass

    try:
        events_client.remove_targets(Rule=rule_name, Ids=["HotColdMoverTarget"])
        events_client.delete_rule(Name=rule_name)
        logger.info(f"Deleted EventBridge rule: {rule_name}")
    except ClientError as e:
        if e.response["Error"]["Code"] != "ResourceNotFoundException":
            raise


# ==========================================
# 4. Cold Storage (S3)
# ==========================================

def create_cold_s3_bucket(provider: 'AWSProvider') -> None:
    """Creates the S3 Bucket for Cold Storage."""
    bucket_name = provider.naming.cold_s3_bucket()
    s3_client = provider.clients["s3"]
    region = s3_client.meta.region_name

    create_args = {"Bucket": bucket_name}
    if region != "us-east-1":
        create_args["CreateBucketConfiguration"] = {"LocationConstraint": region}

    s3_client.create_bucket(**create_args)
    logger.info(f"Created S3 bucket: {bucket_name}")


def destroy_cold_s3_bucket(provider: 'AWSProvider') -> None:
    """Destroys the Cold Storage S3 bucket."""
    util_aws.destroy_s3_bucket(provider.naming.cold_s3_bucket(), provider.clients["s3"])


# ==========================================
# 5. Cold-Archive Mover
# ==========================================

def create_cold_archive_mover_iam_role(provider: 'AWSProvider') -> None:
    """Creates IAM Role for the Cold-to-Archive Data Mover."""
    role_name = provider.naming.cold_archive_mover_iam_role()
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
        CONSTANTS.AWS_POLICY_S3_FULL_ACCESS
    ]
    for policy_arn in policy_arns:
        iam_client.attach_role_policy(RoleName=role_name, PolicyArn=policy_arn)

    logger.info("Waiting for propagation...")
    time.sleep(20)


def destroy_cold_archive_mover_iam_role(provider: 'AWSProvider') -> None:
    _destroy_iam_role(provider, provider.naming.cold_archive_mover_iam_role())


def create_cold_archive_mover_lambda_function(provider: 'AWSProvider', config: 'ProjectConfig', project_path: str) -> None:
    """Creates the Cold-to-Archive Data Mover Lambda.
    
    If L3 Archive is on a different cloud than L3 Cold, injects multi-cloud
    environment variables (REMOTE_ARCHIVE_WRITER_URL, INTER_CLOUD_TOKEN)
    for cross-cloud data transfer.
    """
    function_name = provider.naming.cold_archive_mover_lambda_function()
    role_name = provider.naming.cold_archive_mover_iam_role()
    iam_client = provider.clients["iam"]
    lambda_client = provider.clients["lambda"]

    response = iam_client.get_role(RoleName=role_name)
    role_arn = response['Role']['Arn']

    core_lambda_dir = os.path.join(project_path, CONSTANTS.AWS_CORE_LAMBDA_DIR_NAME)

    # Build environment variables
    env_vars = {
        "DIGITAL_TWIN_INFO": json.dumps(_get_digital_twin_info(config)),
        "COLD_S3_BUCKET_NAME": provider.naming.cold_s3_bucket(),
        "ARCHIVE_S3_BUCKET_NAME": provider.naming.archive_s3_bucket()
    }
    
    # Multi-cloud: Inject remote Archive Writer URL if L3 Archive is on different cloud
    # NOTE: Using direct access [] - missing keys should raise KeyError (fail-fast)
    l3_cold = config.providers["layer_3_cold_provider"]
    l3_archive = config.providers["layer_3_archive_provider"]
    
    if l3_cold != l3_archive:
        conn_id = f"{l3_cold}_l3cold_to_{l3_archive}_l3archive"
        connections = getattr(config, 'inter_cloud', {}).get("connections", {}) if hasattr(config, 'inter_cloud') else {}
        conn = connections.get(conn_id, {})
        
        url = conn.get("url", "")
        token = conn.get("token", "")
        
        if not url or not token:
            raise ValueError(
                f"Multi-cloud config incomplete for {conn_id}: url={bool(url)}, token={bool(token)}. "
                f"Ensure config_inter_cloud.json contains connection '{conn_id}' with 'url' and 'token'."
            )
        
        env_vars["REMOTE_ARCHIVE_WRITER_URL"] = url
        env_vars["INTER_CLOUD_TOKEN"] = token
        logger.info(f"[Cold-Archive Mover] Multi-cloud mode: Will POST to {l3_archive} Archive Writer")

    import util  # Lazy import to avoid circular dependency
    lambda_client.create_function(
        FunctionName=function_name,
        Runtime="python3.13",
        Role=role_arn,
        Handler="lambda_function.lambda_handler",
        Code={"ZipFile": util.compile_lambda_function(os.path.join(core_lambda_dir, "cold-to-archive-mover"))},
        Description="L3 Cold-to-Archive Mover: Moves old data to Glacier",
        Timeout=60,
        MemorySize=256,
        Publish=True,
        Environment={"Variables": env_vars}
    )
    logger.info(f"Created Lambda function: {function_name}")


def destroy_cold_archive_mover_lambda_function(provider: 'AWSProvider') -> None:
    _destroy_lambda(provider, provider.naming.cold_archive_mover_lambda_function())


def create_cold_archive_mover_event_rule(provider: 'AWSProvider') -> None:
    """Creates the EventBridge Rule for Cold-to-Archive Mover."""
    rule_name = provider.naming.cold_archive_mover_event_rule()
    function_name = provider.naming.cold_archive_mover_lambda_function()
    events_client = provider.clients["events"]
    lambda_client = provider.clients["lambda"]

    events_client.put_rule(
        Name=rule_name,
        ScheduleExpression=CONSTANTS.AWS_COLD_ARCHIVE_SCHEDULE,
        State="ENABLED",
        Description="Triggers the Cold-to-Archive Data Mover Lambda on a schedule"
    )

    response = lambda_client.get_function(FunctionName=function_name)
    function_arn = response['Configuration']['FunctionArn']

    events_client.put_targets(
        Rule=rule_name,
        Targets=[{"Id": "ColdArchiveMoverTarget", "Arn": function_arn}]
    )

    try:
        lambda_client.add_permission(
            FunctionName=function_name,
            StatementId="eventbridge-invoke",
            Action="lambda:InvokeFunction",
            Principal="events.amazonaws.com"
        )
    except ClientError as e:
        if e.response["Error"]["Code"] != "ResourceConflictException":
            raise

    logger.info(f"Created EventBridge rule: {rule_name}")


def destroy_cold_archive_mover_event_rule(provider: 'AWSProvider') -> None:
    """Destroys the Cold-Archive Mover EventBridge Rule."""
    rule_name = provider.naming.cold_archive_mover_event_rule()
    function_name = provider.naming.cold_archive_mover_lambda_function()
    events_client = provider.clients["events"]
    lambda_client = provider.clients["lambda"]

    try:
        lambda_client.remove_permission(FunctionName=function_name, StatementId="eventbridge-invoke")
    except ClientError:
        pass

    try:
        events_client.remove_targets(Rule=rule_name, Ids=["ColdArchiveMoverTarget"])
        events_client.delete_rule(Name=rule_name)
        logger.info(f"Deleted EventBridge rule: {rule_name}")
    except ClientError as e:
        if e.response["Error"]["Code"] != "ResourceNotFoundException":
            raise


# ==========================================
# 6. Archive Storage (S3)
# ==========================================

def create_archive_s3_bucket(provider: 'AWSProvider') -> None:
    """Creates the S3 Bucket for Archive Storage."""
    bucket_name = provider.naming.archive_s3_bucket()
    s3_client = provider.clients["s3"]
    region = s3_client.meta.region_name

    create_args = {"Bucket": bucket_name}
    if region != "us-east-1":
        create_args["CreateBucketConfiguration"] = {"LocationConstraint": region}

    s3_client.create_bucket(**create_args)
    logger.info(f"Created S3 bucket: {bucket_name}")


def destroy_archive_s3_bucket(provider: 'AWSProvider') -> None:
    """Destroys the Archive Storage S3 bucket."""
    util_aws.destroy_s3_bucket(provider.naming.archive_s3_bucket(), provider.clients["s3"])


# ==========================================
# 7. Hot Reader Lambda (For TwinMaker)
# ==========================================

def create_hot_reader_iam_role(provider: 'AWSProvider') -> None:
    """Creates IAM Role for the Hot Reader Lambda."""
    role_name = provider.naming.hot_reader_iam_role()
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
        CONSTANTS.AWS_POLICY_DYNAMODB_READ_ONLY,
        CONSTANTS.AWS_POLICY_S3_READ_ONLY
    ]
    for policy_arn in policy_arns:
        iam_client.attach_role_policy(RoleName=role_name, PolicyArn=policy_arn)

    logger.info("Waiting for propagation...")
    time.sleep(20)


def destroy_hot_reader_iam_role(provider: 'AWSProvider') -> None:
    _destroy_iam_role(provider, provider.naming.hot_reader_iam_role())


def create_hot_reader_lambda_function(provider: 'AWSProvider', config: 'ProjectConfig', project_path: str) -> None:
    """Creates the Hot Reader Lambda."""
    function_name = provider.naming.hot_reader_lambda_function()
    role_name = provider.naming.hot_reader_iam_role()
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
        Code={"ZipFile": util.compile_lambda_function(os.path.join(core_lambda_dir, "hot-reader"))},
        Description="L3 Hot Reader: Fetches data range from DynamoDB",
        Timeout=10,
        MemorySize=128,
        Publish=True,
        Environment={
            "Variables": {
                "DIGITAL_TWIN_INFO": json.dumps(_get_digital_twin_info(config)),
                "DYNAMODB_TABLE_NAME": provider.naming.hot_dynamodb_table()
            }
        }
    )
    logger.info(f"Created Lambda function: {function_name}")


def destroy_hot_reader_lambda_function(provider: 'AWSProvider') -> None:
    _destroy_lambda(provider, provider.naming.hot_reader_lambda_function())


# ==========================================
# 8. Hot Reader Last Entry Lambda
# ==========================================

def create_hot_reader_last_entry_iam_role(provider: 'AWSProvider') -> None:
    """Creates IAM Role for the Hot Reader (Last Entry) Lambda."""
    role_name = provider.naming.hot_reader_last_entry_iam_role()
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

    policy_arns = [
        CONSTANTS.AWS_POLICY_LAMBDA_BASIC_EXECUTION,
        CONSTANTS.AWS_POLICY_DYNAMODB_READ_ONLY
    ]
    for policy_arn in policy_arns:
        iam_client.attach_role_policy(RoleName=role_name, PolicyArn=policy_arn)

    logger.info(f"Created IAM role: {role_name}")
    time.sleep(20)


def destroy_hot_reader_last_entry_iam_role(provider: 'AWSProvider') -> None:
    _destroy_iam_role(provider, provider.naming.hot_reader_last_entry_iam_role())


def create_hot_reader_last_entry_lambda_function(provider: 'AWSProvider', config: 'ProjectConfig', project_path: str) -> None:
    """Creates the Hot Reader Last Entry Lambda."""
    function_name = provider.naming.hot_reader_last_entry_lambda_function()
    role_name = provider.naming.hot_reader_last_entry_iam_role()
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
        Code={"ZipFile": util.compile_lambda_function(os.path.join(core_lambda_dir, "hot-reader-last-entry"))},
        Description="L3 Hot Reader: Fetches last entry from DynamoDB",
        Timeout=10,
        MemorySize=128,
        Publish=True,
        Environment={
            "Variables": {
                "DIGITAL_TWIN_INFO": json.dumps(_get_digital_twin_info(config)),
                "DYNAMODB_TABLE_NAME": provider.naming.hot_dynamodb_table()
            }
        }
    )
    logger.info(f"Created Lambda function: {function_name}")


def destroy_hot_reader_last_entry_lambda_function(provider: 'AWSProvider') -> None:
    _destroy_lambda(provider, provider.naming.hot_reader_last_entry_lambda_function())


# ==========================================
# 9. Function URLs for Hot Readers (Multi-Cloud)
# ==========================================
# Function URLs are created when L4 (TwinMaker) is on a different cloud
# than L3 (Hot Storage). The remote Digital Twin Data Connector calls
# these URLs with X-Inter-Cloud-Token for authentication.

def create_hot_reader_function_url(provider: 'AWSProvider', token: str) -> str:
    """Creates Function URL for Hot Reader Lambda (multi-cloud L3→L4).
    
    Args:
        provider: AWS Provider instance
        token: X-Inter-Cloud-Token for authentication
    
    Returns:
        Function URL for the Hot Reader
    """
    function_name = provider.naming.hot_reader_lambda_function()
    lambda_client = provider.clients["lambda"]
    
    # Update Lambda to include the token
    lambda_client.update_function_configuration(
        FunctionName=function_name,
        Environment={
            "Variables": {
                **lambda_client.get_function_configuration(FunctionName=function_name)["Environment"]["Variables"],
                "INTER_CLOUD_TOKEN": token
            }
        }
    )
    logger.info(f"Updated {function_name} with INTER_CLOUD_TOKEN")
    
    # Create Function URL
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


def create_hot_reader_last_entry_function_url(provider: 'AWSProvider', token: str) -> str:
    """Creates Function URL for Hot Reader Last Entry Lambda (multi-cloud L3→L4)."""
    function_name = provider.naming.hot_reader_last_entry_lambda_function()
    lambda_client = provider.clients["lambda"]
    
    # Update Lambda to include the token
    lambda_client.update_function_configuration(
        FunctionName=function_name,
        Environment={
            "Variables": {
                **lambda_client.get_function_configuration(FunctionName=function_name)["Environment"]["Variables"],
                "INTER_CLOUD_TOKEN": token
            }
        }
    )
    logger.info(f"Updated {function_name} with INTER_CLOUD_TOKEN")
    
    # Create Function URL
    url_response = lambda_client.create_function_url_config(
        FunctionName=function_name,
        AuthType='NONE'
    )
    function_url = url_response['FunctionUrl']
    logger.info(f"Created Function URL for {function_name}: {function_url}")
    
    lambda_client.add_permission(
        FunctionName=function_name,
        StatementId='FunctionURLPublicAccess',
        Action='lambda:InvokeFunctionUrl',
        Principal='*',
        FunctionUrlAuthType='NONE'
    )
    
    return function_url


def destroy_hot_reader_function_url(provider: 'AWSProvider') -> None:
    """Destroys Function URL from Hot Reader Lambda."""
    function_name = provider.naming.hot_reader_lambda_function()
    lambda_client = provider.clients["lambda"]
    
    try:
        lambda_client.delete_function_url_config(FunctionName=function_name)
        logger.info(f"Deleted Function URL for: {function_name}")
    except ClientError as e:
        if e.response["Error"]["Code"] != "ResourceNotFoundException":
            raise


def destroy_hot_reader_last_entry_function_url(provider: 'AWSProvider') -> None:
    """Destroys Function URL from Hot Reader Last Entry Lambda."""
    function_name = provider.naming.hot_reader_last_entry_lambda_function()
    lambda_client = provider.clients["lambda"]
    
    try:
        lambda_client.delete_function_url_config(FunctionName=function_name)
        logger.info(f"Deleted Function URL for: {function_name}")
    except ClientError as e:
        if e.response["Error"]["Code"] != "ResourceNotFoundException":
            raise


# ==========================================
# 10. Digital Twin Data Connector (Multi-Cloud L3→L4)
# ==========================================
# Deployed on L4's cloud when L3 ≠ L4. Acts as adapter for TwinMaker
# which can only invoke local Lambdas, not make HTTP calls.

def create_digital_twin_data_connector_iam_role(provider: 'AWSProvider') -> None:
    """Creates IAM Role for the Digital Twin Data Connector Lambda."""
    role_name = provider.naming.digital_twin_data_connector_iam_role()
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

    iam_client.attach_role_policy(
        RoleName=role_name,
        PolicyArn=CONSTANTS.AWS_POLICY_LAMBDA_BASIC_EXECUTION
    )
    # If single-cloud, needs Lambda invoke permission for local Hot Reader
    iam_client.attach_role_policy(
        RoleName=role_name,
        PolicyArn=CONSTANTS.AWS_POLICY_LAMBDA_ROLE
    )
    logger.info(f"Attached policies to {role_name}")
    time.sleep(20)  # Wait for IAM propagation


def destroy_digital_twin_data_connector_iam_role(provider: 'AWSProvider') -> None:
    _destroy_iam_role(provider, provider.naming.digital_twin_data_connector_iam_role())


def create_digital_twin_data_connector_lambda_function(
    provider: 'AWSProvider', 
    config: 'ProjectConfig', 
    project_path: str,
    remote_reader_url: str = "",
    inter_cloud_token: str = ""
) -> None:
    """Creates the Digital Twin Data Connector Lambda.
    
    Args:
        provider: AWS Provider
        config: Project config
        project_path: Path to project
        remote_reader_url: URL of remote Hot Reader (if multi-cloud)
        inter_cloud_token: Token for X-Inter-Cloud-Token header (if multi-cloud)
    """
    function_name = provider.naming.digital_twin_data_connector_lambda_function()
    role_name = provider.naming.digital_twin_data_connector_iam_role()
    iam_client = provider.clients["iam"]
    lambda_client = provider.clients["lambda"]

    response = iam_client.get_role(RoleName=role_name)
    role_arn = response['Role']['Arn']

    core_lambda_dir = os.path.join(project_path, CONSTANTS.AWS_CORE_LAMBDA_DIR_NAME)
    
    env_vars = {
        "DIGITAL_TWIN_INFO": json.dumps(_get_digital_twin_info(config)),
    }
    
    # Multi-cloud: route to remote Hot Reader via HTTP
    if remote_reader_url:
        env_vars["REMOTE_READER_URL"] = remote_reader_url
        env_vars["INTER_CLOUD_TOKEN"] = inter_cloud_token
    else:
        # Single-cloud: direct invoke of local Hot Reader
        env_vars["LOCAL_HOT_READER_NAME"] = provider.naming.hot_reader_lambda_function()

    import src.util as util
    lambda_client.create_function(
        FunctionName=function_name,
        Runtime="python3.13",
        Role=role_arn,
        Handler="lambda_function.lambda_handler",
        Code={"ZipFile": util.compile_lambda_function(os.path.join(core_lambda_dir, "digital-twin-data-connector"))},
        Description="Digital Twin Data Connector: Routes TwinMaker to Hot Reader",
        Timeout=30,
        MemorySize=128,
        Publish=True,
        Environment={"Variables": env_vars}
    )
    logger.info(f"Created Lambda function: {function_name}")


def destroy_digital_twin_data_connector_lambda_function(provider: 'AWSProvider') -> None:
    _destroy_lambda(provider, provider.naming.digital_twin_data_connector_lambda_function())


def create_digital_twin_data_connector_last_entry_iam_role(provider: 'AWSProvider') -> None:
    """Creates IAM Role for the Digital Twin Data Connector Last Entry Lambda."""
    role_name = provider.naming.digital_twin_data_connector_last_entry_iam_role()
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

    iam_client.attach_role_policy(
        RoleName=role_name,
        PolicyArn=CONSTANTS.AWS_POLICY_LAMBDA_BASIC_EXECUTION
    )
    iam_client.attach_role_policy(
        RoleName=role_name,
        PolicyArn=CONSTANTS.AWS_POLICY_LAMBDA_ROLE
    )
    time.sleep(20)


def destroy_digital_twin_data_connector_last_entry_iam_role(provider: 'AWSProvider') -> None:
    _destroy_iam_role(provider, provider.naming.digital_twin_data_connector_last_entry_iam_role())


def create_digital_twin_data_connector_last_entry_lambda_function(
    provider: 'AWSProvider', 
    config: 'ProjectConfig', 
    project_path: str,
    remote_reader_url: str = "",
    inter_cloud_token: str = ""
) -> None:
    """Creates the Digital Twin Data Connector Last Entry Lambda."""
    function_name = provider.naming.digital_twin_data_connector_last_entry_lambda_function()
    role_name = provider.naming.digital_twin_data_connector_last_entry_iam_role()
    iam_client = provider.clients["iam"]
    lambda_client = provider.clients["lambda"]

    response = iam_client.get_role(RoleName=role_name)
    role_arn = response['Role']['Arn']

    core_lambda_dir = os.path.join(project_path, CONSTANTS.AWS_CORE_LAMBDA_DIR_NAME)
    
    env_vars = {
        "DIGITAL_TWIN_INFO": json.dumps(_get_digital_twin_info(config)),
    }
    
    if remote_reader_url:
        env_vars["REMOTE_READER_URL"] = remote_reader_url
        env_vars["INTER_CLOUD_TOKEN"] = inter_cloud_token
    else:
        env_vars["LOCAL_HOT_READER_LAST_ENTRY_NAME"] = provider.naming.hot_reader_last_entry_lambda_function()

    import src.util as util
    lambda_client.create_function(
        FunctionName=function_name,
        Runtime="python3.13",
        Role=role_arn,
        Handler="lambda_function.lambda_handler",
        Code={"ZipFile": util.compile_lambda_function(os.path.join(core_lambda_dir, "digital-twin-data-connector-last-entry"))},
        Description="Digital Twin Data Connector Last Entry: Routes TwinMaker to Hot Reader",
        Timeout=30,
        MemorySize=128,
        Publish=True,
        Environment={"Variables": env_vars}
    )
    logger.info(f"Created Lambda function: {function_name}")


def destroy_digital_twin_data_connector_last_entry_lambda_function(provider: 'AWSProvider') -> None:
    _destroy_lambda(provider, provider.naming.digital_twin_data_connector_last_entry_lambda_function())


# ==========================================
# 11. Info / Status Checks
# ==========================================

def _links():
    return util_aws

def check_hot_dynamodb_table(provider: 'AWSProvider'):
    table_name = provider.naming.hot_dynamodb_table()
    client = provider.clients["dynamodb"]
    try:
        client.describe_table(TableName=table_name)
        logger.info(f"✅ Hot DynamoDB Table exists: {_links().link_to_dynamodb_table(table_name, region=provider.region)}")
    except ClientError as e:
        if e.response["Error"]["Code"] == "ResourceNotFoundException":
            logger.error(f"❌ Hot DynamoDB Table missing: {table_name}")
        else:
            raise

def check_hot_cold_mover_iam_role(provider: 'AWSProvider'):
    role_name = provider.naming.hot_cold_mover_iam_role()
    client = provider.clients["iam"]
    try:
        client.get_role(RoleName=role_name)
        logger.info(f"✅ Hot-Cold Mover IAM Role exists: {_links().link_to_iam_role(role_name, region=provider.region)}")
    except ClientError as e:
        if e.response["Error"]["Code"] == "NoSuchEntity":
            logger.error(f"❌ Hot-Cold Mover IAM Role missing: {role_name}")
        else:
            raise

def check_hot_cold_mover_lambda_function(provider: 'AWSProvider'):
    function_name = provider.naming.hot_cold_mover_lambda_function()
    client = provider.clients["lambda"]
    try:
        client.get_function(FunctionName=function_name)
        logger.info(f"✅ Hot-Cold Mover Lambda Function exists: {_links().link_to_lambda_function(function_name, region=provider.region)}")
    except ClientError as e:
        if e.response["Error"]["Code"] == "ResourceNotFoundException":
            logger.error(f"❌ Hot-Cold Mover Lambda Function missing: {function_name}")
        else:
            raise

def check_hot_cold_mover_event_rule(provider: 'AWSProvider'):
    rule_name = provider.naming.hot_cold_mover_event_rule()
    client = provider.clients["events"]
    try:
        client.describe_rule(Name=rule_name)
        logger.info(f"✅ Hot-Cold Mover Event Rule exists: {_links().link_to_event_rule(rule_name, region=provider.region)}")
    except ClientError as e:
        if e.response["Error"]["Code"] == "ResourceNotFoundException":
            logger.error(f"❌ Hot-Cold Mover Event Rule missing: {rule_name}")
        else:
            raise

def check_hot_reader_iam_role(provider: 'AWSProvider'):
    role_name = provider.naming.hot_reader_iam_role()
    client = provider.clients["iam"]
    try:
        client.get_role(RoleName=role_name)
        logger.info(f"✅ Hot Reader IAM Role exists: {_links().link_to_iam_role(role_name, region=provider.region)}")
    except ClientError as e:
        if e.response["Error"]["Code"] == "NoSuchEntity":
            logger.error(f"❌ Hot Reader IAM Role missing: {role_name}")
        else:
            raise

def check_hot_reader_lambda_function(provider: 'AWSProvider'):
    function_name = provider.naming.hot_reader_lambda_function()
    client = provider.clients["lambda"]
    try:
        client.get_function(FunctionName=function_name)
        logger.info(f"✅ Hot Reader Lambda Function exists: {_links().link_to_lambda_function(function_name, region=provider.region)}")
    except ClientError as e:
        if e.response["Error"]["Code"] == "ResourceNotFoundException":
            logger.error(f"❌ Hot Reader Lambda Function missing: {function_name}")
        else:
            raise

def check_hot_reader_last_entry_iam_role(provider: 'AWSProvider'):
    role_name = provider.naming.hot_reader_last_entry_iam_role()
    client = provider.clients["iam"]
    try:
        client.get_role(RoleName=role_name)
        logger.info(f"✅ Hot Reader Last Entry IAM Role exists: {_links().link_to_iam_role(role_name, region=provider.region)}")
    except ClientError as e:
        if e.response["Error"]["Code"] == "NoSuchEntity":
            logger.error(f"❌ Hot Reader Last Entry IAM Role missing: {role_name}")
        else:
            raise

def check_hot_reader_last_entry_lambda_function(provider: 'AWSProvider'):
    function_name = provider.naming.hot_reader_last_entry_lambda_function()
    client = provider.clients["lambda"]
    try:
        client.get_function(FunctionName=function_name)
        logger.info(f"✅ Hot Reader Last Entry Lambda Function exists: {_links().link_to_lambda_function(function_name, region=provider.region)}")
    except ClientError as e:
        if e.response["Error"]["Code"] == "ResourceNotFoundException":
            logger.error(f"❌ Hot Reader Last Entry Lambda Function missing: {function_name}")
        else:
            raise

def check_cold_s3_bucket(provider: 'AWSProvider'):
    bucket_name = provider.naming.cold_s3_bucket()
    client = provider.clients["s3"]
    try:
        client.head_bucket(Bucket=bucket_name)
        logger.info(f"✅ Cold S3 Bucket exists: {_links().link_to_s3_bucket(bucket_name, region=provider.region)}")
    except ClientError as e:
        if e.response["Error"]["Code"] == "404":
            logger.error(f"❌ Cold S3 Bucket missing: {bucket_name}")
        else:
            # 403 Forbidden might imply existence but no access, still treat as check passed regarding existence?
            # Or fail. For now default to raise if not 404.
            raise

def check_cold_archive_mover_iam_role(provider: 'AWSProvider'):
    role_name = provider.naming.cold_archive_mover_iam_role()
    client = provider.clients["iam"]
    try:
        client.get_role(RoleName=role_name)
        logger.info(f"✅ Cold-Archive Mover IAM Role exists: {_links().link_to_iam_role(role_name, region=provider.region)}")
    except ClientError as e:
        if e.response["Error"]["Code"] == "NoSuchEntity":
            logger.error(f"❌ Cold-Archive Mover IAM Role missing: {role_name}")
        else:
            raise

def check_cold_archive_mover_lambda_function(provider: 'AWSProvider'):
    function_name = provider.naming.cold_archive_mover_lambda_function()
    client = provider.clients["lambda"]
    try:
        client.get_function(FunctionName=function_name)
        logger.info(f"✅ Cold-Archive Mover Lambda Function exists: {_links().link_to_lambda_function(function_name, region=provider.region)}")
    except ClientError as e:
        if e.response["Error"]["Code"] == "ResourceNotFoundException":
            logger.error(f"❌ Cold-Archive Mover Lambda Function missing: {function_name}")
        else:
            raise

def check_cold_archive_mover_event_rule(provider: 'AWSProvider'):
    rule_name = provider.naming.cold_archive_mover_event_rule()
    client = provider.clients["events"]
    try:
        client.describe_rule(Name=rule_name)
        logger.info(f"✅ Cold-Archive Mover Event Rule exists: {_links().link_to_event_rule(rule_name, region=provider.region)}")
    except ClientError as e:
        if e.response["Error"]["Code"] == "ResourceNotFoundException":
            logger.error(f"❌ Cold-Archive Mover Event Rule missing: {rule_name}")
        else:
            raise

def check_archive_s3_bucket(provider: 'AWSProvider'):
    bucket_name = provider.naming.archive_s3_bucket()
    client = provider.clients["s3"]
    try:
        client.head_bucket(Bucket=bucket_name)
        logger.info(f"✅ Archive S3 Bucket exists: {_links().link_to_s3_bucket(bucket_name, region=provider.region)}")
    except ClientError as e:
        if e.response["Error"]["Code"] == "404":
            logger.error(f"❌ Archive S3 Bucket missing: {bucket_name}")
        else:
            raise

def info_l3_hot(provider: 'AWSProvider'):
    check_hot_dynamodb_table(provider)
    check_hot_reader_last_entry_iam_role(provider)
    check_hot_reader_last_entry_lambda_function(provider)
    # Check if Hot Reader is present (might be part of hot storage setup)
    check_hot_reader_iam_role(provider)
    check_hot_reader_lambda_function(provider)

def info_l3_cold(provider: 'AWSProvider'):
    check_cold_s3_bucket(provider)
    check_hot_cold_mover_iam_role(provider)
    check_hot_cold_mover_lambda_function(provider)
    check_hot_cold_mover_event_rule(provider)

def info_l3_archive(provider: 'AWSProvider'):
    check_archive_s3_bucket(provider)
    check_cold_archive_mover_iam_role(provider)
    check_cold_archive_mover_lambda_function(provider)
    check_cold_archive_mover_event_rule(provider)

def info_l3(context: 'DeploymentContext', provider: 'AWSProvider'):
    """Check status of all L3 components."""
    logger.info("Checking Hot Storage...")
    info_l3_hot(provider)
    
    logger.info("Checking Cold Storage...")
    info_l3_cold(provider)
    
    logger.info("Checking Archive Storage...")
    info_l3_archive(provider)

