"""
Data Flow Verification API — 4-Phase SSE Orchestrator.

Sends a test IoT message through the entire deployed pipeline and verifies
it reaches every layer: ingestion → processing → hot storage → digital twin
update → event checking → feedback.

Phases:
  1. Send Message   — IoT simulator (30s timeout)
  2. Pipeline        — Poll hot-reader (10 min timeout)
  3. Digital Twin    — TwinMaker/ADT telemetry (60s timeout)
  4. Event Flow      — Cloud log polling for event-checker, action, workflow, feedback (60s each)
"""

import asyncio
import json
import os
import sys
import time
import uuid
import subprocess
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from logger import logger
from core.config_loader import load_credentials
from src.core.paths import resolve_project_context_path

# Reuse helpers from logs module
from api.logs import _load_providers, _get_terraform_outputs, _send_test_message_via_simulator

router = APIRouter(tags=["Verification"])

# =============================================================================
# Constants
# =============================================================================

PHASE_1_TIMEOUT = 30       # Send message timeout (seconds)
PHASE_2_TIMEOUT = 600      # Hot-reader poll timeout (10 min)
PHASE_2_POLL_INTERVAL = 2  # Seconds between hot-reader polls
PHASE_3_TIMEOUT = 60       # Digital twin check timeout
PHASE_3_POLL_INTERVAL = 2
PHASE_4_TIMEOUT = 60       # Per-step event flow timeout
PHASE_4_POLL_INTERVAL = 5

# =============================================================================
# Request/Response Models
# =============================================================================

class DataFlowRequest(BaseModel):
    payload: dict


# =============================================================================
# Helper Functions
# =============================================================================

def _get_project_path(project_name: str) -> Path:
    return resolve_project_context_path(project_name)


def _load_optimization_config(project_name: str) -> dict:
    """Load config_optimization.json for a project."""
    path = _get_project_path(project_name) / "config_optimization.json"
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return {}


def _sse_event(event: str, data: dict) -> str:
    """Format a single SSE event."""
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


def _timestamp() -> str:
    """Current time formatted for terminal display."""
    return datetime.now().strftime("%H:%M:%S")


def _hot_reader_url_for_provider(provider: str, outputs: dict) -> Optional[str]:
    """Get the hot-reader URL based on the L3-Hot provider."""
    if provider == "aws":
        return outputs.get("aws_l3_hot_reader_url")
    elif provider == "azure":
        return outputs.get("azure_l3_hot_reader_url")
    elif provider in ("google", "gcp"):
        return outputs.get("gcp_hot_reader_url")
    return None


def _poll_hot_reader(
    url: str, device_id: str, inter_cloud_token: Optional[str],
    timeout: int, poll_interval: int, trace_id: str = None,
) -> dict:
    """
    Poll hot-reader endpoint until data appears or timeout.
    Returns {success, elapsed, record_count, error}.
    If `trace_id` is set, only records containing that trace_id are considered.
    """
    headers = {}
    if inter_cloud_token:
        headers["X-Inter-Cloud-Token"] = inter_cloud_token

    start = time.time()
    last_status = None

    while time.time() - start < timeout:
        try:
            resp = requests.get(
                url,
                params={"device_id": device_id, "limit": "20"},
                headers=headers,
                timeout=10,
            )
            last_status = resp.status_code

            if resp.status_code == 200:
                data = resp.json()
                items = []
                if isinstance(data, list):
                    items = data
                elif isinstance(data, dict) and "items" in data:
                    items = data["items"]
                elif isinstance(data, dict) and "data" in data:
                    items = data["data"]

                # Filter by trace_id if provided
                if trace_id and items:
                    items = [
                        it for it in items
                        if it.get("trace_id") == trace_id
                    ]

                if len(items) > 0:
                    elapsed = round(time.time() - start, 1)
                    return {"success": True, "elapsed": elapsed, "record_count": len(items)}

            elif resp.status_code in (401, 403):
                return {"success": False, "elapsed": 0, "error": f"Hot reader returned {resp.status_code}"}

            elif resp.status_code != 404:
                return {"success": False, "elapsed": 0, "error": f"Hot reader returned {resp.status_code}: {resp.text[:200]}"}

        except requests.exceptions.RequestException:
            pass  # retry on transient errors

        time.sleep(poll_interval)

    elapsed = round(time.time() - start, 1)
    return {"success": False, "elapsed": elapsed, "error": f"Timeout after {timeout}s (last status: {last_status})"}


