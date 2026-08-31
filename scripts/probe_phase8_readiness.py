#!/usr/bin/env python3
"""Run the bounded, read-only Phase 8 provider prerequisite probes.

The script intentionally performs only SDK/HTTP read operations. It emits no
account identifiers, resource names, credential paths, or credential values.
Provider errors are reduced to stable status/error codes before serialization.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import boto3
import requests
from azure.identity import ClientSecretCredential
from botocore.exceptions import ClientError
from google.oauth2 import service_account
from googleapiclient.discovery import build as build_google_api
from googleapiclient.errors import HttpError


ROOT = Path(__file__).resolve().parents[1]
DEPLOYER_ROOT = ROOT / "3-cloud-deployer"
for import_root in (DEPLOYER_ROOT, DEPLOYER_ROOT / "src"):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

from src.api.azure_credentials_checker import check_azure_credentials  # noqa: E402
from src.api.credentials_checker import check_aws_credentials  # noqa: E402
from src.api.gcp_credentials_checker import check_gcp_credentials  # noqa: E402
from src.api.preflight import build_provider_preflight  # noqa: E402


AWS_QUOTA_SERVICES = {
    "grafana": "number of workspaces",
    "iottwinmaker": "workspaces in this account in the current region",
    "kinesis": "shards per region",
}
AZURE_CONTROL_PLANES = {
    "Microsoft.App": "managedEnvironments",
    "Microsoft.Dashboard": "grafana",
    "Microsoft.DocumentDB": "databaseAccounts",
    "Microsoft.EventHub": "namespaces",
    "Microsoft.Web": "sites",
}
AZURE_ACCESS_TYPES = {
    "l4": ("Microsoft.DigitalTwins", "digitalTwinsInstances"),
    "l5": ("Microsoft.Dashboard", "grafana"),
}
GCP_QUOTA_SERVICES = (
    "compute.googleapis.com",
    "container.googleapis.com",
    "firestore.googleapis.com",
    "run.googleapis.com",
)
GCP_QUOTA_METRICS = {
    "compute.googleapis.com": {
        "compute.googleapis.com/cpus",
        "compute.googleapis.com/disks_total_storage",
        "compute.googleapis.com/regional_in_use_addresses",
    },
    "container.googleapis.com": {
        "container.googleapis.com/clusters_per_zone",
        "container.googleapis.com/quota/nodes_per_cluster",
    },
    "firestore.googleapis.com": {"firestore.googleapis.com/databases"},
    "run.googleapis.com": {
        "run.googleapis.com/cpu_allocation",
        "run.googleapis.com/instances",
        "run.googleapis.com/mem_allocation",
    },
}
SAFE_MODE = "control_plane_get_list_describe_only"
SENSITIVE_CREDENTIAL_KEYS = {
    "aws_access_key_id",
    "aws_secret_access_key",
    "aws_session_token",
    "azure_subscription_id",
    "azure_tenant_id",
    "azure_client_id",
    "azure_client_secret",
    "azure_preparation_client_id",
    "azure_preparation_client_secret",
    "gcp_project_id",
    "gcp_credentials_file",
}


def _canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _digest(value: object) -> str:
    return "sha256:" + hashlib.sha256(_canonical_json(value).encode()).hexdigest()


def _assert_sensitive_values_absent(
    record: dict[str, Any], credentials: dict[str, dict[str, Any]]
) -> None:
    serialized = _canonical_json(record)
    for provider in credentials.values():
        for key in SENSITIVE_CREDENTIAL_KEYS:
            value = provider.get(key)
            if isinstance(value, str) and len(value) >= 4 and value in serialized:
                raise ValueError(f"Sensitive credential field escaped redaction: {key}")


def _normalize_location(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.lower())


def _safe_error_code(exc: Exception) -> str:
    if isinstance(exc, ClientError):
        return str(exc.response.get("Error", {}).get("Code") or "AWS_CLIENT_ERROR")
    if isinstance(exc, HttpError):
        return f"HTTP_{getattr(exc.resp, 'status', 'ERROR')}"
    return type(exc).__name__.upper()


def _preflight_summary(provider: str, result: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    preflight = build_provider_preflight(provider, result, payload).model_dump()
    summary = result.get("summary") or result.get("permission_status", {}).get("summary")
    return {
        "ready": preflight["ready"],
        "status": result.get("status", "unknown"),
        "checks": [
            {
                "name": item["name"],
                "status": item["status"],
                "code": item["code"],
            }
            for item in preflight["checks"]
        ],
        "summary": summary or {},
    }


def _aws_probe(credentials: dict[str, Any]) -> dict[str, Any]:
    session = boto3.Session(
        aws_access_key_id=credentials["aws_access_key_id"],
        aws_secret_access_key=credentials["aws_secret_access_key"],
        aws_session_token=credentials.get("aws_session_token"),
        region_name=credentials["aws_region"],
    )
    preflight_result = check_aws_credentials(credentials)
    quotas = []
    for service_code, exact_quota_name in AWS_QUOTA_SERVICES.items():
        try:
            client = session.client("service-quotas")
            items = []
            for page in client.get_paginator("list_service_quotas").paginate(
                ServiceCode=service_code,
                QuotaAppliedAtLevel="ACCOUNT",
            ):
                items.extend(page.get("Quotas", []))
            relevant = [
                {
                    "quota_code": str(item.get("QuotaCode", "")),
                    "quota_name": str(item.get("QuotaName", "")),
                    "value": item.get("Value"),
                    "unit": str(item.get("Unit", "")),
                }
                for item in items
                if exact_quota_name == str(item.get("QuotaName", "")).lower()
            ]
            quotas.append(
                {
                    "control_plane": service_code,
                    "status": "readable",
                    "quota_count": len(items),
                    "relevant_quotas": relevant,
                    "sufficiency": "requires_inventory_comparison" if relevant else "not_exposed",
                }
            )
        except Exception as exc:  # provider SDK boundary
            quotas.append(
                {
                    "control_plane": service_code,
                    "status": "not_readable",
                    "error_code": _safe_error_code(exc),
                    "quota_count": 0,
                    "relevant_quotas": [],
                    "sufficiency": "unknown",
                }
            )

    inventory_operations: tuple[tuple[str, str, str, dict[str, Any]], ...] = (
        ("grafana", "list_workspaces", "workspaces", {"maxResults": 25}),
        ("iottwinmaker", "list_workspaces", "workspaceSummaries", {"maxResults": 25}),
        ("kinesis", "list_streams", "StreamNames", {"Limit": 100}),
    )
    inventory = []
    for service, operation, result_key, kwargs in inventory_operations:
        try:
            response = getattr(session.client(service), operation)(**kwargs)
            inventory.append(
                {
                    "control_plane": service,
                    "status": "readable",
                    "existing_resource_count_lower_bound": len(response.get(result_key, [])),
                    "truncated": bool(response.get("nextToken") or response.get("NextToken") or response.get("HasMoreStreams")),
                }
            )
        except Exception as exc:  # provider SDK boundary
            inventory.append(
                {
                    "control_plane": service,
                    "status": "not_readable",
                    "error_code": _safe_error_code(exc),
                }
            )

    for quota in quotas:
        current = next(
            (
                item.get("existing_resource_count_lower_bound", 0)
                for item in inventory
                if item["control_plane"] == quota["control_plane"]
                and item["status"] == "readable"
            ),
            None,
        )
        limits = [
            item.get("value")
            for item in quota["relevant_quotas"]
            if isinstance(item.get("value"), (int, float))
        ]
        if current is not None and limits:
            quota["minimum_required"] = 1
            quota["observed_usage_lower_bound"] = current
            quota["sufficiency"] = (
                "passed" if max(limits) - current >= 1 else "blocked"
            )

    identity_center_ready = any(
        item["code"] == "IDENTITY_CENTER_PRIMARY_REGION_READY"
        and item["status"] == "passed"
        for item in _preflight_summary("aws", preflight_result, credentials)["checks"]
    )
    quota_status = (
        "passed"
        if all(
            item["status"] == "readable" and item["sufficiency"] == "passed"
            for item in quotas
        )
        else "blocked"
    )
    return {
        "preflight": _preflight_summary("aws", preflight_result, credentials),
        "quota": {"status": quota_status, "control_planes": quotas},
        "capacity_inventory": inventory,
        "access_prerequisites": {
            "l4_twinmaker_control_plane": _inventory_status(inventory, "iottwinmaker"),
            "l5_identity_center_primary_region": "passed" if identity_center_ready else "blocked",
            "l5_managed_grafana_control_plane": _inventory_status(inventory, "grafana"),
        },
    }


def _inventory_status(items: list[dict[str, Any]], control_plane: str) -> str:
    item = next((value for value in items if value["control_plane"] == control_plane), None)
    return "passed" if item and item["status"] == "readable" else "blocked"


def _latest_stable_api_version(resource_type: dict[str, Any]) -> str | None:
    versions = [
        str(value)
        for value in resource_type.get("apiVersions", [])
        if "preview" not in str(value).lower()
    ]
    return max(versions, default=None)


def _arm_get(token: str, url: str) -> tuple[dict[str, Any] | None, str | None]:
    try:
        response = requests.get(
            url,
            headers={"Authorization": f"Bearer {token}"},
            timeout=30,
        )
    except requests.RequestException as exc:
        return None, type(exc).__name__.upper()
    if response.status_code >= 400:
        try:
            payload = response.json()
            code = payload.get("error", {}).get("code")
        except ValueError:
            code = None
        return None, str(code or f"HTTP_{response.status_code}")
    try:
        value = response.json()
    except ValueError:
        return None, "INVALID_JSON_RESPONSE"
    return value if isinstance(value, dict) else None, None


def _azure_type_probe(
    token: str,
    subscription_id: str,
    region: str,
    namespace: str,
    type_name: str,
) -> dict[str, Any]:
    provider_url = (
        f"https://management.azure.com/subscriptions/{subscription_id}"
        f"/providers/{namespace}?api-version=2021-04-01"
    )
    provider, error = _arm_get(token, provider_url)
    if error or not provider:
        return {
            "control_plane": namespace,
            "resource_type": type_name,
            "status": "not_readable",
            "error_code": error or "EMPTY_RESPONSE",
        }
    resource_type = next(
        (
            item
            for item in provider.get("resourceTypes", [])
            if str(item.get("resourceType", "")).lower() == type_name.lower()
        ),
        None,
    )
    if resource_type is None:
        return {
            "control_plane": namespace,
            "resource_type": type_name,
            "status": "resource_type_not_exposed",
            "registration_state": provider.get("registrationState"),
        }
    locations = [str(value) for value in resource_type.get("locations", [])]
    api_version = _latest_stable_api_version(resource_type)
    output: dict[str, Any] = {
        "control_plane": namespace,
        "resource_type": type_name,
        "status": "readable",
        "registration_state": provider.get("registrationState"),
        "region_supported": _normalize_location(region)
        in {_normalize_location(value) for value in locations},
        "stable_api_version": api_version,
    }
    if api_version:
        collection_url = (
            f"https://management.azure.com/subscriptions/{subscription_id}"
            f"/providers/{namespace}/{type_name}?api-version={api_version}"
        )
        collection, collection_error = _arm_get(token, collection_url)
        if collection_error:
            output["inventory_status"] = "not_readable"
            output["inventory_error_code"] = collection_error
        else:
            output["inventory_status"] = "readable"
            output["existing_resource_count_lower_bound"] = len(
                (collection or {}).get("value", [])
            )
            output["inventory_truncated"] = bool((collection or {}).get("nextLink"))
    return output


def _azure_probe(credentials: dict[str, Any]) -> dict[str, Any]:
    preflight_result = check_azure_credentials(credentials)
    credential = ClientSecretCredential(
        tenant_id=credentials["azure_tenant_id"],
        client_id=credentials["azure_client_id"],
        client_secret=credentials["azure_client_secret"],
    )
    token = credential.get_token("https://management.azure.com/.default").token
    subscription_id = credentials["azure_subscription_id"]
    region = credentials["azure_region"]
    type_results = [
        _azure_type_probe(token, subscription_id, region, namespace, type_name)
        for namespace, type_name in AZURE_CONTROL_PLANES.items()
    ]
    type_results.append(
        _azure_type_probe(
            token,
            subscription_id,
            credentials.get("azure_region_digital_twin") or region,
            *AZURE_ACCESS_TYPES["l4"],
        )
    )

    web_usage_url = (
        f"https://management.azure.com/subscriptions/{subscription_id}"
        f"/providers/Microsoft.Web/locations/{region}/usages?api-version=2025-05-01"
    )
    web_usage, web_error = _arm_get(token, web_usage_url)
    quota_results = []
    for control_plane in AZURE_CONTROL_PLANES:
        if control_plane == "Microsoft.Web":
            quota_results.append(
                {
                    "control_plane": control_plane,
                    "status": "readable" if not web_error else "not_readable",
                    "quota_count": len((web_usage or {}).get("value", [])),
                    **({"error_code": web_error} if web_error else {}),
                }
            )
        else:
            quota_results.append(
                {
                    "control_plane": control_plane,
                    "status": "not_exposed_before_resource_creation",
                    "quota_count": 0,
                }
            )

    graph_ready = any(
        item["code"] == "MICROSOFT_GRAPH_AUTHORITY_READY"
        and item["status"] == "passed"
        for item in _preflight_summary("azure", preflight_result, credentials)["checks"]
    )
    l4 = next(item for item in type_results if item["control_plane"] == "Microsoft.DigitalTwins")
    l5 = next(item for item in type_results if item["control_plane"] == "Microsoft.Dashboard")
    return {
        "preflight": _preflight_summary("azure", preflight_result, credentials),
        "quota": {
            "status": "partial",
            "reason": "four_control_planes_expose_resource_scoped_or_post_creation_usage_only",
            "control_planes": quota_results,
        },
        "regional_capacity": type_results,
        "access_prerequisites": {
            "l4_digital_twins_region": _azure_region_status(l4),
            "l4_microsoft_graph_authority": "passed" if graph_ready else "blocked",
            "l5_managed_grafana_region": _azure_region_status(l5),
            "l4_l5_runtime_role_assignments": "deferred_to_atomic_twin_apply",
        },
    }


def _azure_region_status(item: dict[str, Any]) -> str:
    if item.get("status") != "readable":
        return "blocked"
    return "passed" if item.get("region_supported") else "blocked"


def _gcp_execute(request: Any) -> tuple[dict[str, Any] | None, str | None]:
    try:
        value = request.execute(num_retries=2)
    except Exception as exc:  # google SDK boundary
        return None, _safe_error_code(exc)
    return value if isinstance(value, dict) else {}, None


def _gcp_project_hierarchy(resource_manager: Any, project_id: str) -> dict[str, Any]:
    project, error = _gcp_execute(
        resource_manager.projects().get(name=f"projects/{project_id}")
    )
    if error or not project:
        return {"status": "not_readable", "error_code": error or "EMPTY_RESPONSE"}
    parent = str(project.get("parent") or "")
    visited = set()
    while parent.startswith("folders/") and parent not in visited:
        visited.add(parent)
        folder, folder_error = _gcp_execute(resource_manager.folders().get(name=parent))
        if folder_error or not folder:
            return {
                "status": "partial",
                "organization_ancestor": "unknown",
                "error_code": folder_error or "EMPTY_RESPONSE",
            }
        parent = str(folder.get("parent") or "")
    return {
        "status": "readable",
        "organization_ancestor": parent.startswith("organizations/"),
        "project_state": project.get("state"),
    }


def _gcp_quota_probe(
    service_usage: Any,
    project_number: str,
    service: str,
    *,
    region: str,
    zone: str,
) -> dict[str, Any]:
    metrics: list[dict[str, Any]] = []
    page_token: str | None = None
    while True:
        request = service_usage.services().consumerQuotaMetrics().list(
            parent=f"projects/{project_number}/services/{service}",
            view="FULL",
            pageSize=200,
            **({"pageToken": page_token} if page_token else {}),
        )
        page, error = _gcp_execute(request)
        if error:
            return {
                "control_plane": service,
                "status": "not_readable",
                "error_code": error,
                "metric_count": len(metrics),
                "limit_count": sum(len(item.get("consumerQuotaLimits", [])) for item in metrics),
                "relevant_limits": [],
            }
        metrics.extend((page or {}).get("metrics", []))
        page_token = str((page or {}).get("nextPageToken") or "") or None
        if not page_token:
            break
    relevant = []
    for metric in metrics:
        if metric.get("metric") not in GCP_QUOTA_METRICS[service]:
            continue
        for limit in metric.get("consumerQuotaLimits", []):
            effective = [
                {
                    "dimensions": bucket.get("dimensions", {}),
                    "effective_limit": bucket.get("effectiveLimit"),
                }
                for bucket in limit.get("quotaBuckets", [])
                if bucket.get("effectiveLimit") is not None
                and (
                    not bucket.get("dimensions")
                    or region in bucket.get("dimensions", {}).values()
                    or zone in bucket.get("dimensions", {}).values()
                )
            ]
            relevant.append(
                {
                    "metric": str(metric.get("metric", "")),
                    "limit": str(limit.get("name", "")).rsplit("/", 1)[-1],
                    "unit": str(limit.get("unit", "")),
                    "effective_limits": effective,
                }
            )
    return {
        "control_plane": service,
        "status": "readable",
        "metric_count": len(metrics),
        "limit_count": sum(len(item.get("consumerQuotaLimits", [])) for item in metrics),
        "relevant_limits": relevant,
    }


def _gcp_effective_limit(
    quota_results: list[dict[str, Any]],
    metric_name: str,
    *,
    dimension_value: str | None = None,
) -> float | None:
    candidates: list[tuple[int, float]] = []
    for result in quota_results:
        for item in result.get("relevant_limits", []):
            if item.get("metric") != metric_name:
                continue
            for bucket in item.get("effective_limits", []):
                dimensions = bucket.get("dimensions") or {}
                raw = bucket.get("effective_limit")
                try:
                    value = float(raw)
                except (TypeError, ValueError):
                    continue
                if value < 0:
                    continue
                if dimension_value and dimension_value in dimensions.values():
                    candidates.append((2, value))
                elif not dimensions:
                    candidates.append((1, value))
    return max(candidates, default=(0, 0.0))[1] if candidates else None


def _minimum_status(limit: float | None, required: float, usage: float = 0) -> str:
    if limit is None:
        return "unknown"
    try:
        remaining = float(limit) - float(usage)
    except (TypeError, ValueError):
        return "unknown"
    return "passed" if remaining >= required else "blocked"


def _gcp_probe(credentials: dict[str, Any]) -> dict[str, Any]:
    preflight_result = check_gcp_credentials(credentials)
    gcp_credentials = service_account.Credentials.from_service_account_file(
        credentials["gcp_credentials_file"],
        scopes=[
            # Several provider GET/LIST endpoints do not accept the generic
            # read-only OAuth scope. The script still exposes only the fixed
            # read operation set above and never constructs a mutation call.
            "https://www.googleapis.com/auth/cloud-platform",
        ],
    )
    project_id = credentials["gcp_project_id"]
    region = credentials["gcp_region"]
    zone = f"{region}-b"
    resource_manager = build_google_api(
        "cloudresourcemanager", "v3", credentials=gcp_credentials, cache_discovery=False
    )
    hierarchy = _gcp_project_hierarchy(resource_manager, project_id)
    project, project_error = _gcp_execute(
        resource_manager.projects().get(name=f"projects/{project_id}")
    )
    project_number = str((project or {}).get("name", "")).rsplit("/", 1)[-1]

    quota_results = []
    if project_error or not project_number:
        quota_results = [
            {
                "control_plane": service,
                "status": "not_readable",
                "error_code": project_error or "PROJECT_NUMBER_UNAVAILABLE",
                "metric_count": 0,
                "limit_count": 0,
                "relevant_limits": [],
            }
            for service in GCP_QUOTA_SERVICES
        ]
    else:
        service_usage = build_google_api(
            "serviceusage", "v1beta1", credentials=gcp_credentials, cache_discovery=False
        )
        quota_results = [
            _gcp_quota_probe(
                service_usage,
                project_number,
                service,
                region=region,
                zone=zone,
            )
            for service in GCP_QUOTA_SERVICES
        ]

    compute = build_google_api(
        "compute", "v1", credentials=gcp_credentials, cache_discovery=False
    )
    machine_types = []
    for machine_type in ("e2-standard-2", "e2-standard-4"):
        _, error = _gcp_execute(
            compute.machineTypes().get(
                project=project_id,
                zone=zone,
                machineType=machine_type,
            )
        )
        machine_types.append(
            {
                "machine_type": machine_type,
                "zone": "configured_region_b",
                "status": "available" if not error else "not_available",
                **({"error_code": error} if error else {}),
            }
        )
    region_info, region_error = _gcp_execute(
        compute.regions().get(project=project_id, region=region)
    )
    regional_quota = []
    if region_info:
        for item in region_info.get("quotas", []):
            metric = str(item.get("metric", ""))
            if metric in {"CPUS", "E2_CPUS", "IN_USE_ADDRESSES", "DISKS_TOTAL_GB", "SSD_TOTAL_GB"}:
                regional_quota.append(
                    {
                        "metric": metric,
                        "limit": item.get("limit"),
                        "usage": item.get("usage"),
                    }
                )

    container = build_google_api(
        "container", "v1", credentials=gcp_credentials, cache_discovery=False
    )
    _, gke_error = _gcp_execute(
        container.projects().locations().getServerConfig(
            name=f"projects/{project_id}/locations/{zone}"
        )
    )
    cluster_inventory, cluster_error = _gcp_execute(
        container.projects().locations().clusters().list(
            parent=f"projects/{project_id}/locations/{zone}"
        )
    )
    firestore = build_google_api(
        "firestore", "v1", credentials=gcp_credentials, cache_discovery=False
    )
    database_inventory, database_error = _gcp_execute(
        firestore.projects().databases().list(parent=f"projects/{project_id}")
    )
    cloud_run = build_google_api(
        "run", "v2", credentials=gcp_credentials, cache_discovery=False
    )
    service_inventory, service_error = _gcp_execute(
        cloud_run.projects().locations().services().list(
            parent=f"projects/{project_id}/locations/{region}"
        )
    )

    regional_by_metric = {
        str(item.get("metric")): item for item in regional_quota
    }
    cpu = regional_by_metric.get("E2_CPUS") or regional_by_metric.get("CPUS") or {}
    disk = regional_by_metric.get("DISKS_TOTAL_GB") or {}
    address = regional_by_metric.get("IN_USE_ADDRESSES") or {}
    existing_clusters = len((cluster_inventory or {}).get("clusters", []))
    existing_databases = len((database_inventory or {}).get("databases", []))
    small_requirements = {
        "gke_e2_vcpu": {
            "minimum_required": 10,
            "status": _minimum_status(cpu.get("limit"), 10, cpu.get("usage", 0)),
        },
        "persistent_disk_gib": {
            "minimum_required": 130,
            "status": _minimum_status(disk.get("limit"), 130, disk.get("usage", 0)),
        },
        "regional_in_use_addresses": {
            "minimum_required": 1,
            "status": _minimum_status(address.get("limit"), 1, address.get("usage", 0)),
        },
        "zonal_gke_clusters": {
            "minimum_required": 1,
            "status": _minimum_status(
                _gcp_effective_limit(
                    quota_results,
                    "container.googleapis.com/clusters_per_zone",
                    dimension_value=zone,
                ),
                1,
                existing_clusters,
            ),
        },
        "firestore_databases": {
            "minimum_required": 1,
            "status": _minimum_status(
                _gcp_effective_limit(
                    quota_results,
                    "firestore.googleapis.com/databases",
                ),
                1,
                existing_databases,
            ),
        },
        "cloud_run_max_instances": {
            "minimum_required": 21,
            "status": _minimum_status(
                _gcp_effective_limit(
                    quota_results,
                    "run.googleapis.com/instances",
                    dimension_value=region,
                ),
                21,
            ),
        },
    }
    iap_status: dict[str, Any]
    if hierarchy.get("organization_ancestor") is True:
        iap_status = {
            "status": "conditional",
            "mode": "google_managed_oauth",
            "condition": "platform_user_must_belong_to_project_organization",
        }
    elif hierarchy.get("organization_ancestor") is False:
        iap_status = {
            "status": "blocked",
            "mode": "custom_oauth_required_for_project_without_organization",
            "condition": "manual_console_configuration_and_review_required",
        }
    else:
        iap_status = {
            "status": "unknown",
            "mode": "project_hierarchy_not_confirmed",
            "condition": "resolve_project_organization_before_apply",
        }

    return {
        "preflight": _preflight_summary("gcp", preflight_result, credentials),
        "quota": {
            "status": "passed" if all(item["status"] == "readable" for item in quota_results) else "blocked",
            "control_planes": quota_results,
        },
        "regional_capacity": {
            "machine_types": machine_types,
            "regional_compute_quota_status": "readable" if not region_error else "not_readable",
            "regional_compute_quota": regional_quota,
            **({"regional_compute_error_code": region_error} if region_error else {}),
            "gke_server_config_status": "readable" if not gke_error else "not_readable",
            **({"gke_error_code": gke_error} if gke_error else {}),
            "inventory": {
                "gke_clusters": {
                    "status": "readable" if not cluster_error else "not_readable",
                    "existing_resource_count_lower_bound": existing_clusters,
                    **({"error_code": cluster_error} if cluster_error else {}),
                },
                "firestore_databases": {
                    "status": "readable" if not database_error else "not_readable",
                    "existing_resource_count_lower_bound": existing_databases,
                    **({"error_code": database_error} if database_error else {}),
                },
                "cloud_run_services": {
                    "status": "readable" if not service_error else "not_readable",
                    "existing_resource_count_lower_bound": len(
                        (service_inventory or {}).get("services", [])
                    ),
                    "truncated": bool((service_inventory or {}).get("nextPageToken")),
                    **({"error_code": service_error} if service_error else {}),
                },
            },
            "small_requirement_evaluation": small_requirements,
        },
        "access_prerequisites": {
            "l4_iap": iap_status,
            "l5_grafana_access": {
                "status": "deferred_to_atomic_twin_apply",
                "mode": "cidr_restricted_gke_and_one_time_viewer_credential",
            },
        },
        "project_hierarchy": hierarchy,
    }


def build_record(
    credentials_path: Path,
    gcp_credentials_path: Path,
    *,
    now: Callable[[], datetime] | None = None,
) -> dict[str, Any]:
    raw = json.loads(credentials_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("Credential configuration must be a JSON object")
    credentials = {
        "aws": dict(raw["aws"]),
        "azure": dict(raw["azure"]),
        "gcp": dict(raw["gcp"]),
    }
    credentials["gcp"]["gcp_credentials_file"] = str(gcp_credentials_path)
    timestamp = (now or (lambda: datetime.now(timezone.utc)))()
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    record: dict[str, Any] = {
        "schema_version": "six-layer-phase8-readonly-readiness.v1",
        "checked_at": timestamp.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
        "mode": SAFE_MODE,
        "mutation_methods_allowed": [],
        "mutations_performed": False,
        "credential_values_included": False,
        "provider_scope_values_included": False,
        "providers": {
            "aws": _aws_probe(credentials["aws"]),
            "azure": _azure_probe(credentials["azure"]),
            "gcp": _gcp_probe(credentials["gcp"]),
        },
    }
    _assert_sensitive_values_absent(record, credentials)
    record["record_digest"] = _digest(record)
    return record


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--credentials", type=Path, required=True)
    parser.add_argument("--gcp-credentials", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(f"Output already exists: {args.output}")
    record = build_record(args.credentials.resolve(), args.gcp_credentials.resolve())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        "Phase 8 read-only readiness probe complete "
        f"({record['record_digest']}); no mutation methods were enabled"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
