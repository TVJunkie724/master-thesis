"""
AWS Resource Tagging Helpers.

This module provides DRY helper functions for tagging AWS resources
with consistent DigitalTwin, Project, and Layer tags.

All resources deployed for a digital twin are tagged to enable:
- Resource grouping via AWS Resource Groups
- Cost tracking and allocation
- Easy identification and cleanup

Usage:
    from src.providers.aws.layers.tagging_helpers import (
        tag_iam_role, tag_lambda, tag_dynamodb_table, tag_s3_bucket
    )
"""

from typing import TYPE_CHECKING
from logger import logger

if TYPE_CHECKING:
    from providers.aws.provider import AWSProvider


# ==========================================
# Core Tag Formatters
# ==========================================

def get_tags_list(provider: 'AWSProvider', layer: str) -> list:
    """
    Get common tags as a list of {Key, Value} dicts.
    
    For: Lambda, DynamoDB, Step Functions, EventBridge
    """
    tags = provider.naming.get_common_tags(layer)
    return [{"Key": k, "Value": v} for k, v in tags.items()]


def get_tags_dict(provider: 'AWSProvider', layer: str) -> dict:
    """
    Get common tags as a plain dict.
    
    For: Grafana, TwinMaker workspaces
    """
    return provider.naming.get_common_tags(layer)


# ==========================================
# IAM Role Tagging
# ==========================================

def tag_iam_role(provider: 'AWSProvider', role_name: str, layer: str) -> None:
    """Tag an IAM role after creation (required - roles don't support inline tags)."""
    iam_client = provider.clients["iam"]
    tags = provider.naming.get_common_tags(layer)
    iam_client.tag_role(
        RoleName=role_name,
        Tags=[{"Key": k, "Value": v} for k, v in tags.items()]
    )
    logger.info(f"Tagged IAM role: {role_name}")


# ==========================================
# Lambda Function Tagging
# ==========================================

def tag_lambda(provider: 'AWSProvider', function_arn: str, layer: str) -> None:
    """Tag a Lambda function after creation."""
    lambda_client = provider.clients["lambda"]
    tags = provider.naming.get_common_tags(layer)
    lambda_client.tag_resource(Resource=function_arn, Tags=tags)
    logger.info(f"Tagged Lambda function: {function_arn.split(':')[-1]}")


# ==========================================
# S3 Bucket Tagging
# ==========================================

def tag_s3_bucket(provider: 'AWSProvider', bucket_name: str, layer: str) -> None:
    """Tag an S3 bucket after creation."""
    s3_client = provider.clients["s3"]
    tags = provider.naming.get_common_tags(layer)
    s3_client.put_bucket_tagging(
        Bucket=bucket_name,
        Tagging={"TagSet": [{"Key": k, "Value": v} for k, v in tags.items()]}
    )
    logger.info(f"Tagged S3 bucket: {bucket_name}")


# ==========================================
# DynamoDB Table Tagging
# ==========================================

def tag_dynamodb_table(provider: 'AWSProvider', table_arn: str, layer: str) -> None:
    """Tag a DynamoDB table after creation."""
    dynamodb_client = provider.clients["dynamodb"]
    tags = get_tags_list(provider, layer)
    dynamodb_client.tag_resource(ResourceArn=table_arn, Tags=tags)
    logger.info(f"Tagged DynamoDB table: {table_arn.split('/')[-1]}")


# ==========================================
# Step Functions Tagging
# ==========================================

def tag_step_function(provider: 'AWSProvider', state_machine_arn: str, layer: str) -> None:
    """Tag a Step Function state machine after creation."""
    sf_client = provider.clients["stepfunctions"]
    tags = get_tags_list(provider, layer)
    sf_client.tag_resource(resourceArn=state_machine_arn, tags=tags)
    logger.info(f"Tagged Step Function: {state_machine_arn.split(':')[-1]}")


# ==========================================
# EventBridge Rule Tagging
# ==========================================

def tag_eventbridge_rule(provider: 'AWSProvider', rule_arn: str, layer: str) -> None:
    """Tag an EventBridge rule after creation."""
    events_client = provider.clients["events"]
    tags = get_tags_list(provider, layer)
    events_client.tag_resource(ResourceARN=rule_arn, Tags=tags)
    logger.info(f"Tagged EventBridge rule: {rule_arn.split('/')[-1]}")