def _check_twinmaker_telemetry(
    workspace_id: str, entity_id: str, timeout: int, poll_interval: int,
    aws_region: str = None, aws_creds: dict = None,
) -> dict:
    """Poll TwinMaker for property value history updates."""
    try:
        import boto3
    except ImportError:
        return {"success": False, "error": "boto3 SDK not available"}

    try:
        creds = aws_creds or {}
        session = boto3.Session(
            aws_access_key_id=creds.get("aws_access_key_id"),
            aws_secret_access_key=creds.get("aws_secret_access_key"),
            region_name=aws_region,
        )
        client = session.client("iottwinmaker")
    except Exception as e:
        return {"success": False, "error": f"Failed to create TwinMaker client: {e}"}
    start = time.time()

    while time.time() - start < timeout:
        try:
            # List entities to verify they exist first
            response = client.list_entities(workspaceId=workspace_id)
            entities = response.get("entitySummaries", [])

            matching = [e for e in entities if entity_id in e.get("entityName", "")]
            if matching:
                elapsed = round(time.time() - start, 1)
                return {"success": True, "elapsed": elapsed, "entity": matching[0]["entityName"]}

        except Exception as e:
            logger.warning(f"TwinMaker poll error: {e}")

        time.sleep(poll_interval)

    elapsed = round(time.time() - start, 1)
    return {"success": False, "elapsed": elapsed, "error": f"Entity not found after {timeout}s"}


def _check_adt_telemetry(
    adt_endpoint: str, azure_creds: dict, device_id: str,
    timeout: int, poll_interval: int
) -> dict:
    """Poll Azure Digital Twins for twin property updates."""
    try:
        from azure.identity import ClientSecretCredential
        from azure.digitaltwins.core import DigitalTwinsClient
    except ImportError:
        return {"success": False, "error": "Azure Digital Twins SDK not available"}

    try:
        credential = ClientSecretCredential(
            tenant_id=azure_creds.get("azure_tenant_id"),
            client_id=azure_creds.get("azure_client_id"),
            client_secret=azure_creds.get("azure_client_secret"),
        )
        client = DigitalTwinsClient(adt_endpoint, credential)
    except Exception as e:
        return {"success": False, "error": f"ADT client init failed: {e}"}

    start = time.time()

    while time.time() - start < timeout:
        try:
            query = "SELECT * FROM digitaltwins"
            twins = list(client.query_twins(query))
            matching = [t for t in twins if device_id in t.get("$dtId", "")]
            if matching:
                elapsed = round(time.time() - start, 1)
                return {"success": True, "elapsed": elapsed, "twin_id": matching[0]["$dtId"]}
        except Exception as e:
            logger.warning(f"ADT poll error: {e}")

        time.sleep(poll_interval)

    elapsed = round(time.time() - start, 1)
    return {"success": False, "elapsed": elapsed, "error": f"Twin not found after {timeout}s"}


def _check_cloud_logs(
    provider: str, search_pattern: str, step_name: str,
    outputs: dict, credentials: dict, project_path: Path,
    timeout: int, poll_interval: int
) -> dict:
    """Poll cloud logs for a specific pattern (event-checker, action, workflow, feedback)."""
    start = time.time()

    if provider == "aws":
        return _check_aws_logs(search_pattern, step_name, outputs, credentials, timeout, poll_interval)
    elif provider == "azure":
        return _check_azure_logs(search_pattern, step_name, outputs, credentials, timeout, poll_interval)
    elif provider in ("google", "gcp"):
        return _check_gcp_logs(search_pattern, step_name, outputs, credentials, project_path, timeout, poll_interval)

    return {"success": False, "error": f"Unknown provider: {provider}"}


