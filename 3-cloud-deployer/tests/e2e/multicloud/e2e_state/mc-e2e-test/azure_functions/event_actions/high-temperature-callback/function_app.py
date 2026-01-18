"""
High Temperature Callback Azure Function.

Event action triggered by event-checker when temperature threshold is met.
Azure equivalent of AWS high-temperature-callback Lambda.
"""
import json

import azure.functions as func

app = func.FunctionApp()


@app.function_name(name="high-temperature-callback")
@app.route(route="high-temperature-callback", methods=["POST"], auth_level=func.AuthLevel.FUNCTION)
def main(req: func.HttpRequest) -> func.HttpResponse:
    """Handle high temperature event callback."""
    event = req.get_json()
    print("Hello from High Temperature Callback!")
    print("Event: " + json.dumps(event))
    
    return func.HttpResponse(
        json.dumps({"statusCode": 200, "body": "Callback executed"}),
        status_code=200,
        mimetype="application/json"
    )
