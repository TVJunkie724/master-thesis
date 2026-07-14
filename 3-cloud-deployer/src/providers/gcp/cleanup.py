"""Explicit, fail-closed GCP SDK cleanup for Terraform orphan recovery."""

from __future__ import annotations

from dataclasses import dataclass
import json
import logging
import time
from typing import Any

from src.providers.cleanup_observability import CleanupRun
from src.providers.cleanup_registry import resource_name_owned_by_prefix

logger = logging.getLogger(__name__)


def _discovery_items(list_method, result_key: str, **kwargs):
    """Yield all resources from a Google Discovery API list method."""
    page_token = None
    while True:
        request_kwargs = dict(kwargs)
        if page_token:
            request_kwargs["pageToken"] = page_token
        response = list_method(**request_kwargs).execute()
        yield from response.get(result_key, [])
        page_token = response.get("nextPageToken")
        if not page_token:
            return


def _delete_custom_role(roles_api, role: dict, *, dry_run: bool) -> bool:
    """Delete active roles and preserve the provider's soft-delete clock."""
    if dry_run:
        return False
    if role.get("deleted", False):
        logger.info(
            "    Already soft-deleted; role ID remains reserved until permanent deletion"
        )
        return False
    roles_api.delete(name=role["name"]).execute()
    return True


def _delete_all_bucket_objects(
    storage_client,
    bucket_name: str,
    *,
    deadline_seconds: float = 600,
    max_stalled_passes: int = 5,
) -> None:
    """Drain live and noncurrent generations without mutation-sensitive page tokens."""
    deadline = time.monotonic() + deadline_seconds
    previous_fingerprint = None
    stalled_passes = 0
    while True:
        if time.monotonic() >= deadline:
            raise TimeoutError("Cloud Storage bucket drain exceeded its deadline")
        response = storage_client.objects().list(
            bucket=bucket_name,
            versions=True,
        ).execute()
        objects = response.get("items", [])
        if not objects:
            return
        fingerprint = tuple(
            (item.get("name"), item.get("generation")) for item in objects
        )
        stalled_passes = stalled_passes + 1 if fingerprint == previous_fingerprint else 0
        if stalled_passes >= max_stalled_passes:
            raise RuntimeError("Cloud Storage bucket drain made no progress")
        previous_fingerprint = fingerprint
        for item in objects:
            delete_args = {"bucket": bucket_name, "object": item["name"]}
            if item.get("generation") is not None:
                delete_args["generation"] = item["generation"]
            storage_client.objects().delete(**delete_args).execute()
        if stalled_passes:
            time.sleep(1)


@dataclass(frozen=True)
class _GcpCleanupContext:
    credentials: Any
    project_id: str
    region: str
    prefix: str
    dry_run: bool
    run: CleanupRun


def _owned(name: str, context: _GcpCleanupContext, **kwargs) -> bool:
    return resource_name_owned_by_prefix(name, context.prefix, **kwargs)


