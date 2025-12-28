"""
High Temperature Callback Google Cloud Function.

Event action triggered by event-checker when temperature threshold is met.
GCP equivalent of AWS high-temperature-callback Lambda.
"""
import json
import functions_framework


@functions_framework.http
def main(request):
    """Handle high temperature event callback."""
    event = request.get_json()
    print("Hello from High Temperature Callback!")
    print("Event: " + json.dumps(event))
    
    return (json.dumps({"statusCode": 200, "body": "Callback executed"}), 200, {"Content-Type": "application/json"})
