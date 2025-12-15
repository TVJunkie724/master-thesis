"""
Glue Layer Adapter for AWS.

This module orchestrates the deployment of all cross-cloud HTTP entry points
BEFORE the normal layer deployment. This ensures URLs are available in
config_inter_cloud.json when senders (Connector, Persister, Movers) deploy.

The Glue Layer deploys:
- Ingestion (L2 receiver for L1 Connector)
- Hot Writer (L3 receiver for L2 Persister)
- Cold Writer (L3 Cold receiver for Hot-to-Cold Mover)
- Archive Writer (L3 Archive receiver for Cold-to-Archive Mover)
- Hot Reader Function URLs (L3 endpoints for L4 DT Data Connector)

Source: src/providers/aws/layers/glue_adapter.py
Editable: Yes - Core deployment orchestration
"""

import time
import secrets
from typing import TYPE_CHECKING
from logger import logger

if TYPE_CHECKING:
    from src.core.context import DeploymentContext
    from ..provider import AWSProvider


def _check_setup_deployed(provider: 'AWSProvider') -> None:
    """
    Verify that Setup Layer (Resource Group) is deployed before deploying L0.
    
    L0 depends on Setup Layer for:
    - Resource Group to exist for resource grouping
    - Tags to be properly configured
    
    Raises:
        ValueError: If Setup Layer Resource Group is not deployed
    """
    from .layer_setup_aws import check_resource_group
    
    if check_resource_group(provider):
        logger.info("[L0] ✓ Pre-flight check: Setup Layer Resource Group exists")
        return
    else:
        raise ValueError(
            "[L0] Pre-flight check FAILED: Setup Layer Resource Group is NOT deployed. "
            "Deploy Setup Layer first using deploy_setup()."
        )


