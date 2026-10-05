"""Actual Azure IoT device receipt, with the existing Core lifecycle/cleanup."""
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import time
from urllib.parse import urlencode

from scripts import core_live_azure as core
from scripts.core_command_receipt import DEVICE, configure, exercise, query, confirm_history
from scripts.run_core_evaluation import save

inventory = core.inventory
stop_builds = core.stop_builds

EXPECTED_FUNCTIONS = {
    "events": {"six-layer-iot-telemetry-adapter", "six-layer-eventing-domain-delivery"},
    "process": {"six-layer-eventing-domain-delivery"},
    "extension": {"main"},
    "action": {"six-layer-poc-extension-action"},
    "history": {"six-layer-raw-history-reader"},
    "event-runtime": {"event-telemetry-processor", "event-historical-persistence", "event-rule-evaluator", "event-control-router"},
}


def functions_ready(values, outputs, attempts=18, pause_seconds=5):
    group = outputs["azure_six_layer_resource_group_name"]
    base = f"/subscriptions/{values['azure_subscription_id']}/resourceGroups/{group}"
    resources = core.arm(values, "GET", base + "/resources?api-version=2021-04-01")["value"]
    sites = [r for r in resources if r["type"].lower() == "microsoft.web/sites"]
    selected = {}
    for role in EXPECTED_FUNCTIONS:
        marker = "-event-runtime-" if role == "event-runtime" else "-six-" + role + "-"
        candidates = [r for r in sites if marker in r["name"]]
        if len(candidates) != 1:
            raise RuntimeError("COMMAND_FUNCTION_APP_SCOPE_MISMATCH")
        selected[role] = candidates[0]
    if len(sites) != len(selected):
        raise RuntimeError("COMMAND_FUNCTION_APP_SCOPE_MISMATCH")
    started = time.monotonic()
    for attempt in range(1, attempts + 1):
        missing = {}
        for role, site in selected.items():
            data = core.arm(values, "GET", site["id"] + "/functions?api-version=2023-12-01", allowed=(200, 404, 503))
            found = {str(r.get("name", "")).split("/")[-1] for r in data.get("value", [])}
            missing[role] = sorted(EXPECTED_FUNCTIONS[role] - found)
        measurement = {"attempts": attempt, "seconds": time.monotonic() - started, "missing": missing}
        save(Path(values["project_path"]) / "function-registration.json", measurement)
        if not any(missing.values()):
            return {"function_readiness_attempts": attempt, "function_readiness_seconds": measurement["seconds"]}
        if attempt < attempts:
            time.sleep(pause_seconds)
    raise RuntimeError("COMMAND_FUNCTION_REGISTRATION_TIMEOUT")


def smoke(values, outputs):
    from src.iot_device_simulator.azure import transmission
    readiness = functions_ready(values, outputs)
    started = time.monotonic()
    hostname, key = core.register_simulator(values, outputs)
    registration_seconds = time.monotonic() - started
    config = {"device_id": DEVICE, "connection_string":
              f"HostName={hostname};DeviceId={DEVICE};SharedAccessKey={key}"}
    now, result = exercise(transmission, config, values)
    result.update(scope="local_azure_simulator_command_and_l3", device_registration_seconds=registration_seconds, **readiness)
    return confirm_history(reader(values, outputs, now), now, result)


def reader(values, outputs, now):
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
    return read


def diagnostics(values, outputs):
    # Capture broker counters before resource deletion and log-ingestion delay.
    # These are diagnostic observations, never a substitute for device receipt.
    broker_metrics(values, outputs)
    result = core.diagnostics(values, outputs)
    fixture = Path(values["project_path"]) / "simulator-fixture.json"
    if fixture.exists():
        try:
            now = datetime.fromisoformat(json.loads(fixture.read_text())["event_time"])
            points = reader(values, outputs, now)()
            result["matching_l3_points_after_receipt_failure"] = sum(
                p.get("value") == 42 and bool(p.get("event_time")) and
                datetime.fromisoformat(p["event_time"].replace("Z", "+00:00")) == now for p in points)
        except Exception as exc:
            result["failure_readback_error_type"] = type(exc).__name__
    return result


def broker_metrics(values, outputs):
    end = datetime.now(timezone.utc)
    query_string = urlencode({
        "api-version": "2018-01-01", "metricnames": "IncomingMessages,OutgoingMessages",
        "aggregation": "Total", "interval": "PT1M", "$filter": "EntityName eq '*'",
        "timespan": (end - timedelta(minutes=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
                    + "/" + end.strftime("%Y-%m-%dT%H:%M:%SZ"),
    })
    scopes = {
        "control": (outputs.get("azure_event_control_topic_id") or "").split("/topics/")[0],
        "telemetry": outputs.get("azure_event_hubs_standard_id"),
    }
    for label, scope in scopes.items():
        if not scope:
            continue
        try:
            observation = core.arm(values, "GET", scope + "/providers/microsoft.insights/metrics?" + query_string)
        except Exception as exc:
            observation = {"error_type": type(exc).__name__}
        save(Path(values["project_path"]) / ("broker-metrics-" + label + ".json"), observation)


# The device is a child of this run's fresh IoT Hub. Terraform removes the hub,
# and the existing independent resource-group inventory verifies its absence.
__all__ = ["configure", "inventory", "stop_builds", "diagnostics", "smoke"]
