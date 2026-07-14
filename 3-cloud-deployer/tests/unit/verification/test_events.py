import json

import pytest

from src.verification.events import sse_event


def _event_data(event: str) -> dict:
    data_line = next(line for line in event.splitlines() if line.startswith("data: "))
    return json.loads(data_line.removeprefix("data: "))


def test_sse_event_recursively_redacts_nested_secrets():
    event = sse_event(
        "log",
        {
            "message": "request failed",
            "details": [
                {"error": "api_key=top-secret"},
                "Authorization: Bearer bearer-secret",
            ],
        },
    )

    serialized = json.dumps(_event_data(event))
    assert "top-secret" not in serialized
    assert "bearer-secret" not in serialized
    assert "<redacted>" in serialized


def test_sse_event_rejects_uncontracted_event_names():
    with pytest.raises(ValueError, match="Unsupported verification event"):
        sse_event("debug", {})
