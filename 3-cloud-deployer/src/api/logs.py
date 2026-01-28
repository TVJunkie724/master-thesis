"""
Log Trace API - Send test IoT message and stream logs from cloud providers.

This module enables end-to-end log tracing for the EDT pipeline by:
1. Sending a test IoT message with a unique trace_id
2. Streaming logs from all configured cloud providers via SSE
3. Aggregating and sorting logs by timestamp

Supports:
- Single-cloud: AWS, Azure, GCP
- Multi-cloud: Any combination of L1/L2/L3 providers
"""
import asyncio
import json
import subprocess
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Dict, Set, Optional

from fastapi import APIRouter, Query, HTTPException
from sse_starlette.sse import EventSourceResponse

from logger import logger
import constants as CONSTANTS
import src.core.state as state
from src.core.config_loader import load_credentials


router = APIRouter(prefix="/logs", tags=["Logs"])

# Rate limiting: track last trace per project
# Note: In-memory rate limiting. For production with horizontal scaling, use Redis.
_last_trace_time: Dict[str, datetime] = {}
RATE_LIMIT_SECONDS = 30

# Trace ID tracking: store issued trace_ids for validation
# Maps trace_id -> (project_name, issued_at)
_issued_traces: Dict[str, tuple] = {}
TRACE_TIMEOUT_SECONDS = 90
POLL_INTERVAL_SECONDS = 2

# Exported for testing
_rate_limit_store = _last_trace_time  # Alias for tests


def generate_trace_id() -> str:
    """Generate a unique trace ID for log tracing."""
    return f"TRACE-{uuid.uuid4().hex[:8].upper()}"


def get_providers_to_query(project_name: str) -> Set[str]:
    """Public wrapper for testing."""
    return _get_providers_to_query(project_name)


# ==============================================================================
# Helper Functions
# ==============================================================================

def _get_project_path(project_name: str) -> Path:
    """Get the project path from project name."""
    return Path(state.get_project_base_path()) / CONSTANTS.PROJECT_UPLOAD_DIR_NAME / project_name


def _load_providers(project_name: str) -> Dict[str, str]:
    """Load layer-to-provider mapping from config_providers.json."""
    project_path = _get_project_path(project_name)
    providers_file = project_path / CONSTANTS.CONFIG_PROVIDERS_FILE
    
    if not providers_file.exists():
        raise ValueError(f"config_providers.json not found for project {project_name}")
    
    with open(providers_file, 'r') as f:
        return json.load(f)


def _get_terraform_outputs(project_name: str) -> Dict:
    """
    Get Terraform outputs for the project.
    Runs terraform output command to fetch current outputs.
    """
    from src.terraform_runner import TerraformRunner
    
    project_path = _get_project_path(project_name)
    state_path = project_path / "terraform" / "terraform.tfstate"
    
    if not state_path.exists():
        logger.warning(f"Terraform state not found for {project_name}")
        return {}
    
    try:
        runner = TerraformRunner(
            terraform_dir="/app/src/terraform",
            state_path=str(state_path)
        )
        return runner.output()
    except Exception as e:
        logger.error(f"Failed to get terraform outputs: {e}")
        return {}


def _get_providers_to_query(project_name: str) -> Set[str]:
    """Determine which cloud providers need log querying."""
    providers = _load_providers(project_name)
    
    # Get unique providers from L1, L2, L3 Hot layers
    return {
        providers.get('layer_1_provider'),
        providers.get('layer_2_provider'),
        providers.get('layer_3_hot_provider')
    } - {None}


# ==============================================================================
# Log Fetchers (one per provider)
# ==============================================================================

def fetch_aws_logs(
    log_groups: Dict[str, str],
    trace_id: str,
    since_ms: int,
    credentials: dict
) -> List[Dict]:
    """Query AWS CloudWatch Logs for entries containing trace_id."""
    import boto3
    
    results = []
    
    try:
        client = boto3.client(
            'logs',
            aws_access_key_id=credentials.get('aws_access_key_id'),
            aws_secret_access_key=credentials.get('aws_secret_access_key'),
            region_name=credentials.get('aws_region', 'eu-central-1')
        )
        
        for layer_name, log_group_name in log_groups.items():
            if not log_group_name:
                continue
                
            try:
                response = client.filter_log_events(
                    logGroupName=log_group_name,
                    startTime=since_ms,
                    filterPattern=f'"{trace_id}"',
                    limit=50
                )
                
                for event in response.get('events', []):
                    results.append({
                        'timestamp': datetime.fromtimestamp(event['timestamp'] / 1000, tz=timezone.utc).isoformat(),
                        'message': event['message'].strip(),
                        'layer': layer_name,
                        'provider': 'aws'
                    })
            except Exception as e:
                logger.warning(f"Failed to query log group {log_group_name}: {e}")
                
    except Exception as e:
        logger.error(f"AWS log fetch error: {e}")
    
    return results


