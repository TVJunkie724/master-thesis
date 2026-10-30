"""
Layer 5 (Visualization) SDK Operations for AWS.

This module provides:
1. Post-Terraform SDK operations (Grafana datasource configuration)
2. SDK-managed resource checks (datasource status)

Components Managed:
- Grafana Datasource: JSON API datasource pointing to Hot Reader

Architecture:
    Hot Reader URL → Grafana Datasource → Dashboard Panels
         │                   │                   │
         │                   │                   └── Visualizations
         │                   └── JSON API Config
         └── L3 Hot Reader Lambda (via API Gateway)

Note:
    Infrastructure (Grafana workspace, IAM roles) is handled by Terraform.
    This file handles SDK-managed datasource configuration.
"""

from datetime import datetime, timedelta, timezone
import hashlib
import logging
import secrets
import time
from urllib.parse import quote, urlsplit
from typing import TYPE_CHECKING, Dict, Any, Optional

import requests

from botocore.exceptions import ClientError

if TYPE_CHECKING:
    from providers.aws.provider import AWSProvider
    from src.core.context import DeploymentContext

logger = logging.getLogger(__name__)
JSON_DATASOURCE_PLUGIN_ID = "yesoreyeram-infinity-datasource"
JSON_DATASOURCE_PLUGIN_VERSION = "4.1.3"
SIX_LAYER_DATASOURCE_UID = "t2mc-aws-hot-reader"
SIX_LAYER_FOLDER_UID = "t2mc-raw-rollups"
SIX_LAYER_DASHBOARD_UID = "t2mc-raw-rollups"
_TRANSIENT_GRAFANA_READINESS_CODES = frozenset({403, 404, 429, 502, 503, 504})


def _require_status(response, expected: tuple[int, ...], operation: str) -> None:
    if response.status_code not in expected:
        error = RuntimeError(f"{operation} returned HTTP {response.status_code}")
        error._aws_grafana_http_status = response.status_code
        error._aws_grafana_cause = _failure_kind(response)
        if operation == "AWS Grafana backend query" and response.status_code == 404:
            error._aws_grafana_cause = "datasource-or-plugin-unavailable"
        raise error


def _failure_kind(response) -> str:
    """Classify upstream failures without forwarding bodies or credentials."""
    detail = str(getattr(response, "text", "")).lower()
    if "no ec2 imds role found" in detail or "failed to refresh cached credentials" in detail:
        return "credential-chain-unavailable"
    if "accessdenied" in detail or "not authorized" in detail or "forbidden" in detail:
        return "permission-denied"
    if "unsupported protocol" in detail or "invalid url" in detail:
        return "invalid-reader-url"
    return "upstream-failure"


def _headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


def _provisioning_service_account(
    provider: "AWSProvider", workspace_id: str
) -> tuple[str, str]:
    """Create one short-lived Grafana v12 automation identity and token."""

    client = provider.clients["grafana"]
    name = f"{provider.twin_name}-six-provisioner"
    accounts = client.list_workspace_service_accounts(
        workspaceId=workspace_id,
        maxResults=100,
    ).get("serviceAccounts", [])
    matching = [account for account in accounts if account.get("name") == name]
    if len(matching) > 1:
        raise RuntimeError("AWS Grafana provisioning service account is ambiguous")
    if matching:
        service_account_id = matching[0]["id"]
    else:
        service_account_id = client.create_workspace_service_account(
            workspaceId=workspace_id,
            name=name,
            grafanaRole="ADMIN",
        )["id"]
    # This is the public service-account token label, never the generated key.
    token_name = "bounded-post-deploy"  # nosec B105
    for token in client.list_workspace_service_account_tokens(
        workspaceId=workspace_id,
        serviceAccountId=service_account_id,
        maxResults=100,
    ).get("serviceAccountTokens", []):
        if token.get("name") == token_name:
            client.delete_workspace_service_account_token(
                workspaceId=workspace_id,
                serviceAccountId=service_account_id,
                tokenId=token["id"],
            )
    created = client.create_workspace_service_account_token(
        workspaceId=workspace_id,
        serviceAccountId=service_account_id,
        name=token_name,
        secondsToLive=3600,
    )
    token = created.get("serviceAccountToken", {}).get("key")
    if not token:
        raise RuntimeError("AWS Grafana service-account token was not returned")
    return service_account_id, str(token)


