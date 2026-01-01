"""
Field normalization utility for cross-cloud data consistency.

Normalizes incoming IoT telemetry to canonical format:
- device_id (from iotDeviceId, deviceId)
- timestamp (from time, ts, id)
"""
from datetime import datetime


def normalize_telemetry(event: dict) -> dict:
    """
    Normalize incoming IoT telemetry to canonical format.
    
    Args:
        event: Raw telemetry event from IoT device
        
    Returns:
        Normalized event with device_id and timestamp fields
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
    
    # timestamp normalization (keep original field for backward compatibility)
    if "timestamp" not in normalized:
        for source in ["time", "ts"]:
            if source in normalized:
                normalized["timestamp"] = str(normalized[source])  # Copy, don't pop
                break
    
    # Generate timestamp if still missing
    if "timestamp" not in normalized:
        normalized["timestamp"] = datetime.utcnow().isoformat() + "Z"
    
    return normalized
