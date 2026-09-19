"""Small Azure Core verification through IoT Hub and authenticated L3 HTTP."""
import base64
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import json
import os
import time
from urllib.parse import quote

from azure.identity import ClientSecretCredential
import requests


def credential(values):
    return ClientSecretCredential(tenant_id=values["azure_tenant_id"],
                                  client_id=values["azure_client_id"],
                                  client_secret=values["azure_client_secret"])


def arm(values, method, path, *, body=None, allowed=(200,)):
    token = credential(values).get_token("https://management.azure.com/.default").token
    response = requests.request(method, "https://management.azure.com" + path,
                                headers={"Authorization": "Bearer " + token},
                                json=body, timeout=45)
    if response.status_code not in allowed:
        raise RuntimeError("CORE_AZURE_ARM_HTTP_" + str(response.status_code))
    return response.json() if response.content else {}


def groups(values):
    path = f"/subscriptions/{values['azure_subscription_id']}/resourcegroups?api-version=2021-04-01"
    found = []
    while path:
        result = arm(values, "GET", path)
        found.extend(result.get("value", []))
        path = result.get("nextLink", "").replace("https://management.azure.com", "")
    return found


def inventory(values, prefix):
    # Every Core resource is in the newly created, deployment-owned group.
    matches = [g for g in groups(values) if g["name"].startswith(prefix + "-")]
    return {"resource_groups": len(matches)}


def stop_builds(values, outputs):
    registry = outputs.get("azure_six_layer_acr_name")
    group = outputs.get("azure_six_layer_resource_group_name")
    if not registry or not group:
        return
    path = (f"/subscriptions/{values['azure_subscription_id']}/resourceGroups/{group}"
            f"/providers/Microsoft.ContainerRegistry/registries/{registry}")
    runs = arm(values, "GET", path + "/runs?api-version=2019-06-01-preview")
    for run in runs.get("value", []):
        if run.get("properties", {}).get("status") in ("Queued", "Started", "Running"):
            arm(values, "POST", path + f"/runs/{run['name']}/cancel?api-version=2019-06-01-preview",
                allowed=(200, 202, 204))


def sas(resource, key, name=None):
    expiry = str(int(time.time()) + 600)
    encoded = quote(resource, safe="")
    signature = base64.b64encode(hmac.new(base64.b64decode(key),
                                        (encoded + "\n" + expiry).encode(), hashlib.sha256).digest())
    result = "SharedAccessSignature sr=" + encoded + "&sig=" + quote(signature, safe="") + "&se=" + expiry
    return result + ("&skn=" + name if name else "")


def poll_points(read, key, query, attempts=60, pause_seconds=3, observation=None):
    started = time.monotonic()
    timeout_count = 0
    for attempt in range(1, attempts + 1):
        try:
            response = requests.get(
                read["access_url"],
                headers={"x-functions-key": key},
                params=query,
                timeout=30,
            )
        except requests.Timeout:
            response = None
            timeout_count += 1
        current = {
            "attempts": attempt,
            "timeout_count": timeout_count,
            "wait_seconds": round(time.monotonic() - started, 3),
        }
        if observation is not None:
            observation.update(current)
        if response is not None and response.status_code == 200:
            points = response.json().get("points", [])
            if len(points) == 10:
                return points
        time.sleep(pause_seconds)
    error = RuntimeError("CORE_READBACK_TIMEOUT")
    error.safe_metrics = {
        "readback_poll_attempts": attempts,
        "readback_timeout_count": timeout_count,
        "readback_wait_seconds": round(time.monotonic() - started, 3),
    }
    raise error