def fetch_azure_logs(
    workspace_id: str,
    trace_id: str,
    since_iso: str,
    credentials: dict
) -> List[Dict]:
    """Query Azure Log Analytics using KQL."""
    from azure.monitor.query import LogsQueryClient
    from azure.identity import ClientSecretCredential
    
    results = []
    
    try:
        credential = ClientSecretCredential(
            tenant_id=credentials.get('azure_tenant_id'),
            client_id=credentials.get('azure_client_id'),
            client_secret=credentials.get('azure_client_secret')
        )
        client = LogsQueryClient(credential)
        
        # Query AppTraces and FunctionAppLogs for trace_id
        query = f'''
        AppTraces
        | where TimeGenerated > datetime({since_iso})
        | where Message contains "{trace_id}"
        | project TimeGenerated, Message, OperationName
        | union (
            FunctionAppLogs
            | where TimeGenerated > datetime({since_iso})
            | where Message contains "{trace_id}"
            | project TimeGenerated, Message, OperationName
        )
        | order by TimeGenerated asc
        | take 100
        '''
        
        response = client.query_workspace(workspace_id, query, timespan="PT5M")
        
        for table in response.tables:
            for row in table.rows:
                timestamp = row[0]
                message = str(row[1])
                operation = str(row[2]) if len(row) > 2 else ""
                
                # Extract layer from operation name (e.g., "l1-dispatcher", "l2-persister")
                layer = "L?"
                if "l1" in operation.lower() or "dispatcher" in operation.lower():
                    layer = "L1"
                elif "l2" in operation.lower() or "persister" in operation.lower() or "processor" in operation.lower():
                    layer = "L2"
                elif "l3" in operation.lower() or "hot" in operation.lower():
                    layer = "L3"
                elif "l0" in operation.lower():
                    layer = "L0"
                
                results.append({
                    'timestamp': timestamp.isoformat() if hasattr(timestamp, 'isoformat') else str(timestamp),
                    'message': message,
                    'layer': layer,
                    'provider': 'azure'
                })
                
    except Exception as e:
        logger.error(f"Azure log fetch error: {e}")
    
    return results


def fetch_gcp_logs(
    project_id: str,
    trace_id: str,
    since_iso: str,
    credentials: dict
) -> List[Dict]:
    """Query GCP Cloud Logging."""
    from google.cloud import logging as gcp_logging
    from google.oauth2 import service_account
    
    results = []
    
    try:
        # Build credentials from dict (service account key)
        if isinstance(credentials, dict) and 'private_key' in credentials:
            creds = service_account.Credentials.from_service_account_info(credentials)
        else:
            # Fall back to default credentials
            creds = None
        
        client = gcp_logging.Client(project=project_id, credentials=creds)
        
        # Filter for trace_id in Cloud Functions logs
        filter_str = f'''
        resource.type="cloud_function" OR resource.type="cloud_run_revision"
        textPayload:"{trace_id}" OR jsonPayload.message:"{trace_id}"
        timestamp >= "{since_iso}"
        '''
        
        entries = list(client.list_entries(filter_=filter_str, max_results=50))
        
        for entry in entries:
            # Extract message from payload
            if entry.payload:
                if isinstance(entry.payload, dict):
                    message = entry.payload.get('message', str(entry.payload))
                else:
                    message = str(entry.payload)
            else:
                message = ""
            
            # Extract layer from resource labels
            layer = "L?"
            resource_name = entry.resource.labels.get('function_name', '') if entry.resource else ""
            if 'l1' in resource_name.lower() or 'dispatcher' in resource_name.lower():
                layer = "L1"
            elif 'l2' in resource_name.lower() or 'persister' in resource_name.lower():
                layer = "L2"
            elif 'l3' in resource_name.lower() or 'hot' in resource_name.lower():
                layer = "L3"
            elif 'l0' in resource_name.lower() or 'ingestion' in resource_name.lower():
                layer = "L0"
            
            results.append({
                'timestamp': entry.timestamp.isoformat() if entry.timestamp else '',
                'message': message,
                'layer': layer,
                'provider': 'gcp'
            })
            
    except Exception as e:
        logger.error(f"GCP log fetch error: {e}")
    
    return results


