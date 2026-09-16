"""GCP Core: TLS MQTT ingress, Google-authenticated readback and residual checks."""
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import ssl
import time
from urllib.parse import urlparse

from google.auth.transport.requests import AuthorizedSession, Request
from google.oauth2 import service_account
import paho.mqtt.client as mqtt
import requests
from src.core.secure_files import atomic_write_private_bytes

_compute_baseline = {}


def client(values):
    info = json.loads(values["gcp_credentials_json"])
    return AuthorizedSession(service_account.Credentials.from_service_account_info(
        info, scopes=["https://www.googleapis.com/auth/cloud-platform"]))


def get(session, url, **params):
    response = session.get(url, params=params, timeout=45)
    if response.status_code != 200:
        raise RuntimeError("CORE_GCP_INVENTORY_HTTP_" + str(response.status_code))
    return response.json()


def pages(session, url, key, **params):
    result = []
    while True:
        data = get(session, url, **params)
        result.extend(data.get(key, []))
        token = data.get("nextPageToken")
        if not token:
            return result
        params["pageToken"] = token


def inventory(values, prefix):
    session = client(values)
    project, region = values["gcp_project_id"], values["gcp_region"]
    parent = f"projects/{project}/locations/{region}"
    result = {}
    for label, url, key in (
        ("clusters", f"https://container.googleapis.com/v1/projects/{project}/locations/-/clusters", "clusters"),
        ("services", f"https://run.googleapis.com/v2/{parent}/services", "services"),
        ("jobs", f"https://run.googleapis.com/v2/{parent}/jobs", "jobs"),
        ("scheduler", f"https://cloudscheduler.googleapis.com/v1/{parent}/jobs", "jobs"),
        ("workflows", f"https://workflows.googleapis.com/v1/{parent}/workflows", "workflows"),
        ("topics", f"https://pubsub.googleapis.com/v1/projects/{project}/topics", "topics"),
        ("subscriptions", f"https://pubsub.googleapis.com/v1/projects/{project}/subscriptions", "subscriptions"),
        ("repositories", f"https://artifactregistry.googleapis.com/v1/{parent}/repositories", "repositories"),
        ("databases", f"https://firestore.googleapis.com/v1/projects/{project}/databases", "databases"),
        ("service_accounts", f"https://iam.googleapis.com/v1/projects/{project}/serviceAccounts", "accounts"),
        ("log_sinks", f"https://logging.googleapis.com/v2/projects/{project}/sinks", "sinks"),
    ):
        items = pages(session, url, key)
        result[label] = sum(prefix in str(item.get("name", "")) or prefix in str(item.get("email", "")) for item in items)
    result["buckets"] = sum(prefix in item["name"] for item in pages(
        session, "https://storage.googleapis.com/storage/v1/b", "items", project=project))
    policy = session.post(f"https://cloudresourcemanager.googleapis.com/v1/projects/{project}:getIamPolicy",
                          json={}, timeout=45)
    policy.raise_for_status()
    result["project_iam_bindings"] = sum(prefix in member for binding in policy.json().get("bindings", [])
                                          for member in binding.get("members", []))
    # GKE-generated names need baseline comparison, not just the deployment prefix.
    compute = set()
    for kind in ("instances", "disks", "addresses", "forwardingRules", "backendServices",
                 "targetPools", "instanceGroups", "instanceGroupManagers"):
        data = get(session, f"https://compute.googleapis.com/compute/v1/projects/{project}/aggregated/{kind}")
        while True:
            for scope in data.get("items", {}).values():
                compute.update(item["selfLink"] for item in scope.get(kind, []))
            if not data.get("nextPageToken"):
                break
            data = get(session, f"https://compute.googleapis.com/compute/v1/projects/{project}/aggregated/{kind}",
                       pageToken=data["nextPageToken"])
    for kind in ("firewalls", "healthChecks", "httpHealthChecks", "httpsHealthChecks"):
        compute.update(item["selfLink"] for item in pages(session,
            f"https://compute.googleapis.com/compute/v1/projects/{project}/global/{kind}", "items"))
    if prefix not in _compute_baseline:
        snapshot = Path(values["project_path"]) / "compute-baseline.json" if values.get("project_path") else None
        if snapshot and snapshot.exists():
            _compute_baseline[prefix] = set(json.loads(snapshot.read_text()))
            result["compute_children"] = len(compute - _compute_baseline[prefix])
        else:
            _compute_baseline[prefix] = compute
            if snapshot:
                atomic_write_private_bytes(snapshot, json.dumps(sorted(compute)).encode())
            result["compute_children"] = sum(prefix in item for item in compute)
    else:
        result["compute_children"] = len(compute - _compute_baseline[prefix])
    return result


