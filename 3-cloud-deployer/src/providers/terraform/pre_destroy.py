"""Pre-destroy cleanup for SDK-owned resources that block Terraform."""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Iterator

from src.api.deployment_trace import sanitize_deployment_message
from src.providers.cleanup_observability import enforce_cleanup_outcome
from src.providers.cleanup_registry import resource_name_owned_by_prefix

if TYPE_CHECKING:
    from src.core.context import DeploymentContext

logger = logging.getLogger(__name__)


def _paginate(client, operation: str, result_key: str, **kwargs) -> Iterator[dict]:
    paginator = client.get_paginator(operation)
    for page in paginator.paginate(**kwargs):
        yield from page.get(result_key, [])


def cleanup_azure_diagnostics(
    context: "DeploymentContext",
    *,
    dry_run: bool,
) -> None:
    """Remove orphaned diagnostic settings while parent resources still exist."""
    azure_creds = context.credentials.get("azure", {})
    if not azure_creds:
        return

    from azure.identity import ClientSecretCredential

    from src.providers.azure import diagnostic_settings_helper as helper_module
    from src.providers.azure.diagnostic_settings_helper import DiagnosticSettingsHelper

    credential = ClientSecretCredential(
        tenant_id=azure_creds["azure_tenant_id"],
        client_id=azure_creds["azure_client_id"],
        client_secret=azure_creds["azure_client_secret"],
    )
    helper = DiagnosticSettingsHelper(
        credential,
        azure_creds["azure_subscription_id"],
    )
    with enforce_cleanup_outcome(helper_module.logger, "Azure diagnostic settings"):
        result = helper.cleanup_orphaned_by_prefix(
            context.config.digital_twin_name,
            dry_run=dry_run,
        )
    if result.get("errors"):
        raise RuntimeError(
            "Azure diagnostic settings cleanup reported "
            f"{result['errors']} errors"
        )


def cleanup_twinmaker_entities(
    context: "DeploymentContext",
    providers_config: dict,
    *,
    dry_run: bool,
) -> None:
    """Remove SDK-owned TwinMaker children before Terraform deletes workspaces."""
    if not any(
        value == "aws"
        for key, value in providers_config.items()
        if key.startswith("layer_") and key.endswith("_provider")
    ):
        return

    aws_creds = context.credentials.get("aws", {})
    if not aws_creds.get("aws_access_key_id"):
        return

    import boto3

    session = boto3.Session(
        aws_access_key_id=aws_creds["aws_access_key_id"],
        aws_secret_access_key=aws_creds["aws_secret_access_key"],
        aws_session_token=aws_creds.get("aws_session_token"),
        region_name=aws_creds.get("aws_region", "eu-central-1"),
    )
    twinmaker = session.client("iottwinmaker")
    prefix = context.config.digital_twin_name

    workspaces = _paginate(
        twinmaker,
        "list_workspaces",
        "workspaceSummaries",
    )
    for workspace in workspaces:
        workspace_id = workspace.get("workspaceId", "")
        if not resource_name_owned_by_prefix(workspace_id, prefix):
            continue
        if dry_run:
            logger.info("Would clean TwinMaker workspace children: %s", workspace_id)
            continue

        entities = list(
            _paginate(
                twinmaker,
                "list_entities",
                "entitySummaries",
                workspaceId=workspace_id,
            )
        )
        for entity in entities:
            twinmaker.delete_entity(
                workspaceId=workspace_id,
                entityId=entity["entityId"],
                isRecursive=True,
            )

        deadline = time.monotonic() + 60
        while entities and time.monotonic() < deadline:
            time.sleep(3)
            entities = list(
                _paginate(
                    twinmaker,
                    "list_entities",
                    "entitySummaries",
                    workspaceId=workspace_id,
                )
            )
        if entities:
            logger.warning(
                "TwinMaker entities still pending deletion in workspace %s",
                workspace_id,
            )

        component_types = _paginate(
            twinmaker,
            "list_component_types",
            "componentTypeSummaries",
            workspaceId=workspace_id,
        )
        for component_type in component_types:
            component_type_id = component_type.get("componentTypeId", "")
            if not component_type_id or component_type_id.startswith("com.amazon"):
                continue
            for attempt in range(3):
                try:
                    twinmaker.delete_component_type(
                        workspaceId=workspace_id,
                        componentTypeId=component_type_id,
                    )
                    break
                except Exception as exc:
                    message = sanitize_deployment_message(str(exc))
                    if "being used by entities" in message and attempt < 2:
                        time.sleep(2**attempt)
                        continue
                    logger.warning(
                        "TwinMaker component cleanup failed for %s: %s",
                        component_type_id,
                        message,
                    )
                    break


def run_pre_destroy_cleanup(
    context: "DeploymentContext",
    providers_config: dict,
    *,
    dry_run: bool,
) -> None:
    """Run independent pre-destroy cleanup steps without hiding diagnostics."""
    steps = (
        (
            "TwinMaker",
            lambda: cleanup_twinmaker_entities(
                context,
                providers_config,
                dry_run=dry_run,
            ),
        ),
        (
            "Azure diagnostics",
            lambda: cleanup_azure_diagnostics(context, dry_run=dry_run),
        ),
    )
    for label, cleanup in steps:
        try:
            cleanup()
        except Exception as exc:
            logger.warning(
                "%s pre-destroy cleanup failed: %s",
                label,
                sanitize_deployment_message(str(exc)),
            )
