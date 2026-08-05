"""
Layer 5 (Visualization) SDK Operations for Azure.

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
         └── L3 Hot Reader endpoint

Note:
    Infrastructure (Grafana workspace) is handled by Terraform.
    This file handles SDK-managed datasource configuration.
"""

import logging
import secrets
import time
from typing import TYPE_CHECKING, Optional, Dict, Any

import requests

from azure.core.exceptions import (
    ResourceNotFoundError,
    ClientAuthenticationError,
    AzureError,
)

if TYPE_CHECKING:
    from src.core.context import DeploymentContext
    from src.providers.azure.provider import AzureProvider

logger = logging.getLogger(__name__)
MANAGEMENT_API_VERSION = "2025-08-01"
APP_SERVICE_API_VERSION = "2025-05-01"
JSON_DATASOURCE_PLUGIN_ID = "marcusolsson-json-datasource"
JSON_DATASOURCE_PLUGIN_VERSION = "1.4.0"
V2_DATASOURCE_UID = "t2mc-azure-hot-reader"
V2_FOLDER_UID = "t2mc-raw-rollups"
V2_DASHBOARD_UID = "t2mc-raw-rollups"
V2_READER_FUNCTION_NAME = "v2-raw-history-reader"
_TRANSIENT_GRAFANA_READINESS_CODES = frozenset({403, 404, 429, 502, 503, 504})


# ==========================================
# Helper Functions
# ==========================================


def get_grafana_workspace_url(provider: "AzureProvider") -> Optional[str]:
    """
    Get the endpoint URL of the Azure Managed Grafana workspace.

    Args:
        provider: Initialized AzureProvider with clients and naming

    Returns:
        The Grafana workspace URL or None if not found

    Raises:
        ValueError: If provider is None
        ClientAuthenticationError: If permission denied
    """
    if provider is None:
        raise ValueError("provider is required")

    rg_name = provider.naming.resource_group()
    workspace_name = provider.naming.grafana_workspace()

    try:
        grafana_client = provider.clients.get("dashboard")
        if grafana_client is None:
            logger.warning("Dashboard client not initialized")
            return None

        workspace = grafana_client.grafana.get(
            resource_group_name=rg_name, workspace_name=workspace_name
        )
        if workspace.properties and workspace.properties.endpoint:
            return workspace.properties.endpoint
        return None
    except ResourceNotFoundError:
        logger.info(f"✗ Grafana workspace not found: {workspace_name}")
        return None
    except ClientAuthenticationError as e:
        logger.error(f"PERMISSION DENIED getting Grafana workspace: {e.message}")
        raise
    except AzureError as e:
        logger.error(f"Azure error getting Grafana workspace: {type(e).__name__}: {e}")
        raise


def _get_grafana_service_account_token(provider: "AzureProvider") -> Optional[str]:
    """
    Get a service account token for Grafana API access.

    Azure Managed Grafana uses Azure AD authentication.
    This function retrieves an access token for the Grafana API.

    Args:
        provider: Initialized AzureProvider

    Returns:
        Access token for Grafana API or None if not available
    """
    if provider is None:
        raise ValueError("provider is required")

    try:
        # Use provider's credential (ClientSecretCredential or DefaultAzureCredential)
        # Azure Managed Grafana uses a well-known Application ID for OAuth2 tokens.
        # The GUID ce34e7e5-485f-4d76-964f-b3d2b16d1e4f is Microsoft's official
        # Azure Managed Grafana service principal ID, used globally across all tenants.
        # Using "https://grafana.azure.com/.default" returns 401 because the token
        # audience doesn't match what Grafana expects.
        GRAFANA_APP_ID = "ce34e7e5-485f-4d76-964f-b3d2b16d1e4f"
        token = provider.credential.get_token(f"{GRAFANA_APP_ID}/.default")
        return token.token
    except Exception as e:
        logger.warning(f"Could not get Grafana API token: {e}")
        return None


def _get_management_token(provider: "AzureProvider") -> str:
    try:
        return provider.credential.get_token(
            "https://management.azure.com/.default"
        ).token
    except Exception as exc:
        raise RuntimeError("Azure management token was not created") from exc


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def _workspace_arm_url(provider: "AzureProvider", workspace_name: str) -> str:
    return (
        "https://management.azure.com/subscriptions/"
        f"{provider.subscription_id}/resourceGroups/{provider.naming.resource_group()}"
        f"/providers/Microsoft.Dashboard/grafana/{workspace_name}"
    )


