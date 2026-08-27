"""Provider-specific, side-effect-bounded data-flow verification probes."""

from __future__ import annotations

import hashlib
import json
import math
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

import requests

from src.core.observability import redact_sensitive
from src.utils.gcp_utils import parse_gcp_service_account
from src.verification.contracts import ProbeResult


def check_hot_storage_trace(
    provider: str | None,
    device_id: str,
    trace_id: str,
    outputs: dict,
    credentials: dict,
    project_path: Path,
    timeout: float,
    poll_interval: float,
) -> ProbeResult:
    """Read the selected Six-layer L3 store and require the exact source sequence."""

    normalized = (provider or "").lower()
    if normalized == "aws":
        return _check_aws_hot_storage_trace(
            device_id,
            trace_id,
            outputs,
            credentials.get("aws", {}),
            timeout,
            poll_interval,
        )
    if normalized == "azure":
        return _check_azure_hot_storage_trace(
            device_id,
            trace_id,
            outputs,
            credentials.get("azure", {}),
            timeout,
            poll_interval,
        )
    if normalized in {"google", "gcp"}:
        return _check_gcp_hot_storage_trace(
            device_id,
            trace_id,
            outputs,
            credentials.get("gcp", {}),
            project_path,
            timeout,
            poll_interval,
        )
    return ProbeResult(success=False, error=f"Unsupported L3 provider: {provider}")


def _check_aws_hot_storage_trace(
    device_id: str,
    trace_id: str,
    outputs: dict,
    aws_credentials: dict,
    timeout: float,
    poll_interval: float,
) -> ProbeResult:
    bundle = outputs.get("aws_component_hot_storage_output")
    raw_arn = bundle.get("raw_table_arn") if isinstance(bundle, dict) else None
    if not isinstance(raw_arn, str) or "/" not in raw_arn:
        return ProbeResult(success=False, error="AWS raw table evidence missing")
    try:
        import boto3

        session = boto3.Session(
            aws_access_key_id=aws_credentials.get("aws_access_key_id"),
            aws_secret_access_key=aws_credentials.get("aws_secret_access_key"),
            aws_session_token=aws_credentials.get("aws_session_token"),
            region_name=outputs.get("aws_region")
            or aws_credentials.get("aws_region")
            or aws_credentials.get("region_name"),
        )
        client = session.client("dynamodb")
    except Exception as exc:
        return ProbeResult(
            success=False,
            error=f"AWS hot-storage client unavailable: {redact_sensitive(exc)}",
        )
    table_name = raw_arn.rsplit("/", 1)[-1]
    started = time.monotonic()
    last_error = "trace not found"
    while time.monotonic() - started < timeout:
        try:
            response = client.query(
                TableName=table_name,
                IndexName="device-stored-at-index",
                KeyConditionExpression=(
                    "device_id = :device AND stored_at_event_id >= :start"
                ),
                FilterExpression="contains(payload_json, :trace)",
                ExpressionAttributeValues={
                    ":device": {"S": device_id},
                    ":start": {
                        "S": (datetime.now(timezone.utc) - timedelta(minutes=15))
                        .isoformat()
                        .replace("+00:00", "Z")
                    },
                    ":trace": {"S": trace_id},
                },
                ScanIndexForward=False,
                Limit=20,
            )
            matches = [
                item
                for item in response.get("Items", [])
                if _payload_source_sequence(
                    json.loads(item.get("payload_json", {}).get("S", "{}"))
                )
                == trace_id
            ]
            if matches:
                return ProbeResult(
                    success=True,
                    elapsed=round(time.monotonic() - started, 1),
                    evidence={"record_count": len(matches)},
                )
        except Exception as exc:
            last_error = redact_sensitive(exc)
        time.sleep(poll_interval)
    return ProbeResult(
        success=False,
        elapsed=round(time.monotonic() - started, 1),
        error=f"AWS hot-storage trace unavailable: {last_error}",
    )


