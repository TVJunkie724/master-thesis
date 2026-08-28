"""Trace start and concurrent provider-log aggregation."""

from __future__ import annotations

import asyncio
from dataclasses import asdict
from datetime import datetime, timezone
import json
import time
import uuid
from pathlib import Path

from logger import logger
from src.core.config_loader import ProjectConfigLoader, normalize_provider_name
from src.core.observability import redact_sensitive, redact_structure
from src.iot_device_simulator.sender import send_test_message
from src.log_tracing.fetchers import (
    ProviderFetchResult,
    fetch_aws_logs,
    fetch_azure_logs,
    fetch_gcp_logs,
)
from src.log_tracing.registry import TraceRegistry
from src.runtime_outputs import load_terraform_outputs


FORWARD_TRACE_CHECKPOINTS = (
    "l1_accepted",
    "event_layer_durable",
    "l2_started",
    "l2_completed",
    "l3_hot_persisted",
)


def generate_trace_id() -> str:
    return f"TRACE-{uuid.uuid4().hex[:8].upper()}"


def providers_to_query(providers: dict, resolved_graph=None) -> set[str]:
    """Return every provider participating in the active deployment graph."""
    selected = {
        normalized
        for key, provider in providers.items()
        if key == "event_layer_provider" or key.startswith("layer_")
        if isinstance(provider, str)
        if (normalized := normalize_provider_name(provider)) and normalized != "none"
    }
    for node in getattr(resolved_graph, "nodes", ()) or ():
        normalized = normalize_provider_name(getattr(node, "provider", None))
        if normalized and normalized != "none":
            selected.add(normalized)
    return selected


def expected_trace_checkpoints(resolved_graph) -> tuple[str, ...]:
    """Return the bounded forward-path evidence required by the active PoC profile."""
    profile_ref = getattr(resolved_graph, "profile_ref", {}) or {}
    if (
        profile_ref.get("id") == "six-layer-eventing"
        and str(profile_ref.get("version")) == "1"
    ):
        return FORWARD_TRACE_CHECKPOINTS
    return ()