def _delete_provisioning_service_account(
    provider: "AWSProvider", workspace_id: str, service_account_id: str
) -> None:
    provider.clients["grafana"].delete_workspace_service_account(
        workspaceId=workspace_id,
        serviceAccountId=service_account_id,
    )


def _revoke_provisioning_tokens(provider, workspace_id, service_account_id):
    """Keep one billable identity per workspace; revoke all short-lived tokens."""
    client = provider.clients["grafana"]
    for token in client.list_workspace_service_account_tokens(
        workspaceId=workspace_id, serviceAccountId=service_account_id, maxResults=100
    ).get("serviceAccountTokens", []):
        client.delete_workspace_service_account_token(
            workspaceId=workspace_id, serviceAccountId=service_account_id,
            tokenId=token["id"],
        )


def _wait_for_exact_plugin(
    grafana_url: str,
    token: str,
    *,
    attempts: int = 12,
    delay_seconds: float = 5,
) -> None:
    last_detail = "not queried"
    for attempt in range(attempts):
        response = requests.get(
            f"{grafana_url}/api/plugins/{JSON_DATASOURCE_PLUGIN_ID}/settings",
            headers=_headers(token),
            timeout=30,
        )
        if response.status_code == 200:
            version = str(response.json().get("info", {}).get("version") or "")
            if version != JSON_DATASOURCE_PLUGIN_VERSION:
                raise RuntimeError(
                    "AWS Grafana JSON API plugin version mismatch: "
                    f"expected {JSON_DATASOURCE_PLUGIN_VERSION}, received {version or 'unknown'}"
                )
            return
        last_detail = f"HTTP {response.status_code}"
        if response.status_code not in _TRANSIENT_GRAFANA_READINESS_CODES:
            break
        if attempt + 1 < attempts:
            time.sleep(delay_seconds)
    raise RuntimeError(
        "AWS Grafana JSON API plugin did not become ready "
        f"after {attempts} attempts (last result: {last_detail})"
    )


def _ensure_exact_plugin(grafana_url: str, token: str) -> None:
    response = requests.post(
        f"{grafana_url}/api/plugins/{JSON_DATASOURCE_PLUGIN_ID}/install",
        headers=_headers(token),
        json={"version": JSON_DATASOURCE_PLUGIN_VERSION},
        timeout=30,
    )
    _require_status(response, (200, 409), "AWS Grafana plugin installation")
    _wait_for_exact_plugin(grafana_url, token)


def _install_reader_key(
    provider: "AWSProvider", function_name: str, reader_key: str
) -> None:
    client = provider.clients["lambda"]
    current = client.get_function_configuration(FunctionName=function_name)
    variables = dict(current.get("Environment", {}).get("Variables", {}))
    variables["READER_KEY_SHA256"] = hashlib.sha256(
        reader_key.encode("utf-8")
    ).hexdigest()
    client.update_function_configuration(
        FunctionName=function_name,
        Environment={"Variables": variables},
    )
    client.get_waiter("function_updated_v2").wait(FunctionName=function_name)