def _check_azure_hot_storage_trace(
    device_id: str,
    trace_id: str,
    outputs: dict,
    azure_credentials: dict,
    timeout: float,
    poll_interval: float,
) -> ProbeResult:
    bundle = outputs.get("azure_component_hot_storage_output")
    if not isinstance(bundle, dict):
        return ProbeResult(success=False, error="Azure hot-storage evidence missing")
    try:
        from azure.cosmos import CosmosClient
        from azure.identity import ClientSecretCredential
        from azure.mgmt.cosmosdb import CosmosDBManagementClient

        credential = ClientSecretCredential(
            tenant_id=azure_credentials.get("azure_tenant_id"),
            client_id=azure_credentials.get("azure_client_id"),
            client_secret=azure_credentials.get("azure_client_secret"),
        )
        management = CosmosDBManagementClient(
            credential,
            azure_credentials.get("azure_subscription_id"),
        )
        keys = management.database_accounts.list_keys(
            bundle["resource_group_name"],
            bundle["account_name"],
        )
        account_key = keys.primary_master_key
        if not isinstance(account_key, str) or not account_key:
            raise ValueError("Cosmos account key unavailable")
        client = CosmosClient(bundle["endpoint"], credential=account_key)
        container = client.get_database_client(
            bundle["database_name"]
        ).get_container_client(bundle["container_name"])
    except Exception as exc:
        return ProbeResult(
            success=False,
            error=f"Azure hot-storage client unavailable: {redact_sensitive(exc)}",
        )
    started = time.monotonic()
    last_error = "trace not found"
    while time.monotonic() - started < timeout:
        try:
            items = list(
                container.query_items(
                    query=(
                        "SELECT TOP 20 * FROM c WHERE c.device_id = @device "
                        "AND c.kind = 'raw' ORDER BY c.stored_at DESC"
                    ),
                    parameters=[{"name": "@device", "value": device_id}],
                    partition_key=device_id,
                )
            )
            matches = [
                item
                for item in items
                if _payload_source_sequence(item.get("payload")) == trace_id
            ]
            if matches:
                return ProbeResult(
                    success=True,
                    elapsed=round(time.monotonic() - started, 1),
                    evidence={"record_count": len(matches)},
                )
        except Exception as exc:
            last_error = redact_sensitive(exc)
        time.sleep(poll_interval)
    return ProbeResult(
        success=False,
        elapsed=round(time.monotonic() - started, 1),
        error=f"Azure hot-storage trace unavailable: {last_error}",
    )


def _check_gcp_hot_storage_trace(
    device_id: str,
    trace_id: str,
    outputs: dict,
    gcp_credentials: dict,
    project_path: Path,
    timeout: float,
    poll_interval: float,
) -> ProbeResult:
    bundle = outputs.get("gcp_component_hot_storage_output")
    if not isinstance(bundle, dict):
        return ProbeResult(success=False, error="GCP hot-storage evidence missing")
    try:
        from google.cloud import firestore
        from google.cloud.firestore_v1.base_query import FieldFilter

        project_id, parsed_credentials = _gcp_project_credentials(
            gcp_credentials,
            outputs,
            project_path,
        )
        client = firestore.Client(
            project=project_id,
            credentials=parsed_credentials,
            database=bundle["database_name"],
        )
    except Exception as exc:
        return ProbeResult(
            success=False,
            error=f"GCP hot-storage client unavailable: {redact_sensitive(exc)}",
        )
    started = time.monotonic()
    last_error = "trace not found"
    while time.monotonic() - started < timeout:
        try:
            snapshots = (
                client.collection(bundle.get("collection_name", "telemetry"))
                .where(filter=FieldFilter("device_id", "==", device_id))
                .order_by("stored_at", direction=firestore.Query.DESCENDING)
                .limit(20)
                .stream()
            )
            matches = [
                snapshot
                for snapshot in snapshots
                if _payload_source_sequence((snapshot.to_dict() or {}).get("payload"))
                == trace_id
            ]
            if matches:
                return ProbeResult(
                    success=True,
                    elapsed=round(time.monotonic() - started, 1),
                    evidence={"record_count": len(matches)},
                )
        except Exception as exc:
            last_error = redact_sensitive(exc)
        time.sleep(poll_interval)
    return ProbeResult(
        success=False,
        elapsed=round(time.monotonic() - started, 1),
        error=f"GCP hot-storage trace unavailable: {last_error}",
    )