def deploy_l0(context: 'DeploymentContext', provider: 'AWSProvider') -> None:
    """
    Deploy Layer 0 (cross-cloud HTTP receivers) for AWS.
    
    This must run BEFORE normal layer deployment to ensure all URLs
    are available when senders deploy.
    
    Creates (conditionally):
        1. Ingestion Lambda + Function URL (if L1 ≠ L2)
        2. Hot Writer Lambda + Function URL (if L2 ≠ L3 Hot)
        3. Cold Writer Lambda + Function URL (if L3 Hot ≠ L3 Cold)
        4. Archive Writer Lambda + Function URL (if L3 Cold ≠ L3 Archive)
        5. Hot Reader Function URLs (if L3 ≠ L4)
    
    Args:
        context: Deployment context with config and credentials
        provider: Initialized AWSProvider instance
    """
    from src.core.config_loader import save_inter_cloud_connection
    
    logger.info(f"[L0] Deploying Layer 0 (Glue) for {context.config.digital_twin_name}")
    
    # Pre-flight check: Verify Setup Layer is deployed
    _check_setup_deployed(provider)
    
    # Path to tool source code
    project_path = str(context.project_path.parent.parent)
    
    # Get provider mappings
    providers = context.config.providers
    l1_provider = providers["layer_1_provider"]
    l2_provider = providers["layer_2_provider"]
    l3_hot_provider = providers["layer_3_hot_provider"]
    l3_cold_provider = providers.get("layer_3_cold_provider", l3_hot_provider)
    l3_archive_provider = providers.get("layer_3_archive_provider", l3_cold_provider)
    l4_provider = providers["layer_4_provider"]
    
    # Track what was deployed
    deployed = []
    
    # 1. Ingestion (L2 receiver for remote L1 Connector)
    if l1_provider != l2_provider:
        from .layer_0_glue import (
            create_ingestion_iam_role,
            create_ingestion_lambda_function,
        )
        
        logger.info(f"[Glue] Deploying Ingestion (L1={l1_provider} → L2={l2_provider})")
        create_ingestion_iam_role(provider)
        time.sleep(10)  # Wait for IAM propagation
        
        token = secrets.token_urlsafe(32)
        ingestion_url = create_ingestion_lambda_function(provider, context.config, project_path)
        
        conn_id = f"{l1_provider}_l1_to_{l2_provider}_l2"
        save_inter_cloud_connection(
            project_path=context.project_path.parent.parent,
            conn_id=conn_id,
            url=ingestion_url,
            token=token
        )
        logger.info(f"[Glue] Ingestion URL: {ingestion_url}")
        deployed.append("Ingestion")
    
    # 2. Hot Writer (L3 receiver for remote L2 Persister)
    if l2_provider != l3_hot_provider:
        from .layer_0_glue import (
            create_hot_writer_iam_role,
            create_hot_writer_lambda_function,
        )
        
        logger.info(f"[Glue] Deploying Hot Writer (L2={l2_provider} → L3={l3_hot_provider})")
        create_hot_writer_iam_role(provider)
        time.sleep(10)  # Wait for IAM propagation
        
        token = secrets.token_urlsafe(32)
        writer_url = create_hot_writer_lambda_function(provider, context.config, project_path)
        
        conn_id = f"{l2_provider}_l2_to_{l3_hot_provider}_l3"
        save_inter_cloud_connection(
            project_path=context.project_path.parent.parent,
            conn_id=conn_id,
            url=writer_url,
            token=token
        )
        logger.info(f"[Glue] Hot Writer URL: {writer_url}")
        deployed.append("Hot Writer")
    
    # 3. Cold Writer (L3 Cold receiver for remote Hot-to-Cold Mover)
    if l3_hot_provider != l3_cold_provider:
        from .layer_0_glue import (
            create_cold_writer_iam_role,
            create_cold_writer_lambda_function,
        )
        
        logger.info(f"[L0] Deploying Cold Writer (L3 Hot={l3_hot_provider} → L3 Cold={l3_cold_provider})")
        create_cold_writer_iam_role(provider)
        time.sleep(10)  # Wait for IAM propagation
        
        token = secrets.token_urlsafe(32)
        cold_writer_url = create_cold_writer_lambda_function(
            provider, context.config, project_path, token
        )
        
        conn_id = f"{l3_hot_provider}_l3hot_to_{l3_cold_provider}_l3cold"
        save_inter_cloud_connection(
            project_path=context.project_path.parent.parent,
            conn_id=conn_id,
            url=cold_writer_url,
            token=token
        )
        logger.info(f"[Glue] Cold Writer URL: {cold_writer_url}")
        deployed.append("Cold Writer")
    
    # 4. Archive Writer (L3 Archive receiver for remote Cold-to-Archive Mover)
    if l3_cold_provider != l3_archive_provider:
        from .layer_0_glue import (
            create_archive_writer_iam_role,
            create_archive_writer_lambda_function,
        )
        
        logger.info(f"[L0] Deploying Archive Writer (L3 Cold={l3_cold_provider} → L3 Archive={l3_archive_provider})")
        create_archive_writer_iam_role(provider)
        time.sleep(10)  # Wait for IAM propagation
        
        token = secrets.token_urlsafe(32)
        archive_writer_url = create_archive_writer_lambda_function(
            provider, context.config, project_path, token
        )
        
        conn_id = f"{l3_cold_provider}_l3cold_to_{l3_archive_provider}_l3archive"
        save_inter_cloud_connection(
            project_path=context.project_path.parent.parent,
            conn_id=conn_id,
            url=archive_writer_url,
            token=token
        )
        logger.info(f"[Glue] Archive Writer URL: {archive_writer_url}")
        deployed.append("Archive Writer")
    
    # 5. Hot Reader Function URLs (L3 endpoints for remote L4 DT Data Connector)
    if l3_hot_provider != l4_provider:
        from .layer_0_glue import (
            create_hot_reader_function_url,
            create_hot_reader_last_entry_function_url,
        )
        
        logger.info(f"[L0] Creating Hot Reader Function URLs (L3={l3_hot_provider} → L4={l4_provider})")
        
        token = secrets.token_urlsafe(32)
        hot_reader_url = create_hot_reader_function_url(provider, token)
        hot_reader_last_entry_url = create_hot_reader_last_entry_function_url(provider, token)
        
        conn_id = f"{l3_hot_provider}_l3_to_{l4_provider}_l4"
        save_inter_cloud_connection(
            project_path=context.project_path.parent.parent,
            conn_id=conn_id,
            url=hot_reader_url,
            token=token
        )
        save_inter_cloud_connection(
            project_path=context.project_path.parent.parent,
            conn_id=f"{conn_id}_last_entry",
            url=hot_reader_last_entry_url,
            token=token
        )
        logger.info(f"[Glue] Hot Reader URLs: {hot_reader_url}, {hot_reader_last_entry_url}")
        deployed.append("Hot Reader URLs")
    
    if deployed:
        logger.info(f"[Glue] Deployed: {', '.join(deployed)}")
    else:
        logger.info("[Glue] No cross-cloud boundaries detected, skipping Glue Layer")
    
    logger.info("[L0] Layer 0 deployment complete")


