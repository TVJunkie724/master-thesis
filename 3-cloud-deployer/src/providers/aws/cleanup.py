"""Explicit, fail-closed AWS SDK cleanup for Terraform orphan recovery."""

from __future__ import annotations

from dataclasses import dataclass
import logging
import time
from typing import Any

from src.providers.cleanup_observability import CleanupRun
from src.providers.cleanup_registry import resource_name_owned_by_prefix

logger = logging.getLogger(__name__)


def _create_session(aws_creds: dict, region: str):
    import boto3

    session_args = {
        "aws_access_key_id": aws_creds["aws_access_key_id"],
        "aws_secret_access_key": aws_creds["aws_secret_access_key"],
        "region_name": region,
    }
    if aws_creds.get("aws_session_token"):
        session_args["aws_session_token"] = aws_creds["aws_session_token"]
    return boto3.Session(**session_args)


def _items(client, operation: str, result_key: str, **kwargs):
    """Yield every item from a paginated or single-page boto3 list operation."""
    can_paginate = getattr(client, "can_paginate", lambda _operation: False)
    if can_paginate(operation):
        for page in client.get_paginator(operation).paginate(**kwargs):
            yield from page.get(result_key, [])
        return
    response = getattr(client, operation)(**kwargs)
    yield from response.get(result_key, [])


@dataclass(frozen=True)
class _AwsCleanupContext:
    session: Any
    prefix: str
    dry_run: bool
    run: CleanupRun


def _owned(name: str, context: _AwsCleanupContext, **kwargs) -> bool:
    return resource_name_owned_by_prefix(name, context.prefix, **kwargs)


def _delete_or_log(
    context: _AwsCleanupContext,
    step: str,
    resource: str,
    delete,
) -> None:
    logger.info("  Found orphan: %s", resource)
    if context.dry_run:
        logger.info("    [DRY RUN] Would delete")
        return
    def execute_delete() -> bool:
        delete()
        return True

    if context.run.attempt(step, resource, execute_delete, default=False):
        logger.info("    Deleted")


def _cleanup_twinmaker(context: _AwsCleanupContext) -> None:
    client = context.session.client("iottwinmaker")
    for workspace in _items(client, "list_workspaces", "workspaceSummaries"):
        workspace_id = workspace["workspaceId"]
        if not _owned(workspace_id, context):
            continue
        logger.info("  Found orphan: %s", workspace_id)
        if context.dry_run:
            logger.info("    [DRY RUN] Would delete workspace and contents")
            continue
        context.run.attempt(
            "TwinMaker",
            workspace_id,
            lambda workspace_id=workspace_id: _delete_twinmaker_workspace(
                context,
                client,
                workspace_id,
            ),
        )


def _delete_twinmaker_workspace(
    context: _AwsCleanupContext,
    client,
    workspace_id: str,
) -> None:
    for entity in _items(
        client,
        "list_entities",
        "entitySummaries",
        workspaceId=workspace_id,
    ):
        client.delete_entity(
            workspaceId=workspace_id,
            entityId=entity["entityId"],
            isRecursive=True,
        )

    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        remaining = list(
            _items(
                client,
                "list_entities",
                "entitySummaries",
                workspaceId=workspace_id,
            )
        )
        if not remaining:
            break
        time.sleep(3)
    else:
        raise TimeoutError("TwinMaker entities did not finish deleting within 60 seconds")

    for scene in _items(
        client,
        "list_scenes",
        "sceneSummaries",
        workspaceId=workspace_id,
    ):
        client.delete_scene(workspaceId=workspace_id, sceneId=scene["sceneId"])

    for component_type in _items(
        client,
        "list_component_types",
        "componentTypeSummaries",
        workspaceId=workspace_id,
    ):
        component_type_id = component_type["componentTypeId"]
        if component_type_id.startswith("com.amazon"):
            continue
        _delete_component_type_with_retry(client, workspace_id, component_type_id)

    time.sleep(2)
    client.delete_workspace(workspaceId=workspace_id)
    logger.info("    Deleted")


def _delete_component_type_with_retry(client, workspace_id: str, component_type_id: str) -> None:
    for attempt in range(3):
        try:
            client.delete_component_type(
                workspaceId=workspace_id,
                componentTypeId=component_type_id,
            )
            return
        except Exception as exc:
            if "being used by entities" in str(exc) and attempt < 2:
                time.sleep(2**attempt)
                continue
            raise


