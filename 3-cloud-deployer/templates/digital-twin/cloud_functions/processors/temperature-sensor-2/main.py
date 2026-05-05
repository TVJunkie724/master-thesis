"""User Processor GCP Cloud Function for temperature-sensor-2."""
import json
import functions_framework


@functions_framework.http
def main(request):
    """Process incoming IoT event."""
    event = request.get_json()
    
    # === YOUR PROCESSING LOGIC HERE ===
    processed_event = event
    # ==================================
    
    return json.dumps(processed_event), 200, {"Content-Type": "application/json"}
