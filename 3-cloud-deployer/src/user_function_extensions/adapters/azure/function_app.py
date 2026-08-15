"""Azure HTTP trigger adapter for the canonical user-function runtime envelope."""

import json

import azure.functions as func

from _platform_runtime import invoke


app = func.FunctionApp()


@app.route(route="extension", methods=["POST"], auth_level=func.AuthLevel.FUNCTION)
def main(request: func.HttpRequest) -> func.HttpResponse:
    response = invoke(request.get_json())
    status = 200 if response["status"] in {"success", "rejected"} else 500
    return func.HttpResponse(
        json.dumps(response, separators=(",", ":"), sort_keys=True),
        status_code=status,
        mimetype="application/json",
    )