def _cleanup_grafana(context: _AwsCleanupContext) -> None:
    client = context.session.client("grafana")
    for workspace in _items(client, "list_workspaces", "workspaces"):
        if _owned(workspace["name"], context):
            _delete_or_log(
                context,
                "Grafana",
                workspace["name"],
                lambda workspace=workspace: client.delete_workspace(
                    workspaceId=workspace["id"]
                ),
            )


def _cleanup_step_functions(context: _AwsCleanupContext) -> None:
    client = context.session.client("stepfunctions")
    for machine in _items(client, "list_state_machines", "stateMachines"):
        if _owned(machine["name"], context):
            _delete_or_log(
                context,
                "Step Functions",
                machine["name"],
                lambda machine=machine: client.delete_state_machine(
                    stateMachineArn=machine["stateMachineArn"]
                ),
            )


def _cleanup_s3(context: _AwsCleanupContext) -> None:
    client = context.session.client("s3")
    resource = context.session.resource("s3")
    for bucket in _items(client, "list_buckets", "Buckets"):
        name = bucket["Name"]
        if not _owned(name, context):
            continue

        def delete_bucket(name=name):
            bucket_object = resource.Bucket(name)
            bucket_object.object_versions.all().delete()
            bucket_object.objects.all().delete()
            client.delete_bucket(Bucket=name)

        _delete_or_log(context, "S3", name, delete_bucket)


def _cleanup_lambda(context: _AwsCleanupContext) -> None:
    client = context.session.client("lambda")
    for function in _items(client, "list_functions", "Functions"):
        name = function["FunctionName"]
        if _owned(name, context):
            _delete_or_log(
                context,
                "Lambda",
                name,
                lambda name=name: client.delete_function(FunctionName=name),
            )


def _cleanup_iot(context: _AwsCleanupContext) -> None:
    client = context.session.client("iot")
    for rule in _items(client, "list_topic_rules", "rules"):
        name = rule["ruleName"]
        if _owned(name, context):
            _delete_or_log(
                context,
                "IoT topic rules",
                name,
                lambda name=name: client.delete_topic_rule(ruleName=name),
            )
    for thing in _items(client, "list_things", "things"):
        name = thing["thingName"]
        if not _owned(name, context):
            continue

        def delete_thing(name=name):
            for principal in _items(
                client,
                "list_thing_principals",
                "principals",
                thingName=name,
            ):
                client.detach_thing_principal(thingName=name, principal=principal)
            client.delete_thing(thingName=name)

        _delete_or_log(context, "IoT things", name, delete_thing)


def _cleanup_dynamodb(context: _AwsCleanupContext) -> None:
    client = context.session.client("dynamodb")
    for name in _items(client, "list_tables", "TableNames"):
        if _owned(name, context):
            _delete_or_log(
                context,
                "DynamoDB",
                name,
                lambda name=name: client.delete_table(TableName=name),
            )


def _cleanup_logs(context: _AwsCleanupContext) -> None:
    client = context.session.client("logs")
    for group in _items(client, "describe_log_groups", "logGroups"):
        name = group["logGroupName"]
        if _owned(name, context, allow_embedded=True):
            _delete_or_log(
                context,
                "CloudWatch Logs",
                name,
                lambda name=name: client.delete_log_group(logGroupName=name),
            )


def _cleanup_iam_roles(context: _AwsCleanupContext) -> None:
    client = context.session.client("iam")
    for role in _items(client, "list_roles", "Roles"):
        name = role["RoleName"]
        if not _owned(name, context):
            continue

        def delete_role(name=name):
            for policy in _items(
                client,
                "list_attached_role_policies",
                "AttachedPolicies",
                RoleName=name,
            ):
                client.detach_role_policy(RoleName=name, PolicyArn=policy["PolicyArn"])
            for policy_name in _items(
                client,
                "list_role_policies",
                "PolicyNames",
                RoleName=name,
            ):
                client.delete_role_policy(RoleName=name, PolicyName=policy_name)
            client.delete_role(RoleName=name)

        _delete_or_log(context, "IAM roles", name, delete_role)