def _payload_source_sequence(value: object) -> str | None:
    if not isinstance(value, dict):
        return None
    sequence = value.get("source_sequence")
    return sequence if isinstance(sequence, str) else None


def _gcp_project_credentials(
    gcp_credentials: dict,
    outputs: dict,
    project_path: Path,
):
    project_id = gcp_credentials.get("gcp_project_id") or outputs.get("gcp_project_id")
    credentials_input = gcp_credentials.get("gcp_credentials_file")
    if not project_id or not credentials_input:
        raise ValueError("GCP project or credentials not configured")
    if not str(credentials_input).lstrip().startswith("{"):
        credentials_path = Path(credentials_input)
        if not credentials_path.is_absolute():
            credentials_input = str(project_path / credentials_path)
    _, _, parsed_credentials = parse_gcp_service_account(str(credentials_input))
    return project_id, parsed_credentials


def hot_reader_url(provider: str | None, outputs: dict) -> str | None:
    mapping = {
        "aws": "aws_l3_hot_reader_url",
        "azure": "azure_l3_hot_reader_url",
        "google": "gcp_hot_reader_url",
        "gcp": "gcp_hot_reader_url",
    }
    key = mapping.get((provider or "").lower())
    return outputs.get(key) if key else None


def _validated_https_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username:
        raise ValueError("Verification endpoint must be an authenticated HTTPS URL")
    return url


def poll_hot_reader(
    url: str,
    device_id: str,
    inter_cloud_token: str | None,
    timeout: float,
    poll_interval: float,
    *,
    trace_id: str,
) -> ProbeResult:
    """Poll the canonical hot-reader contract for the current trace."""
    try:
        endpoint = _validated_https_url(url)
    except ValueError as exc:
        return ProbeResult(success=False, error=str(exc))

    headers = {}
    if inter_cloud_token:
        headers["X-Inter-Cloud-Token"] = inter_cloud_token
    started = time.monotonic()
    last_diagnostic = "no response"

    while time.monotonic() - started < timeout:
        try:
            response = requests.get(  # nosec B113
                endpoint,
                params={"device_id": device_id, "limit": "20"},
                headers=headers,
                timeout=min(10, max(1, timeout)),
            )
            last_diagnostic = f"HTTP {response.status_code}"
            if response.status_code == 200:
                body = response.json()
                if isinstance(body, list):
                    items = body
                elif isinstance(body, dict):
                    items = body.get("items") or body.get("data") or []
                else:
                    items = []
                matches = [
                    item
                    for item in items
                    if isinstance(item, dict) and item.get("trace_id") == trace_id
                ]
                if matches:
                    return ProbeResult(
                        success=True,
                        elapsed=round(time.monotonic() - started, 1),
                        evidence={"record_count": len(matches)},
                    )
            elif response.status_code in {401, 403}:
                return ProbeResult(
                    success=False,
                    error=f"Hot reader authorization failed ({response.status_code})",
                )
            elif response.status_code != 404:
                return ProbeResult(
                    success=False,
                    error=f"Hot reader returned HTTP {response.status_code}",
                )
        except (requests.RequestException, ValueError) as exc:
            last_diagnostic = redact_sensitive(exc)
        time.sleep(poll_interval)

    return ProbeResult(
        success=False,
        elapsed=round(time.monotonic() - started, 1),
        error=f"Timeout after {timeout:.0f}s ({last_diagnostic})",
    )