def _upsert_v2_datasource(
    *, grafana_url: str, token: str, reader_url: str, region: str,
    reader_credentials: dict[str, str],
) -> None:
    config = {
        "uid": SIX_LAYER_DATASOURCE_UID,
        "name": "Twin2MultiCloud Raw History",
        "type": JSON_DATASOURCE_PLUGIN_ID,
        "url": reader_url,
        "access": "proxy",
        "basicAuth": False,
        "isDefault": False,
        "jsonData": {
            "auth_method": "aws",
            "aws": {"authType": "keys", "region": region, "service": "lambda"},
            "allowedHosts": [f"https://{urlsplit(reader_url).hostname}"],
        },
        "secureJsonData": {
            "awsAccessKey": reader_credentials["AccessKeyId"],
            "awsSecretKey": reader_credentials["SecretAccessKey"],
        },
    }
    response = requests.get(
        f"{grafana_url}/api/datasources/uid/{SIX_LAYER_DATASOURCE_UID}",
        headers=_headers(token),
        timeout=30,
    )
    if response.status_code == 200:
        response = requests.put(
            f"{grafana_url}/api/datasources/uid/{SIX_LAYER_DATASOURCE_UID}",
            headers=_headers(token),
            json=config,
            timeout=30,
        )
        _require_status(response, (200,), "AWS Grafana datasource update")
    elif response.status_code == 404:
        response = requests.post(
            f"{grafana_url}/api/datasources",
            headers=_headers(token),
            json=config,
            timeout=30,
        )
        _require_status(response, (200, 201), "AWS Grafana datasource creation")
    else:
        raise RuntimeError(
            f"AWS Grafana datasource lookup returned HTTP {response.status_code}"
        )


def _history_target(device_id: str, metric: str, bucket_seconds: int) -> dict[str, Any]:
    timestamp_field = "stored_at" if bucket_seconds == 0 else "bucket_start"
    value_field = "value" if bucket_seconds == 0 else "avg"
    return {
        "refId": "A",
        "datasource": {
            "type": JSON_DATASOURCE_PLUGIN_ID,
            "uid": SIX_LAYER_DATASOURCE_UID,
        },
        "type": "json", "source": "url", "parser": "backend",
        # Infinity's browser query migration reads this before backend dispatch.
        "url_options": {"method": "GET"},
        "format": "timeseries", "root_selector": "points",
        "url": (f"?device_id={quote(device_id, safe='')}&metric={quote(metric, safe='')}"
                "&from=${__from:date:iso}&to=${__to:date:iso}"
                f"&bucket_seconds={bucket_seconds}&limit=1000"),
        "columns": [
            {"selector": timestamp_field, "text": "Time", "type": "timestamp"},
            {"selector": value_field, "text": metric, "type": "number"},
        ],
    }


def _v2_dashboard(
    device_id: str,
    metric: str,
    architecture_profile: str,
) -> dict[str, Any]:
    datasource = {"type": JSON_DATASOURCE_PLUGIN_ID, "uid": SIX_LAYER_DATASOURCE_UID}
    return {
        "uid": SIX_LAYER_DASHBOARD_UID,
        "title": "Twin2MultiCloud Raw & Rollups",
        "description": (
            f"Bounded {architecture_profile} PoC view over provider-local "
            "L3 hot storage."
        ),
        "tags": [architecture_profile, "thesis-poc"],
        "timezone": "browser",
        "schemaVersion": 41,
        "version": 0,
        "refresh": "",
        "time": {"from": "now-6h", "to": "now"},
        "panels": [
            {
                "id": 1,
                "type": "text",
                "title": "PoC scope",
                "gridPos": {"h": 4, "w": 24, "x": 0, "y": 0},
                "options": {
                    "mode": "markdown",
                    "content": (
                        f"Device: `{device_id}` · Metric: `{metric}`  \n"
                        "Raw is limited to 24 hours; hourly rollups are limited to 30 days. "
                        "No data is a valid initial state; use the existing test-message utility."
                    ),
                },
            },
            {
                "id": 2,
                "type": "timeseries",
                "title": "Raw telemetry",
                "datasource": datasource,
                "gridPos": {"h": 10, "w": 12, "x": 0, "y": 4},
                "targets": [_history_target(device_id, metric, 0)],
            },
            {
                "id": 3,
                "type": "timeseries",
                "title": "Hourly rollups",
                "datasource": datasource,
                "gridPos": {"h": 10, "w": 12, "x": 12, "y": 4},
                "targets": [_history_target(device_id, metric, 3600)],
            },
        ],
    }


