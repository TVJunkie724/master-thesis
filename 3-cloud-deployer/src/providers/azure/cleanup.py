"""
Azure SDK Cleanup Module.

Provides fallback cleanup for Azure resources that may be orphaned after
Terraform destroy fails or misses resources.
"""
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def cleanup_azure_resources(
    credentials: dict, 
    prefix: str, 
    cleanup_entra_user: bool = False, 
    grafana_email: str = "",
    dry_run: bool = False
) -> None:
    """
    Clean up Azure resources matching prefix.
    
    Args:
        credentials: Dict with Azure credentials
        prefix: Resource name prefix (e.g., 'tf-e2e-az')
        cleanup_entra_user: Delete Entra ID user if True
        grafana_email: Email for Entra ID user lookup
        dry_run: Log what would be deleted without deleting
        
    Resources cleaned:
        - CosmosDB accounts
        - Grafana workspaces
        - IoT Hubs
        - Digital Twins instances
        - Function Apps
        - Storage Accounts
        - Logic Apps
        - App Service Plans
        - Entra ID users (conditional)
        - Resource Groups (nuclear option)
    """
    from azure.identity import ClientSecretCredential
    from azure.mgmt.resource import ResourceManagementClient
    
    azure_creds = credentials.get("azure", {})
    tenant_id = azure_creds["azure_tenant_id"]
    
    credential = ClientSecretCredential(
        tenant_id=tenant_id,
        client_id=azure_creds["azure_client_id"],
        client_secret=azure_creds["azure_client_secret"]
    )
    
    subscription_id = azure_creds["azure_subscription_id"]
    resource_client = ResourceManagementClient(credential, subscription_id)
    
    logger.info(f"[Azure SDK] Fallback cleanup for prefix: {prefix}")
    if dry_run:
        logger.info("[Azure SDK] DRY RUN MODE - no resources will be deleted")
    
    # ========================================
    # PHASE 1: Check for orphaned resources
    # ========================================
    
    # 1. CosmosDB accounts
    logger.info("[CosmosDB] Checking for orphans...")
    try:
        from azure.mgmt.cosmosdb import CosmosDBManagementClient
        cosmos_client = CosmosDBManagementClient(credential, subscription_id)
        for account in cosmos_client.database_accounts.list():
            if prefix in account.name:
                logger.info(f"  Found orphan: {account.name}")
                if dry_run:
                    logger.info(f"    [DRY RUN] Would delete")
                else:
                    try:
                        rg_name = account.id.split('/')[4]
                        poller = cosmos_client.database_accounts.begin_delete(rg_name, account.name)
                        poller.result(timeout=600)
                        logger.info(f"    ✓ Deleted")
                    except Exception as e:
                        logger.warning(f"    ✗ Error: {e}")
    except Exception as e:
        logger.warning(f"  Error: {e}")
    
    # 2. Grafana workspaces
    logger.info("[Grafana] Checking for orphans...")
    try:
        from azure.mgmt.dashboard import DashboardManagementClient
        dashboard_client = DashboardManagementClient(credential, subscription_id)
        for workspace in dashboard_client.grafana.list():
            if prefix in workspace.name:
                logger.info(f"  Found orphan: {workspace.name}")
                if dry_run:
                    logger.info(f"    [DRY RUN] Would delete")
                else:
                    try:
                        rg_name = workspace.id.split('/')[4]
                        poller = dashboard_client.grafana.begin_delete(rg_name, workspace.name)
                        poller.result(timeout=600)
                        logger.info(f"    ✓ Deleted")
                    except Exception as e:
                        logger.warning(f"    ✗ Error: {e}")
    except Exception as e:
        logger.warning(f"  Error: {e}")
    
    # 3. IoT Hubs
    logger.info("[IoT Hub] Checking for orphans...")
    try:
        from azure.mgmt.iothub import IotHubClient
        iothub_client = IotHubClient(credential, subscription_id)
        for hub in iothub_client.iot_hub_resource.list_by_subscription():
            if prefix in hub.name:
                logger.info(f"  Found orphan: {hub.name}")
                if dry_run:
                    logger.info(f"    [DRY RUN] Would delete")
                else:
                    try:
                        rg_name = hub.id.split('/')[4]
                        poller = iothub_client.iot_hub_resource.begin_delete(rg_name, hub.name)
                        poller.result(timeout=600)
                        logger.info(f"    ✓ Deleted")
                    except Exception as e:
                        logger.warning(f"    ✗ Error: {e}")
    except Exception as e:
        logger.warning(f"  Error: {e}")
    
    # 4. Digital Twins instances
    logger.info("[Digital Twins] Checking for orphans...")
    try:
        from azure.mgmt.digitaltwins import AzureDigitalTwinsManagementClient
        dt_client = AzureDigitalTwinsManagementClient(credential, subscription_id)
        for instance in dt_client.digital_twins.list():
            if prefix in instance.name:
                logger.info(f"  Found orphan: {instance.name}")
                if dry_run:
                    logger.info(f"    [DRY RUN] Would delete")
                else:
                    try:
                        rg_name = instance.id.split('/')[4]
                        poller = dt_client.digital_twins.begin_delete(rg_name, instance.name)
                        poller.result(timeout=600)
                        logger.info(f"    ✓ Deleted")
                    except Exception as e:
                        logger.warning(f"    ✗ Error: {e}")
    except Exception as e:
        logger.warning(f"  Error: {e}")
    
    # 5. Function Apps
    logger.info("[Function Apps] Checking for orphans...")
    try:
        from azure.mgmt.web import WebSiteManagementClient
        web_client = WebSiteManagementClient(credential, subscription_id)
        for app in web_client.web_apps.list():
            if prefix in app.name:
                logger.info(f"  Found orphan: {app.name}")
                if dry_run:
                    logger.info(f"    [DRY RUN] Would delete")
                else:
                    try:
                        rg_name = app.id.split('/')[4]
                        web_client.web_apps.delete(rg_name, app.name)
                        logger.info(f"    ✓ Deleted")
                    except Exception as e:
                        logger.warning(f"    ✗ Error: {e}")
    except Exception as e:
        logger.warning(f"  Error: {e}")
    
    # 6. Storage Accounts
    logger.info("[Storage Accounts] Checking for orphans...")
    try:
        from azure.mgmt.storage import StorageManagementClient
        storage_client = StorageManagementClient(credential, subscription_id)
        prefix_nohyphen = prefix.replace("-", "")
        for account in storage_client.storage_accounts.list():
            if prefix in account.name or prefix_nohyphen in account.name:
                logger.info(f"  Found orphan: {account.name}")
                if dry_run:
                    logger.info(f"    [DRY RUN] Would delete")
                else:
                    try:
                        rg_name = account.id.split('/')[4]
                        storage_client.storage_accounts.delete(rg_name, account.name)
                        logger.info(f"    ✓ Deleted")
                    except Exception as e:
                        logger.warning(f"    ✗ Error: {e}")
    except Exception as e:
        logger.warning(f"  Error: {e}")
    
    # 7. Logic Apps
    logger.info("[Logic Apps] Checking for orphans...")
    try:
        from azure.mgmt.logic import LogicManagementClient
        logic_client = LogicManagementClient(credential, subscription_id)
        for workflow in logic_client.workflows.list_by_subscription():
            if prefix in workflow.name:
                logger.info(f"  Found orphan: {workflow.name}")
                if dry_run:
                    logger.info(f"    [DRY RUN] Would delete")
                else:
                    try:
                        rg_name = workflow.id.split('/')[4]
                        logic_client.workflows.delete(rg_name, workflow.name)
                        logger.info(f"    ✓ Deleted")
                    except Exception as e:
                        logger.warning(f"    ✗ Error: {e}")
    except Exception as e:
        logger.warning(f"  Error: {e}")
    
    # 8. App Service Plans
    logger.info("[App Service Plans] Checking for orphans...")
    try:
        from azure.mgmt.web import WebSiteManagementClient
        web_client = WebSiteManagementClient(credential, subscription_id)
        for plan in web_client.app_service_plans.list():
            if prefix in plan.name:
                logger.info(f"  Found orphan: {plan.name}")
                if dry_run:
                    logger.info(f"    [DRY RUN] Would delete")
                else:
                    try:
                        rg_name = plan.id.split('/')[4]
                        web_client.app_service_plans.delete(rg_name, plan.name)
                        logger.info(f"    ✓ Deleted")
                    except Exception as e:
                        logger.warning(f"    ✗ Error: {e}")
    except Exception as e:
        logger.warning(f"  Error: {e}")
    
    # ========================================
    # PHASE 2: Delete Resource Groups (nuclear option)
    # ========================================
    logger.info("[Resource Groups] Cleaning up (nuclear option)...")
    try:
        for rg in resource_client.resource_groups.list():
            if prefix in rg.name:
                logger.info(f"  Found RG: {rg.name}")
                if dry_run:
                    logger.info(f"    [DRY RUN] Would delete RG and all contents")
                else:
                    try:
                        poller = resource_client.resource_groups.begin_delete(rg.name)
                        poller.result(timeout=600)
                        logger.info(f"    ✓ Deleted")
                    except Exception as e:
                        logger.warning(f"    ✗ Error: {e}")
    except Exception as e:
        logger.warning(f"  Error listing RGs: {e}")
    
    # ========================================
    # PHASE 3: Entra ID User Cleanup (conditional)
    # ========================================
    if cleanup_entra_user:
        logger.info("[Entra ID] Checking for user to clean up...")
        try:
            from msgraph import GraphServiceClient
            from azure.identity import ClientSecretCredential as GraphCredential
            
            graph_credential = GraphCredential(
                tenant_id=tenant_id,
                client_id=azure_creds["azure_client_id"],
                client_secret=azure_creds["azure_client_secret"]
            )
            
            graph_client = GraphServiceClient(credentials=graph_credential)
            
            if not grafana_email:
                logger.info("  No grafana_email provided, skipping")
            else:
                logger.info(f"  Looking for user: {grafana_email}")
                try:
                    users = graph_client.users.get()
                    if users and users.value:
                        for user in users.value:
                            if (user.user_principal_name and 
                                user.user_principal_name.lower() == grafana_email.lower()):
                                logger.info(f"  Found user: {user.user_principal_name} (ID: {user.id})")
                                if dry_run:
                                    logger.info(f"    [DRY RUN] Would delete")
                                else:
                                    graph_client.users.by_user_id(user.id).delete()
                                    logger.info(f"    ✓ Deleted")
                                break
                        else:
                            logger.info(f"  User not found (may already be deleted)")
                except Exception as e:
                    logger.warning(f"  Error searching users: {e}")
        except ImportError:
            logger.warning("  msgraph SDK not installed, skipping Entra ID cleanup")
        except Exception as e:
            logger.warning(f"  Error: {e}")
    else:
        logger.info("[Entra ID] Skipping (user was pre-existing)")
    
    logger.info("[Azure SDK] Fallback cleanup complete")