def check_twinmaker_entity(
    workspace_id: str,
    entity_id: str,
    timeout: float,
    poll_interval: float,
    *,
    aws_region: str | None,
    aws_credentials: dict,
) -> ProbeResult:
    """Verify the configured TwinMaker entity is addressable.

    TwinMaker uses an external data connector rather than ingesting telemetry
    into the entity itself, so this probe deliberately reports entity-presence
    evidence instead of claiming a direct twin update.
    """
    try:
        import boto3
    except ImportError:
        return ProbeResult(success=False, error="boto3 SDK not available")

    try:
        session = boto3.Session(
            aws_access_key_id=aws_credentials.get("aws_access_key_id"),
            aws_secret_access_key=aws_credentials.get("aws_secret_access_key"),
            aws_session_token=aws_credentials.get("aws_session_token"),
            region_name=aws_region,
        )
        client = session.client("iottwinmaker")
    except Exception as exc:
        return ProbeResult(
            success=False,
            error=f"TwinMaker client initialization failed: {redact_sensitive(exc)}",
        )

    started = time.monotonic()
    while time.monotonic() - started < timeout:
        try:
            paginator = client.get_paginator("list_entities")
            entities = [
                entity
                for page in paginator.paginate(workspaceId=workspace_id)
                for entity in page.get("entitySummaries", [])
            ]
            matching = [
                entity
                for entity in entities
                if entity_id
                in {
                    entity.get("entityId", ""),
                    entity.get("entityName", ""),
                }
            ]
            if matching:
                entity = matching[0]
                return ProbeResult(
                    success=True,
                    elapsed=round(time.monotonic() - started, 1),
                    evidence={
                        "kind": "entity_presence",
                        "entity": entity.get("entityName") or entity.get("entityId"),
                    },
                )
        except Exception as exc:
            last_error = redact_sensitive(exc)
        else:
            last_error = "entity not found"
        time.sleep(poll_interval)

    return ProbeResult(
        success=False,
        elapsed=round(time.monotonic() - started, 1),
        error=f"TwinMaker entity unavailable: {last_error}",
    )


def check_twinmaker_projection(
    workspace_id: str,
    entity_id: str,
    metric: str,
    expected_value: float,
    expected_source_sequence: str,
    sent_at: datetime,
    timeout: float,
    poll_interval: float,
    *,
    aws_region: str | None,
    aws_credentials: dict,
) -> ProbeResult:
    """Require the exact source sequence and value in the AWS L4 projection."""

    try:
        import boto3

        session = boto3.Session(
            aws_access_key_id=aws_credentials.get("aws_access_key_id"),
            aws_secret_access_key=aws_credentials.get("aws_secret_access_key"),
            aws_session_token=aws_credentials.get("aws_session_token"),
            region_name=aws_region,
        )
        client = session.client("iottwinmaker")
    except Exception as exc:
        return ProbeResult(
            success=False,
            error=f"TwinMaker client initialization failed: {redact_sensitive(exc)}",
        )
    started = time.monotonic()
    last_error = "projection not found"
    window_start = sent_at - timedelta(minutes=1)
    while time.monotonic() - started < timeout:
        try:
            response = client.get_property_value_history(
                workspaceId=workspace_id,
                entityId=entity_id,
                componentName="telemetry",
                selectedProperties=["metric", "value", "sourceSequence"],
                startDateTime=window_start,
                endDateTime=datetime.now(timezone.utc) + timedelta(minutes=1),
                maxResults=20,
                orderByTime="DESCENDING",
            )
            value_matches = []
            metric_matches = []
            sequence_matches = []
            for entry in response.get("propertyValues", []):
                reference = entry.get("entityPropertyReference", {})
                property_name = reference.get("propertyName")
                for item in entry.get("values", []):
                    property_value = item.get("value", {})
                    timestamp = item.get("timestamp")
                    in_window = (
                        isinstance(timestamp, datetime) and timestamp >= window_start
                    )
                    value = property_value.get("doubleValue")
                    if property_name == "value" and (
                        isinstance(value, (int, float))
                        and not isinstance(value, bool)
                        and math.isclose(
                            float(value),
                            expected_value,
                            rel_tol=1e-9,
                            abs_tol=1e-9,
                        )
                        and in_window
                    ):
                        value_matches.append(item)
                    sequence = property_value.get("stringValue")
                    if property_name == "metric" and sequence == metric and in_window:
                        metric_matches.append(item)
                    if (
                        property_name == "sourceSequence"
                        and sequence == expected_source_sequence
                        and in_window
                    ):
                        sequence_matches.append(item)
            if metric_matches and value_matches and sequence_matches:
                return ProbeResult(
                    success=True,
                    elapsed=round(time.monotonic() - started, 1),
                    evidence={
                        "kind": "twinmaker_property_projection",
                        "correlation": "source_sequence",
                        "entity": entity_id,
                        "metric": metric,
                    },
                )
        except Exception as exc:
            last_error = redact_sensitive(exc)
        time.sleep(poll_interval)
    return ProbeResult(
        success=False,
        elapsed=round(time.monotonic() - started, 1),
        error=f"TwinMaker projection unavailable: {last_error}",
    )