def _upsert_v2_dashboard(
    *,
    grafana_url: str,
    token: str,
    device_id: str,
    metric: str,
    architecture_profile: str,
) -> None:
    response = requests.get(
        f"{grafana_url}/api/folders/{SIX_LAYER_FOLDER_UID}",
        headers=_headers(token),
        timeout=30,
    )
    if response.status_code == 404:
        response = requests.post(
            f"{grafana_url}/api/folders",
            headers=_headers(token),
            json={"uid": SIX_LAYER_FOLDER_UID, "title": "Raw & Rollups"},
            timeout=30,
        )
        _require_status(response, (200,), "AWS Grafana folder creation")
    elif response.status_code != 200:
        raise RuntimeError(
            f"AWS Grafana folder lookup returned HTTP {response.status_code}"
        )
    response = requests.post(
        f"{grafana_url}/api/dashboards/db",
        headers=_headers(token),
        json={
            "dashboard": _v2_dashboard(device_id, metric, architecture_profile),
            "folderUid": SIX_LAYER_FOLDER_UID,
            "message": f"Provision {architecture_profile} PoC dashboard",
            "overwrite": True,
        },
        timeout=30,
    )
    _require_status(response, (200,), "AWS Grafana dashboard provisioning")


def _probe_v2_surface(
    *,
    grafana_url: str,
    token: str,
    reader_url: str,
    reader_key: str,
    device_id: str,
    metric: str,
) -> None:
    now = datetime.now(timezone.utc)
    for bucket, start in (
        (0, now - timedelta(hours=24)),
        (3600, now - timedelta(days=30)),
    ):
        response = requests.get(
            reader_url,
            headers={"X-Twin-Reader-Key": reader_key},
            params={
                "device_id": device_id,
                "metric": metric,
                "from": start.isoformat().replace("+00:00", "Z"),
                "to": now.isoformat().replace("+00:00", "Z"),
                "bucket_seconds": str(bucket),
                "limit": "1",
            },
            timeout=30,
        )
        _require_status(response, (200,), "AWS raw-history query probe")
        if response.json().get("schema_version") != "raw-history-query.v1":
            raise RuntimeError(
                "AWS raw-history query probe returned an invalid contract"
            )
    response = requests.get(
        f"{grafana_url}/api/datasources/uid/{SIX_LAYER_DATASOURCE_UID}/health",
        headers=_headers(token),
        timeout=30,
    )
    _require_status(response, (200,), "AWS Grafana datasource health probe")
    if response.json().get("status") != "OK":
        raise RuntimeError("AWS Grafana datasource health probe was not OK")
    response = requests.get(
        f"{grafana_url}/api/dashboards/uid/{SIX_LAYER_DASHBOARD_UID}",
        headers=_headers(token),
        timeout=30,
    )
    _require_status(response, (200,), "AWS Grafana dashboard probe")


def _replace_reader_credentials(provider, user_name: str) -> dict[str, str]:
    """Only rotate keys of the dedicated Terraform-owned, tagged reader user."""
    iam = provider.clients["iam"]
    user = iam.get_user(UserName=user_name)["User"]
    tags = {item["Key"]: item["Value"] for item in user.get("Tags", [])}
    if user.get("Path") != "/twin2multicloud/grafana/" or tags.get("Purpose") != "grafana-l3-reader":
        raise ValueError("Grafana reader identity ownership is invalid")
    keys = iam.list_access_keys(UserName=user_name)
    if keys.get("IsTruncated"):
        raise ValueError("Grafana reader key inventory is incomplete")
    for key in keys.get("AccessKeyMetadata", []):
        iam.delete_access_key(UserName=user_name, AccessKeyId=key["AccessKeyId"])
    return iam.create_access_key(UserName=user_name)["AccessKey"]


