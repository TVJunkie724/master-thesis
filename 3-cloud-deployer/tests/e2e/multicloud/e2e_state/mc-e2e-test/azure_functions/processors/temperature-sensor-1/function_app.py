"""
User Processor Azure Function for temperature-sensor-1.
Replace this with your custom processing logic.
"""
import json
import azure.functions as func

app = func.FunctionApp()


@app.function_name(name="temperature-sensor-1-processor")
@app.route(route="temperature-sensor-1-processor", methods=["POST"], auth_level=func.AuthLevel.FUNCTION)
def main(req: func.HttpRequest) -> func.HttpResponse:
    """Process incoming IoT event and return modified event."""
    event = req.get_json()
    
    # === YOUR PROCESSING LOGIC HERE ===
    processed_event = event  # Modify as needed
    # ==================================
    
    return func.HttpResponse(
        json.dumps(processed_event),
        status_code=200,
        mimetype="application/json"
    )