class LogTraceService:
    def __init__(
        self,
        registry: TraceRegistry,
        *,
        timeout_seconds: float,
        poll_interval_seconds: float,
        heartbeat_seconds: float = 30,
        provider_timeout_seconds: float = 20,
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError("Trace timeout must be positive")
        if poll_interval_seconds <= 0:
            raise ValueError("Trace poll interval must be positive")
        if provider_timeout_seconds <= 0:
            raise ValueError("Provider query timeout must be positive")
        if heartbeat_seconds <= 0:
            raise ValueError("Heartbeat interval must be positive")
        self.registry = registry
        self.timeout_seconds = timeout_seconds
        self.poll_interval_seconds = poll_interval_seconds
        self.heartbeat_seconds = heartbeat_seconds
        self.provider_timeout_seconds = provider_timeout_seconds

    def start(self, project_name: str, project_path: Path | None = None) -> dict:
        now = datetime.now(timezone.utc)
        bundle = (
            ProjectConfigLoader().load_bundle_from_path(project_name, project_path)
            if project_path is not None
            else ProjectConfigLoader().load_bundle(project_name)
        )
        provider = bundle.config.providers.get("layer_1_provider")
        if not provider:
            raise ValueError("L1 provider not configured")
        self.registry.reserve(project_name, now)
        trace_id = generate_trace_id()
        try:
            if not send_test_message(
                provider,
                project_name,
                trace_id,
                project_path=bundle.project_path,
            ):
                raise RuntimeError(
                    "Failed to send test message. Check simulator configuration."
                )
            self.registry.issue(project_name, trace_id, now)
        except Exception:
            self.registry.rollback(project_name, now)
            raise
        return {
            "trace_id": trace_id,
            "sent_at": now.isoformat().replace("+00:00", "Z"),
            "l1_provider": provider,
            "providers": sorted(
                providers_to_query(
                    bundle.config.providers,
                    getattr(bundle, "resolved_deployment_graph", None),
                )
            ),
            "message": f"Test message sent to {provider} IoT endpoint",
        }

    def validate(self, trace_id: str, project_name: str) -> None:
        self.registry.validate(trace_id, project_name, datetime.now(timezone.utc))

    async def stream(
        self,
        trace_id: str,
        project_name: str,
        project_path: Path | None = None,
    ):
        started_at = datetime.now(timezone.utc)
        started_monotonic = time.monotonic()
        last_heartbeat = started_monotonic
        seen: set[tuple] = set()
        reported_provider_errors: set[str] = set()
        had_provider_errors = False
        expected_checkpoints: tuple[str, ...] = ()
        observed_checkpoints: set[str] = set()
        checkpoint_count = 0
        total_logs = 0
        try:
            try:
                bundle, outputs = await asyncio.gather(
                    asyncio.to_thread(
                        ProjectConfigLoader().load_bundle_from_path,
                        project_name,
                        project_path,
                    )
                    if project_path is not None
                    else asyncio.to_thread(
                        ProjectConfigLoader().load_bundle, project_name
                    ),
                    asyncio.to_thread(
                        load_terraform_outputs, project_name, project_path
                    )
                    if project_path is not None
                    else asyncio.to_thread(load_terraform_outputs, project_name),
                )
            except Exception as exc:
                logger.error(
                    "Trace configuration load failed: %s", redact_sensitive(exc)
                )
                yield self._event(
                    "error", {"message": "Trace configuration unavailable"}
                )
                yield self._event(
                    "done",
                    {
                        "message": "Trace failed",
                        "status": "failed",
                        "total_logs": 0,
                        "duration_seconds": round(
                            time.monotonic() - started_monotonic,
                            1,
                        ),
                    },
                )
                return

            resolved_graph = getattr(bundle, "resolved_deployment_graph", None)
            providers = providers_to_query(
                bundle.config.providers,
                resolved_graph,
            )
            expected_checkpoints = expected_trace_checkpoints(resolved_graph)
            deadline = started_monotonic + self.timeout_seconds
            first_iteration = True
            while first_iteration or time.monotonic() < deadline:
                first_iteration = False
                remaining = max(0.001, deadline - time.monotonic())
                results = await asyncio.gather(
                    *(
                        self._fetch_with_timeout(
                            provider,
                            trace_id,
                            started_at,
                            bundle.credentials,
                            outputs,
                            bundle.project_path,
                            timeout=min(self.provider_timeout_seconds, remaining),
                        )
                        for provider in sorted(providers)
                    )
                )
                entries = []
                for result in results:
                    entries.extend(result.entries)
                    if result.error and result.provider not in reported_provider_errors:
                        had_provider_errors = True
                        reported_provider_errors.add(result.provider)
                        logger.warning(
                            "%s log query failed: %s",
                            result.provider,
                            result.error,
                        )
                        yield self._event(
                            "error",
                            {
                                "provider": result.provider,
                                "message": "Provider log query unavailable",
                            },
                        )

                for entry in sorted(entries, key=lambda item: item.timestamp):
                    key = (
                        entry.provider,
                        entry.function,
                        entry.timestamp,
                        entry.message,
                    )
                    if key in seen:
                        continue
                    seen.add(key)
                    total_logs += 1
                    if (
                        entry.checkpoint
                        and entry.checkpoint.get("trace_id") == trace_id
                    ):
                        observed_checkpoints.add(str(entry.checkpoint["stage"]))
                        checkpoint_count += 1
                    payload = asdict(entry)
                    payload["prefix"] = f"[{entry.layer}-{entry.provider.upper()}]"
                    yield self._event("log", payload)

                if expected_checkpoints and set(expected_checkpoints).issubset(
                    observed_checkpoints
                ):
                    break

                now = time.monotonic()
                if now - last_heartbeat >= self.heartbeat_seconds:
                    last_heartbeat = now
                    yield self._event(
                        "heartbeat",
                        {"elapsed_seconds": round(now - started_monotonic, 1)},
                    )
                remaining = deadline - time.monotonic()
                if remaining > 0:
                    await asyncio.sleep(min(self.poll_interval_seconds, remaining))

            missing_checkpoints = [
                stage
                for stage in expected_checkpoints
                if stage not in observed_checkpoints
            ]
            yield self._event(
                "done",
                {
                    "message": "Trace complete",
                    "status": (
                        "partial"
                        if had_provider_errors or missing_checkpoints
                        else "completed"
                    ),
                    "total_logs": total_logs,
                    "checkpoint_count": checkpoint_count,
                    "expected_checkpoints": list(expected_checkpoints),
                    "observed_checkpoints": sorted(observed_checkpoints),
                    "missing_checkpoints": missing_checkpoints,
                    "duration_seconds": round(time.monotonic() - started_monotonic, 1),
                },
            )
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.error("Log trace stream failed: %s", redact_sensitive(exc))
            yield self._event("error", {"message": "Log trace stream failed"})
            yield self._event(
                "done",
                {
                    "message": "Trace failed",
                    "status": "failed",
                    "total_logs": total_logs,
                    "duration_seconds": round(
                        time.monotonic() - started_monotonic,
                        1,
                    ),
                },
            )
        finally:
            self.registry.complete(trace_id)

    async def _fetch_with_timeout(
        self,
        provider: str,
        trace_id: str,
        started_at: datetime,
        credentials: dict,
        outputs: dict,
        project_path,
        *,
        timeout: float,
    ) -> ProviderFetchResult:
        try:
            return await asyncio.wait_for(
                asyncio.to_thread(
                    self._fetch_provider,
                    provider,
                    trace_id,
                    started_at,
                    credentials,
                    outputs,
                    project_path,
                    timeout,
                ),
                timeout=timeout,
            )
        except TimeoutError:
            return ProviderFetchResult(provider, error="Provider query timed out")
        except Exception as exc:
            return ProviderFetchResult(provider, error=redact_sensitive(exc))

    @staticmethod
    def _fetch_provider(
        provider: str,
        trace_id: str,
        started_at: datetime,
        credentials: dict,
        outputs: dict,
        project_path,
        query_timeout: float,
    ) -> ProviderFetchResult:
        if provider == "aws":
            return fetch_aws_logs(
                outputs.get("aws_cloudwatch_log_groups", {}),
                trace_id,
                int(started_at.timestamp() * 1000),
                credentials.get("aws", {}),
                query_timeout_seconds=query_timeout,
            )
        if provider == "azure":
            workspace_ids = outputs.get(
                "azure_log_analytics_workspace_ids"
            ) or outputs.get("azure_log_analytics_workspace_id")
            if not workspace_ids:
                return ProviderFetchResult("azure", error="Workspace ID not available")
            return fetch_azure_logs(
                workspace_ids,
                trace_id,
                credentials.get("azure", {}),
                started_at,
                query_timeout_seconds=query_timeout,
            )
        if provider == "gcp":
            gcp_credentials = credentials.get("gcp", {})
            project_id = gcp_credentials.get("gcp_project_id") or outputs.get(
                "gcp_project_id"
            )
            if not project_id:
                return ProviderFetchResult("gcp", error="Project ID not available")
            return fetch_gcp_logs(
                project_id,
                trace_id,
                gcp_credentials,
                project_path,
                started_at,
                query_timeout_seconds=query_timeout,
            )
        return ProviderFetchResult(provider, error="Unsupported provider")

    @staticmethod
    def _event(event: str, data: dict) -> dict:
        return {
            "event": event,
            "data": json.dumps(redact_structure(data), separators=(",", ":")),
        }