def configure_six_layer_grafana(
    provider: "AWSProvider",
    *,
    workspace_id: str,
    grafana_url: str,
    reader_url: str,
    reader_function_name: str,
    reader_user_name: str,
    device_id: str,
    metric: str,
    architecture_profile: str,
) -> None:
    """Provision and probe the deterministic Phase 8 Managed Grafana surface."""

    if not all(
        (
            workspace_id,
            grafana_url,
            reader_url,
            reader_function_name,
            reader_user_name,
            device_id,
            metric,
            architecture_profile,
        )
    ):
        raise ValueError("AWS Phase 8 Grafana inputs must be non-empty")
    service_account_id, token = _provisioning_service_account(provider, workspace_id)
    stage = "plugin"
    reader_credentials = None
    ready = False
    try:
        _ensure_exact_plugin(grafana_url, token)
        stage = "reader-identity"
        reader_credentials = _replace_reader_credentials(provider, reader_user_name)
        stage = "datasource"
        _upsert_v2_datasource(
            grafana_url=grafana_url,
            token=token,
            reader_url=reader_url,
            region=provider.clients["lambda"].meta.region_name,
            reader_credentials=reader_credentials,
        )
        stage = "dashboard"
        _upsert_v2_dashboard(
            grafana_url=grafana_url,
            token=token,
            device_id=device_id,
            metric=metric,
            architecture_profile=architecture_profile,
        )
        # Exercise the Grafana backend, not a direct reader request signed by
        # the deployment administrator. Empty frames are valid before telemetry.
        stage = "backend-query"
        now = datetime.now(timezone.utc)
        for bucket in (0, 3600):
            target = _history_target(device_id, metric, bucket)
            target["url"] = target["url"].replace("${__from:date:iso}", quote(
                (now - timedelta(hours=6)).isoformat(), safe=""
            )).replace("${__to:date:iso}", quote(now.isoformat(), safe=""))
            # IAM keys and freshly installed datasource/plugin query paths can
            # take time to become usable. Grafana documents /api/ds/query 404
            # as datasource/plugin unavailable, not a successful empty result.
            for attempt in range(12):
                response = requests.post(
                    f"{grafana_url}/api/ds/query", headers=_headers(token),
                    json={"from": str(int((now-timedelta(hours=6)).timestamp()*1000)),
                          "to": str(int(now.timestamp()*1000)), "queries": [target]},
                    timeout=30,
                )
                pending_auth = response.status_code in (401, 403) or (
                    response.status_code == 400 and _failure_kind(response) == "permission-denied"
                )
                pending_query_path = response.status_code == 404
                if not (pending_auth or pending_query_path) or attempt == 11:
                    break
                logger.info("AWS Grafana backend query readiness retry %s/12: HTTP %s",
                            attempt + 1, response.status_code)
                time.sleep(5)
            _require_status(response, (200,), "AWS Grafana backend query")
            result = response.json().get("results", {}).get("A", {})
            if result.get("error") or result.get("status", 200) != 200 or "frames" not in result:
                error = RuntimeError("AWS Grafana backend query did not return data frames")
                error._aws_grafana_cause = _failure_kind(response)
                raise error
        ready = True
    except Exception as error:
        error._aws_grafana_stage = stage
        raise
    finally:
        try:
            if reader_credentials and not ready:
                provider.clients["iam"].delete_access_key(
                    UserName=reader_user_name, AccessKeyId=reader_credentials["AccessKeyId"]
                )
        finally:
            _revoke_provisioning_tokens(provider, workspace_id, service_account_id)
    logger.info("✓ AWS %s Grafana surface is ready", architecture_profile)


# ==========================================
# Helper Functions
# ==========================================


