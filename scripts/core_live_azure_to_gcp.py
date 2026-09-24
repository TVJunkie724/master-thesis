"""Fixed Azure-ingress/GCP-Core telemetry smoke and two-cloud cleanup checks."""

import json
import time

import requests

from scripts import core_live_azure as azure, core_live_gcp as gcp
from scripts.prepare_core_evaluation import materialize
from src.core.secure_files import atomic_write_private_bytes
from src.providers.terraform.package_builders.azure_six_layer import build_azure_six_layer_graph_apps


# Azure is ingress only: its Functions use ZIP packages, not an ACR image.
image_providers = ("gcp",)


def configure(values, runtime):
    values.update(materialize("core-small-azure-to-gcp")["tfvars"])
    build_azure_six_layer_graph_apps(runtime, ("six-layer-domain", "six-layer-eventing"))
    atomic_write_private_bytes(runtime / "runtime.tfvars.json", json.dumps(values).encode())


def readiness(_values):
    # Terraform creates only run-owned, directional trust; no shared account setup.
    return {}


def inventory(values, prefix):
    result = {"azure:" + key: count for key, count in azure.inventory(values, prefix).items()}
    result.update({("pending_deletion:gcp:" + key.split(":", 1)[1]
                    if key.startswith("pending_deletion:") else "gcp:" + key): count
                   for key, count in gcp.inventory(values, prefix).items()})
    token = azure.credential(values).get_token("https://graph.microsoft.com/.default").token
    for kind in ("applications", "servicePrincipals"):
        url = "https://graph.microsoft.com/v1.0/" + kind
        params = {"$filter": f"startswith(displayName,'{prefix} ')", "$select": "id"}
        count = 0
        while url:
            response = requests.get(url, params=params,
                                    headers={"Authorization": "Bearer " + token}, timeout=30)
            if response.status_code != 200:
                raise RuntimeError("CORE_ENTRA_INVENTORY_HTTP_" + str(response.status_code))
            data = response.json()
            count += len(data.get("value", []))
            url, params = data.get("@odata.nextLink"), None
        result["entra:" + kind] = count
    pool_id = prefix[:14] + "-azure-bridge"
    pool_url = ("https://iam.googleapis.com/v1/projects/" + values["gcp_project_id"]
                + "/locations/global/workloadIdentityPools/" + pool_id)
    response = gcp.client(values).get(pool_url, timeout=45)
    if response.status_code == 404:
        result["gcp:workload_identity_pools"] = 0
    elif response.status_code == 200:
        deleted = response.json().get("state") == "DELETED"
        result["gcp:workload_identity_pools"] = 0 if deleted else 1
        if deleted:
            result["pending_deletion:gcp:workload_identity_pools"] = 1
    else:
        raise RuntimeError("CORE_GCP_POOL_INVENTORY_HTTP_" + str(response.status_code))
    return result


def smoke(values, outputs):
    source = source_functions_ready(values, outputs)
    now, started = azure.send_telemetry(values, outputs)
    return {**gcp.readback(values, outputs, now, started),
            **source, "source_provider": "azure", "destination_provider": "gcp"}


def source_functions_ready(values, outputs, attempts=18, pause_seconds=5):
    """Wait only for the two expected source triggers to be indexed by Azure."""
    group = outputs["azure_six_layer_resource_group_name"]
    base = f"/subscriptions/{values['azure_subscription_id']}/resourceGroups/{group}"
    resources = azure.arm(values, "GET", base + "/resources?api-version=2021-04-01")["value"]
    sites = [resource for resource in resources
             if resource["type"].lower() == "microsoft.web/sites"]
    if len(sites) != 1:
        raise RuntimeError("CORE_AZURE_SOURCE_FUNCTION_APP_MISSING")
    expected = {"six-layer-iot-telemetry-adapter", "six-layer-cross-cloud-telemetry-bridge"}
    for attempt in range(1, attempts + 1):
        result = azure.arm(values, "GET", sites[0]["id"] + "/functions?api-version=2023-12-01",
                           allowed=(200, 404, 503))
        found = {str(item.get("name", "")).split("/")[-1]
                 for item in result.get("value", [])} if "value" in result else set()
        if expected <= found:
            return {"azure_source_function_readiness_attempts": attempt}
        if attempt < attempts:
            time.sleep(pause_seconds)
    raise RuntimeError("CORE_AZURE_SOURCE_FUNCTIONS_NOT_READY")


def stop_builds(values, outputs):
    azure.stop_builds(values, outputs)
    gcp.stop_builds(values, outputs)


def diagnostics(values, outputs):
    return {"azure": azure.diagnostics(values, outputs), "gcp": gcp.diagnostics(values, outputs)}
