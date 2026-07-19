"""GCP HTTP trigger adapter for the canonical user-function runtime envelope."""

import json

from _platform_runtime import invoke


def main(request):
    response = invoke(request.get_json())
    status = 200 if response["status"] in {"success", "rejected"} else 500
    return (
        json.dumps(response, separators=(",", ":"), sort_keys=True),
        status,
        {"Content-Type": "application/json"},
    )
