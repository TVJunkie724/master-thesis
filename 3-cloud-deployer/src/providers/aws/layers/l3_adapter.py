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
        # Multi-cloud: Writer
        create_writer_iam_role,
        create_writer_lambda_function,
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
    
    # Multi-cloud: Writer (when L2 is on different cloud)
    # NOTE: No fallbacks - missing provider config is a critical error
    l2_provider = context.config.providers["layer_2_provider"]
    l3_provider = context.config.providers["layer_3_hot_provider"]
    
    if l2_provider != l3_provider:
        import time
        import secrets
        from src.core.config_loader import save_inter_cloud_connection
        
        logger.info(f"[L3-Hot] Multi-cloud: Deploying Writer (L2 on {l2_provider}, L3 on {l3_provider})")
        create_writer_iam_role(provider)
        time.sleep(10)  # Wait for IAM propagation
        
        # Generate token for inter-cloud auth
        token = secrets.token_urlsafe(32)
        writer_url = create_writer_lambda_function(provider, context.config, project_path)
        logger.info(f"[L3-Hot] Multi-cloud: Writer URL: {writer_url}")
        
        # Persist connection info for remote Persister
        conn_id = f"{l2_provider}_l2_to_aws_l3"
        save_inter_cloud_connection(
            project_path=context.project_path.parent.parent,
            conn_id=conn_id,
            url=writer_url,
            token=token
        )
        logger.info(f"[L3-Hot] Saved inter-cloud connection: {conn_id}")
    
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
        # Multi-cloud: Writer
        destroy_writer_lambda_function,
        destroy_writer_iam_role,
    )
    
    logger.info(f"[L3-Hot] Destroying Layer 3 Hot Storage for {context.config.digital_twin_name}")
    context.set_active_layer("3_hot")
    
    # Multi-cloud: Writer (when L2 is on different cloud)
    # NOTE: No fallbacks - missing provider config is a critical error
    l2_provider = context.config.providers["layer_2_provider"]
    l3_provider = context.config.providers["layer_3_hot_provider"]
    
    if l2_provider != l3_provider:
        logger.info(f"[L3-Hot] Multi-cloud: Destroying Writer")
        destroy_writer_lambda_function(provider)
        destroy_writer_iam_role(provider)
    
    destroy_l3_api_gateway(provider)
    destroy_hot_reader_last_entry_lambda_function(provider)
    destroy_hot_reader_last_entry_iam_role(provider)
    destroy_hot_reader_lambda_function(provider)
    destroy_hot_reader_iam_role(provider)
    destroy_hot_dynamodb_table(provider)
    
    logger.info(f"[L3-Hot] Layer 3 Hot Storage destruction complete")


def deploy_l3_cold(context: 'DeploymentContext', provider: 'AWSProvider') -> None:
    """Deploy Layer 3 Cold Storage components.
    
    If this AWS L3 Cold is receiving data from a different cloud's L3 Hot,
    also deploys the Cold Writer Lambda with Function URL.
    """
    from .layer_3_storage import (
        create_cold_s3_bucket,
        create_hot_cold_mover_iam_role,
        create_hot_cold_mover_lambda_function,
        create_hot_cold_mover_event_rule,
        create_cold_writer_iam_role,
        create_cold_writer_lambda_function,
    )
    from src.core.config_loader import save_inter_cloud_connection
    import secrets
    
    logger.info(f"[L3-Cold] Deploying Layer 3 Cold Storage for {context.config.digital_twin_name}")
    context.set_active_layer("3_cold")
    
    project_path = str(context.project_path.parent.parent)
    
    create_cold_s3_bucket(provider)
    create_hot_cold_mover_iam_role(provider)
    create_hot_cold_mover_lambda_function(provider, context.config, project_path)
    create_hot_cold_mover_event_rule(provider)
    
    # Multi-cloud: Deploy Cold Writer if L3 Hot is on different cloud
    l3_hot_provider = context.config.providers["layer_3_hot_provider"]
    l3_cold_provider = context.config.providers["layer_3_cold_provider"]
    
    if l3_hot_provider != l3_cold_provider and l3_cold_provider == "aws":
        logger.info(f"[L3-Cold] Multi-cloud detected: L3 Hot ({l3_hot_provider}) -> L3 Cold (aws)")
        
        # Generate secure token for inter-cloud auth
        token = secrets.token_urlsafe(32)
        
        create_cold_writer_iam_role(provider)
        function_url = create_cold_writer_lambda_function(
            provider, context.config, project_path, token
        )
        
        # Save connection info for the remote mover to use
        conn_id = f"{l3_hot_provider}_l3hot_to_aws_l3cold"
        save_inter_cloud_connection(
            project_path=context.project_path.parent.parent,
            conn_id=conn_id,
            url=function_url,
            token=token
        )
        logger.info(f"[L3-Cold] Cold Writer deployed for multi-cloud ingestion")
    
    logger.info(f"[L3-Cold] Layer 3 Cold Storage deployment complete")