# ==============================================================================
# IoT Message Senders (via subprocess to existing simulators)
# ==============================================================================

def _send_test_message_via_simulator(
    provider: str,
    project_name: str,
    trace_id: str
) -> bool:
    """
    Send test message via existing IoT simulator using subprocess.
    Uses the --payload CLI argument for single-shot mode.
    """
    # Map provider to simulator script path
    provider_map = {
        'aws': 'aws',
        'azure': 'azure',
        'google': 'google',
        'gcp': 'google'
    }
    
    simulator_provider = provider_map.get(provider)
    if not simulator_provider:
        logger.error(f"Unknown provider: {provider}")
        return False
    
    script_path = f"/app/src/iot_device_simulator/{simulator_provider}/main.py"
    
    # Create payload with trace_id
    payload = {
        "iotDeviceId": "log-trace-test",
        "trace_id": trace_id,
        "type": "log_trace_test",
        "time": datetime.now(timezone.utc).isoformat(timespec='milliseconds').replace('+00:00', 'Z'),
        "value": 42.0
    }
    
    try:
        result = subprocess.run(
            [sys.executable, "-m", f"src.iot_device_simulator.{simulator_provider}.main",
             "--project", project_name,
             "--payload", json.dumps(payload)],
            capture_output=True,
            text=True,
            timeout=30,
            cwd="/app"
        )
        
        if result.returncode != 0:
            logger.error(f"Simulator failed: {result.stderr}")
            return False
            
        logger.info(f"Test message sent via {provider} simulator: {trace_id}")
        return True
        
    except subprocess.TimeoutExpired:
        logger.error(f"Simulator timeout for {provider}")
        return False
    except Exception as e:
        logger.error(f"Simulator error for {provider}: {e}")
        return False


# ==============================================================================
# API Endpoints
# ==============================================================================

@router.post("/trace/start")
async def start_log_trace(
    project_name: str = Query(..., description="Digital twin project name"),
):
    """
    Send test IoT message with unique trace_id.
    
    Rate limited: 1 trace per 30 seconds per project.
    
    Returns:
        trace_id: Unique identifier to track in logs
        l1_provider: Primary IoT provider (where message is sent)
        providers: Set of providers that will be queried for logs
    """
    # Validate project exists
    project_path = _get_project_path(project_name)
    if not project_path.exists():
        raise HTTPException(status_code=404, detail=f"Project '{project_name}' not found")
    
    # Rate limiting
    now = datetime.utcnow()
    if project_name in _last_trace_time:
        elapsed = (now - _last_trace_time[project_name]).total_seconds()
        if elapsed < RATE_LIMIT_SECONDS:
            raise HTTPException(
                status_code=429,
                detail=f"Rate limited. Wait {RATE_LIMIT_SECONDS - int(elapsed)} seconds."
            )
    _last_trace_time[project_name] = now
    
    # Generate trace_id using helper function
    trace_id = generate_trace_id()
    
    # Store trace_id for validation in stream endpoint
    _issued_traces[trace_id] = (project_name, now)
    
    # Load providers config
    try:
        providers = _load_providers(project_name)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    l1_provider = providers.get('layer_1_provider')
    if not l1_provider:
        raise HTTPException(status_code=400, detail="L1 provider not configured")
    
    # Send test message via simulator
    success = _send_test_message_via_simulator(l1_provider, project_name, trace_id)
    
    if not success:
        raise HTTPException(
            status_code=500,
            detail="Failed to send test message. Check simulator configuration."
        )
    
    providers_to_query = list(_get_providers_to_query(project_name))
    
    return {
        "trace_id": trace_id,
        "sent_at": now.isoformat() + "Z",
        "l1_provider": l1_provider,
        "providers": providers_to_query,
        "message": f"Test message sent to {l1_provider} IoT endpoint"
    }


