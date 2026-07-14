"""Bounded subprocess adapter for one-shot simulator messages."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import re
import subprocess  # nosec B404
import sys

from logger import logger
from src.core.observability import redact_sensitive
from src.core.paths import resolve_project_context_path

SIMULATOR_MODULES = {
    "aws": "aws",
    "azure": "azure",
    "google": "google",
    "gcp": "google",
}
TRACE_ID_PATTERN = re.compile(r"^(?:TRACE|VERIFY)-[A-F0-9]{8}$")
SIMULATOR_TIMEOUT_SECONDS = 30


def _load_default_payload(project_path: Path) -> dict | None:
    payloads_path = project_path / "iot_device_simulator" / "payloads.json"
    if not payloads_path.exists():
        return None
    try:
        with payloads_path.open(encoding="utf-8") as handle:
            payloads = json.load(handle)
    except (OSError, ValueError) as exc:
        logger.warning(
            "Could not load simulator payloads: "
            f"{redact_sensitive(exc)}"
        )
        return None
    if not isinstance(payloads, list) or not payloads:
        return None
    return payloads[0].copy() if isinstance(payloads[0], dict) else None


def send_test_message(
    provider: str,
    project_name: str,
    trace_id: str,
    *,
    payload_override: dict | None = None,
) -> bool:
    """Send one traceable message through a provider simulator process."""
    simulator_module = SIMULATOR_MODULES.get(provider)
    if simulator_module is None:
        logger.error(f"Unsupported simulator provider: {provider}")
        return False
    if not TRACE_ID_PATTERN.fullmatch(trace_id):
        logger.error("Simulator trace ID has an invalid format")
        return False

    project_path = resolve_project_context_path(project_name)
    payload = (
        payload_override.copy()
        if payload_override is not None
        else _load_default_payload(project_path)
    )
    if payload is None:
        logger.error(
            "Simulator payloads are not configured; provide a payload or "
            "iot_device_simulator/payloads.json"
        )
        return False

    device_id = payload.get("iotDeviceId")
    payload["trace_id"] = trace_id
    payload["time"] = (
        datetime.now(timezone.utc)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )
    command = [
        sys.executable,
        "-m",
        f"src.iot_device_simulator.{simulator_module}.main",
        "--project",
        project_name,
        "--payload",
        json.dumps(payload, separators=(",", ":")),
    ]
    if isinstance(device_id, str) and device_id:
        command.extend(["--device", device_id])

    repository_root = Path(__file__).resolve().parents[2]
    try:
        result = subprocess.run(  # nosec B603
            command,
            capture_output=True,
            text=True,
            timeout=SIMULATOR_TIMEOUT_SECONDS,
            cwd=repository_root,
            check=False,
        )
    except subprocess.TimeoutExpired:
        logger.error(f"Simulator timed out for provider {provider}")
        return False
    except OSError as exc:
        logger.error(f"Simulator process failed: {redact_sensitive(exc)}")
        return False

    if result.returncode != 0:
        logger.error(
            "Simulator returned a failure: "
            f"{redact_sensitive(result.stderr)}"
        )
        return False
    logger.info(f"Test message sent via {provider} simulator: {trace_id}")
    return True
