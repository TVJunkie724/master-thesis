"""Provider-specific read-only cloud log fetchers."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from src.core.observability import redact_sensitive
from src.log_tracing.checkpoints import parse_checkpoint_message
from src.utils.gcp_utils import parse_gcp_service_account


@dataclass(frozen=True)
class LogEntry:
    timestamp: str
    message: str
    layer: str
    provider: str
    function: str = ""
    checkpoint: dict[str, Any] | None = None


@dataclass(frozen=True)
class ProviderFetchResult:
    provider: str
    entries: list[LogEntry] = field(default_factory=list)
    error: str | None = None


def _layer(resource_name: str) -> str:
    normalized = resource_name.lower()
    if "event" in normalized or "bridge" in normalized:
        return "EVENT"
    if "l0" in normalized or "ingestion" in normalized:
        return "L0"
    if "l1" in normalized or "dispatcher" in normalized:
        return "L1"
    if any(value in normalized for value in ("l2", "persister", "processor")):
        return "L2"
    if any(value in normalized for value in ("l3", "hot", "cold", "archive")):
        return "L3"
    if any(value in normalized for value in ("l4", "twin")):
        return "L4"
    if any(value in normalized for value in ("l5", "grafana")):
        return "L5"
    return "L?"


def fetch_aws_logs(
    log_groups: dict[str, str],
    trace_id: str,
    since_ms: int,
    credentials: dict,
    *,
    query_timeout_seconds: float = 15,
) -> ProviderFetchResult:
    try:
        import boto3
        from botocore.config import Config

        client_args = {
            key: credentials[key]
            for key in (
                "aws_access_key_id",
                "aws_secret_access_key",
                "aws_session_token",
            )
            if credentials.get(key)
        }
        region = credentials.get("aws_region") or credentials.get("region_name")
        if region:
            client_args["region_name"] = region
        client_args["config"] = Config(
            connect_timeout=max(1, query_timeout_seconds),
            read_timeout=max(1, query_timeout_seconds),
            retries={"max_attempts": 2, "mode": "standard"},
        )
        client = boto3.client("logs", **client_args)
    except Exception as exc:
        return ProviderFetchResult("aws", error=redact_sensitive(exc))

    entries = []
    failures = []
    for layer_name, log_group in sorted(log_groups.items()):
        if not log_group:
            continue
        try:
            response = client.filter_log_events(
                logGroupName=log_group,
                startTime=since_ms,
                filterPattern=f'"{trace_id}"',
                limit=50,
            )
            function_name = log_group.rsplit("/", 1)[-1]
            for event in response.get("events", []):
                message = redact_sensitive(event.get("message", "").strip())
                entries.append(
                    LogEntry(
                        timestamp=datetime.fromtimestamp(
                            event["timestamp"] / 1000,
                            tz=timezone.utc,
                        ).isoformat(),
                        message=message,
                        layer=layer_name,
                        provider="aws",
                        function=function_name,
                        checkpoint=parse_checkpoint_message(message),
                    )
                )
        except Exception as exc:
            failures.append(f"{log_group}: {redact_sensitive(exc)}")
    return ProviderFetchResult(
        "aws",
        entries=entries,
        error="; ".join(failures) or None,
    )


def fetch_azure_logs(
    workspace_ids: str | dict[str, str],
    trace_id: str,
    credentials: dict,
    started_at: datetime,
    *,
    query_timeout_seconds: float = 15,
) -> ProviderFetchResult:
    single_workspace = isinstance(workspace_ids, str)
    normalized_workspaces = (
        {"primary": workspace_ids}
        if isinstance(workspace_ids, str)
        else {
            str(name): str(workspace_id)
            for name, workspace_id in workspace_ids.items()
            if isinstance(workspace_id, str) and workspace_id
        }
    )
    if not normalized_workspaces:
        return ProviderFetchResult("azure", error="Workspace ID not available")
    try:
        from azure.identity import ClientSecretCredential
        from azure.monitor.query import LogsQueryClient

        credential = ClientSecretCredential(
            tenant_id=credentials.get("azure_tenant_id"),
            client_id=credentials.get("azure_client_id"),
            client_secret=credentials.get("azure_client_secret"),
        )
        client = LogsQueryClient(credential)
        query = (
            "union isfuzzy=true AppTraces, FunctionAppLogs "
            f'| where Message contains "{trace_id}" '
            "| project TimeGenerated, Message, OperationName "
            "| order by TimeGenerated asc | take 100"
        )
        entries: list[LogEntry] = []
        failures: list[str] = []
        for workspace_name, workspace_id in sorted(normalized_workspaces.items()):
            try:
                response = client.query_workspace(
                    workspace_id,
                    query,
                    timespan=(started_at, datetime.now(timezone.utc)),
                    server_timeout=max(1, int(query_timeout_seconds)),
                )
                tables = getattr(response, "tables", None)
                partial_error = None
                if tables is None:
                    tables = getattr(response, "partial_data", [])
                    partial_error = getattr(response, "partial_error", None)
                for table in tables:
                    for row in table.rows:
                        message = redact_sensitive(row[1])
                        operation = str(row[2]) if len(row) > 2 else workspace_name
                        entries.append(
                            LogEntry(
                                timestamp=(
                                    row[0].isoformat()
                                    if hasattr(row[0], "isoformat")
                                    else str(row[0])
                                ),
                                message=message,
                                layer=_layer(operation),
                                provider="azure",
                                function=operation,
                                checkpoint=parse_checkpoint_message(message),
                            )
                        )
                if partial_error:
                    failures.append(
                        redact_sensitive(partial_error)
                        if single_workspace
                        else f"{workspace_name}: {redact_sensitive(partial_error)}"
                    )
            except Exception as exc:
                failures.append(
                    redact_sensitive(exc)
                    if single_workspace
                    else f"{workspace_name}: {redact_sensitive(exc)}"
                )
        return ProviderFetchResult(
            "azure",
            entries=entries,
            error="; ".join(failures) or None,
        )
    except Exception as exc:
        return ProviderFetchResult("azure", error=redact_sensitive(exc))


def fetch_gcp_logs(
    project_id: str,
    trace_id: str,
    credentials: dict,
    project_path: Path,
    started_at: datetime,
    *,
    query_timeout_seconds: float = 15,
) -> ProviderFetchResult:
    try:
        from google.cloud import logging as cloud_logging

        credentials_input = credentials.get("gcp_credentials_file")
        if not credentials_input:
            raise ValueError("GCP credentials are not configured")
        if not str(credentials_input).lstrip().startswith("{"):
            path = Path(credentials_input)
            if not path.is_absolute():
                credentials_input = str(project_path / path)
        _, _, parsed_credentials = parse_gcp_service_account(str(credentials_input))
        client = cloud_logging.Client(
            project=project_id,
            credentials=parsed_credentials,
        )
        cutoff = started_at - timedelta(seconds=30)
        filter_value = (
            '(resource.type="cloud_function" OR '
            'resource.type="cloud_run_revision" OR '
            'resource.type="cloud_run_workerpool" OR '
            'resource.type="k8s_container") '
            f'AND (textPayload:"{trace_id}" OR jsonPayload.message:"{trace_id}") '
            f'AND timestamp >= "{cutoff.isoformat()}"'
        )
        entries = []
        for entry in client.list_entries(
            filter_=filter_value,
            max_results=50,
            timeout=max(1, query_timeout_seconds),
        ):
            payload: Any = entry.payload
            message = (
                payload.get("message", payload)
                if isinstance(payload, dict)
                else payload
            )
            labels = entry.resource.labels if entry.resource else {}
            resource_name = (
                labels.get("function_name")
                or labels.get("service_name")
                or labels.get("worker_pool_name")
                or labels.get("container_name")
                or str(getattr(entry, "log_name", "")).rsplit("/", 1)[-1]
            )
            safe_message = redact_sensitive(message or "")
            entries.append(
                LogEntry(
                    timestamp=entry.timestamp.isoformat() if entry.timestamp else "",
                    message=safe_message,
                    layer=_layer(resource_name),
                    provider="gcp",
                    function=resource_name,
                    checkpoint=parse_checkpoint_message(safe_message),
                )
            )
        return ProviderFetchResult("gcp", entries=entries)
    except Exception as exc:
        return ProviderFetchResult("gcp", error=redact_sensitive(exc))