def destroy_l0(context: 'DeploymentContext', provider: 'AWSProvider') -> None:
    """
    Destroy Layer 0 (cross-cloud HTTP receivers) for AWS.
    
    Args:
        context: Deployment context with config and credentials
        provider: Initialized AWSProvider instance
    """
    logger.info(f"[L0] Destroying Layer 0 (Glue) for {context.config.digital_twin_name}")
    
    # Get provider mappings
    providers = context.config.providers
    l1_provider = providers["layer_1_provider"]
    l2_provider = providers["layer_2_provider"]
    l3_hot_provider = providers["layer_3_hot_provider"]
    l3_cold_provider = providers.get("layer_3_cold_provider", l3_hot_provider)
    l3_archive_provider = providers.get("layer_3_archive_provider", l3_cold_provider)
    l4_provider = providers["layer_4_provider"]
    
    # Destroy in reverse order
    
    # 5. Hot Reader Function URLs
    if l3_hot_provider != l4_provider:
        from .layer_0_glue import (
            destroy_hot_reader_function_url,
            destroy_hot_reader_last_entry_function_url,
        )
        logger.info("[L0] Destroying Hot Reader Function URLs")
        destroy_hot_reader_function_url(provider)
        destroy_hot_reader_last_entry_function_url(provider)
    
    # 4. Archive Writer
    if l3_cold_provider != l3_archive_provider:
        from .layer_0_glue import (
            destroy_archive_writer_lambda_function,
            destroy_archive_writer_iam_role,
        )
        logger.info("[L0] Destroying Archive Writer")
        destroy_archive_writer_lambda_function(provider)
        destroy_archive_writer_iam_role(provider)
    
    # 3. Cold Writer
    if l3_hot_provider != l3_cold_provider:
        from .layer_0_glue import (
            destroy_cold_writer_lambda_function,
            destroy_cold_writer_iam_role,
        )
        logger.info("[L0] Destroying Cold Writer")
        destroy_cold_writer_lambda_function(provider)
        destroy_cold_writer_iam_role(provider)
    
    # 2. Hot Writer
    if l2_provider != l3_hot_provider:
        from .layer_0_glue import (
            destroy_hot_writer_lambda_function,
            destroy_hot_writer_iam_role,
        )
        logger.info("[L0] Destroying Hot Writer")
        destroy_hot_writer_lambda_function(provider)
        destroy_hot_writer_iam_role(provider)
    
    # 1. Ingestion
    if l1_provider != l2_provider:
        from .layer_0_glue import (
            destroy_ingestion_lambda_function,
            destroy_ingestion_iam_role,
        )
        logger.info("[L0] Destroying Ingestion")
        destroy_ingestion_lambda_function(provider)
        destroy_ingestion_iam_role(provider)
    
    logger.info("[L0] Layer 0 destruction complete")


def info_l0(context: 'DeploymentContext', provider: 'AWSProvider') -> None:
    """
    Check status of Layer 0 components for AWS.
    
    Checks each cross-cloud boundary and verifies the corresponding
    glue components are deployed.
    
    Args:
        context: Deployment context with config and credentials
        provider: Initialized AWSProvider instance
    """
    from .layer_0_glue import (
        check_ingestion_iam_role,
        check_ingestion_lambda_function,
        check_hot_writer_iam_role,
        check_hot_writer_lambda_function,
        check_cold_writer_iam_role,
        check_cold_writer_lambda_function,
        check_archive_writer_iam_role,
        check_archive_writer_lambda_function,
        check_hot_reader_function_url,
        check_hot_reader_last_entry_function_url,
    )
    
    logger.info(f"[L0] Checking Layer 0 status for {context.config.digital_twin_name}")
    
    providers = context.config.providers
    l1_provider = providers["layer_1_provider"]
    l2_provider = providers["layer_2_provider"]
    l3_hot_provider = providers["layer_3_hot_provider"]
    l3_cold_provider = providers.get("layer_3_cold_provider", l3_hot_provider)
    l3_archive_provider = providers.get("layer_3_archive_provider", l3_cold_provider)
    l4_provider = providers["layer_4_provider"]
    
    boundaries_found = False
    
    # 1. Check Ingestion (L1 → L2)
    if l1_provider != l2_provider:
        boundaries_found = True
        logger.info(f"[L0] L1→L2 boundary detected (L1={l1_provider}, L2={l2_provider})")
        check_ingestion_iam_role(provider)
        check_ingestion_lambda_function(provider)
    
    # 2. Check Hot Writer (L2 → L3 Hot)
    if l2_provider != l3_hot_provider:
        boundaries_found = True
        logger.info(f"[L0] L2→L3 boundary detected (L2={l2_provider}, L3={l3_hot_provider})")
        check_hot_writer_iam_role(provider)
        check_hot_writer_lambda_function(provider)
    
    # 3. Check Cold Writer (L3 Hot → L3 Cold)
    if l3_hot_provider != l3_cold_provider:
        boundaries_found = True
        logger.info(f"[L0] L3 Hot→Cold boundary detected (Hot={l3_hot_provider}, Cold={l3_cold_provider})")
        check_cold_writer_iam_role(provider)
        check_cold_writer_lambda_function(provider)
    
    # 4. Check Archive Writer (L3 Cold → L3 Archive)
    if l3_cold_provider != l3_archive_provider:
        boundaries_found = True
        logger.info(f"[L0] L3 Cold→Archive boundary detected (Cold={l3_cold_provider}, Archive={l3_archive_provider})")
        check_archive_writer_iam_role(provider)
        check_archive_writer_lambda_function(provider)
    
    # 5. Check Hot Reader Function URLs (L3 Hot → L4)
    if l3_hot_provider != l4_provider:
        boundaries_found = True
        logger.info(f"[L0] L3→L4 boundary detected (L3={l3_hot_provider}, L4={l4_provider})")
        check_hot_reader_function_url(provider)
        check_hot_reader_last_entry_function_url(provider)
    
    if not boundaries_found:
        logger.info("[L0] No cross-cloud boundaries detected - L0 components not needed")
    else:
        logger.info("[L0] Layer 0 status check complete")