def _function_arm_url(
    provider: "AzureProvider", function_app_name: str, suffix: str
) -> str:
    return (
        "https://management.azure.com/subscriptions/"
        f"{provider.subscription_id}/resourceGroups/{provider.naming.resource_group()}"
        f"/providers/Microsoft.Web/sites/{function_app_name}"
        f"/functions/{V2_READER_FUNCTION_NAME}/{suffix}"
    )


def _require_status(response, allowed: tuple[int, ...], operation: str) -> None:
    if response.status_code not in allowed:
        raise RuntimeError(f"{operation} returned HTTP {response.status_code}")


def _ensure_managed_grafana_plugin(
    provider: "AzureProvider", workspace_name: str
) -> None:
    """Fail closed unless Azure offers and loads the frozen v2 plugin."""

    token = _get_management_token(provider)
    workspace_url = _workspace_arm_url(provider, workspace_name)
    response = requests.post(
        f"{workspace_url}/fetchAvailablePlugins?api-version={MANAGEMENT_API_VERSION}",
        headers=_headers(token),
        timeout=30,
    )
    _require_status(response, (200,), "Azure Grafana plugin catalog preflight")
    available = response.json().get("value", [])
    if not any(
        isinstance(item, dict) and item.get("pluginId") == JSON_DATASOURCE_PLUGIN_ID
        for item in available
    ):
        raise RuntimeError(
            f"Azure Managed Grafana does not offer {JSON_DATASOURCE_PLUGIN_ID}"
        )

    response = requests.get(
        f"{workspace_url}?api-version={MANAGEMENT_API_VERSION}",
        headers=_headers(token),
        timeout=30,
    )
    _require_status(response, (200,), "Azure Grafana workspace preflight")
    properties = response.json().get("properties", {})
    if str(properties.get("grafanaMajorVersion")) != "12":
        raise RuntimeError("Azure Managed Grafana workspace is not on major version 12")
    installed = properties.get("grafanaPlugins", {})
    if not isinstance(installed, dict) or JSON_DATASOURCE_PLUGIN_ID not in installed:
        response = requests.patch(
            f"{workspace_url}?api-version={MANAGEMENT_API_VERSION}",
            headers=_headers(token),
            json={
                "properties": {
                    "grafanaPlugins": {
                        JSON_DATASOURCE_PLUGIN_ID: {
                            "pluginId": JSON_DATASOURCE_PLUGIN_ID
                        }
                    }
                }
            },
            timeout=30,
        )
        _require_status(response, (200, 202), "Azure Grafana plugin installation")


def _wait_for_exact_plugin(
    grafana_url: str,
    grafana_token: str,
    *,
    attempts: int = 12,
    delay_seconds: float = 5,
) -> None:
    headers = _headers(grafana_token)
    last_detail = "no response"
    for attempt in range(attempts):
        try:
            response = requests.get(
                f"{grafana_url}/api/plugins/{JSON_DATASOURCE_PLUGIN_ID}/settings",
                headers=headers,
                timeout=30,
            )
        except requests.RequestException as exc:
            # The workspace endpoint and its freshly assigned Grafana Admin role
            # can become reachable shortly after Terraform completes.
            last_detail = exc.__class__.__name__
            response = None
        if response is None:
            if attempt + 1 < attempts:
                time.sleep(delay_seconds)
            continue
        if response.status_code == 200:
            body = response.json()
            info = body.get("info", {}) if isinstance(body, dict) else {}
            version = info.get("version") or body.get("version")
            if version != JSON_DATASOURCE_PLUGIN_VERSION:
                raise RuntimeError(
                    "Azure Grafana JSON API plugin version mismatch: "
                    f"expected {JSON_DATASOURCE_PLUGIN_VERSION}, got {version or 'unknown'}"
                )
            return
        last_detail = f"HTTP {response.status_code}"
        if response.status_code not in _TRANSIENT_GRAFANA_READINESS_CODES:
            raise RuntimeError(
                f"Azure Grafana plugin readiness returned HTTP {response.status_code}"
            )
        if attempt + 1 < attempts:
            time.sleep(delay_seconds)
    raise RuntimeError(
        "Azure Grafana JSON API plugin did not become ready "
        f"after {attempts} attempts (last result: {last_detail})"
    )


