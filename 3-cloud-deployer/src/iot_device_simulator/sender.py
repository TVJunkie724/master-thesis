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
from src.simulator.session import SimulatorSessionError, resolve_simulator_session

TRACE_ID_PATTERN = re.compile(r"^(?:TRACE|VERIFY)-[A-F0-9]{8}$")
SIMULATOR_TIMEOUT_SECONDS = 30
MAX_ONE_SHOT_PAYLOAD_BYTES = 4 * 1024 * 1024


def _load_default_payload(project_path: Path) -> dict | None:
    payloads_path = project_path / "iot_device_simulator" / "payloads.json"
    if not payloads_path.exists():
        return None
    try:
        with payloads_path.open(encoding="utf-8") as handle:
            payloads = json.load(handle)
    except (OSError, ValueError) as exc:
        logger.warning(f"Could not load simulator payloads: {redact_sensitive(exc)}")
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
    project_path: Path | None = None,
) -> bool:
    """Send one traceable message through a provider simulator process."""
    if not TRACE_ID_PATTERN.fullmatch(trace_id):
        logger.error("Simulator trace ID has an invalid format")
        return False

    project_path = project_path or resolve_project_context_path(project_name)
    if payload_override is not None and not isinstance(payload_override, dict):
        logger.error("Simulator payload override must be a JSON object")
        return False
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
    try:
        spec = resolve_simulator_session(
            project_name=project_name,
            provider=provider,
            device_id=device_id if isinstance(device_id, str) and device_id else None,
            project_path=project_path,
        )
    except SimulatorSessionError as exc:
        logger.error(f"Simulator configuration is unavailable: {redact_sensitive(exc)}")
        return False

    command = [
        sys.executable,
        "-m",
        spec.module,
        "--config",
        str(spec.config_path),
        "--payload-stdin",
    ]
    payload_json = json.dumps(payload, separators=(",", ":"))
    if len(payload_json.encode("utf-8")) > MAX_ONE_SHOT_PAYLOAD_BYTES:
        logger.error("Simulator payload exceeds its size limit")
        return False
    try:
        result = subprocess.run(  # nosec B603
            command,
            input=payload_json,
            capture_output=True,
            text=True,
            timeout=SIMULATOR_TIMEOUT_SECONDS,
            cwd=spec.repository_root,
            check=False,
        )
    except subprocess.TimeoutExpired:
        logger.error(f"Simulator timed out for provider {provider}")
        return False
    except OSError as exc:
        logger.error(f"Simulator process failed: {redact_sensitive(exc)}")
        return False

    if result.returncode != 0:
        logger.error(f"Simulator returned a failure: {redact_sensitive(result.stderr)}")
        return False
    logger.info(f"Test message sent via {provider} simulator: {trace_id}")
    return True
