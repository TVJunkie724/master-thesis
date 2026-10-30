"""Pre-destroy cleanup for SDK-owned resources that block Terraform."""

from __future__ import annotations

import logging
import json
from pathlib import Path
import time
from typing import TYPE_CHECKING, Iterator

from src.api.deployment_trace import sanitize_deployment_message
from src.providers.cleanup_registry import resource_name_owned_by_prefix

if TYPE_CHECKING:
    from src.core.context import DeploymentContext

logger = logging.getLogger(__name__)


def _paginate(client, operation: str, result_key: str, **kwargs) -> Iterator[dict]:
    # TwinMaker exposes nextToken even where boto3 has no paginator model.
    if client.can_paginate(operation):
        for page in client.get_paginator(operation).paginate(**kwargs):
            yield from page.get(result_key, [])
        return
    token = None
    while True:
        page = getattr(client, operation)(
            **kwargs, **({"nextToken": token} if token else {})
        )
        yield from page.get(result_key, [])
        token = page.get("nextToken")
        if not token:
            return


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


def disable_owned_sns_archives(context, state_path: Path | None, *, dry_run: bool) -> None:
    """SNS requires archive removal before deletion; use only this run's state."""
    credentials = context.credentials.get("aws", {})
    if not credentials or state_path is None or not Path(state_path).is_file():
        return
    state = json.loads(Path(state_path).read_text())
    topics = []
    for resource in state.get("resources", []):
        if resource.get("mode") != "managed" or resource.get("type") != "aws_sns_topic":
            continue
        for instance in resource.get("instances", []):
            attributes = instance.get("attributes", {})
            arn = attributes.get("arn", "")
            if attributes.get("archive_policy") and resource_name_owned_by_prefix(
                arn.rsplit(":", 1)[-1], context.config.digital_twin_name
            ):
                topics.append(arn)
    if dry_run or not topics:
        return
    import boto3
    client = boto3.client(
        "sns", region_name=credentials["aws_region"],
        aws_access_key_id=credentials["aws_access_key_id"],
        aws_secret_access_key=credentials["aws_secret_access_key"],
        aws_session_token=credentials.get("aws_session_token"),
    )
    for arn in topics:
        client.set_topic_attributes(TopicArn=arn, AttributeName="ArchivePolicy", AttributeValue="{}")


def cleanup_aws_simulator_identities(context, *, dry_run: bool) -> None:
    """Remove exclusive SDK simulator identities before Terraform deletes Things."""
    credentials = context.credentials.get("aws", {})
    devices = getattr(context.config, "iot_devices", [])
    if dry_run or not credentials or not devices:
        return
    import boto3
    from botocore.exceptions import ClientError

    client = boto3.client(
        "iot", region_name=credentials["aws_region"],
        aws_access_key_id=credentials["aws_access_key_id"],
        aws_secret_access_key=credentials["aws_secret_access_key"],
        aws_session_token=credentials.get("aws_session_token"),
    )
    for device in devices:
        thing = f"{context.config.digital_twin_name}-{device['id']}"
        policy = f"{thing}-policy"
        try:
            page = client.list_targets_for_policy(policyName=policy)
        except ClientError as error:
            if error.response["Error"]["Code"] == "ResourceNotFoundException":
                continue
            raise
        targets = page.get("targets", [])
        if page.get("nextMarker") or len(targets) > 1:
            raise RuntimeError("Simulator policy is not an exclusive device identity")
        for target in targets:
            things = client.list_principal_things(principal=target)
            attached = client.list_attached_policies(target=target)
            if (things.get("nextToken") or attached.get("nextMarker")
                    or set(things.get("things", [])) - {thing}
                    or [p["policyName"] for p in attached.get("policies", [])] != [policy]
                    or ":cert/" not in target):
                raise RuntimeError("Simulator certificate is shared; refusing deletion")
            if thing in things.get("things", []):
                client.detach_thing_principal(thingName=thing, principal=target)
            client.detach_policy(policyName=policy, target=target)
            certificate_id = target.rsplit("/", 1)[-1]
            client.update_certificate(certificateId=certificate_id, newStatus="INACTIVE")
            client.delete_certificate(certificateId=certificate_id)
        for version in client.list_policy_versions(policyName=policy).get("policyVersions", []):
            if not version["isDefaultVersion"]:
                client.delete_policy_version(policyName=policy, policyVersionId=version["versionId"])
        client.delete_policy(policyName=policy)


def run_pre_destroy_cleanup(
    context: "DeploymentContext",
    providers_config: dict,
    *,
    dry_run: bool,
    state_path: Path | None = None,
) -> None:
    """Run independent pre-destroy cleanup steps without hiding diagnostics."""
    steps = (
        ("AWS simulator identities", lambda: cleanup_aws_simulator_identities(context, dry_run=dry_run)
         if providers_config.get("layer_1_provider") == "aws" else None),
        ("SNS archives", lambda: disable_owned_sns_archives(context, state_path, dry_run=dry_run)),
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
