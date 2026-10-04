"""Actual Azure IoT device receipt, with the existing Core lifecycle/cleanup."""
import time

from scripts import core_live_azure as core
from scripts.core_command_receipt import DEVICE, configure, exercise, query, confirm_history

inventory = core.inventory
stop_builds = core.stop_builds
diagnostics = core.diagnostics


def smoke(values, outputs):
    from src.iot_device_simulator.azure import transmission
    started = time.monotonic()
    hostname, key = core.register_simulator(values, outputs)
    registration_seconds = time.monotonic() - started
    config = {"device_id": DEVICE, "connection_string":
              f"HostName={hostname};DeviceId={DEVICE};SharedAccessKey={key}"}
    now, result = exercise(transmission, config, values)
    result.update(scope="local_azure_simulator_command_and_l3", device_registration_seconds=registration_seconds)
    group = outputs["azure_six_layer_resource_group_name"]
    base = f"/subscriptions/{values['azure_subscription_id']}/resourceGroups/{group}"
    resources = core.arm(values, "GET", base + "/resources?api-version=2021-04-01")["value"]
    access = outputs["azure_component_storage_read_access_output"]
    reader_id = next(r["id"] for r in resources if r["name"] == access["reader_function_name"])
    keys = core.arm(values, "POST", reader_id + "/host/default/listkeys?api-version=2024-04-01")
    reader_key = keys.get("functionKeys", {}).get("default") or keys["masterKey"]
    def read():
        response = core.requests.get(access["access_url"], headers={"x-functions-key": reader_key},
                                     params=query(now), timeout=30)
        if response.status_code in (401, 403):
            raise RuntimeError("COMMAND_READER_UNAUTHORIZED")
        return response.json().get("points", []) if response.status_code == 200 else []
    return confirm_history(read, now, result)


# The device is a child of this run's fresh IoT Hub. Terraform removes the hub,
# and the existing independent resource-group inventory verifies its absence.
__all__ = ["configure", "inventory", "stop_builds", "diagnostics", "smoke"]