def _get_grafana_workspace_id(provider: "AWSProvider") -> Optional[str]:
    """
    Get the Grafana workspace ID.

    Args:
        provider: Initialized AWSProvider

    Returns:
        Workspace ID or None if not found

    Raises:
        ValueError: If provider is None
    """
    if provider is None:
        raise ValueError("provider is required")

    workspace_name = provider.naming.grafana_workspace()
    client = provider.clients["grafana"]

    try:
        response = client.list_workspaces()
        for workspace in response.get("workspaces", []):
            if workspace.get("name") == workspace_name:
                return workspace.get("id")
        logger.info(f"✗ Grafana workspace not found: {workspace_name}")
        return None
    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        if error_code == "AccessDeniedException":
            logger.error(f"PERMISSION DENIED listing Grafana workspaces: {e}")
            raise
        else:
            logger.error(f"AWS error listing Grafana workspaces: {error_code} - {e}")
            raise


def _get_grafana_workspace_url(provider: "AWSProvider") -> Optional[str]:
    """
    Get the Grafana workspace URL.

    Args:
        provider: Initialized AWSProvider

    Returns:
        Workspace URL or None if not found
    """
    if provider is None:
        raise ValueError("provider is required")

    workspace_id = _get_grafana_workspace_id(provider)
    if not workspace_id:
        return None

    client = provider.clients["grafana"]

    try:
        response = client.describe_workspace(workspaceId=workspace_id)
        return response.get("workspace", {}).get("endpoint")
    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        logger.error(f"AWS error getting Grafana workspace: {error_code}")
        return None


def _get_grafana_api_key(provider: "AWSProvider", workspace_id: str) -> Optional[str]:
    """
    Get or create a Grafana API key for datasource configuration.

    Args:
        provider: Initialized AWSProvider
        workspace_id: Grafana workspace ID

    Returns:
        API key or None if not available
    """
    if provider is None:
        raise ValueError("provider is required")
    if not workspace_id:
        raise ValueError("workspace_id is required")

    client = provider.clients["grafana"]
    key_name = f"{provider.twin_name}-deployer-key"

    try:
        # Create a new API key
        response = client.create_workspace_api_key(
            workspaceId=workspace_id,
            keyName=key_name,
            keyRole="ADMIN",
            secondsToLive=3600,  # 1 hour
        )
        return response.get("key")
    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        if error_code == "ConflictException":
            # Key already exists, delete and recreate
            try:
                client.delete_workspace_api_key(
                    workspaceId=workspace_id, keyName=key_name
                )
                response = client.create_workspace_api_key(
                    workspaceId=workspace_id,
                    keyName=key_name,
                    keyRole="ADMIN",
                    secondsToLive=3600,
                )
                return response.get("key")
            except ClientError:
                logger.warning("Could not create Grafana API key")
                return None
        else:
            logger.warning(f"Could not create Grafana API key: {error_code}")
            return None


# ==========================================
# SDK-Managed Resource Checks
# ==========================================


def check_datasource(datasource_name: str, provider: "AWSProvider") -> bool:
    """
    Check if a Grafana datasource exists.

    Uses the Grafana HTTP API to check datasource status.

    Args:
        datasource_name: Name of the datasource to check
        provider: Initialized AWSProvider

    Returns:
        True if datasource exists, False otherwise

    Raises:
        ValueError: If datasource_name or provider is None
    """
    if datasource_name is None:
        raise ValueError("datasource_name is required")
    if provider is None:
        raise ValueError("provider is required")

    workspace_id = _get_grafana_workspace_id(provider)
    if not workspace_id:
        logger.info("✗ Grafana workspace not accessible")
        return False

    grafana_url = _get_grafana_workspace_url(provider)
    if not grafana_url:
        return False

    api_key = _get_grafana_api_key(provider, workspace_id)
    if not api_key:
        logger.info("✗ Could not get Grafana API key")
        return False

    try:
        response = requests.get(
            f"https://{grafana_url}/api/datasources/name/{datasource_name}",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=30,
        )

        if response.status_code == 200:
            logger.info(f"✓ Grafana datasource exists: {datasource_name}")
            return True
        elif response.status_code == 404:
            logger.info(f"✗ Grafana datasource not found: {datasource_name}")
            return False
        else:
            logger.warning(f"Unexpected response: {response.status_code}")
            return False
    except requests.RequestException as e:
        logger.error(f"HTTP error checking datasource: {e}")
        return False


