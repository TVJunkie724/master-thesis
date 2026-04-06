"""
Field normalization utility for cross-cloud data consistency.

Normalizes incoming IoT telemetry to canonical format:
- device_id (from iotDeviceId, deviceId)
- timestamp (from time, ts) → Always ISO8601 format
"""
from datetime import datetime, timezone


def _is_iso8601_like(value: str) -> bool:
    """
    Check if string looks like ISO8601 datetime.
    
    Matches patterns like:
    - 2026-01-30T18:00:00Z
    - 2026-01-30T18:00:00.000Z
    - 2026-01-30T18:00:00+00:00
    """
    # Must be at least "YYYY-MM-DD" (10 chars) with proper separators
    if len(value) < 10:
        return False
    # Check for date pattern: YYYY-MM-DD
    return value[4:5] == "-" and value[7:8] == "-" and value[:4].isdigit()


def _convert_to_iso8601(value) -> str:
    """
    Convert various timestamp formats to ISO8601.
    
    Handles:
    - Epoch milliseconds (int or string): 1738267800000
    - Epoch seconds (int or string): 1738267800
    - Already ISO8601: "2026-01-30T18:00:00Z"
    
    Returns:
        ISO8601 formatted string with Z suffix
    """
    # Already a proper ISO8601 string
    if isinstance(value, str) and _is_iso8601_like(value):
        # Ensure Z suffix for UTC
        if value.endswith("Z") or "+" in value or value.endswith("-00:00"):
            return value
        return value + "Z"
    
    # Numeric or numeric string - treat as epoch
    try:
        epoch = float(value)
        # Heuristic: if > 1e12, it's milliseconds; otherwise seconds
        if epoch > 1e12:
            epoch = epoch / 1000
        dt = datetime.fromtimestamp(epoch, tz=timezone.utc)
        return dt.isoformat().replace("+00:00", "Z")
    except (ValueError, TypeError, OSError):
        # OSError for out-of-range timestamps, fallback to string
        return str(value)


def normalize_telemetry(event: dict) -> dict:
    """
    Normalize incoming IoT telemetry to canonical format.
    
    Args:
        event: Raw telemetry event from IoT device
        
    Returns:
        Normalized event with device_id and timestamp (ISO8601) fields
    """
    if not isinstance(event, dict):
        return event
    
    normalized = event.copy()
    
    # device_id normalization
    if "device_id" not in normalized:
        for source in ["iotDeviceId", "deviceId", "IoTDeviceId"]:
            if source in normalized:
                normalized["device_id"] = normalized.pop(source)
                break
    
    # timestamp normalization - convert to ISO8601
    if "timestamp" not in normalized:
        for source in ["time", "ts"]:
            if source in normalized:
                normalized["timestamp"] = _convert_to_iso8601(normalized[source])
                break
    
    # Generate timestamp if still missing
    if "timestamp" not in normalized:
        normalized["timestamp"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    
    return normalized
