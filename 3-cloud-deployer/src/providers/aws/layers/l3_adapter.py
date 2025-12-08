"""
Layer 3 (Storage) Adapter for AWS.

This module provides context-based wrappers around the Layer 3
deployment functions, passing provider and config explicitly.
"""

from typing import TYPE_CHECKING
from logger import logger

if TYPE_CHECKING:
    from src.core.context import DeploymentContext
    from ..provider import AWSProvider


def deploy_l3_hot(context: 'DeploymentContext', provider: 'AWSProvider') -> None:
    """Deploy Layer 3 Hot Storage components."""
    from .layer_3_storage import (
        create_hot_dynamodb_table,
        create_hot_reader_iam_role,
        create_hot_reader_lambda_function,
        create_hot_reader_last_entry_iam_role,
        create_hot_reader_last_entry_lambda_function,
        create_l3_api_gateway,
    )
    
    logger.info(f"[L3-Hot] Deploying Layer 3 Hot Storage for {context.config.digital_twin_name}")
    context.set_active_layer("3_hot")
    
    project_path = str(context.project_path.parent.parent)
    
    create_hot_dynamodb_table(provider)
    create_hot_reader_iam_role(provider)
    create_hot_reader_lambda_function(provider, context.config, project_path)
    create_hot_reader_last_entry_iam_role(provider)
    create_hot_reader_last_entry_lambda_function(provider, context.config, project_path)
    
    if context.config.should_deploy_api_gateway("aws"):
        create_l3_api_gateway(provider, context.config)
    
    logger.info(f"[L3-Hot] Layer 3 Hot Storage deployment complete")


def destroy_l3_hot(context: 'DeploymentContext', provider: 'AWSProvider') -> None:
    """Destroy Layer 3 Hot Storage components."""
    from .layer_3_storage import (
        destroy_hot_dynamodb_table,
        destroy_hot_reader_lambda_function,
        destroy_hot_reader_iam_role,
        destroy_hot_reader_last_entry_lambda_function,
        destroy_hot_reader_last_entry_iam_role,
        destroy_l3_api_gateway,
    )
    
    logger.info(f"[L3-Hot] Destroying Layer 3 Hot Storage for {context.config.digital_twin_name}")
    context.set_active_layer("3_hot")
    
    destroy_l3_api_gateway(provider)
    destroy_hot_reader_last_entry_lambda_function(provider)
    destroy_hot_reader_last_entry_iam_role(provider)
    destroy_hot_reader_lambda_function(provider)
    destroy_hot_reader_iam_role(provider)
    destroy_hot_dynamodb_table(provider)
    
    logger.info(f"[L3-Hot] Layer 3 Hot Storage destruction complete")


def deploy_l3_cold(context: 'DeploymentContext', provider: 'AWSProvider') -> None:
    """Deploy Layer 3 Cold Storage components."""
    from .layer_3_storage import (
        create_cold_s3_bucket,
        create_hot_cold_mover_iam_role,
        create_hot_cold_mover_lambda_function,
        create_hot_cold_mover_event_rule,
    )
    
    logger.info(f"[L3-Cold] Deploying Layer 3 Cold Storage for {context.config.digital_twin_name}")
    context.set_active_layer("3_cold")
    
    project_path = str(context.project_path.parent.parent)
    
    create_cold_s3_bucket(provider)
    create_hot_cold_mover_iam_role(provider)
    create_hot_cold_mover_lambda_function(provider, context.config, project_path)
    create_hot_cold_mover_event_rule(provider)
    
    logger.info(f"[L3-Cold] Layer 3 Cold Storage deployment complete")


def destroy_l3_cold(context: 'DeploymentContext', provider: 'AWSProvider') -> None:
    """Destroy Layer 3 Cold Storage components."""
    from .layer_3_storage import (
        destroy_hot_cold_mover_event_rule,
        destroy_hot_cold_mover_lambda_function,
        destroy_hot_cold_mover_iam_role,
        destroy_cold_s3_bucket,
    )
    
    logger.info(f"[L3-Cold] Destroying Layer 3 Cold Storage for {context.config.digital_twin_name}")
    context.set_active_layer("3_cold")
    
    destroy_hot_cold_mover_event_rule(provider)
    destroy_hot_cold_mover_lambda_function(provider)
    destroy_hot_cold_mover_iam_role(provider)
    destroy_cold_s3_bucket(provider)
    
    logger.info(f"[L3-Cold] Layer 3 Cold Storage destruction complete")


def deploy_l3_archive(context: 'DeploymentContext', provider: 'AWSProvider') -> None:
    """Deploy Layer 3 Archive Storage components."""
    from .layer_3_storage import (
        create_archive_s3_bucket,
        create_cold_archive_mover_iam_role,
        create_cold_archive_mover_lambda_function,
        create_cold_archive_mover_event_rule,
    )
    
    logger.info(f"[L3-Archive] Deploying Layer 3 Archive Storage for {context.config.digital_twin_name}")
    context.set_active_layer("3_archive")
    
    project_path = str(context.project_path.parent.parent)
    
    create_archive_s3_bucket(provider)
    create_cold_archive_mover_iam_role(provider)
    create_cold_archive_mover_lambda_function(provider, context.config, project_path)
    create_cold_archive_mover_event_rule(provider)
    
    logger.info(f"[L3-Archive] Layer 3 Archive Storage deployment complete")


def destroy_l3_archive(context: 'DeploymentContext', provider: 'AWSProvider') -> None:
    """Destroy Layer 3 Archive Storage components."""
    from .layer_3_storage import (
        destroy_cold_archive_mover_event_rule,
        destroy_cold_archive_mover_lambda_function,
        destroy_cold_archive_mover_iam_role,
        destroy_archive_s3_bucket,
    )
    
    logger.info(f"[L3-Archive] Destroying Layer 3 Archive Storage for {context.config.digital_twin_name}")
    context.set_active_layer("3_archive")
    
    destroy_cold_archive_mover_event_rule(provider)
    destroy_cold_archive_mover_lambda_function(provider)
    destroy_cold_archive_mover_iam_role(provider)
    destroy_archive_s3_bucket(provider)
    
    logger.info(f"[L3-Archive] Layer 3 Archive Storage destruction complete")