def info_l5(context: "DeploymentContext", provider: "AWSProvider") -> Dict[str, Any]:
    """
    Check status of SDK-managed L5 resources.

    Checks Grafana datasource configuration status.

    Args:
        context: Deployment context with config
        provider: Initialized AWSProvider

    Returns:
        Dictionary with L5 status information

    Raises:
        ValueError: If context or provider is None
    """
    if context is None:
        raise ValueError("context is required")
    if provider is None:
        raise ValueError("provider is required")

    logger.info(
        f"[L5] Checking SDK-managed resources for {context.config.digital_twin_name}"
    )

    workspace_url = _get_grafana_workspace_url(provider)
    datasource_name = f"{context.config.digital_twin_name}-hot-reader"
    datasource_exists = False

    if workspace_url:
        datasource_exists = check_datasource(datasource_name, provider)

    return {
        "layer": "5",
        "provider": "aws",
        "grafana_url": workspace_url,
        "datasources": {datasource_name: datasource_exists},
    }


# ==========================================
# Post-Terraform SDK Operations
# ==========================================


def configure_grafana_datasource(provider: "AWSProvider", hot_reader_url: str) -> None:
    """
    Configure JSON API datasource in AWS Managed Grafana (post-Terraform).

    Creates a JSON API datasource that points to the Hot Reader Lambda
    for data visualization.

    Args:
        provider: Initialized AWSProvider
        hot_reader_url: URL of the Hot Reader Lambda (via API Gateway)

    Raises:
        ValueError: If provider or hot_reader_url is None/empty
        requests.RequestException: If HTTP request fails
    """
    if provider is None:
        raise ValueError("provider is required")
    if not hot_reader_url:
        raise ValueError("hot_reader_url is required")

    workspace_id = _get_grafana_workspace_id(provider)
    if not workspace_id:
        logger.warning("Grafana workspace not found, skipping datasource config")
        return

    grafana_url = _get_grafana_workspace_url(provider)
    if not grafana_url:
        logger.warning("Grafana workspace URL not found, skipping datasource config")
        return

    api_key = _get_grafana_api_key(provider, workspace_id)
    if not api_key:
        logger.warning("Could not get Grafana API key, skipping datasource config")
        return

    datasource_name = f"{provider.twin_name}-hot-reader"

    logger.info(f"Configuring Grafana datasource: {datasource_name}")
    logger.info(f"  Hot Reader URL: {hot_reader_url}")

    datasource_config = {
        "name": datasource_name,
        "type": "marcusolsson-json-datasource",
        "url": hot_reader_url,
        "access": "proxy",
        "basicAuth": False,
        "jsonData": {"httpMethod": "GET"},
    }

    try:
        # Check if datasource exists
        response = requests.get(
            f"https://{grafana_url}/api/datasources/name/{datasource_name}",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=30,
        )

        if response.status_code == 200:
            # Update existing
            existing_ds = response.json()
            datasource_id = existing_ds.get("id")

            response = requests.put(
                f"https://{grafana_url}/api/datasources/{datasource_id}",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=datasource_config,
                timeout=30,
            )

            if response.status_code == 200:
                logger.info(f"✓ Grafana datasource updated: {datasource_name}")
            else:
                logger.warning(f"Failed to update datasource: {response.status_code}")
        else:
            # Create new
            response = requests.post(
                f"https://{grafana_url}/api/datasources",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=datasource_config,
                timeout=30,
            )

            if response.status_code in (200, 201):
                logger.info(f"✓ Grafana datasource created: {datasource_name}")
            else:
                logger.warning(f"Failed to create datasource: {response.status_code}")

    except requests.RequestException as e:
        logger.error(f"HTTP error configuring datasource: {e}")
        raise

    logger.info("✓ Grafana datasource configuration complete")