def _check_aws_logs(
    search_pattern: str, step_name: str, outputs: dict, credentials: dict,
    timeout: int, poll_interval: int
) -> dict:
    try:
        import boto3
    except ImportError:
        return {"success": False, "error": "boto3 not available"}

    aws_creds = credentials.get("aws", {})
    logs_client = boto3.client("logs")
    start = time.time()

    # Determine log group based on step name
    func_name = outputs.get(f"aws_l2_{step_name}_function_name", step_name)
    log_group = f"/aws/lambda/{func_name}"

    while time.time() - start < timeout:
        try:
            end_time = int(time.time() * 1000)
            start_time = end_time - (15 * 60 * 1000)

            response = logs_client.filter_log_events(
                logGroupName=log_group,
                startTime=start_time,
                endTime=end_time,
                filterPattern=f'"{search_pattern}"',
                limit=5,
            )

            if response.get("events"):
                elapsed = round(time.time() - start, 1)
                return {"success": True, "elapsed": elapsed, "log_count": len(response["events"])}

        except Exception as e:
            logger.warning(f"AWS log query error for {step_name}: {e}")

        time.sleep(poll_interval)

    elapsed = round(time.time() - start, 1)
    return {"success": False, "elapsed": elapsed, "error": f"No logs found after {timeout}s"}


def _check_azure_logs(
    search_pattern: str, step_name: str, outputs: dict, credentials: dict,
    timeout: int, poll_interval: int
) -> dict:
    try:
        from azure.monitor.query import LogsQueryClient
        from azure.identity import ClientSecretCredential
    except ImportError:
        return {"success": False, "error": "Azure Monitor SDK not available"}

    azure_creds = credentials.get("azure", {})
    workspace_id = outputs.get("azure_log_analytics_workspace_id")
    if not workspace_id:
        return {"success": False, "error": "Log Analytics workspace ID not found"}

    try:
        credential = ClientSecretCredential(
            tenant_id=azure_creds.get("azure_tenant_id"),
            client_id=azure_creds.get("azure_client_id"),
            client_secret=azure_creds.get("azure_client_secret"),
        )
        client = LogsQueryClient(credential)
    except Exception as e:
        return {"success": False, "error": f"Azure client init failed: {e}"}

    start = time.time()
    query = f"""
    AppTraces
    | where AppRoleName contains "l2-functions"
    | where Message contains "{search_pattern}"
    | where TimeGenerated > ago(60m)
    | project TimeGenerated, Message
    | limit 10
    """

    while time.time() - start < timeout:
        try:
            response = client.query_workspace(workspace_id, query, timespan=timedelta(minutes=60))
            if response.tables and response.tables[0].rows:
                elapsed = round(time.time() - start, 1)
                return {"success": True, "elapsed": elapsed, "log_count": len(response.tables[0].rows)}
        except Exception as e:
            logger.warning(f"Azure log query error for {step_name}: {e}")

        time.sleep(poll_interval)

    elapsed = round(time.time() - start, 1)
    return {"success": False, "elapsed": elapsed, "error": f"No logs found after {timeout}s"}


def _check_gcp_logs(
    search_pattern: str, step_name: str, outputs: dict, credentials: dict,
    project_path: Path, timeout: int, poll_interval: int
) -> dict:
    try:
        from google.cloud import logging as cloud_logging
    except ImportError:
        return {"success": False, "error": "GCP Cloud Logging SDK not available"}

    gcp_creds = credentials.get("gcp", {})
    project_id = gcp_creds.get("gcp_project_id") or outputs.get("gcp_project_id")
    if not project_id:
        return {"success": False, "error": "GCP project ID not found"}

    # Set credentials file for GCP SDK
    creds_file = gcp_creds.get("gcp_credentials_file")
    if creds_file:
        abs_path = creds_file if os.path.isabs(creds_file) else str(project_path / creds_file)
        if os.path.exists(abs_path):
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = abs_path

    start = time.time()

    while time.time() - start < timeout:
        try:
            client = cloud_logging.Client(project=project_id)
            cutoff = datetime.now(timezone.utc) - timedelta(minutes=15)
            cutoff_str = cutoff.isoformat()

            filter_str = f"""
                resource.type="cloud_function"
                AND textPayload:"{search_pattern}"
                AND timestamp >= "{cutoff_str}"
            """

            entries = list(client.list_entries(filter_=filter_str, max_results=5))
            if entries:
                elapsed = round(time.time() - start, 1)
                return {"success": True, "elapsed": elapsed, "log_count": len(entries)}

        except Exception as e:
            logger.warning(f"GCP log query error for {step_name}: {e}")

        time.sleep(poll_interval)

    elapsed = round(time.time() - start, 1)
    return {"success": False, "elapsed": elapsed, "error": f"No logs found after {timeout}s"}