def destroy_l3_cold(context: 'DeploymentContext', provider: 'AWSProvider') -> None:
    """Destroy Layer 3 Cold Storage components."""
    from .layer_3_storage import (
        destroy_hot_cold_mover_event_rule,
        destroy_hot_cold_mover_lambda_function,
        destroy_hot_cold_mover_iam_role,
        destroy_cold_s3_bucket,
        destroy_cold_writer_lambda_function,
        destroy_cold_writer_iam_role,
    )
    
    logger.info(f"[L3-Cold] Destroying Layer 3 Cold Storage for {context.config.digital_twin_name}")
    context.set_active_layer("3_cold")
    
    # Destroy Cold Writer if it exists (multi-cloud)
    destroy_cold_writer_lambda_function(provider)
    destroy_cold_writer_iam_role(provider)
    
    destroy_hot_cold_mover_event_rule(provider)
    destroy_hot_cold_mover_lambda_function(provider)
    destroy_hot_cold_mover_iam_role(provider)
    destroy_cold_s3_bucket(provider)
    
    logger.info(f"[L3-Cold] Layer 3 Cold Storage destruction complete")


def deploy_l3_archive(context: 'DeploymentContext', provider: 'AWSProvider') -> None:
    """Deploy Layer 3 Archive Storage components.
    
    If this AWS L3 Archive is receiving data from a different cloud's L3 Cold,
    also deploys the Archive Writer Lambda with Function URL.
    """
    from .layer_3_storage import (
        create_archive_s3_bucket,
        create_cold_archive_mover_iam_role,
        create_cold_archive_mover_lambda_function,
        create_cold_archive_mover_event_rule,
        create_archive_writer_iam_role,
        create_archive_writer_lambda_function,
    )
    from src.core.config_loader import save_inter_cloud_connection
    import secrets
    
    logger.info(f"[L3-Archive] Deploying Layer 3 Archive Storage for {context.config.digital_twin_name}")
    context.set_active_layer("3_archive")
    
    project_path = str(context.project_path.parent.parent)
    
    create_archive_s3_bucket(provider)
    create_cold_archive_mover_iam_role(provider)
    create_cold_archive_mover_lambda_function(provider, context.config, project_path)
    create_cold_archive_mover_event_rule(provider)
    
    # Multi-cloud: Deploy Archive Writer if L3 Cold is on different cloud
    l3_cold_provider = context.config.providers["layer_3_cold_provider"]
    l3_archive_provider = context.config.providers["layer_3_archive_provider"]
    
    if l3_cold_provider != l3_archive_provider and l3_archive_provider == "aws":
        logger.info(f"[L3-Archive] Multi-cloud detected: L3 Cold ({l3_cold_provider}) -> L3 Archive (aws)")
        
        token = secrets.token_urlsafe(32)
        
        create_archive_writer_iam_role(provider)
        function_url = create_archive_writer_lambda_function(
            provider, context.config, project_path, token
        )
        
        conn_id = f"{l3_cold_provider}_l3cold_to_aws_l3archive"
        save_inter_cloud_connection(
            project_path=context.project_path.parent.parent,
            conn_id=conn_id,
            url=function_url,
            token=token
        )
        logger.info(f"[L3-Archive] Archive Writer deployed for multi-cloud ingestion")
    
    logger.info(f"[L3-Archive] Layer 3 Archive Storage deployment complete")


def destroy_l3_archive(context: 'DeploymentContext', provider: 'AWSProvider') -> None:
    """Destroy Layer 3 Archive Storage components."""
    from .layer_3_storage import (
        destroy_cold_archive_mover_event_rule,
        destroy_cold_archive_mover_lambda_function,
        destroy_cold_archive_mover_iam_role,
        destroy_archive_s3_bucket,
        destroy_archive_writer_lambda_function,
        destroy_archive_writer_iam_role,
    )
    
    logger.info(f"[L3-Archive] Destroying Layer 3 Archive Storage for {context.config.digital_twin_name}")
    context.set_active_layer("3_archive")
    
    # Destroy Archive Writer if it exists (multi-cloud)
    destroy_archive_writer_lambda_function(provider)
    destroy_archive_writer_iam_role(provider)
    
    destroy_cold_archive_mover_event_rule(provider)
    destroy_cold_archive_mover_lambda_function(provider)
    destroy_cold_archive_mover_iam_role(provider)
    destroy_archive_s3_bucket(provider)
    
    logger.info(f"[L3-Archive] Layer 3 Archive Storage destruction complete")


def info_l3(context: 'DeploymentContext', provider: 'AWSProvider') -> None:
    """
    Check status of Layer 3 (Storage) components for AWS.
    
    Args:
        context: Deployment context with config and credentials
        provider: Initialized AWSProvider instance
    """
    from .layer_3_storage import info_l3 as _info_l3_impl
    
    logger.info(f"[L3] Checking status for {context.config.digital_twin_name}")
    _info_l3_impl(context, provider)

