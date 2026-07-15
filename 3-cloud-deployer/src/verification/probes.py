"""Provider-specific, side-effect-bounded data-flow verification probes."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import time
from urllib.parse import urlparse

import requests

from src.core.observability import redact_sensitive
from src.utils.gcp_utils import parse_gcp_service_account
from src.verification.contracts import ProbeResult


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
                if entity_id in {
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


def check_adt_twin(
    endpoint: str,
    azure_credentials: dict,
    device_id: str,
    timeout: float,
    poll_interval: float,
) -> ProbeResult:
    """Verify the configured Azure Digital Twin is addressable."""
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
            if twin:
                return ProbeResult(
                    success=True,
                    elapsed=round(time.monotonic() - started, 1),
                    evidence={
                        "kind": "twin_presence",
                        "twin_id": twin.get("$dtId", device_id),
                    },
                )
        except Exception as exc:
            last_error = redact_sensitive(exc)
        else:
            last_error = "twin not found"
        time.sleep(poll_interval)

    return ProbeResult(
        success=False,
        elapsed=round(time.monotonic() - started, 1),
        error=f"Azure Digital Twin unavailable: {last_error}",
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
        return ProbeResult(success=False, error="GCP project or credentials not configured")
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