def _cleanup_iam_policies(context: _AwsCleanupContext) -> None:
    client = context.session.client("iam")
    for policy in _items(client, "list_policies", "Policies", Scope="Local"):
        name = policy["PolicyName"]
        if not _owned(name, context):
            continue

        def delete_policy(policy=policy):
            arn = policy["Arn"]
            entity_types = (
                ("User", "PolicyUsers", "UserName", client.detach_user_policy),
                ("Role", "PolicyRoles", "RoleName", client.detach_role_policy),
                ("Group", "PolicyGroups", "GroupName", client.detach_group_policy),
            )
            for entity_filter, key, name_key, detach in entity_types:
                for entity in _items(
                    client,
                    "list_entities_for_policy",
                    key,
                    PolicyArn=arn,
                    EntityFilter=entity_filter,
                ):
                    detach(**{name_key: entity[name_key], "PolicyArn": arn})
            for version in client.list_policy_versions(PolicyArn=arn)["Versions"]:
                if not version["IsDefaultVersion"]:
                    client.delete_policy_version(
                        PolicyArn=arn,
                        VersionId=version["VersionId"],
                    )
            client.delete_policy(PolicyArn=arn)

        _delete_or_log(context, "IAM policies", name, delete_policy)


def _cleanup_resource_groups(context: _AwsCleanupContext) -> None:
    client = context.session.client("resource-groups")
    for group in _items(client, "list_groups", "Groups"):
        name = group["Name"]
        if _owned(name, context):
            _delete_or_log(
                context,
                "Resource Groups",
                name,
                lambda name=name: client.delete_group(Group=name),
            )


def _cleanup_identity_user(
    context: _AwsCleanupContext,
    aws_creds: dict,
    sso_region: str,
    email: str,
) -> None:
    if not email:
        logger.info("  No platform_user_email provided, skipping")
        return
    session = _create_session(aws_creds, sso_region)
    admin = session.client("sso-admin")
    instances = list(_items(admin, "list_instances", "Instances"))
    if not instances:
        return
    store_id = instances[0]["IdentityStoreId"]
    store = session.client("identitystore")
    for user in _items(store, "list_users", "Users", IdentityStoreId=store_id):
        if user.get("UserName", "").casefold() != email.casefold():
            continue
        _delete_or_log(
            context,
            "Identity Store",
            email,
            lambda user=user: store.delete_user(
                IdentityStoreId=store_id,
                UserId=user["UserId"],
            ),
        )


_CLEANUP_STEPS = (
    ("TwinMaker", _cleanup_twinmaker),
    ("Grafana", _cleanup_grafana),
    ("Step Functions", _cleanup_step_functions),
    ("S3", _cleanup_s3),
    ("Lambda", _cleanup_lambda),
    ("IoT", _cleanup_iot),
    ("DynamoDB", _cleanup_dynamodb),
    ("CloudWatch Logs", _cleanup_logs),
    ("IAM roles", _cleanup_iam_roles),
    ("IAM policies", _cleanup_iam_policies),
    ("Resource Groups", _cleanup_resource_groups),
)


def cleanup_aws_resources(
    credentials: dict,
    prefix: str,
    cleanup_identity_user: bool = False,
    platform_user_email: str = "",
    dry_run: bool = False,
) -> None:
    """Clean AWS resources and raise one typed aggregate for incomplete work."""
    aws_creds = credentials.get("aws", {})
    region = aws_creds.get("aws_region", "eu-central-1")
    session = _create_session(aws_creds, region)
    run = CleanupRun("AWS", logger)
    context = _AwsCleanupContext(session, prefix, dry_run, run)

    logger.info("[AWS SDK] Fallback cleanup for prefix: %s", prefix)
    if dry_run:
        logger.info("[AWS SDK] DRY RUN MODE - no resources will be deleted")

    for label, step in _CLEANUP_STEPS:
        logger.info("[%s] Checking for orphans...", label)
        run.attempt(label, "inventory", lambda step=step: step(context))

    if cleanup_identity_user:
        run.attempt(
            "Identity Store",
            platform_user_email or "configured platform user",
            lambda: _cleanup_identity_user(
                context,
                aws_creds,
                aws_creds.get("aws_sso_region", "us-east-1"),
                platform_user_email,
            ),
        )

    run.raise_if_failed()
    logger.info("[AWS SDK] Fallback cleanup complete")