def check_adt_twin(
    endpoint: str,
    azure_credentials: dict,
    device_id: str,
    timeout: float,
    poll_interval: float,
    *,
    expected_source_sequence: str | None = None,
) -> ProbeResult:
    """Verify the Azure twin, optionally requiring the sent source sequence."""
    try:
        from azure.digitaltwins.core import DigitalTwinsClient
        from azure.identity import ClientSecretCredential
    except ImportError:
        return ProbeResult(success=False, error="Azure Digital Twins SDK not available")

    try:
        _validated_https_url(endpoint)
        credential = ClientSecretCredential(
            tenant_id=azure_credentials.get("azure_tenant_id"),
            client_id=azure_credentials.get("azure_client_id"),
            client_secret=azure_credentials.get("azure_client_secret"),
        )
        client = DigitalTwinsClient(endpoint, credential)
    except Exception as exc:
        return ProbeResult(
            success=False,
            error=f"ADT client initialization failed: {redact_sensitive(exc)}",
        )

    started = time.monotonic()
    while time.monotonic() - started < timeout:
        try:
            twin = client.get_digital_twin(device_id)
            if twin and (
                expected_source_sequence is None
                or twin.get("sourceSequence") == expected_source_sequence
            ):
                return ProbeResult(
                    success=True,
                    elapsed=round(time.monotonic() - started, 1),
                    evidence={
                        "kind": "azure_twin_projection",
                        "twin_id": twin.get("$dtId", device_id),
                        "correlation": (
                            "source_sequence"
                            if expected_source_sequence is not None
                            else "entity_presence"
                        ),
                    },
                )
        except Exception as exc:
            last_error = redact_sensitive(exc)
        else:
            last_error = (
                "source sequence not projected"
                if twin and expected_source_sequence is not None
                else "twin not found"
            )
        time.sleep(poll_interval)

    return ProbeResult(
        success=False,
        elapsed=round(time.monotonic() - started, 1),
        error=f"Azure Digital Twin unavailable: {last_error}",
    )


def check_gcp_twin_projection(
    device_id: str,
    expected_source_sequence: str,
    outputs: dict,
    gcp_credentials: dict,
    project_path: Path,
    timeout: float,
    poll_interval: float,
) -> ProbeResult:
    """Require the exact source sequence on the materialized Firestore twin."""

    bundle = outputs.get("gcp_component_twin_state_output")
    if not isinstance(bundle, dict):
        return ProbeResult(success=False, error="GCP twin-state evidence missing")
    database_name = outputs.get("gcp_firestore_database")
    if not isinstance(database_name, str) or not database_name:
        hot_bundle = outputs.get("gcp_component_hot_storage_output")
        database_name = (
            hot_bundle.get("database_name") if isinstance(hot_bundle, dict) else None
        )
    if not isinstance(database_name, str) or not database_name:
        return ProbeResult(success=False, error="GCP twin database evidence missing")
    try:
        from google.cloud import firestore

        project_id, parsed_credentials = _gcp_project_credentials(
            gcp_credentials,
            outputs,
            project_path,
        )
        client = firestore.Client(
            project=project_id,
            credentials=parsed_credentials,
            database=database_name,
        )
    except Exception as exc:
        return ProbeResult(
            success=False,
            error=f"GCP twin client unavailable: {redact_sensitive(exc)}",
        )
    document_id = hashlib.sha256(device_id.encode("utf-8")).hexdigest()
    started = time.monotonic()
    last_error = "projection not found"
    while time.monotonic() - started < timeout:
        try:
            snapshot = client.collection("twins").document(document_id).get()
            value = snapshot.to_dict() if snapshot.exists else None
            if (
                isinstance(value, dict)
                and value.get("last_source_sequence") == expected_source_sequence
            ):
                return ProbeResult(
                    success=True,
                    elapsed=round(time.monotonic() - started, 1),
                    evidence={
                        "kind": "gcp_twin_projection",
                        "correlation": "source_sequence",
                        "twin_id": device_id,
                    },
                )
        except Exception as exc:
            last_error = redact_sensitive(exc)
        time.sleep(poll_interval)
    return ProbeResult(
        success=False,
        elapsed=round(time.monotonic() - started, 1),
        error=f"GCP twin projection unavailable: {last_error}",
    )


