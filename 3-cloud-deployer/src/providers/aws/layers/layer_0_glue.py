"""
Layer 0 (Glue) Component Implementations for AWS.

This module contains ALL multi-cloud receiver implementations that are
deployed by the L0 adapter BEFORE the normal layer deployment.

These components receive data from remote (different-cloud) senders:
- Ingestion: receives from remote Connectors (L1→L2)
- Hot Writer: receives from remote Persisters (L2→L3)
- Cold Writer: receives from remote Hot-to-Cold Movers (L3 internal)
- Archive Writer: receives from remote Cold-to-Archive Movers (L3 internal)
- Hot Reader Function URLs: allow remote Digital Twin Data Connectors to read (L3→L4)

Design:
    Each section is marked with which layer the function is "used in" for clarity.
    The L0 adapter orchestrates WHEN to deploy these based on provider differences.
"""

import json
import os
import time
from typing import TYPE_CHECKING
from logger import logger
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
        "config_events": config.events,
        "config_providers": config.providers
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
# L2 Receivers: Ingestion (when L1 ≠ L2)
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
# L3 Receivers: Hot Writer (when L2 ≠ L3 Hot)
# ==========================================
# Hot Writer is deployed when L2 is on a DIFFERENT cloud than L3 Hot.
# It receives data FROM remote Persisters via HTTP POST.

def create_hot_writer_iam_role(provider: 'AWSProvider') -> None:
    """Creates IAM Role for the Hot Writer Lambda (multi-cloud only).
    
    Hot Writer needs:
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


def destroy_hot_writer_iam_role(provider: 'AWSProvider') -> None:
    """Destroys the Hot Writer IAM Role."""
    _destroy_iam_role(provider, provider.naming.hot_writer_iam_role())


def create_hot_writer_lambda_function(
    provider: 'AWSProvider',
    config: 'ProjectConfig',
    project_path: str
) -> str:
    """Creates the Hot Writer Lambda Function with Function URL (multi-cloud only).
    
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
        Description="Multi-cloud Hot Writer: Receives data from remote Persisters",
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
    """Destroys the Hot Writer Lambda Function and its Function URL."""
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
# L3 Receivers: Cold Writer (when L3 Hot ≠ L3 Cold)
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
    import src.providers.aws.util_aws as util_aws
    
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
# L3 Receivers: Archive Writer (when L3 Cold ≠ L3 Archive)
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
    import src.providers.aws.util_aws as util_aws
    
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
# L3→L4: Hot Reader Function URLs (when L3 Hot ≠ L4)
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
# Check/Info Functions for L0 Components
# ==========================================
# These functions verify that L0 resources exist in the cloud.

def _links():
    """Return AWS console links helper (util_aws module)."""
    import src.providers.aws.util_aws as util_aws
    return util_aws



# --- Ingestion Check Functions ---

def check_ingestion_iam_role(provider: 'AWSProvider') -> bool:
    """Check if Ingestion IAM Role exists.
    
    Returns:
        True if role exists, False otherwise.
    """
    role_name = provider.naming.ingestion_iam_role()
    iam_client = provider.clients["iam"]
    
    try:
        iam_client.get_role(RoleName=role_name)
        logger.info(f"✅ Ingestion IAM Role exists: {_links().link_to_iam_role(role_name, region=provider.region)}")
        return True
    except ClientError as e:
        if e.response["Error"]["Code"] == "NoSuchEntity":
            logger.info(f"❔ Ingestion IAM Role not deployed: {role_name}")
            return False
        raise


def check_ingestion_lambda_function(provider: 'AWSProvider') -> bool:
    """Check if Ingestion Lambda exists and has Function URL."""
    function_name = provider.naming.ingestion_lambda_function()
    lambda_client = provider.clients["lambda"]
    
    try:
        lambda_client.get_function(FunctionName=function_name)
        
        # Check if Function URL exists
        try:
            url_config = lambda_client.get_function_url_config(FunctionName=function_name)
            url = url_config.get("FunctionUrl", "")
            logger.info(f"✅ Ingestion Lambda exists with URL: {_links().link_to_lambda_function(function_name, region=provider.region)}")
            logger.info(f"   Function URL: {url}")
            return True
        except ClientError:
            logger.warning(f"⚠️ Ingestion Lambda exists but missing Function URL: {function_name}")
            return True
            
    except ClientError as e:
        if e.response["Error"]["Code"] == "ResourceNotFoundException":
            logger.info(f"❔ Ingestion Lambda not deployed: {function_name}")
            return False
        raise


# --- Hot Writer Check Functions ---

def check_hot_writer_iam_role(provider: 'AWSProvider') -> bool:
    """Check if Hot Writer IAM Role exists."""
    role_name = provider.naming.hot_writer_iam_role()
    iam_client = provider.clients["iam"]
    
    try:
        iam_client.get_role(RoleName=role_name)
        logger.info(f"✅ Hot Writer IAM Role exists: {_links().link_to_iam_role(role_name, region=provider.region)}")
        return True
    except ClientError as e:
        if e.response["Error"]["Code"] == "NoSuchEntity":
            logger.info(f"❔ Hot Writer IAM Role not deployed: {role_name}")
            return False
        raise