def _ensure_reader_function_key(
    provider: "AzureProvider", function_app_name: str
) -> str:
    """Create once or reuse one function-scoped key without logging it."""

    token = _get_management_token(provider)
    headers = _headers(token)
    response = requests.post(
        _function_arm_url(provider, function_app_name, "listkeys")
        + f"?api-version={APP_SERVICE_API_VERSION}",
        headers=headers,
        timeout=30,
    )
    _require_status(response, (200,), "Azure Function key lookup")
    properties = response.json().get("properties", {})
    existing = (
        properties.get("twin2multicloud-grafana")
        if isinstance(properties, dict)
        else None
    )
    if isinstance(existing, str) and existing:
        return existing

    value = secrets.token_urlsafe(32)
    response = requests.put(
        _function_arm_url(
            provider,
            function_app_name,
            "keys/twin2multicloud-grafana",
        )
        + f"?api-version={APP_SERVICE_API_VERSION}",
        headers=headers,
        json={"name": "twin2multicloud-grafana", "value": value},
        timeout=30,
    )
    _require_status(response, (200, 201), "Azure Function key creation")
    return value


# ==========================================
# SDK-Managed Resource Checks
# ==========================================


def check_datasource(datasource_name: str, provider: "AzureProvider") -> bool:
    """
    Check if a Grafana datasource exists.

    Uses the Grafana HTTP API to check datasource status.

    Args:
        datasource_name: Name of the datasource to check
        provider: Initialized AzureProvider

    Returns:
        True if datasource exists, False otherwise

    Raises:
        ValueError: If datasource_name or provider is None
    """
    if datasource_name is None:
        raise ValueError("datasource_name is required")
    if provider is None:
        raise ValueError("provider is required")

    grafana_url = get_grafana_workspace_url(provider)
    if not grafana_url:
        logger.info("✗ Grafana workspace not accessible")
        return False

    token = _get_grafana_service_account_token(provider)
    if not token:
        logger.info("✗ Could not get Grafana API token")
        return False

    try:
        response = requests.get(
            f"{grafana_url}/api/datasources/name/{datasource_name}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=30,
        )

        if response.status_code == 200:
            logger.info(f"✓ Grafana datasource exists: {datasource_name}")
            return True
        elif response.status_code == 404:
            logger.info(f"✗ Grafana datasource not found: {datasource_name}")
            return False
        else:
            logger.warning(
                f"Unexpected response checking datasource: {response.status_code}"
            )
            return False
    except requests.RequestException as e:
        logger.error(f"HTTP error checking datasource: {e}")
        return False


