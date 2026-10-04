"""Fixed one-message receipt assertion shared by the Azure/GCP research cuts."""
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timedelta, timezone
import io
import json
from pathlib import Path
import time
import uuid

from src.core.secure_files import atomic_write_private_bytes
from scripts.run_core_evaluation import save

DEVICE = "core-sensor"


def configure(values, root):
    values["events"] = [{"rule_id": "command-check", "condition": "value == INTEGER(42)", "action": {
        "type": "function", "functionName": "poc-command-check",
        "feedback": {"device_id": DEVICE, "payload": "roundtrip-confirmed"}}}]
    save(root / "config_events.json", values["events"])
    save(root / "config_iot_devices.json", [{"id": DEVICE}])


def exercise(runtime, config, values):
    trace = "TRACE-" + uuid.uuid4().hex.upper()
    now = datetime.now(timezone.utc)
    payload = {"event_id": trace, "source_id": DEVICE, "source_sequence": trace,
               "correlation_id": trace, "device_id": DEVICE, "metric": "temperature",
               "value": 42, "event_time": now.isoformat()}
    capture, previous = io.StringIO(), runtime.globals.config
    try:
        runtime.globals.config = config
        with redirect_stdout(capture), redirect_stderr(capture):
            received = runtime.listen_for_command(300, telemetry_payload=payload)
    finally:
        runtime.globals.config = previous
        atomic_write_private_bytes(Path(values["project_path"]) / "simulator.log", capture.getvalue().encode())
    if not received:
        raise RuntimeError("COMMAND_RECEIPT_TIMEOUT")
    checkpoints = [json.loads(line.removeprefix("T2MC_CHECKPOINT ")) for line in capture.getvalue().splitlines()
                   if line.startswith("T2MC_CHECKPOINT ")]
    correlated = {p["stage"]: p for p in checkpoints if p.get("trace_id") == trace}
    if not {"simulator_sent", "simulator_command_received"} <= correlated.keys():
        raise RuntimeError("COMMAND_CHECKPOINTS_MISSING")
    stamps = [datetime.fromisoformat(correlated[stage]["observed_at"].replace("Z", "+00:00"))
              for stage in ("simulator_sent", "simulator_command_received")]
    elapsed = (stamps[1] - stamps[0]).total_seconds()
    if elapsed < 0:
        raise RuntimeError("COMMAND_CHECKPOINT_ORDER_INVALID")
    return now, {"sent": 1, "command_received": 1, "roundtrip_seconds": elapsed, "checkpoints": checkpoints}


def query(now):
    return {"device_id": DEVICE, "metric": "temperature", "bucket_seconds": "0", "limit": "20",
            "from": (now - timedelta(minutes=1)).isoformat(), "to": (now + timedelta(minutes=10)).isoformat()}


def confirm_history(read, now, result):
    started = time.monotonic()
    for attempt in range(60):
        points = read()
        if any(p.get("value") == 42 and p.get("event_time") and
               datetime.fromisoformat(p["event_time"].replace("Z", "+00:00")) == now for p in points):
            result.update(read_back=1, readback_poll_attempts=attempt + 1,
                          readback_seconds=time.monotonic() - started)
            return result
        time.sleep(2)
    raise RuntimeError("COMMAND_L3_READBACK_TIMEOUT")