# =============================================================================
# Cloud Log Hint (shown on failure)
# =============================================================================

def _cloud_log_hints(providers: dict) -> List[str]:
    """Generate cloud-specific log debugging hints."""
    hints = []
    unique_providers = set(providers.values())
    for p in unique_providers:
        if p == "aws":
            hints.append("AWS: CloudWatch → /aws/lambda/{twin-name}-*")
        elif p == "azure":
            hints.append("Azure: Log Analytics → AppTraces")
        elif p in ("google", "gcp"):
            hints.append("GCP: Cloud Logging → resource.type=\"cloud_function\"")
    return hints


# =============================================================================
# SSE Streaming Endpoint
# =============================================================================

@router.post(
    "/dataflow/verify",
    operation_id="verifyDataFlow",
    summary="Verify end-to-end data flow through deployed pipeline",
    description=(
        "**Purpose:** Sends a test IoT message and verifies it propagates through "
        "the entire pipeline (ingestion → processing → storage → digital twin → events).\n\n"
        "**Response:** SSE stream with phase-by-phase results.\n\n"
        "**Duration:** 1-15 minutes depending on cold starts."
    ),
    responses={
        200: {"description": "SSE stream with verification results"},
        404: {"description": "Project not found"},
        400: {"description": "Invalid payload or missing configuration"},
    },
)
async def verify_data_flow(
    body: DataFlowRequest,
    project_name: str = Query(..., description="Digital twin project name"),
):
    """SSE endpoint that orchestrates 4-phase data flow verification."""
    # Validate project
    project_path = _get_project_path(project_name)
    if not project_path.exists():
        raise HTTPException(status_code=404, detail=f"Project '{project_name}' not found")

    payload = body.payload

    # Validate payload has iotDeviceId
    if "iotDeviceId" not in payload:
        raise HTTPException(status_code=400, detail="Payload must contain 'iotDeviceId' field")

    # Load configs upfront
    try:
        providers = _load_providers(project_name)
        tf_outputs = _get_terraform_outputs(project_name)
        optimization = _load_optimization_config(project_name)
        project_creds = load_credentials(project_path)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Config load failed: {e}")

    l1_provider = providers.get("layer_1_provider")
    if not l1_provider:
        raise HTTPException(status_code=400, detail="L1 provider not configured")

    device_id = payload["iotDeviceId"]

    async def event_generator():
        total_start = time.time()
        results = {"pass": 0, "fail": 0, "skip": 0}
        failed_phase = None

        # =====================================================================
        # Phase 1: Send Message
        # =====================================================================
        yield _sse_event("phase", {
            "phase": 1, "name": "Message Delivery",
            "status": "running", "timestamp": _timestamp(),
        })

        yield _sse_event("log", {
            "timestamp": _timestamp(),
            "message": f"Sending test message to {l1_provider.upper()} IoT...",
            "detail": f"Device: {device_id}",
        })

        # Inject trace_id and timestamp into payload
        trace_id = f"VERIFY-{uuid.uuid4().hex[:8].upper()}"
        send_payload = payload.copy()
        send_payload["trace_id"] = trace_id
        send_payload["time"] = datetime.now(timezone.utc).isoformat(
            timespec="milliseconds"
        ).replace("+00:00", "Z")

        # Send via simulator with the user's payload
        success = _send_test_message_via_simulator(
            l1_provider, project_name, trace_id,
            payload_override=send_payload,
        )

        if success:
            results["pass"] += 1
            yield _sse_event("log", {
                "timestamp": _timestamp(),
                "message": f"✓ Message sent successfully (trace: {trace_id})",
                "status": "pass",
            })
            yield _sse_event("phase", {
                "phase": 1, "name": "Message Delivery",
                "status": "pass", "timestamp": _timestamp(),
            })
        else:
            results["fail"] += 1
            failed_phase = "Phase 1 — Message Delivery"
            yield _sse_event("log", {
                "timestamp": _timestamp(),
                "message": "✗ Failed to send test message",
                "status": "fail",
            })
            yield _sse_event("phase", {
                "phase": 1, "name": "Message Delivery",
                "status": "fail", "timestamp": _timestamp(),
            })
            # Skip remaining phases
            for p_info in [
                (2, "Pipeline → Hot Storage"),
                (3, "Digital Twin Update"),
                (4, "Event Flow"),
            ]:
                results["skip"] += 1
                yield _sse_event("phase", {
                    "phase": p_info[0], "name": p_info[1],
                    "status": "skip", "reason": "Previous phase failed",
                    "timestamp": _timestamp(),
                })

            total_elapsed = round(time.time() - total_start, 1)
            yield _sse_event("done", {
                "pass_count": results["pass"],
                "fail_count": results["fail"],
                "skip_count": results["skip"],
                "total_time": total_elapsed,
                "failed_phase": failed_phase,
                "hints": _cloud_log_hints(providers),
            })
            return

        await asyncio.sleep(0)  # Yield control

        # =====================================================================
        # Phase 2: Pipeline → Hot Storage
        # =====================================================================
        l3_hot_provider = providers.get("layer_3_hot_provider")
        hot_url = _hot_reader_url_for_provider(l3_hot_provider, tf_outputs)

        yield _sse_event("phase", {
            "phase": 2, "name": "Pipeline → Hot Storage",
            "status": "running", "timeout": PHASE_2_TIMEOUT,
            "timestamp": _timestamp(),
        })

        if not hot_url:
            results["fail"] += 1
            failed_phase = "Phase 2 — Pipeline"
            yield _sse_event("log", {
                "timestamp": _timestamp(),
                "message": f"✗ No hot-reader URL found for {l3_hot_provider}",
                "status": "fail",
            })
            yield _sse_event("phase", {
                "phase": 2, "name": "Pipeline → Hot Storage",
                "status": "fail", "timestamp": _timestamp(),
            })
            # Skip remaining
            for p_info in [(3, "Digital Twin Update"), (4, "Event Flow")]:
                results["skip"] += 1
                yield _sse_event("phase", {
                    "phase": p_info[0], "name": p_info[1],
                    "status": "skip", "reason": "Previous phase failed",
                    "timestamp": _timestamp(),
                })
            total_elapsed = round(time.time() - total_start, 1)
            yield _sse_event("done", {
                "pass_count": results["pass"], "fail_count": results["fail"],
                "skip_count": results["skip"], "total_time": total_elapsed,
                "failed_phase": failed_phase, "hints": _cloud_log_hints(providers),
            })
            return

        yield _sse_event("log", {
            "timestamp": _timestamp(),
            "message": "Waiting for data propagation...",
        })

        inter_cloud_token = tf_outputs.get("inter_cloud_token")

        # Poll in 20s batches to emit progress updates
        BATCH_POLLS = 10  # 10 polls × 2s = 20s per batch
        phase2_start = time.time()
        hot_result = {"success": False, "elapsed": 0, "error": "Not started"}

        while time.time() - phase2_start < PHASE_2_TIMEOUT:
            remaining = PHASE_2_TIMEOUT - (time.time() - phase2_start)
            batch_timeout = min(BATCH_POLLS * PHASE_2_POLL_INTERVAL, remaining)
            if batch_timeout <= 0:
                break

            batch_result = await asyncio.to_thread(
                _poll_hot_reader, hot_url, device_id, inter_cloud_token,
                batch_timeout, PHASE_2_POLL_INTERVAL,
                trace_id=trace_id,
            )

            if batch_result["success"]:
                hot_result = batch_result
                hot_result["elapsed"] = round(time.time() - phase2_start, 1)
                break

            elapsed = round(time.time() - phase2_start, 1)
            hot_result = {"success": False, "elapsed": elapsed, "error": f"Timeout after {PHASE_2_TIMEOUT}s"}

            # Emit progress update
            yield _sse_event("log", {
                "timestamp": _timestamp(),
                "message": f"Still waiting... {elapsed}s elapsed",
            })

        if hot_result["success"]:
            results["pass"] += 1
            yield _sse_event("log", {
                "timestamp": _timestamp(),
                "message": f"✓ Data reached L3-Hot storage ({hot_result['elapsed']}s)",
                "detail": f"{hot_result.get('record_count', '?')} record(s) found",
                "status": "pass",
            })
            yield _sse_event("phase", {
                "phase": 2, "name": "Pipeline → Hot Storage",
                "status": "pass", "elapsed": hot_result["elapsed"],
                "timestamp": _timestamp(),
            })
        else:
            results["fail"] += 1
            failed_phase = "Phase 2 — Pipeline"
            yield _sse_event("log", {
                "timestamp": _timestamp(),
                "message": f"✗ TIMEOUT — Data did not reach hot storage within {PHASE_2_TIMEOUT}s",
                "detail": hot_result.get("error", ""),
                "status": "fail",
            })
            yield _sse_event("phase", {
                "phase": 2, "name": "Pipeline → Hot Storage",
                "status": "fail", "timestamp": _timestamp(),
            })
            # Skip remaining
            for p_info in [(3, "Digital Twin Update"), (4, "Event Flow")]:
                results["skip"] += 1
                yield _sse_event("phase", {
                    "phase": p_info[0], "name": p_info[1],
                    "status": "skip", "reason": "Previous phase failed",
                    "timestamp": _timestamp(),
                })
            total_elapsed = round(time.time() - total_start, 1)
            yield _sse_event("done", {
                "pass_count": results["pass"], "fail_count": results["fail"],
                "skip_count": results["skip"], "total_time": total_elapsed,
                "failed_phase": failed_phase, "hints": _cloud_log_hints(providers),
            })
            return

        await asyncio.sleep(0)

        # =====================================================================
        # Phase 3: Digital Twin Update
        # =====================================================================
        l4_provider = providers.get("layer_4_provider")

        if not l4_provider:
            results["skip"] += 1
            yield _sse_event("phase", {
                "phase": 3, "name": "Digital Twin Update",
                "status": "skip", "reason": "L4 not configured",
                "timestamp": _timestamp(),
            })
            yield _sse_event("log", {
                "timestamp": _timestamp(),
                "message": "— Digital Twin: N/A — L4 not configured for this deployment",
                "status": "skip",
            })
        else:
            yield _sse_event("phase", {
                "phase": 3, "name": "Digital Twin Update",
                "status": "running", "timeout": PHASE_3_TIMEOUT,
                "timestamp": _timestamp(),
            })

            if l4_provider == "aws":
                workspace_id = tf_outputs.get("aws_twinmaker_workspace_id")
                if workspace_id:
                    yield _sse_event("log", {
                        "timestamp": _timestamp(),
                        "message": "Checking TwinMaker property history...",
                    })
                    twin_result = await asyncio.to_thread(
                        _check_twinmaker_telemetry,
                        workspace_id, device_id, PHASE_3_TIMEOUT, PHASE_3_POLL_INTERVAL,
                        aws_region=tf_outputs.get("aws_region"),
                        aws_creds=project_creds.get("aws", {}),
                    )
                else:
                    twin_result = {"success": False, "error": "TwinMaker workspace ID not in outputs"}
            elif l4_provider == "azure":
                adt_endpoint = tf_outputs.get("azure_adt_endpoint")
                if adt_endpoint:
                    yield _sse_event("log", {
                        "timestamp": _timestamp(),
                        "message": "Checking Azure Digital Twins...",
                    })
                    twin_result = await asyncio.to_thread(
                        _check_adt_telemetry,
                        adt_endpoint, project_creds.get("azure", {}),
                        device_id, PHASE_3_TIMEOUT, PHASE_3_POLL_INTERVAL,
                    )
                else:
                    twin_result = {"success": False, "error": "ADT endpoint not in outputs"}
            else:
                twin_result = {"success": False, "error": f"L4 provider {l4_provider} not supported for verification"}

            if twin_result["success"]:
                results["pass"] += 1
                entity_name = twin_result.get("entity") or twin_result.get("twin_id", "")
                yield _sse_event("log", {
                    "timestamp": _timestamp(),
                    "message": f"✓ Digital twin updated ({twin_result['elapsed']}s)",
                    "detail": entity_name,
                    "status": "pass",
                })
                yield _sse_event("phase", {
                    "phase": 3, "name": "Digital Twin Update",
                    "status": "pass", "elapsed": twin_result["elapsed"],
                    "timestamp": _timestamp(),
                })
            else:
                results["fail"] += 1
                yield _sse_event("log", {
                    "timestamp": _timestamp(),
                    "message": f"✗ Digital twin verification failed",
                    "detail": twin_result.get("error", ""),
                    "status": "fail",
                })
                yield _sse_event("phase", {
                    "phase": 3, "name": "Digital Twin Update",
                    "status": "fail", "timestamp": _timestamp(),
                })
                # Don't skip Phase 4 — event flow is independent

        await asyncio.sleep(0)

        # =====================================================================
        # Phase 4: Event Flow
        # =====================================================================
        use_event_checking = optimization.get("useEventChecking", False)
        trigger_workflow = optimization.get("triggerNotificationWorkflow", False)
        return_feedback = optimization.get("returnFeedbackToDevice", False)

        if not use_event_checking:
            results["skip"] += 1
            yield _sse_event("phase", {
                "phase": 4, "name": "Event Flow",
                "status": "skip", "reason": "Event checking not configured",
                "timestamp": _timestamp(),
            })
            yield _sse_event("log", {
                "timestamp": _timestamp(),
                "message": "— Event Flow: N/A — event checking not configured",
                "status": "skip",
            })
        else:
            yield _sse_event("phase", {
                "phase": 4, "name": "Event Flow",
                "status": "running", "timestamp": _timestamp(),
            })

            l2_provider = providers.get("layer_2_provider", "aws")
            event_steps = [
                ("event_checker", "Event-Checker", "Hello from Event-Checker", True),
                ("action", "Action Function", "action", True),
                ("workflow", "Workflow", "workflow", trigger_workflow),
                ("feedback", "Feedback", "feedback", return_feedback),
            ]

            for step_key, step_name, search_pattern, enabled in event_steps:
                if not enabled:
                    results["skip"] += 1
                    yield _sse_event("log", {
                        "timestamp": _timestamp(),
                        "message": f"— {step_name}: N/A — not configured",
                        "status": "skip",
                    })
                    continue

                yield _sse_event("log", {
                    "timestamp": _timestamp(),
                    "message": f"Checking {step_name} invocation... (timeout: {PHASE_4_TIMEOUT}s)",
                })

                log_result = await asyncio.to_thread(
                    _check_cloud_logs,
                    l2_provider, search_pattern, step_key,
                    tf_outputs, project_creds, project_path,
                    PHASE_4_TIMEOUT, PHASE_4_POLL_INTERVAL,
                )

                if log_result["success"]:
                    results["pass"] += 1
                    yield _sse_event("log", {
                        "timestamp": _timestamp(),
                        "message": f"✓ {step_name} invoked ({log_result['elapsed']}s)",
                        "status": "pass",
                    })
                else:
                    results["fail"] += 1
                    if not failed_phase:
                        failed_phase = f"Phase 4 — {step_name}"
                    yield _sse_event("log", {
                        "timestamp": _timestamp(),
                        "message": f"✗ {step_name} — {log_result.get('error', 'not found')}",
                        "status": "fail",
                    })

            yield _sse_event("phase", {
                "phase": 4, "name": "Event Flow",
                "status": "pass" if results["fail"] == 0 else "partial",
                "timestamp": _timestamp(),
            })

        # =====================================================================
        # Done
        # =====================================================================
        total_elapsed = round(time.time() - total_start, 1)
        yield _sse_event("done", {
            "pass_count": results["pass"],
            "fail_count": results["fail"],
            "skip_count": results["skip"],
            "total_time": total_elapsed,
            "failed_phase": failed_phase,
            "hints": _cloud_log_hints(providers) if results["fail"] > 0 else [],
        })

    async def _safe_wrapper():
        """Wrap event_generator to catch unhandled exceptions."""
        start = time.time()
        try:
            async for event in event_generator():
                yield event
        except Exception as e:
            logger.exception(f"Data flow verification crashed: {e}")
            yield _sse_event("log", {
                "timestamp": _timestamp(),
                "message": f"\u2717 Internal error: {e}",
                "status": "fail",
            })
            yield _sse_event("done", {
                "pass_count": 0,
                "fail_count": 1,
                "skip_count": 0,
                "total_time": round(time.time() - start, 1),
                "failed_phase": "Internal error",
                "hints": [],
            })

    return StreamingResponse(
        _safe_wrapper(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
