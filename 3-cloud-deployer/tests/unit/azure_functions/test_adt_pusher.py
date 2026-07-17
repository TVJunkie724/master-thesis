"""Security and error-boundary tests for the canonical Azure ADT Pusher."""

import importlib.util
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


DEPLOYER_ROOT = Path(__file__).resolve().parents[3]
AZURE_FUNCTIONS_ROOT = (
    DEPLOYER_ROOT / "src/providers/azure/azure_functions"
)
ADT_PUSHER_PATH = AZURE_FUNCTIONS_ROOT / "adt-pusher/function_app.py"


def _clear_shared_modules() -> None:
    for module_name in list(sys.modules):
        if module_name == "_shared" or module_name.startswith("_shared."):
            del sys.modules[module_name]


def _load_adt_pusher(
    monkeypatch: pytest.MonkeyPatch,
    *,
    token: str | None = "expected-token",
    adt_url: str | None = "https://test.api.westeurope.digitaltwins.azure.net",
):
    if token is None:
        monkeypatch.delenv("INTER_CLOUD_TOKEN", raising=False)
    else:
        monkeypatch.setenv("INTER_CLOUD_TOKEN", token)
    if adt_url is None:
        monkeypatch.delenv("ADT_INSTANCE_URL", raising=False)
    else:
        monkeypatch.setenv("ADT_INSTANCE_URL", adt_url)
    monkeypatch.setenv(
        "DIGITAL_TWIN_INFO",
        json.dumps({
            "devices": {
                "sensor-1": {"twin_id": "twin-sensor-1"},
            }
        }),
    )

    function_root = str(AZURE_FUNCTIONS_ROOT)
    _clear_shared_modules()
    sys.path.insert(0, function_root)
    try:
        spec = importlib.util.spec_from_file_location(
            f"test_adt_pusher_{id(monkeypatch)}",
            ADT_PUSHER_PATH,
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.remove(function_root)
        _clear_shared_modules()


def _request(
    body,
    *,
    token: str | None = "expected-token",
    json_error: Exception | None = None,
):
    request = MagicMock()
    request.headers = {}
    if token is not None:
        request.headers["X-Inter-Cloud-Token"] = token
    if json_error is not None:
        request.get_json.side_effect = json_error
    else:
        request.get_json.return_value = body
    return request


def _json_body(response) -> dict:
    return json.loads(response.get_body().decode("utf-8"))


def test_rejects_requests_when_server_token_is_not_configured(monkeypatch):
    module = _load_adt_pusher(monkeypatch, token=None)
    response = module.adt_pusher(_request({}))
    assert response.status_code == 500
    assert _json_body(response) == {"error": "Service configuration unavailable"}


@pytest.mark.parametrize("request_token", [None, "wrong-token"])
def test_rejects_missing_or_invalid_request_token(monkeypatch, request_token):
    module = _load_adt_pusher(monkeypatch)
    response = module.adt_pusher(_request({}, token=request_token))
    assert response.status_code == 401
    assert _json_body(response) == {"error": "Unauthorized"}


def test_rejects_requests_when_adt_endpoint_is_not_configured(monkeypatch):
    module = _load_adt_pusher(monkeypatch, adt_url=None)
    response = module.adt_pusher(_request({}))
    assert response.status_code == 503
    assert _json_body(response) == {"error": "Service unavailable"}


@pytest.mark.parametrize("json_error", [TypeError("invalid"), ValueError("invalid")])
def test_rejects_invalid_json(monkeypatch, json_error):
    module = _load_adt_pusher(monkeypatch)
    response = module.adt_pusher(
        _request(None, json_error=json_error),
    )
    assert response.status_code == 400
    assert _json_body(response) == {"error": "Invalid JSON"}


@pytest.mark.parametrize(
    ("body", "error"),
    [
        ([], "Request body must be an object"),
        (
            {"source_cloud": "aws", "payload": []},
            "Envelope payload must be an object",
        ),
        ({"telemetry": {"temperature": 20}}, "Missing device_id"),
        (
            {"device_id": "sensor-1", "telemetry": []},
            "Telemetry must be a non-empty object",
        ),
        (
            {"device_id": "sensor-1", "telemetry": {}},
            "Telemetry must be a non-empty object",
        ),
    ],
)
def test_rejects_invalid_payload_shapes(monkeypatch, body, error):
    module = _load_adt_pusher(monkeypatch)
    response = module.adt_pusher(_request(body))
    assert response.status_code == 400
    assert _json_body(response) == {"error": error}


def test_updates_mapped_twin_from_inter_cloud_envelope(monkeypatch):
    module = _load_adt_pusher(monkeypatch)
    adt_client = MagicMock()
    body = {
        "source_cloud": "aws",
        "target_layer": "L4",
        "payload": {
            "device_id": "sensor-1",
            "telemetry": {"temperature": 20.5},
        },
    }

    with (
        patch.object(module, "create_adt_client", return_value=adt_client),
        patch.object(
            module,
            "update_adt_twin",
            return_value="twin-sensor-1",
        ) as update_adt_twin,
    ):
        response = module.adt_pusher(_request(body))

    assert response.status_code == 200
    assert _json_body(response) == {
        "status": "updated",
        "twin_id": "twin-sensor-1",
    }
    update_adt_twin.assert_called_once_with(
        adt_client=adt_client,
        device_id="sensor-1",
        telemetry={"temperature": 20.5},
        digital_twin_info={
            "devices": {
                "sensor-1": {"twin_id": "twin-sensor-1"},
            }
        },
    )


@pytest.mark.parametrize(
    ("failure", "status_code", "error"),
    [
        (
            ValueError("secret-validation-detail"),
            400,
            "Invalid telemetry or twin mapping",
        ),
        (
            RuntimeError("secret-provider-detail"),
            500,
            "Azure Digital Twins update failed",
        ),
    ],
)
def test_redacts_validation_and_provider_failures(
    monkeypatch,
    caplog,
    failure,
    status_code,
    error,
):
    module = _load_adt_pusher(monkeypatch)
    body = {
        "device_id": "sensor-1",
        "telemetry": {"temperature": 20.5},
    }
    with (
        patch.object(module, "create_adt_client", return_value=MagicMock()),
        patch.object(module, "update_adt_twin", side_effect=failure),
    ):
        response = module.adt_pusher(_request(body))

    assert response.status_code == status_code
    assert _json_body(response) == {"error": error}
    assert str(failure) not in caplog.text
    assert str(failure) not in response.get_body().decode("utf-8")


def test_does_not_log_telemetry_payload(monkeypatch, caplog):
    module = _load_adt_pusher(monkeypatch)
    unique_value = "payload-value-that-must-not-be-logged"
    body = {
        "device_id": "sensor-1",
        "telemetry": {"diagnostic": unique_value},
    }
    with (
        patch.object(module, "create_adt_client", return_value=MagicMock()),
        patch.object(module, "update_adt_twin", return_value="twin-sensor-1"),
    ):
        response = module.adt_pusher(_request(body))

    assert response.status_code == 200
    assert unique_value not in caplog.text