def check_hot_writer_lambda_function(provider: 'AWSProvider') -> bool:
    """Check if Hot Writer Lambda exists and has Function URL."""
    function_name = provider.naming.hot_writer_lambda_function()
    lambda_client = provider.clients["lambda"]
    
    try:
        lambda_client.get_function(FunctionName=function_name)
        
        try:
            url_config = lambda_client.get_function_url_config(FunctionName=function_name)
            url = url_config.get("FunctionUrl", "")
            logger.info(f"✅ Hot Writer Lambda exists with URL: {_links().link_to_lambda_function(function_name, region=provider.region)}")
            logger.info(f"   Function URL: {url}")
            return True
        except ClientError:
            logger.warning(f"⚠️ Hot Writer Lambda exists but missing Function URL: {function_name}")
            return True
            
    except ClientError as e:
        if e.response["Error"]["Code"] == "ResourceNotFoundException":
            logger.info(f"❔ Hot Writer Lambda not deployed: {function_name}")
            return False
        raise


# --- Cold Writer Check Functions ---

def check_cold_writer_iam_role(provider: 'AWSProvider') -> bool:
    """Check if Cold Writer IAM Role exists."""
    role_name = provider.naming.cold_writer_iam_role()
    iam_client = provider.clients["iam"]
    
    try:
        iam_client.get_role(RoleName=role_name)
        logger.info(f"✅ Cold Writer IAM Role exists: {_links().link_to_iam_role(role_name, region=provider.region)}")
        return True
    except ClientError as e:
        if e.response["Error"]["Code"] == "NoSuchEntity":
            logger.info(f"❔ Cold Writer IAM Role not deployed: {role_name}")
            return False
        raise


def check_cold_writer_lambda_function(provider: 'AWSProvider') -> bool:
    """Check if Cold Writer Lambda exists and has Function URL."""
    function_name = provider.naming.cold_writer_lambda_function()
    lambda_client = provider.clients["lambda"]
    
    try:
        lambda_client.get_function(FunctionName=function_name)
        
        try:
            url_config = lambda_client.get_function_url_config(FunctionName=function_name)
            url = url_config.get("FunctionUrl", "")
            logger.info(f"✅ Cold Writer Lambda exists with URL: {_links().link_to_lambda_function(function_name, region=provider.region)}")
            logger.info(f"   Function URL: {url}")
            return True
        except ClientError:
            logger.warning(f"⚠️ Cold Writer Lambda exists but missing Function URL: {function_name}")
            return True
            
    except ClientError as e:
        if e.response["Error"]["Code"] == "ResourceNotFoundException":
            logger.info(f"❔ Cold Writer Lambda not deployed: {function_name}")
            return False
        raise


# --- Archive Writer Check Functions ---

def check_archive_writer_iam_role(provider: 'AWSProvider') -> bool:
    """Check if Archive Writer IAM Role exists."""
    role_name = provider.naming.archive_writer_iam_role()
    iam_client = provider.clients["iam"]
    
    try:
        iam_client.get_role(RoleName=role_name)
        logger.info(f"✅ Archive Writer IAM Role exists: {_links().link_to_iam_role(role_name, region=provider.region)}")
        return True
    except ClientError as e:
        if e.response["Error"]["Code"] == "NoSuchEntity":
            logger.info(f"❔ Archive Writer IAM Role not deployed: {role_name}")
            return False
        raise


def check_archive_writer_lambda_function(provider: 'AWSProvider') -> bool:
    """Check if Archive Writer Lambda exists and has Function URL."""
    function_name = provider.naming.archive_writer_lambda_function()
    lambda_client = provider.clients["lambda"]
    
    try:
        lambda_client.get_function(FunctionName=function_name)
        
        try:
            url_config = lambda_client.get_function_url_config(FunctionName=function_name)
            url = url_config.get("FunctionUrl", "")
            logger.info(f"✅ Archive Writer Lambda exists with URL: {_links().link_to_lambda_function(function_name, region=provider.region)}")
            logger.info(f"   Function URL: {url}")
            return True
        except ClientError:
            logger.warning(f"⚠️ Archive Writer Lambda exists but missing Function URL: {function_name}")
            return True
            
    except ClientError as e:
        if e.response["Error"]["Code"] == "ResourceNotFoundException":
            logger.info(f"❔ Archive Writer Lambda not deployed: {function_name}")
            return False
        raise


# --- Hot Reader Function URL Check Functions ---

def check_hot_reader_function_url(provider: 'AWSProvider') -> bool:
    """Check if Hot Reader has a Function URL configured."""
    function_name = provider.naming.hot_reader_lambda_function()
    lambda_client = provider.clients["lambda"]
    
    try:
        url_config = lambda_client.get_function_url_config(FunctionName=function_name)
        url = url_config.get("FunctionUrl", "")
        logger.info(f"✅ Hot Reader Function URL exists: {url}")
        return True
    except ClientError as e:
        if e.response["Error"]["Code"] == "ResourceNotFoundException":
            logger.info(f"❔ Hot Reader Function URL not configured: {function_name}")
            return False
        raise


def check_hot_reader_last_entry_function_url(provider: 'AWSProvider') -> bool:
    """Check if Hot Reader Last Entry has a Function URL configured."""
    function_name = provider.naming.hot_reader_last_entry_lambda_function()
    lambda_client = provider.clients["lambda"]
    
    try:
        url_config = lambda_client.get_function_url_config(FunctionName=function_name)
        url = url_config.get("FunctionUrl", "")
        logger.info(f"✅ Hot Reader Last Entry Function URL exists: {url}")
        return True
    except ClientError as e:
        if e.response["Error"]["Code"] == "ResourceNotFoundException":
            logger.info(f"❔ Hot Reader Last Entry Function URL not configured: {function_name}")
            return False
        raise