def check_cloud_logs(
    provider: str,
    search_pattern: str,
    step_name: str,
    outputs: dict,
    credentials: dict,
    project_path: Path,
    timeout: float,
    poll_interval: float,
) -> ProbeResult:
    normalized = provider.lower()
    if normalized == "aws":
        return _check_aws_logs(
            search_pattern,
            step_name,
            outputs,
            credentials,
            timeout,
            poll_interval,
        )
    if normalized == "azure":
        return _check_azure_logs(
            search_pattern,
            outputs,
            credentials,
            timeout,
            poll_interval,
        )
    if normalized in {"google", "gcp"}:
        return _check_gcp_logs(
            search_pattern,
            outputs,
            credentials,
            project_path,
            timeout,
            poll_interval,
        )
    return ProbeResult(success=False, error=f"Unsupported provider: {provider}")


def _check_aws_logs(
    pattern: str,
    step_name: str,
    outputs: dict,
    credentials: dict,
    timeout: float,
    poll_interval: float,
) -> ProbeResult:
    try:
        import boto3
    except ImportError:
        return ProbeResult(success=False, error="boto3 SDK not available")

    aws_credentials = credentials.get("aws", {})
    client_args = {
        key: aws_credentials[key]
        for key in (
            "aws_access_key_id",
            "aws_secret_access_key",
            "aws_session_token",
        )
        if aws_credentials.get(key)
    }
    region = aws_credentials.get("aws_region") or aws_credentials.get("region_name")
    if region:
        client_args["region_name"] = region
    try:
        client = boto3.client("logs", **client_args)
    except Exception as exc:
        return ProbeResult(
            success=False,
            error=f"CloudWatch client initialization failed: {redact_sensitive(exc)}",
        )

    function_name = outputs.get(f"aws_l2_{step_name}_function_name", step_name)
    log_group = f"/aws/lambda/{function_name}"
    started = time.monotonic()
    while time.monotonic() - started < timeout:
        try:
            end_time = int(time.time() * 1000)
            response = client.filter_log_events(
                logGroupName=log_group,
                startTime=end_time - 15 * 60 * 1000,
                endTime=end_time,
                filterPattern=f'"{pattern}"',
                limit=5,
            )
            if response.get("events"):
                return ProbeResult(
                    success=True,
                    elapsed=round(time.monotonic() - started, 1),
                    evidence={"log_count": len(response["events"])},
                )
        except Exception as exc:
            last_error = redact_sensitive(exc)
        else:
            last_error = "no matching logs"
        time.sleep(poll_interval)
    return ProbeResult(
        success=False,
        elapsed=round(time.monotonic() - started, 1),
        error=f"CloudWatch evidence unavailable: {last_error}",
    )


