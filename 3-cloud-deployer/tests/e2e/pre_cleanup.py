"""
Pre-Test Cleanup Module.

Provides functions to clean orphaned cloud resources before starting E2E tests.
This ensures tests start with a clean slate even if previous runs were interrupted.

Usage:
    from tests.e2e.pre_cleanup import cleanup_orphans_for_scenario
    cleanup_orphans_for_scenario("aws-azure", credentials)
"""
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def cleanup_orphans_for_scenario(
    scenario_name: str,
    credentials: dict,
    dry_run: bool = False
) -> dict:
    """
    Clean up orphaned cloud resources from previous failed test runs.
    
    This function runs SDK cleanup for all cloud providers, ensuring any
    resources left behind from interrupted tests are removed.
    
    Args:
        scenario_name: Scenario name (e.g., "aws-azure")
        credentials: Dict with aws, azure, gcp credential sections
        dry_run: If True, log what would be deleted without deleting
        
    Returns:
        Dict with cleanup results per provider: {"aws": True, "azure": True, "gcp": True}
    """
    prefix = f"sc2-{scenario_name}"
    results = {}
    
    logger.info(f"[PRE-CLEANUP] Checking for orphaned resources: {prefix}")
    if dry_run:
        logger.info("[PRE-CLEANUP] DRY RUN MODE - no resources will be deleted")
    
    # AWS cleanup
    if credentials.get("aws"):
        try:
            from src.providers.aws.cleanup import cleanup_aws_resources
            logger.info(f"[PRE-CLEANUP] AWS: Cleaning orphans for {prefix}...")
            cleanup_aws_resources(
                credentials, 
                prefix, 
                cleanup_identity_user=False,  # Don't delete identity users in pre-cleanup
                platform_user_email="",
                dry_run=dry_run
            )
            results["aws"] = True
            logger.info("[PRE-CLEANUP] AWS: Done")
        except Exception as e:
            logger.warning(f"[PRE-CLEANUP] AWS: Error - {e}")
            results["aws"] = False
    else:
        logger.info("[PRE-CLEANUP] AWS: Skipped (no credentials)")
        results["aws"] = None
    
    # Azure cleanup
    if credentials.get("azure"):
        try:
            from src.providers.azure.cleanup import cleanup_azure_resources
            logger.info(f"[PRE-CLEANUP] Azure: Cleaning orphans for {prefix}...")
            cleanup_azure_resources(
                credentials,
                prefix,
                cleanup_entra_user=False,  # Don't delete Entra users in pre-cleanup
                platform_user_email="",
                dry_run=dry_run
            )
            results["azure"] = True
            logger.info("[PRE-CLEANUP] Azure: Done")
        except Exception as e:
            logger.warning(f"[PRE-CLEANUP] Azure: Error - {e}")
            results["azure"] = False
    else:
        logger.info("[PRE-CLEANUP] Azure: Skipped (no credentials)")
        results["azure"] = None
    
    # GCP cleanup
    if credentials.get("gcp"):
        try:
            from src.providers.gcp.cleanup import cleanup_gcp_resources
            logger.info(f"[PRE-CLEANUP] GCP: Cleaning orphans for {prefix}...")
            cleanup_gcp_resources(credentials, prefix, dry_run=dry_run)
            results["gcp"] = True
            logger.info("[PRE-CLEANUP] GCP: Done")
        except Exception as e:
            logger.warning(f"[PRE-CLEANUP] GCP: Error - {e}")
            results["gcp"] = False
    else:
        logger.info("[PRE-CLEANUP] GCP: Skipped (no credentials)")
        results["gcp"] = None
    
    logger.info(f"[PRE-CLEANUP] Complete: {results}")
    return results


def cleanup_stale_project_directory(project_path, scenario_name: str) -> bool:
    """
    Check if project directory exists and clean it up.
    
    This handles the case where Terraform state exists but cloud resources
    were already deleted (or never created due to early failure).
    
    Args:
        project_path: Path to project directory
        scenario_name: Scenario name for logging
        
    Returns:
        True if directory was cleaned, False otherwise
    """
    import shutil
    from pathlib import Path
    
    path = Path(project_path) if not hasattr(project_path, 'exists') else project_path
    
    if path.exists():
        logger.info(f"[PRE-CLEANUP] Found stale project directory: {path}")
        try:
            shutil.rmtree(path)
            logger.info(f"[PRE-CLEANUP] Removed stale directory: {path}")
            return True
        except Exception as e:
            logger.warning(f"[PRE-CLEANUP] Could not remove directory: {e}")
            return False
    
    return False