@router.get("/trace/stream/{trace_id}")
async def stream_log_trace(
    trace_id: str,
    project_name: str = Query(...),
):
    """
    SSE endpoint streaming logs matching trace_id.
    
    Polls each provider every 2 seconds for 90 seconds.
    Returns logs with layer and provider prefix.
    
    Events:
    - "log": {layer, provider, timestamp, message}
    - "error": {message}
    - "done": {summary}
    """
    # Validate project exists
    project_path = _get_project_path(project_name)
    if not project_path.exists():
        raise HTTPException(status_code=404, detail=f"Project '{project_name}' not found")
    
    # Validate trace_id was issued for this project
    if trace_id not in _issued_traces:
        raise HTTPException(status_code=404, detail=f"Unknown trace_id: {trace_id}")
    
    issued_project, issued_at = _issued_traces[trace_id]
    if issued_project != project_name:
        raise HTTPException(status_code=403, detail="Trace ID does not belong to this project")
    
    # Check if trace has expired (issued more than 2 minutes ago)
    if (datetime.utcnow() - issued_at).total_seconds() > 120:
        del _issued_traces[trace_id]
        raise HTTPException(status_code=410, detail="Trace has expired")
    
    async def event_generator():
        seen_messages: Set[str] = set()
        start_time = datetime.now(timezone.utc)
        start_ms = int(start_time.timestamp() * 1000)
        start_iso = start_time.isoformat().replace('+00:00', 'Z')
        last_heartbeat = start_time
        
        # Load configuration once at start
        try:
            providers_to_query = _get_providers_to_query(project_name)
            credentials = load_credentials(project_path)
            tf_outputs = _get_terraform_outputs(project_name)
        except Exception as e:
            yield {"event": "error", "data": json.dumps({"message": f"Config load failed: {e}"})}
            return
        
        total_logs = 0
        
        # Poll for 90 seconds (CloudWatch can have 30-60s delay)
        for iteration in range(45):  # 45 iterations * 2s = 90s
            all_logs = []
            
            # Query each provider
            for provider in providers_to_query:
                if provider == 'aws':
                    aws_creds = credentials.get('aws', {})
                    log_groups = tf_outputs.get('aws_cloudwatch_log_groups', {})
                    logs = fetch_aws_logs(log_groups, trace_id, start_ms, aws_creds)
                    all_logs.extend(logs)
                    
                elif provider == 'azure':
                    azure_creds = credentials.get('azure', {})
                    workspace_id = tf_outputs.get('azure_log_analytics_workspace_id')
                    if workspace_id:
                        logs = fetch_azure_logs(workspace_id, trace_id, start_iso, azure_creds)
                        all_logs.extend(logs)
                    
                elif provider in ('google', 'gcp'):
                    gcp_creds = credentials.get('gcp', {})
                    project_id = gcp_creds.get('gcp_project_id') or gcp_creds.get('project_id')
                    if project_id:
                        logs = fetch_gcp_logs(project_id, trace_id, start_iso, gcp_creds)
                        all_logs.extend(logs)
            
            # Sort by timestamp and dedupe
            all_logs.sort(key=lambda x: x.get('timestamp', ''))
            
            for log in all_logs:
                # Create unique key for deduplication
                log_key = f"{log['timestamp']}:{log['message'][:100]}"
                if log_key not in seen_messages:
                    seen_messages.add(log_key)
                    total_logs += 1
                    
                    # Format log line with prefix
                    prefix = f"[{log.get('layer', 'L?')}-{log.get('provider', '?').upper()}]"
                    formatted = {
                        "prefix": prefix,
                        "timestamp": log['timestamp'],
                        "message": log['message'],
                        "layer": log.get('layer'),
                        "provider": log.get('provider')
                    }
                    
                    yield {"event": "log", "data": json.dumps(formatted)}
            
            await asyncio.sleep(POLL_INTERVAL_SECONDS)
            
            # Send heartbeat every 30 seconds to keep connection alive
            now = datetime.now(timezone.utc)
            if (now - last_heartbeat).total_seconds() >= 30:
                last_heartbeat = now
                yield {
                    "event": "heartbeat",
                    "data": json.dumps({"elapsed_seconds": iteration * POLL_INTERVAL_SECONDS})
                }
        
        # Cleanup issued trace
        if trace_id in _issued_traces:
            del _issued_traces[trace_id]
        
        # Done
        yield {
            "event": "done",
            "data": json.dumps({
                "message": "Trace complete",
                "total_logs": total_logs,
                "duration_seconds": 90
            })
        }
    
    return EventSourceResponse(event_generator())
