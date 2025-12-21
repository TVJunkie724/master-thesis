# --- CONTEXT: System Wrapper (DO NOT EDIT) ---
# Your process() function is imported and called by the Processor wrapper.
# See default_processor/process.py for full wrapper context.
# ---------------------------------------------

def process(event: dict) -> dict:
    """
    Process temperature-sensor-2 events with validation.
    
    Checks for high temperature readings and logs warnings.
    
    Args:
        event: IoT telemetry event dict
        
    Returns:
        dict: Processed event (returned as-is after validation)
    """
    # Handle both single events and lists
    records = event if isinstance(event, list) else [event]
    
    for record in records:
        if "temperature" in record and record["temperature"] > 100:
            print(f"⚠️ High temp detected: {record['temperature']}°C")
    
    return event
