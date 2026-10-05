"""Actual authenticated GCP MQTT simulator receipt; no extra cloud resources."""
from pathlib import Path
import json
from types import SimpleNamespace
from urllib.parse import urlparse

from src.core.secure_files import atomic_write_private_bytes
from scripts import core_live_gcp as core
from scripts.core_command_receipt import DEVICE, configure, exercise, query, confirm_history

inventory = core.inventory
stop_builds = core.stop_builds
diagnostics = core.diagnostics


def preflight():
    """Construct the actual simulator client offline before any cloud work."""
    from src.iot_device_simulator.google import transmission
    transmission._client({"device_id": "offline-preflight", "username": "offline",
                          "password": "offline", "server_ca_path": None}, suffix="preflight")


def smoke(values, outputs):
    from src.iot_device_simulator.google import transmission
    endpoint = urlparse(outputs["gcp_six_layer_mqtt_endpoint"])
    auth = outputs["gcp_six_layer_mqtt_device_credentials"]
    ca = Path(values["project_path"]) / "mqtt-server-ca.pem"
    atomic_write_private_bytes(ca, outputs["gcp_six_layer_mqtt_server_certificate"].encode())
    config = SimpleNamespace(endpoint=endpoint.hostname, port=endpoint.port or 8883,
        device_id=DEVICE, username=auth["username"], password=auth["password"],
        telemetry_topic=f"devices/{DEVICE}/telemetry", command_topic=f"devices/{DEVICE}/commands",
        server_ca_path=str(ca), payload_path="", digital_twin_name=values["digital_twin_name"])
    now, result = exercise(transmission, config, values)
    result["scope"] = "local_gcp_simulator_command_and_l3"
    access = outputs["gcp_component_storage_read_access_output"]["access_url"]
    token = core.service_account.IDTokenCredentials.from_service_account_info(
        json.loads(values["gcp_credentials_json"]), target_audience=access.split("/raw-history/")[0])
    token.refresh(core.Request())
    def read():
        response = core.requests.get(access, headers={"Authorization": "Bearer " + token.token},
                                     params=query(now), timeout=30)
        if response.status_code in (401, 403):
            raise RuntimeError("COMMAND_READER_UNAUTHORIZED")
        return response.json().get("points", []) if response.status_code == 200 else []
    return confirm_history(read, now, result)


__all__ = ["configure", "inventory", "stop_builds", "diagnostics", "smoke"]