def stop_builds(values, outputs):
    session = client(values)
    project, region = values["gcp_project_id"], values["gcp_region"]
    parent = f"projects/{project}/locations/{region}"
    builds = pages(session, f"https://cloudbuild.googleapis.com/v1/{parent}/builds", "builds")
    for build in builds:
        source = build.get("source", {}).get("storageSource", {}).get("bucket")
        if source == outputs.get("gcp_six_layer_build_source_bucket") and build.get("status") in ("QUEUED", "WORKING"):
            response = session.post(f"https://cloudbuild.googleapis.com/v1/{parent}/builds/{build['id']}:cancel",
                                    json={}, timeout=45)
            response.raise_for_status()


def diagnostics(values, outputs):
    session = client(values)
    response = session.post("https://logging.googleapis.com/v2/entries:list", json={
        "resourceNames": ["projects/" + values["gcp_project_id"]],
        "filter": 'resource.type="cloud_run_revision" AND resource.labels.service_name:"' + values["digital_twin_name"] + '"',
        "orderBy": "timestamp desc", "pageSize": 1000}, timeout=45)
    response.raise_for_status()
    return response.json()


def smoke(values, outputs):
    endpoint = urlparse(outputs["gcp_six_layer_mqtt_endpoint"])
    auth = outputs["gcp_six_layer_mqtt_device_credentials"]
    context = ssl.create_default_context(cadata=outputs["gcp_six_layer_mqtt_server_certificate"])
    connection = mqtt.Client(client_id="core-smoke")
    connection.username_pw_set(auth["username"], auth["password"])
    connection.tls_set_context(context)
    connected = []
    connection.on_connect = lambda c, u, f, code: connected.append(code)
    connection.connect(endpoint.hostname, endpoint.port, 60)
    connection.loop_start()
    now = datetime.now(timezone.utc)
    started = time.monotonic()
    try:
        for _ in range(50):
            if connected:
                break
            time.sleep(0.2)
        if connected != [0]:
            raise RuntimeError("CORE_MQTT_AUTH_FAILED")
        for number in range(10):
            payload = {"event_id": f"{values['digital_twin_name']}-{number}", "source_id": "core-sensor",
                       "source_sequence": str(number), "correlation_id": f"{values['digital_twin_name']}-{number}",
                       "payload": {"device_id": "core-sensor", "metric": "temperature", "value": number,
                                   "event_time": (now + timedelta(milliseconds=number)).isoformat()}}
            payload.update(payload.pop("payload"))
            payload["source_sequence"] = "TRACE-" + values["digital_twin_name"].replace("-", "").upper() + str(number)
            published = connection.publish("devices/core-sensor/telemetry", json.dumps(payload), qos=1)
            published.wait_for_publish(timeout=10)
            if not published.is_published():
                raise RuntimeError("CORE_MQTT_PUBLISH_TIMEOUT")
    finally:
        connection.disconnect()
        connection.loop_stop()
    read = outputs["gcp_component_storage_read_access_output"]["access_url"]
    audience = read.split("/raw-history/")[0]
    token = service_account.IDTokenCredentials.from_service_account_info(
        json.loads(values["gcp_credentials_json"]), target_audience=audience)
    token.refresh(Request())
    query = {"device_id": "core-sensor", "metric": "temperature", "bucket_seconds": "0", "limit": "100",
             "from": (now - timedelta(minutes=1)).isoformat(), "to": (now + timedelta(minutes=10)).isoformat()}
    for _ in range(60):
        response = requests.get(read, headers={"Authorization": "Bearer " + token.token}, params=query, timeout=30)
        if response.status_code == 200:
            points = response.json().get("points", [])
            if len(points) == 10:
                assert sorted(float(p["value"]) for p in points) == list(range(10))
                return {"sent": 10, "read_back": 10, "delivery_seconds": time.monotonic() - started,
                        "message_persistence_latency_ms": [round((datetime.fromisoformat(p["stored_at"].replace("Z", "+00:00")) -
                            datetime.fromisoformat(p["event_time"].replace("Z", "+00:00"))).total_seconds() * 1000, 3) for p in points]}
        time.sleep(3)
    raise RuntimeError("CORE_READBACK_TIMEOUT")