def info_l5(context: "DeploymentContext", provider: "AzureProvider") -> Dict[str, Any]:
    """
    Check status of SDK-managed L5 resources.

    Checks Grafana datasource configuration status.

    Args:
        context: Deployment context with config
        provider: Initialized AzureProvider

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

    workspace_url = get_grafana_workspace_url(provider)
    datasource_name = f"{context.config.digital_twin_name}-hot-reader"
    datasource_exists = False

    if workspace_url:
        datasource_exists = check_datasource(datasource_name, provider)

    return {
        "layer": "5",
        "provider": "azure",
        "grafana_url": workspace_url,
        "datasources": {datasource_name: datasource_exists},
    }


# ==========================================
# Post-Terraform SDK Operations
# ==========================================


def configure_grafana_datasource(
    provider: "AzureProvider", hot_reader_url: str
) -> None:
    """
    Configure JSON API datasource in Grafana (post-Terraform).

    Creates a JSON API datasource in Azure Managed Grafana that points
    to the Hot Reader function for data visualization.

    Args:
        provider: Initialized AzureProvider with clients and naming
        hot_reader_url: URL of the Hot Reader function (L3)

    Raises:
        ValueError: If provider or hot_reader_url is None/empty
        requests.RequestException: If HTTP request fails
    """
    if provider is None:
        raise ValueError("provider is required")
    if not hot_reader_url:
        raise ValueError("hot_reader_url is required")

    grafana_url = get_grafana_workspace_url(provider)
    if not grafana_url:
        raise RuntimeError("Azure Grafana workspace was not found")

    token = _get_grafana_service_account_token(provider)
    if not token:
        raise RuntimeError("Azure Grafana service-account token was not created")

    datasource_name = f"{provider.twin_name}-hot-reader"

    logger.info(f"Configuring Grafana datasource: {datasource_name}")
    logger.info(f"  Hot Reader URL: {hot_reader_url}")

    # Create JSON API datasource
    datasource_config = {
        "name": datasource_name,
        "type": "marcusolsson-json-datasource",
        "url": hot_reader_url,
        "access": "proxy",
        "basicAuth": False,
        "jsonData": {"httpMethod": "GET"},
    }

    try:
        # Check if datasource already exists
        response = requests.get(
            f"{grafana_url}/api/datasources/name/{datasource_name}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=30,
        )

        if response.status_code == 200:
            # Update existing datasource
            existing_ds = response.json()
            datasource_id = existing_ds.get("id")
            if datasource_id is None:
                raise RuntimeError("Grafana datasource response did not contain an id")

            response = requests.put(
                f"{grafana_url}/api/datasources/{datasource_id}",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                json=datasource_config,
                timeout=30,
            )

            if response.status_code == 200:
                logger.info(f"✓ Grafana datasource updated: {datasource_name}")
            else:
                raise RuntimeError(
                    f"Grafana datasource update returned HTTP {response.status_code}"
                )
        elif response.status_code == 404:
            # Create new datasource
            response = requests.post(
                f"{grafana_url}/api/datasources",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                json=datasource_config,
                timeout=30,
            )

            if response.status_code in (200, 201):
                logger.info(f"✓ Grafana datasource created: {datasource_name}")
            else:
                raise RuntimeError(
                    f"Grafana datasource create returned HTTP {response.status_code}"
                )
        else:
            raise RuntimeError(
                f"Grafana datasource lookup returned HTTP {response.status_code}"
            )

    except requests.RequestException as e:
        logger.error(f"HTTP error configuring Grafana datasource: {e}")
        raise

    logger.info("✓ Grafana datasource configuration complete")


def _upsert_v2_datasource(
    *,
    grafana_url: str,
    grafana_token: str,
    datasource_name: str,
    hot_reader_url: str,
    function_key: str,
) -> None:
    headers = _headers(grafana_token)
    config = {
        "uid": V2_DATASOURCE_UID,
        "name": datasource_name,
        "type": JSON_DATASOURCE_PLUGIN_ID,
        "url": hot_reader_url,
        "access": "proxy",
        "basicAuth": False,
        "isDefault": False,
        "jsonData": {
            "httpMethod": "GET",
            "httpHeaderName1": "x-functions-key",
        },
        "secureJsonData": {"httpHeaderValue1": function_key},
    }
    response = requests.get(
        f"{grafana_url}/api/datasources/uid/{V2_DATASOURCE_UID}",
        headers=headers,
        timeout=30,
    )
    if response.status_code == 200:
        response = requests.put(
            f"{grafana_url}/api/datasources/uid/{V2_DATASOURCE_UID}",
            headers=headers,
            json=config,
            timeout=30,
        )
        _require_status(response, (200,), "Azure Grafana datasource update")
        return
    if response.status_code != 404:
        raise RuntimeError(
            f"Azure Grafana datasource lookup returned HTTP {response.status_code}"
        )
    response = requests.post(
        f"{grafana_url}/api/datasources",
        headers=headers,
        json=config,
        timeout=30,
    )
    _require_status(response, (200, 201), "Azure Grafana datasource creation")


def _history_target(
    *, device_id: str, metric: str, bucket_seconds: int
) -> dict[str, Any]:
    timestamp_field = "stored_at" if bucket_seconds == 0 else "bucket_start"
    value_field = "value" if bucket_seconds == 0 else "avg"
    return {
        "refId": "A",
        "datasource": {"type": JSON_DATASOURCE_PLUGIN_ID, "uid": V2_DATASOURCE_UID},
        "method": "GET",
        "urlPath": "",
        "queryParams": "",
        "params": [
            ["device_id", device_id],
            ["metric", metric],
            ["from", "$__isoFrom()"],
            ["to", "$__isoTo()"],
            ["bucket_seconds", str(bucket_seconds)],
            ["limit", "1000"],
        ],
        "headers": [],
        "body": "",
        "cacheDurationSeconds": 0,
        "fields": [
            {
                "jsonPath": f"$.points[*].{timestamp_field}",
                "name": "Time",
                "type": "time",
                "language": "jsonpath",
            },
            {
                "jsonPath": f"$.points[*].{value_field}",
                "name": metric,
                "type": "number",
                "language": "jsonpath",
            },
        ],
    }


def _v2_dashboard(device_id: str, metric: str) -> dict[str, Any]:
    datasource = {"type": JSON_DATASOURCE_PLUGIN_ID, "uid": V2_DATASOURCE_UID}
    field_config = {
        "defaults": {
            "color": {"mode": "palette-classic"},
            "custom": {
                "drawStyle": "line",
                "lineInterpolation": "linear",
                "lineWidth": 1,
                "fillOpacity": 10,
                "showPoints": "auto",
            },
        },
        "overrides": [],
    }
    return {
        "uid": V2_DASHBOARD_UID,
        "title": "Raw & Rollups",
        "description": (
            "Five-layer v2 PoC view over provider-local L3 hot storage. "
            "Empty panels mean that no simulator telemetry exists in the selected interval."
        ),
        "tags": ["five-layer-baseline@2", "thesis-poc"],
        "timezone": "browser",
        "schemaVersion": 41,
        "version": 0,
        "refresh": "30s",
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
                        "No data is a valid initial state before simulator telemetry arrives."
                    ),
                },
            },
            {
                "id": 2,
                "type": "timeseries",
                "title": "Raw telemetry",
                "description": "Individual L3-hot samples; maximum query window 24 hours.",
                "datasource": datasource,
                "gridPos": {"h": 10, "w": 12, "x": 0, "y": 4},
                "fieldConfig": field_config,
                "options": {
                    "legend": {"displayMode": "list", "placement": "bottom"},
                    "tooltip": {"mode": "single", "sort": "none"},
                },
                "targets": [
                    _history_target(
                        device_id=device_id, metric=metric, bucket_seconds=0
                    )
                ],
            },
            {
                "id": 3,
                "type": "timeseries",
                "title": "Hourly rollups",
                "description": "Hourly averages from L3 hot; maximum query window 30 days.",
                "datasource": datasource,
                "gridPos": {"h": 10, "w": 12, "x": 12, "y": 4},
                "fieldConfig": field_config,
                "options": {
                    "legend": {"displayMode": "list", "placement": "bottom"},
                    "tooltip": {"mode": "single", "sort": "none"},
                },
                "targets": [
                    _history_target(
                        device_id=device_id, metric=metric, bucket_seconds=3600
                    )
                ],
            },
        ],
    }


def _upsert_v2_folder_and_dashboard(
    *,
    grafana_url: str,
    grafana_token: str,
    device_id: str,
    metric: str,
) -> None:
    headers = _headers(grafana_token)
    response = requests.get(
        f"{grafana_url}/api/folders/{V2_FOLDER_UID}",
        headers=headers,
        timeout=30,
    )
    if response.status_code == 404:
        response = requests.post(
            f"{grafana_url}/api/folders",
            headers=headers,
            json={"uid": V2_FOLDER_UID, "title": "Raw & Rollups"},
            timeout=30,
        )
        _require_status(response, (200,), "Azure Grafana folder creation")
    elif response.status_code == 200:
        if response.json().get("title") != "Raw & Rollups":
            response = requests.put(
                f"{grafana_url}/api/folders/{V2_FOLDER_UID}",
                headers=headers,
                json={"title": "Raw & Rollups", "version": -1},
                timeout=30,
            )
            _require_status(response, (200,), "Azure Grafana folder update")
    else:
        raise RuntimeError(
            f"Azure Grafana folder lookup returned HTTP {response.status_code}"
        )

    response = requests.post(
        f"{grafana_url}/api/dashboards/db",
        headers=headers,
        json={
            "dashboard": _v2_dashboard(device_id, metric),
            "folderUid": V2_FOLDER_UID,
            "message": "Provision Five-layer v2 PoC dashboard",
            "overwrite": True,
        },
        timeout=30,
    )
    _require_status(response, (200,), "Azure Grafana dashboard provisioning")


def configure_five_layer_v2_grafana(
    provider: "AzureProvider",
    *,
    workspace_name: str,
    grafana_url: str,
    hot_reader_url: str,
    function_app_name: str,
    device_id: str,
    metric: str,
) -> None:
    """Provision the exact v2 plugin, secret datasource, folder, and dashboard."""

    if not all(
        (
            workspace_name,
            grafana_url,
            hot_reader_url,
            function_app_name,
            device_id,
            metric,
        )
    ):
        raise ValueError("Azure Five-layer v2 Grafana inputs must be non-empty")
    _ensure_managed_grafana_plugin(provider, workspace_name)
    grafana_token = _get_grafana_service_account_token(provider)
    if not grafana_token:
        raise RuntimeError("Azure Grafana service-account token was not created")
    _wait_for_exact_plugin(grafana_url, grafana_token)
    function_key = _ensure_reader_function_key(provider, function_app_name)
    _upsert_v2_datasource(
        grafana_url=grafana_url,
        grafana_token=grafana_token,
        datasource_name=f"{provider.twin_name}-hot-reader",
        hot_reader_url=hot_reader_url,
        function_key=function_key,
    )
    _upsert_v2_folder_and_dashboard(
        grafana_url=grafana_url,
        grafana_token=grafana_token,
        device_id=device_id,
        metric=metric,
    )
    logger.info("✓ Azure Five-layer v2 Grafana surface is ready")
