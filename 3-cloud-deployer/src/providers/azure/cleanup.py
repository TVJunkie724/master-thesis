"""Explicit, fail-closed Azure SDK cleanup for Terraform orphan recovery."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any

from src.providers.cleanup_observability import CleanupRun
from src.providers.cleanup_registry import resource_name_owned_by_prefix

logger = logging.getLogger(__name__)

GRAPH_SCOPE = "https://graph.microsoft.com/.default"
GRAPH_USERS_URL = "https://graph.microsoft.com/v1.0/users"


def _cleanup_entra_user(
    credential,
    platform_user_email: str,
    *,
    dry_run: bool,
    http_session=None,
) -> bool:
    """Delete one exact Entra principal through bounded Microsoft Graph calls."""
    import requests

    session = http_session or requests.Session()
    token = credential.get_token(GRAPH_SCOPE).token
    escaped_email = platform_user_email.replace("'", "''")
    response = session.get(
        GRAPH_USERS_URL,
        headers={"Authorization": f"Bearer {token}"},
        params={
            "$filter": f"userPrincipalName eq '{escaped_email}'",
            "$select": "id,userPrincipalName",
        },
        timeout=30,
    )
    response.raise_for_status()
    users = response.json().get("value", [])
    matching = [
        user
        for user in users
        if str(user.get("userPrincipalName", "")).casefold()
        == platform_user_email.casefold()
    ]
    if not matching:
        logger.info("  User not found (may already be deleted)")
        return False
    if len(matching) > 1:
        raise RuntimeError("Microsoft Graph returned multiple exact user matches")
    user = matching[0]
    logger.info("  Found platform user: %s", user["userPrincipalName"])
    if dry_run:
        return True
    delete_response = session.delete(
        f"{GRAPH_USERS_URL}/{user['id']}",
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )
    delete_response.raise_for_status()
    logger.info("    Deleted")
    return True


@dataclass(frozen=True)
class _AzureCleanupContext:
    credential: Any
    subscription_id: str
    resource_client: Any
    prefix: str
    dry_run: bool
    run: CleanupRun


def _owned(name: str, context: _AzureCleanupContext, **kwargs) -> bool:
    return resource_name_owned_by_prefix(name, context.prefix, **kwargs)


def _resource_group(resource_id: str) -> str:
    parts = resource_id.split("/")
    if len(parts) <= 4 or not parts[4]:
        raise ValueError("Azure resource ID does not contain a resource group")
    return parts[4]


def _delete_or_log(
    context: _AzureCleanupContext,
    step: str,
    resource: str,
    delete,
    *,
    dry_run_message: str = "Would delete",
) -> None:
    logger.info("  Found orphan: %s", resource)
    if context.dry_run:
        logger.info("    [DRY RUN] %s", dry_run_message)
        return

    def execute_delete() -> bool:
        delete()
        return True

    if context.run.attempt(step, resource, execute_delete, default=False):
        logger.info("    Deleted")


def _cleanup_log_analytics(context: _AzureCleanupContext) -> None:
    from azure.mgmt.loganalytics import LogAnalyticsManagementClient

    client = LogAnalyticsManagementClient(context.credential, context.subscription_id)
    for workspace in client.workspaces.list():
        if workspace.name.startswith(f"{context.prefix}-") and "-logs-" in workspace.name:
            _delete_or_log(
                context,
                "Log Analytics",
                workspace.name,
                lambda workspace=workspace: client.workspaces.begin_delete(
                    _resource_group(workspace.id),
                    workspace.name,
                    force=True,
                ).result(timeout=300),
            )


def _cleanup_application_insights(context: _AzureCleanupContext) -> None:
    from azure.mgmt.applicationinsights import ApplicationInsightsManagementClient

    client = ApplicationInsightsManagementClient(
        context.credential,
        context.subscription_id,
    )
    for component in client.components.list():
        if component.name.startswith(f"{context.prefix}-") and "-insights-" in component.name:
            _delete_or_log(
                context,
                "Application Insights",
                component.name,
                lambda component=component: client.components.delete(
                    _resource_group(component.id),
                    component.name,
                ),
            )


def _cleanup_subscription_diagnostics(context: _AzureCleanupContext) -> None:
    from .diagnostic_settings_helper import DiagnosticSettingsHelper

    helper = DiagnosticSettingsHelper(context.credential, context.subscription_id)
    result = helper.cleanup_orphaned_by_prefix(
        context.prefix,
        dry_run=context.dry_run,
    )
    if result.get("errors"):
        raise RuntimeError(
            f"Diagnostic settings cleanup reported {result['errors']} errors"
        )


def _cleanup_resource_diagnostics(context: _AzureCleanupContext) -> None:
    from .diagnostic_settings_helper import DiagnosticSettingsHelper

    helper = DiagnosticSettingsHelper(context.credential, context.subscription_id)
    for resource_group in context.resource_client.resource_groups.list():
        if not _owned(resource_group.name, context):
            continue
        resources = list(
            context.resource_client.resources.list_by_resource_group(resource_group.name)
        )
        targets = [(resource.id, resource.name) for resource in resources]
        targets.extend(
            (f"{resource.id}/blobServices/default", f"{resource.name}/blobServices/default")
            for resource in resources
            if resource.type == "Microsoft.Storage/storageAccounts"
        )
        for resource_id, resource_name in targets:
            settings = context.run.attempt(
                "Diagnostic Settings",
                resource_name,
                lambda resource_id=resource_id: list(helper.list(resource_id)),
                default=[],
            )
            for setting in settings or []:
                setting_name = setting.get("name", "unknown")
                _delete_or_log(
                    context,
                    "Diagnostic Settings",
                    f"{resource_name}/{setting_name}",
                    lambda resource_id=resource_id, setting_name=setting_name: helper.delete(
                        resource_id,
                        setting_name,
                    ),
                )


def _cleanup_role_assignments(context: _AzureCleanupContext) -> None:
    from azure.mgmt.authorization import AuthorizationManagementClient

    client = AuthorizationManagementClient(context.credential, context.subscription_id)
    for resource_group in context.resource_client.resource_groups.list():
        if not _owned(resource_group.name, context):
            continue
        scope = (
            f"/subscriptions/{context.subscription_id}"
            f"/resourceGroups/{resource_group.name}"
        )
        for assignment in client.role_assignments.list_for_scope(scope):
            if not assignment.scope.casefold().startswith(scope.casefold()):
                continue
            _delete_or_log(
                context,
                "Role Assignments",
                assignment.id,
                lambda assignment=assignment: client.role_assignments.delete_by_id(
                    assignment.id
                ),
            )


def _cleanup_cosmos_role_assignments(context: _AzureCleanupContext) -> None:
    from azure.mgmt.cosmosdb import CosmosDBManagementClient

    client = CosmosDBManagementClient(context.credential, context.subscription_id)
    for account in client.database_accounts.list():
        if not _owned(account.name, context):
            continue
        resource_group = _resource_group(account.id)
        for assignment in client.sql_resources.list_sql_role_assignments(
            resource_group,
            account.name,
        ):
            _delete_or_log(
                context,
                "CosmosDB SQL Roles",
                f"{account.name}/{assignment.name}",
                lambda assignment=assignment, account=account: client.sql_resources.begin_delete_sql_role_assignment(
                    assignment.name,
                    _resource_group(account.id),
                    account.name,
                ).result(timeout=120),
            )


def _cleanup_cosmos_accounts(context: _AzureCleanupContext) -> None:
    from azure.mgmt.cosmosdb import CosmosDBManagementClient

    client = CosmosDBManagementClient(context.credential, context.subscription_id)
    for account in client.database_accounts.list():
        if _owned(account.name, context):
            _delete_or_log(
                context,
                "CosmosDB",
                account.name,
                lambda account=account: client.database_accounts.begin_delete(
                    _resource_group(account.id),
                    account.name,
                ).result(timeout=600),
            )


def _cleanup_grafana(context: _AzureCleanupContext) -> None:
    from azure.mgmt.dashboard import DashboardManagementClient

    client = DashboardManagementClient(context.credential, context.subscription_id)
    for workspace in client.grafana.list():
        if _owned(workspace.name, context):
            _delete_or_log(
                context,
                "Grafana",
                workspace.name,
                lambda workspace=workspace: client.grafana.begin_delete(
                    _resource_group(workspace.id),
                    workspace.name,
                ).result(timeout=600),
            )


def _cleanup_iot_hubs(context: _AzureCleanupContext) -> None:
    from azure.mgmt.iothub import IotHubClient

    client = IotHubClient(context.credential, context.subscription_id)
    for hub in client.iot_hub_resource.list_by_subscription():
        if _owned(hub.name, context):
            _delete_or_log(
                context,
                "IoT Hub",
                hub.name,
                lambda hub=hub: client.iot_hub_resource.begin_delete(
                    _resource_group(hub.id),
                    hub.name,
                ).result(timeout=600),
            )


def _cleanup_digital_twins(context: _AzureCleanupContext) -> None:
    from azure.mgmt.digitaltwins import AzureDigitalTwinsManagementClient

    client = AzureDigitalTwinsManagementClient(
        context.credential,
        context.subscription_id,
    )
    for instance in client.digital_twins.list():
        if _owned(instance.name, context):
            _delete_or_log(
                context,
                "Digital Twins",
                instance.name,
                lambda instance=instance: client.digital_twins.begin_delete(
                    _resource_group(instance.id),
                    instance.name,
                ).result(timeout=600),
            )


def _cleanup_function_apps(context: _AzureCleanupContext) -> None:
    from azure.mgmt.web import WebSiteManagementClient

    client = WebSiteManagementClient(context.credential, context.subscription_id)
    for app in client.web_apps.list():
        if _owned(app.name, context):
            _delete_or_log(
                context,
                "Function Apps",
                app.name,
                lambda app=app: client.web_apps.delete(
                    _resource_group(app.id),
                    app.name,
                ),
            )


def _cleanup_storage_accounts(context: _AzureCleanupContext) -> None:
    from azure.mgmt.storage import StorageManagementClient

    client = StorageManagementClient(context.credential, context.subscription_id)
    for account in client.storage_accounts.list():
        if _owned(account.name, context, allow_compact=True):
            _delete_or_log(
                context,
                "Storage Accounts",
                account.name,
                lambda account=account: client.storage_accounts.delete(
                    _resource_group(account.id),
                    account.name,
                ),
            )


def _cleanup_logic_apps(context: _AzureCleanupContext) -> None:
    from azure.mgmt.logic import LogicManagementClient

    client = LogicManagementClient(context.credential, context.subscription_id)
    for workflow in client.workflows.list_by_subscription():
        if _owned(workflow.name, context):
            _delete_or_log(
                context,
                "Logic Apps",
                workflow.name,
                lambda workflow=workflow: client.workflows.delete(
                    _resource_group(workflow.id),
                    workflow.name,
                ),
            )


def _cleanup_app_service_plans(context: _AzureCleanupContext) -> None:
    from azure.mgmt.web import WebSiteManagementClient

    client = WebSiteManagementClient(context.credential, context.subscription_id)
    for plan in client.app_service_plans.list():
        if _owned(plan.name, context):
            _delete_or_log(
                context,
                "App Service Plans",
                plan.name,
                lambda plan=plan: client.app_service_plans.delete(
                    _resource_group(plan.id),
                    plan.name,
                ),
            )


def _cleanup_resource_groups(context: _AzureCleanupContext) -> None:
    for resource_group in context.resource_client.resource_groups.list():
        if _owned(resource_group.name, context):
            _delete_or_log(
                context,
                "Resource Groups",
                resource_group.name,
                lambda resource_group=resource_group: context.resource_client.resource_groups.begin_delete(
                    resource_group.name
                ).result(timeout=600),
                dry_run_message="Would delete resource group and all contents",
            )


_CLEANUP_STEPS = (
    ("Log Analytics", _cleanup_log_analytics),
    ("Application Insights", _cleanup_application_insights),
    ("Subscription Diagnostics", _cleanup_subscription_diagnostics),
    ("Resource Diagnostics", _cleanup_resource_diagnostics),
    ("Role Assignments", _cleanup_role_assignments),
    ("CosmosDB SQL Roles", _cleanup_cosmos_role_assignments),
    ("CosmosDB", _cleanup_cosmos_accounts),
    ("Grafana", _cleanup_grafana),
    ("IoT Hub", _cleanup_iot_hubs),
    ("Digital Twins", _cleanup_digital_twins),
    ("Function Apps", _cleanup_function_apps),
    ("Storage Accounts", _cleanup_storage_accounts),
    ("Logic Apps", _cleanup_logic_apps),
    ("App Service Plans", _cleanup_app_service_plans),
    ("Resource Groups", _cleanup_resource_groups),
)


def cleanup_azure_resources(
    credentials: dict,
    prefix: str,
    cleanup_entra_user: bool = False,
    platform_user_email: str = "",
    dry_run: bool = False,
) -> None:
    """Clean Azure resources and raise one typed aggregate for incomplete work."""
    from azure.identity import ClientSecretCredential
    from azure.mgmt.resource.resources import ResourceManagementClient

    azure_creds = credentials.get("azure", {})
    credential = ClientSecretCredential(
        tenant_id=azure_creds["azure_tenant_id"],
        client_id=azure_creds["azure_client_id"],
        client_secret=azure_creds["azure_client_secret"],
    )
    subscription_id = azure_creds["azure_subscription_id"]
    resource_client = ResourceManagementClient(credential, subscription_id)
    run = CleanupRun("Azure", logger)
    context = _AzureCleanupContext(
        credential,
        subscription_id,
        resource_client,
        prefix,
        dry_run,
        run,
    )

    logger.info("[Azure SDK] Fallback cleanup for prefix: %s", prefix)
    if dry_run:
        logger.info("[Azure SDK] DRY RUN MODE - no resources will be deleted")

    for label, step in _CLEANUP_STEPS:
        logger.info("[%s] Checking for orphans...", label)
        run.attempt(label, "inventory", lambda step=step: step(context))

    if cleanup_entra_user and platform_user_email:
        run.attempt(
            "Entra ID",
            platform_user_email,
            lambda: _cleanup_entra_user(
                credential,
                platform_user_email,
                dry_run=dry_run,
            ),
        )

    run.raise_if_failed()
    logger.info("[Azure SDK] Fallback cleanup complete")