def smoke(values, outputs):
    group = outputs["azure_six_layer_resource_group_name"]
    base = f"/subscriptions/{values['azure_subscription_id']}/resourceGroups/{group}"
    resources = arm(values, "GET", base + "/resources?api-version=2021-04-01")["value"]
    hub = next(r for r in resources if r["type"].lower() == "microsoft.devices/iothubs")
    hub_data = arm(values, "GET", hub["id"] + "?api-version=2023-06-30")
    hostname = hub_data["properties"]["hostName"]
    keys = arm(values, "POST", hub["id"] + "/listkeys?api-version=2023-06-30")["value"]
    owner = next(key for key in keys if key["keyName"] == "iothubowner")
    device = "core-sensor"
    resource = hostname + "/devices/" + device
    device_key = base64.b64encode(os.urandom(32)).decode()
    response = requests.put("https://" + resource + "?api-version=2021-04-12",
                            headers={"Authorization": sas(hostname, owner["primaryKey"], "iothubowner")},
                            json={"deviceId": device, "status": "enabled",
                                  "authentication": {"type": "sas", "symmetricKey": {
                                      "primaryKey": device_key,
                                      "secondaryKey": base64.b64encode(os.urandom(32)).decode()}}}, timeout=30)
    if response.status_code not in (200, 201):
        raise RuntimeError("CORE_AZURE_DEVICE_HTTP_" + str(response.status_code))
    read = outputs["azure_component_storage_read_access_output"]
    reader_id = next(r["id"] for r in resources if r["name"] == read["reader_function_name"])
    read_keys = arm(values, "POST", reader_id + "/host/default/listkeys?api-version=2024-04-01")
    key = read_keys.get("functionKeys", {}).get("default") or read_keys["masterKey"]
    now = datetime.now(timezone.utc)
    started = time.monotonic()
    for number in range(10):
        payload = {"event_id": f"{values['digital_twin_name']}-{number}", "source_id": device,
                   "source_sequence": str(number), "correlation_id": f"{values['digital_twin_name']}-{number}",
                   "payload": {"device_id": device, "metric": "temperature", "value": number,
                               "event_time": (now + timedelta(milliseconds=number)).isoformat()}}
        payload.update(payload.pop("payload"))
        payload["source_sequence"] = "TRACE-" + values["digital_twin_name"].replace("-", "").upper() + str(number)
        sent = requests.post("https://" + resource + "/messages/events?api-version=2021-04-12",
                             headers={"Authorization": sas(resource, device_key),
                                      "Content-Type": "application/json", "iothub-contenttype": "application/json",
                                      "iothub-contentencoding": "utf-8"}, data=json.dumps(payload), timeout=30)
        if sent.status_code != 204:
            raise RuntimeError("CORE_AZURE_SEND_HTTP_" + str(sent.status_code))
    query = {"device_id": device, "metric": "temperature", "bucket_seconds": "0", "limit": "100",
             "from": (now - timedelta(minutes=1)).isoformat(), "to": (now + timedelta(minutes=10)).isoformat()}
    readback = {}
    points = poll_points(read, key, query, observation=readback)
    assert sorted(float(p["value"]) for p in points) == list(range(10))
    return {"sent": 10, "read_back": 10, "delivery_seconds": time.monotonic() - started,
            "readback_poll_attempts": readback["attempts"],
            "readback_timeout_count": readback["timeout_count"],
            "readback_wait_seconds": readback["wait_seconds"],
            "message_persistence_latency_ms": [round((datetime.fromisoformat(p["stored_at"].replace("Z", "+00:00")) -
                datetime.fromisoformat(p["event_time"].replace("Z", "+00:00"))).total_seconds() * 1000, 3) for p in points]}


def diagnostics(values, outputs):
    group = outputs.get("azure_six_layer_resource_group_name")
    if not group:
        return {}
    base = f"/subscriptions/{values['azure_subscription_id']}/resourceGroups/{group}"
    resources = arm(values, "GET", base + "/resources?api-version=2021-04-01")["value"]
    workspaces = [r for r in resources if r["type"].lower() == "microsoft.operationalinsights/workspaces"]
    if not workspaces:
        return {}
    token = credential(values).get_token("https://api.loganalytics.io/.default").token
    result = []
    # Container Apps and Functions use separate workspaces; the first can be
    # empty even while the Function hosts report the cause of a failed run.
    for workspace in workspaces:
        identifier = arm(values, "GET", workspace["id"] + "?api-version=2022-10-01")["properties"]["customerId"]
        response = requests.post(f"https://api.loganalytics.io/v1/workspaces/{identifier}/query",
                                 headers={"Authorization": "Bearer " + token},
                                 json={"query": "union isfuzzy=true FunctionAppLogs, AzureDiagnostics | take 1000",
                                       "timespan": "PT30M"}, timeout=20)
        result.append({"status": response.status_code, "data": response.json()})
    return {"workspaces": result}
