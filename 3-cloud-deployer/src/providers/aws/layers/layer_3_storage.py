"""
Layer 3 (Storage) Deployment for AWS.

This module handles deployment and destruction of Layer 3 components:
- Hot Storage: DynamoDB + Hot Reader Lambdas
- Cold Storage: S3 + Hot-to-Cold Mover
- Archive Storage: S3 + Cold-to-Archive Mover
- API Gateway (optional, for cross-cloud access)

All functions accept provider and config parameters instead of using globals.
"""

import json
import os
import time
from datetime import datetime, timezone
from typing import TYPE_CHECKING
from logger import logger
# util is imported lazily inside functions to avoid circular import
import aws.util_aws as util_aws
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
        BillingMode="PAY_PER_REQUEST"
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

    logger.info("Waiting for propagation...")
    time.sleep(20)


def destroy_hot_cold_mover_iam_role(provider: 'AWSProvider') -> None:
    _destroy_iam_role(provider, provider.naming.hot_cold_mover_iam_role())


def create_hot_cold_mover_lambda_function(provider: 'AWSProvider', config: 'ProjectConfig', project_path: str) -> None:
    """Creates the Hot-to-Cold Data Mover Lambda."""
    function_name = provider.naming.hot_cold_mover_lambda_function()
    role_name = provider.naming.hot_cold_mover_iam_role()
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
        Code={"ZipFile": util.compile_lambda_function(os.path.join(core_lambda_dir, "hot-to-cold-mover"))},
        Description="L3 Hot-to-Cold Mover: Moves old data to S3",
        Timeout=60,
        MemorySize=256,
        Publish=True,
        Environment={
            "Variables": {
                "DIGITAL_TWIN_INFO": json.dumps(_get_digital_twin_info(config)),
                "DYNAMODB_TABLE_NAME": provider.naming.hot_dynamodb_table(),
                "S3_BUCKET_NAME": provider.naming.cold_s3_bucket()
            }
        }
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
    """Creates the Cold-to-Archive Data Mover Lambda."""
    function_name = provider.naming.cold_archive_mover_lambda_function()
    role_name = provider.naming.cold_archive_mover_iam_role()
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
        Code={"ZipFile": util.compile_lambda_function(os.path.join(core_lambda_dir, "cold-to-archive-mover"))},
        Description="L3 Cold-to-Archive Mover: Moves old data to Glacier",
        Timeout=60,
        MemorySize=256,
        Publish=True,
        Environment={
            "Variables": {
                "DIGITAL_TWIN_INFO": json.dumps(_get_digital_twin_info(config)),
                "COLD_S3_BUCKET_NAME": provider.naming.cold_s3_bucket(),
                "ARCHIVE_S3_BUCKET_NAME": provider.naming.archive_s3_bucket()
            }
        }
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
# 9. API Gateway (for cross-cloud)
# ==========================================

def create_l3_api_gateway(provider: 'AWSProvider', config: 'ProjectConfig') -> None:
    """Creates the API Gateway for cross-cloud L3 access."""
    api_name = provider.naming.api_gateway()
    apigw_client = provider.clients["apigatewayv2"]
    lambda_client = provider.clients["lambda"]
    sts_client = provider.clients["sts"]

    # Create HTTP API
    response = apigw_client.create_api(
        Name=api_name,
        ProtocolType="HTTP",
        Description="API Gateway for cross-cloud L3 access"
    )
    api_id = response["ApiId"]
    logger.info(f"Created API Gateway: {api_name}")

    # Get Hot Reader function ARN
    function_name = provider.naming.hot_reader_lambda_function()
    response = lambda_client.get_function(FunctionName=function_name)
    function_arn = response['Configuration']['FunctionArn']

    region = lambda_client.meta.region_name
    account_id = sts_client.get_caller_identity()['Account']

    # Create integration
    response = apigw_client.create_integration(
        ApiId=api_id,
        IntegrationType="AWS_PROXY",
        IntegrationUri=function_arn,
        PayloadFormatVersion="2.0"
    )
    integration_id = response["IntegrationId"]

    # Create route
    apigw_client.create_route(
        ApiId=api_id,
        RouteKey="GET /data",
        Target=f"integrations/{integration_id}"
    )

    # Create stage
    apigw_client.create_stage(ApiId=api_id, StageName="prod", AutoDeploy=True)

    # Add Lambda permission
    lambda_client.add_permission(
        FunctionName=function_name,
        StatementId="apigw-invoke",
        Action="lambda:InvokeFunction",
        Principal="apigateway.amazonaws.com",
        SourceArn=f"arn:aws:execute-api:{region}:{account_id}:{api_id}/*"
    )

    logger.info(f"API Gateway endpoint: https://{api_id}.execute-api.{region}.amazonaws.com/prod/data")


def destroy_l3_api_gateway(provider: 'AWSProvider') -> None:
    """Destroys the L3 API Gateway."""
    api_name = provider.naming.api_gateway()
    apigw_client = provider.clients["apigatewayv2"]
    lambda_client = provider.clients["lambda"]

    # Find API by name
    response = apigw_client.get_apis()
    api_id = None
    for api in response.get("Items", []):
        if api["Name"] == api_name:
            api_id = api["ApiId"]
            break

    if not api_id:
        return

    # Remove Lambda permission
    try:
        lambda_client.remove_permission(
            FunctionName=provider.naming.hot_reader_lambda_function(),
            StatementId="apigw-invoke"
        )
    except ClientError:
        pass

    apigw_client.delete_api(ApiId=api_id)
    logger.info(f"Deleted API Gateway: {api_name}")
