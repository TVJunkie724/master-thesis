"""
Layer 3 (Storage) Adapter for AWS.

This module provides context-based wrappers around the existing Layer 3
deployment functions in src/aws/deployer_layers/layer_3_storage.py.

Layer 3 is split into three tiers for multi-cloud flexibility:
- Hot: DynamoDB (recent data, low latency)
- Cold: S3 Standard-IA (older data, occasional access)
- Archive: S3 Glacier (long-term storage)

Note:
    The underlying layer code still uses globals internally.
    This adapter provides the context-based interface.
"""

from typing import TYPE_CHECKING
from logger import logger

if TYPE_CHECKING:
    from src.core.context import DeploymentContext
    from ..provider import AWSProvider


def deploy_l3_hot(context: 'DeploymentContext', provider: 'AWSProvider') -> None:
    """
    Deploy Layer 3 Hot Storage components for AWS.
    
    Creates:
        1. DynamoDB Table for hot storage
        2. Hot Reader IAM Role and Lambda (for TwinMaker queries)
        3. Hot Reader Last Entry Lambda (for latest value queries)
        4. API Gateway (optional, for cross-cloud access)
    
    Args:
        context: Deployment context with config and credentials
        provider: Initialized AWSProvider instance
    """
    from src.aws.deployer_layers.layer_3_storage import (
        create_hot_dynamodb_table,
        create_hot_reader_iam_role,
        create_hot_reader_lambda_function,
        create_hot_reader_last_entry_iam_role,
        create_hot_reader_last_entry_lambda_function,
    )
    
    logger.info(f"[L3-Hot] Deploying Layer 3 Hot Storage for {context.config.digital_twin_name}")
    context.set_active_layer("3_hot")
    
    create_hot_dynamodb_table()
    create_hot_reader_iam_role()
    create_hot_reader_lambda_function()
    create_hot_reader_last_entry_iam_role()
    create_hot_reader_last_entry_lambda_function()
    
    # API Gateway for cross-cloud access (check via context)
    if context.config.should_deploy_api_gateway("aws"):
        from src.aws.deployer_layers.layer_3_storage import create_l3_api_gateway
        create_l3_api_gateway()
    
    logger.info(f"[L3-Hot] Layer 3 Hot Storage deployment complete")


def destroy_l3_hot(context: 'DeploymentContext', provider: 'AWSProvider') -> None:
    """Destroy Layer 3 Hot Storage components."""
    from src.aws.deployer_layers.layer_3_storage import (
        destroy_hot_dynamodb_table,
        destroy_hot_reader_lambda_function,
        destroy_hot_reader_iam_role,
        destroy_hot_reader_last_entry_lambda_function,
        destroy_hot_reader_last_entry_iam_role,
        destroy_l3_api_gateway,
    )
    
    logger.info(f"[L3-Hot] Destroying Layer 3 Hot Storage for {context.config.digital_twin_name}")
    context.set_active_layer("3_hot")
    
    destroy_l3_api_gateway()
    destroy_hot_reader_last_entry_lambda_function()
    destroy_hot_reader_last_entry_iam_role()
    destroy_hot_reader_lambda_function()
    destroy_hot_reader_iam_role()
    destroy_hot_dynamodb_table()
    
    logger.info(f"[L3-Hot] Layer 3 Hot Storage destruction complete")


def deploy_l3_cold(context: 'DeploymentContext', provider: 'AWSProvider') -> None:
    """
    Deploy Layer 3 Cold Storage components for AWS.
    
    Creates:
        1. S3 Bucket (Standard-IA tier)
        2. Hot-to-Cold Mover IAM Role and Lambda
        3. EventBridge Rule for scheduled migration
    """
    from src.aws.deployer_layers.layer_3_storage import (
        create_cold_s3_bucket,
        create_hot_cold_mover_iam_role,
        create_hot_cold_mover_lambda_function,
        create_hot_cold_mover_event_rule,
    )
    
    logger.info(f"[L3-Cold] Deploying Layer 3 Cold Storage for {context.config.digital_twin_name}")
    context.set_active_layer("3_cold")
    
    create_cold_s3_bucket()
    create_hot_cold_mover_iam_role()
    create_hot_cold_mover_lambda_function()
    create_hot_cold_mover_event_rule()
    
    logger.info(f"[L3-Cold] Layer 3 Cold Storage deployment complete")


def destroy_l3_cold(context: 'DeploymentContext', provider: 'AWSProvider') -> None:
    """Destroy Layer 3 Cold Storage components."""
    from src.aws.deployer_layers.layer_3_storage import (
        destroy_hot_cold_mover_event_rule,
        destroy_hot_cold_mover_lambda_function,
        destroy_hot_cold_mover_iam_role,
        destroy_cold_s3_bucket,
    )
    
    logger.info(f"[L3-Cold] Destroying Layer 3 Cold Storage for {context.config.digital_twin_name}")
    context.set_active_layer("3_cold")
    
    destroy_hot_cold_mover_event_rule()
    destroy_hot_cold_mover_lambda_function()
    destroy_hot_cold_mover_iam_role()
    destroy_cold_s3_bucket()
    
    logger.info(f"[L3-Cold] Layer 3 Cold Storage destruction complete")


def deploy_l3_archive(context: 'DeploymentContext', provider: 'AWSProvider') -> None:
    """
    Deploy Layer 3 Archive Storage components for AWS.
    
    Creates:
        1. S3 Bucket (Glacier Deep Archive tier)
        2. Cold-to-Archive Mover IAM Role and Lambda
        3. EventBridge Rule for scheduled migration
    """
    from src.aws.deployer_layers.layer_3_storage import (
        create_archive_s3_bucket,
        create_cold_archive_mover_iam_role,
        create_cold_archive_mover_lambda_function,
        create_cold_archive_mover_event_rule,
    )
    
    logger.info(f"[L3-Archive] Deploying Layer 3 Archive Storage for {context.config.digital_twin_name}")
    context.set_active_layer("3_archive")
    
    create_archive_s3_bucket()
    create_cold_archive_mover_iam_role()
    create_cold_archive_mover_lambda_function()
    create_cold_archive_mover_event_rule()
    
    logger.info(f"[L3-Archive] Layer 3 Archive Storage deployment complete")


def destroy_l3_archive(context: 'DeploymentContext', provider: 'AWSProvider') -> None:
    """Destroy Layer 3 Archive Storage components."""
    from src.aws.deployer_layers.layer_3_storage import (
        destroy_cold_archive_mover_event_rule,
        destroy_cold_archive_mover_lambda_function,
        destroy_cold_archive_mover_iam_role,
        destroy_archive_s3_bucket,
    )
    
    logger.info(f"[L3-Archive] Destroying Layer 3 Archive Storage for {context.config.digital_twin_name}")
    context.set_active_layer("3_archive")
    
    destroy_cold_archive_mover_event_rule()
    destroy_cold_archive_mover_lambda_function()
    destroy_cold_archive_mover_iam_role()
    destroy_archive_s3_bucket()
    
    logger.info(f"[L3-Archive] Layer 3 Archive Storage destruction complete")