def _delete_or_log(
    context: _GcpCleanupContext,
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
        logger.info("    Delete accepted")


def _cleanup_functions(context: _GcpCleanupContext) -> None:
    from googleapiclient import discovery

    client = discovery.build("cloudfunctions", "v2", credentials=context.credentials)
    functions = client.projects().locations().functions()
    parent = f"projects/{context.project_id}/locations/{context.region}"
    for function in _discovery_items(functions.list, "functions", parent=parent):
        name = function["name"].rsplit("/", 1)[-1]
        if _owned(name, context):
            _delete_or_log(
                context,
                "Cloud Functions",
                name,
                lambda function=function: functions.delete(
                    name=function["name"]
                ).execute(),
            )


def _cleanup_pubsub_topics(context: _GcpCleanupContext) -> None:
    from googleapiclient import discovery

    client = discovery.build("pubsub", "v1", credentials=context.credentials)
    topics = client.projects().topics()
    project = f"projects/{context.project_id}"
    for topic in _discovery_items(topics.list, "topics", project=project):
        name = topic["name"].rsplit("/", 1)[-1]
        if _owned(name, context):
            _delete_or_log(
                context,
                "Pub/Sub Topics",
                name,
                lambda topic=topic: topics.delete(topic=topic["name"]).execute(),
            )


def _cleanup_pubsub_subscriptions(context: _GcpCleanupContext) -> None:
    from googleapiclient import discovery

    client = discovery.build("pubsub", "v1", credentials=context.credentials)
    subscriptions = client.projects().subscriptions()
    project = f"projects/{context.project_id}"
    for subscription in _discovery_items(
        subscriptions.list,
        "subscriptions",
        project=project,
    ):
        name = subscription["name"].rsplit("/", 1)[-1]
        if _owned(name, context):
            _delete_or_log(
                context,
                "Pub/Sub Subscriptions",
                name,
                lambda subscription=subscription: subscriptions.delete(
                    subscription=subscription["name"]
                ).execute(),
            )


def _cleanup_firestore_collections(context: _GcpCleanupContext) -> None:
    from google.cloud import firestore

    database = firestore.Client(
        project=context.project_id,
        credentials=context.credentials,
    )
    for collection in database.collections():
        if _owned(collection.id, context):
            _delete_or_log(
                context,
                "Firestore Collections",
                collection.id,
                lambda collection=collection: database.recursive_delete(collection),
                dry_run_message="Would recursively delete all documents",
            )


def _cleanup_storage_buckets(context: _GcpCleanupContext) -> None:
    from googleapiclient import discovery

    client = discovery.build("storage", "v1", credentials=context.credentials)
    for bucket in _discovery_items(
        client.buckets().list,
        "items",
        project=context.project_id,
    ):
        name = bucket["name"]
        if not (
            _owned(name, context)
            or resource_name_owned_by_prefix(
                name,
                f"{context.project_id}-{context.prefix}",
            )
        ):
            continue

        def delete_bucket(name=name):
            _delete_all_bucket_objects(client, name)
            client.buckets().delete(bucket=name).execute()

        _delete_or_log(
            context,
            "Cloud Storage",
            name,
            delete_bucket,
            dry_run_message="Would delete bucket and every object generation",
        )


def _cleanup_workflows(context: _GcpCleanupContext) -> None:
    from googleapiclient import discovery

    client = discovery.build("workflows", "v1", credentials=context.credentials)
    workflows = client.projects().locations().workflows()
    parent = f"projects/{context.project_id}/locations/{context.region}"
    for workflow in _discovery_items(workflows.list, "workflows", parent=parent):
        name = workflow["name"].rsplit("/", 1)[-1]
        if _owned(name, context):
            _delete_or_log(
                context,
                "Cloud Workflows",
                name,
                lambda workflow=workflow: workflows.delete(
                    name=workflow["name"]
                ).execute(),
            )


def _cleanup_service_accounts(context: _GcpCleanupContext) -> None:
    from googleapiclient import discovery

    client = discovery.build("iam", "v1", credentials=context.credentials)
    accounts = client.projects().serviceAccounts()
    for account in _discovery_items(
        accounts.list,
        "accounts",
        name=f"projects/{context.project_id}",
    ):
        email = account["email"]
        if _owned(email.split("@", 1)[0], context):
            _delete_or_log(
                context,
                "Service Accounts",
                email,
                lambda email=email: accounts.delete(
                    name=f"projects/{context.project_id}/serviceAccounts/{email}"
                ).execute(),
            )


def _cleanup_custom_roles(context: _GcpCleanupContext) -> None:
    from googleapiclient import discovery

    client = discovery.build("iam", "v1", credentials=context.credentials)
    roles = client.projects().roles()
    for role in _discovery_items(
        roles.list,
        "roles",
        parent=f"projects/{context.project_id}",
        showDeleted=True,
    ):
        role_id = role["name"].rsplit("/", 1)[-1]
        if not _owned(role_id, context):
            continue
        logger.info("  Found orphan: %s", role_id)
        if context.dry_run:
            logger.info("    [DRY RUN] Would delete if active")
            continue
        context.run.attempt(
            "Custom IAM Roles",
            role_id,
            lambda role=role: _delete_custom_role(roles, role, dry_run=False),
        )


def _cleanup_firestore_databases(context: _GcpCleanupContext) -> None:
    from googleapiclient import discovery

    client = discovery.build("firestore", "v1", credentials=context.credentials)
    databases = client.projects().databases()
    for database in _discovery_items(
        databases.list,
        "databases",
        parent=f"projects/{context.project_id}",
    ):
        name = database["name"].rsplit("/", 1)[-1]
        if name != "(default)" and _owned(name, context):
            _delete_or_log(
                context,
                "Firestore Databases",
                name,
                lambda database=database: databases.delete(
                    name=database["name"]
                ).execute(),
            )


def _cleanup_scheduler_jobs(context: _GcpCleanupContext) -> None:
    from googleapiclient import discovery

    client = discovery.build("cloudscheduler", "v1", credentials=context.credentials)
    jobs = client.projects().locations().jobs()
    parent = f"projects/{context.project_id}/locations/{context.region}"
    for job in _discovery_items(jobs.list, "jobs", parent=parent):
        name = job["name"].rsplit("/", 1)[-1]
        if _owned(name, context):
            _delete_or_log(
                context,
                "Cloud Scheduler",
                name,
                lambda job=job: jobs.delete(name=job["name"]).execute(),
            )


_CLEANUP_STEPS = (
    ("Cloud Functions", _cleanup_functions),
    ("Pub/Sub Topics", _cleanup_pubsub_topics),
    ("Pub/Sub Subscriptions", _cleanup_pubsub_subscriptions),
    ("Firestore Collections", _cleanup_firestore_collections),
    ("Cloud Storage", _cleanup_storage_buckets),
    ("Cloud Workflows", _cleanup_workflows),
    ("Service Accounts", _cleanup_service_accounts),
    ("Custom IAM Roles", _cleanup_custom_roles),
    ("Firestore Databases", _cleanup_firestore_databases),
    ("Cloud Scheduler", _cleanup_scheduler_jobs),
)


def cleanup_gcp_resources(
    credentials: dict,
    prefix: str,
    dry_run: bool = False,
) -> None:
    """Clean GCP resources and raise one typed aggregate for incomplete work."""
    from src.utils.gcp_utils import parse_gcp_service_account

    gcp_creds = credentials.get("gcp", {})
    project_id = gcp_creds.get("gcp_project_id")
    if not project_id:
        raise ValueError("GCP cleanup requires gcp_project_id")

    credentials_input = gcp_creds.get("gcp_service_account_key") or gcp_creds.get(
        "gcp_credentials_file"
    )
    if isinstance(credentials_input, dict):
        credentials_input = json.dumps(credentials_input)
    if not isinstance(credentials_input, str) or not credentials_input.strip():
        raise ValueError("GCP cleanup requires service account credentials")
    _, _, google_credentials = parse_gcp_service_account(credentials_input)

    region = gcp_creds.get("gcp_region", "europe-west1")
    run = CleanupRun("GCP", logger)
    context = _GcpCleanupContext(
        google_credentials,
        project_id,
        region,
        prefix,
        dry_run,
        run,
    )

    logger.info("[GCP SDK] Fallback cleanup for prefix: %s", prefix)
    logger.info("[GCP SDK] Project: %s, Region: %s", project_id, region)
    if dry_run:
        logger.info("[GCP SDK] DRY RUN MODE - no resources will be deleted")

    for label, step in _CLEANUP_STEPS:
        logger.info("[%s] Checking for orphans...", label)
        run.attempt(label, "inventory", lambda step=step: step(context))

    run.raise_if_failed()
    logger.info("[GCP SDK] Fallback cleanup complete")