def _check_azure_logs(
    pattern: str,
    outputs: dict,
    credentials: dict,
    timeout: float,
    poll_interval: float,
) -> ProbeResult:
    try:
        from azure.identity import ClientSecretCredential
        from azure.monitor.query import LogsQueryClient
    except ImportError:
        return ProbeResult(success=False, error="Azure Monitor SDK not available")

    workspace_id = outputs.get("azure_log_analytics_workspace_id")
    if not workspace_id:
        return ProbeResult(success=False, error="Log Analytics workspace ID not found")
    azure_credentials = credentials.get("azure", {})
    try:
        credential = ClientSecretCredential(
            tenant_id=azure_credentials.get("azure_tenant_id"),
            client_id=azure_credentials.get("azure_client_id"),
            client_secret=azure_credentials.get("azure_client_secret"),
        )
        client = LogsQueryClient(credential)
    except Exception as exc:
        return ProbeResult(
            success=False,
            error=f"Azure Monitor client initialization failed: {redact_sensitive(exc)}",
        )

    escaped_pattern = pattern.replace('"', '""')
    query = (
        'AppTraces | where AppRoleName contains "l2-functions" '
        f'| where Message contains "{escaped_pattern}" '
        "| where TimeGenerated > ago(60m) | limit 10"
    )
    started = time.monotonic()
    while time.monotonic() - started < timeout:
        try:
            response = client.query_workspace(
                workspace_id,
                query,
                timespan=timedelta(minutes=60),
            )
            rows = response.tables[0].rows if response.tables else []
            if rows:
                return ProbeResult(
                    success=True,
                    elapsed=round(time.monotonic() - started, 1),
                    evidence={"log_count": len(rows)},
                )
        except Exception as exc:
            last_error = redact_sensitive(exc)
        else:
            last_error = "no matching logs"
        time.sleep(poll_interval)
    return ProbeResult(
        success=False,
        elapsed=round(time.monotonic() - started, 1),
        error=f"Azure log evidence unavailable: {last_error}",
    )


def _check_gcp_logs(
    pattern: str,
    outputs: dict,
    credentials: dict,
    project_path: Path,
    timeout: float,
    poll_interval: float,
) -> ProbeResult:
    try:
        from google.cloud import logging as cloud_logging
    except ImportError:
        return ProbeResult(success=False, error="GCP Cloud Logging SDK not available")

    gcp_credentials = credentials.get("gcp", {})
    project_id = gcp_credentials.get("gcp_project_id") or outputs.get("gcp_project_id")
    credentials_input = gcp_credentials.get("gcp_credentials_file")
    if not project_id or not credentials_input:
        return ProbeResult(
            success=False, error="GCP project or credentials not configured"
        )
    if not str(credentials_input).lstrip().startswith("{"):
        credentials_path = Path(credentials_input)
        if not credentials_path.is_absolute():
            credentials_input = str(project_path / credentials_path)

    try:
        _, _, parsed_credentials = parse_gcp_service_account(str(credentials_input))
        client = cloud_logging.Client(
            project=project_id,
            credentials=parsed_credentials,
        )
    except Exception as exc:
        return ProbeResult(
            success=False,
            error=f"GCP logging client initialization failed: {redact_sensitive(exc)}",
        )

    escaped_pattern = pattern.replace('"', '\\"')
    started = time.monotonic()
    while time.monotonic() - started < timeout:
        try:
            cutoff = datetime.now(timezone.utc) - timedelta(minutes=15)
            filter_value = (
                '(resource.type="cloud_function" OR '
                'resource.type="cloud_run_revision") '
                f'AND textPayload:"{escaped_pattern}" '
                f'AND timestamp >= "{cutoff.isoformat()}"'
            )
            entries = list(client.list_entries(filter_=filter_value, max_results=5))
            if entries:
                return ProbeResult(
                    success=True,
                    elapsed=round(time.monotonic() - started, 1),
                    evidence={"log_count": len(entries)},
                )
        except Exception as exc:
            last_error = redact_sensitive(exc)
        else:
            last_error = "no matching logs"
        time.sleep(poll_interval)
    return ProbeResult(
        success=False,
        elapsed=round(time.monotonic() - started, 1),
        error=f"GCP log evidence unavailable: {last_error}",
    )


def cloud_log_hints(providers: dict) -> list[str]:
    hints = []
    for provider in sorted(set(providers.values())):
        if provider == "aws":
            hints.append("AWS: CloudWatch /aws/lambda/{twin-name}-*")
        elif provider == "azure":
            hints.append("Azure: Log Analytics AppTraces")
        elif provider in {"google", "gcp"}:
            hints.append("GCP: Cloud Logging function and Cloud Run resources")
    return hints
