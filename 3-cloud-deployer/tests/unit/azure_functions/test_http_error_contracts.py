"""Cross-adapter tests for the Azure Function runtime error boundary."""

from __future__ import annotations

import ast
import io
import importlib.util
import json
import sys
import urllib.error
import uuid
from pathlib import Path
from unittest.mock import MagicMock

import pytest


DEPLOYER_ROOT = Path(__file__).resolve().parents[3]
AZURE_FUNCTIONS_ROOT = (
    DEPLOYER_ROOT / "src/providers/azure/azure_functions"
)
HTTP_ADAPTERS = {
    "adt-pusher": "adt_pusher",
    "archive-writer": "archive_writer",
    "cold-writer": "cold_writer",
    "connector": "connector",
    "event-checker": "event_checker",
    "event_feedback_wrapper": "main",
    "hot-reader": "hot_reader",
    "hot-reader-last-entry": "hot_reader_last_entry",
    "hot-writer": "hot_writer",
    "ingestion": "ingestion",
    "persister": "persister",
    "processor_wrapper": "processor",
}
AUTH_ADAPTERS = (
    ("adt-pusher", "adt_pusher", 401),
    ("archive-writer", "archive_writer", 403),
    ("cold-writer", "cold_writer", 403),
    ("hot-reader", "hot_reader", 401),
    ("hot-reader-last-entry", "hot_reader_last_entry", 401),
    ("hot-writer", "hot_writer", 403),
    ("ingestion", "ingestion", 403),
)
CONFIGURATION_ADAPTERS = {
    directory: function_name
    for directory, function_name in HTTP_ADAPTERS.items()
    if directory != "adt-pusher"
}


def _clear_shared_modules() -> None:
    for module_name in list(sys.modules):
        if module_name == "_shared" or module_name.startswith("_shared."):
            del sys.modules[module_name]


def _load_adapter(
    monkeypatch: pytest.MonkeyPatch,
    directory: str,
):
    monkeypatch.setenv("INTER_CLOUD_TOKEN", "expected-token")
    monkeypatch.setenv(
        "ADT_INSTANCE_URL",
        "https://test.api.westeurope.digitaltwins.azure.net",
    )
    monkeypatch.setenv(
        "DIGITAL_TWIN_INFO",
        '{"devices":{"sensor-1":{"twin_id":"twin-sensor-1"}}}',
    )
    path = AZURE_FUNCTIONS_ROOT / directory / "function_app.py"
    module_name = (
        f"test_http_error_{directory.replace('-', '_')}_{id(monkeypatch)}"
    )

    _clear_shared_modules()
    sys.path.insert(0, str(AZURE_FUNCTIONS_ROOT))
    try:
        spec = importlib.util.spec_from_file_location(module_name, path)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.remove(str(AZURE_FUNCTIONS_ROOT))


def _request(*, body=None, failure: Exception | None = None):
    request = MagicMock()
    request.headers = {}
    request.method = "POST"
    request.params = {}
    if failure is None:
        request.get_json.return_value = body
    else:
        request.get_json.side_effect = failure
    return request


def _body(response) -> dict:
    return json.loads(response.get_body().decode("utf-8"))


def _assert_correlated_failure(
    response,
    caplog,
    *,
    status_code=500,
    code="INTERNAL_ERROR",
    message="The request could not be completed.",
) -> None:
    payload = _body(response)
    assert response.status_code == status_code
    assert payload["error"]["code"] == code
    assert payload["error"]["message"] == message
    correlation_id = payload["error"]["correlation_id"]
    uuid.UUID(correlation_id)
    assert correlation_id in caplog.text


def test_shared_failure_boundary_redacts_and_bounds_diagnostics(
    monkeypatch,
    caplog,
):
    monkeypatch.setenv("AZURE_TEST_SECRET", "bare-runtime-secret")
    sys.path.insert(0, str(AZURE_FUNCTIONS_ROOT))
    _clear_shared_modules()
    try:
        from _shared.http_errors import (
            MAX_DIAGNOSTIC_LENGTH,
            MAX_PUBLIC_MESSAGE_LENGTH,
            error_response,
            failure_response,
            redact_runtime_diagnostic,
        )

        diagnostic = (
            "bare-runtime-secret "
            "https://host.test/path?sig=signed-value&code=function-key "
            "/home/site/wwwroot/function_app.py "
            r"C:\home\site\wwwroot\function_app.py "
            "client_secret=inline-secret\nsecond line "
            + ("x" * 900)
        )
        redacted = redact_runtime_diagnostic(diagnostic)
        response = failure_response(
            component="azure.test",
            error=RuntimeError(diagnostic),
        )
        bounded_response = error_response(
            code="invalid code",
            message=(" public\nmessage " * 100),
            status_code=500,
        )
    finally:
        sys.path.remove(str(AZURE_FUNCTIONS_ROOT))
        _clear_shared_modules()

    _assert_correlated_failure(response, caplog)
    assert len(redacted) <= MAX_DIAGNOSTIC_LENGTH
    assert "\n" not in redacted
    for forbidden in (
        "bare-runtime-secret",
        "signed-value",
        "function-key",
        "inline-secret",
        "/home/site/wwwroot",
        r"C:\home\site\wwwroot",
    ):
        assert forbidden not in redacted
        assert forbidden not in caplog.text
    assert "<redacted>" in redacted
    assert "<runtime-path>" in redacted
    bounded_error = _body(bounded_response)["error"]
    assert bounded_error["code"] == "INTERNAL_ERROR"
    assert "\n" not in bounded_error["message"]
    assert len(bounded_error["message"]) == MAX_PUBLIC_MESSAGE_LENGTH


@pytest.mark.parametrize(
    ("directory", "function_name"),
    HTTP_ADAPTERS.items(),
)
def test_unexpected_adapter_failures_are_correlated_and_redacted(
    monkeypatch,
    caplog,
    directory,
    function_name,
):
    secret = f"runtime-secret-{directory}"
    monkeypatch.setenv("AZURE_TEST_SECRET", secret)
    module = _load_adapter(monkeypatch, directory)
    request = _request(
        failure=RuntimeError(
            f"{secret} code=signed-key /home/site/wwwroot/{directory}.py"
        )
    )

    if directory in {
        "archive-writer",
        "cold-writer",
        "hot-writer",
        "ingestion",
    }:
        module._inter_cloud_token = "expected-token"
        module.validate_token = MagicMock(return_value=True)
    elif directory == "hot-reader":
        module._get_inter_cloud_token = MagicMock(return_value="")
    elif directory == "hot-reader-last-entry":
        request.headers = {"X-Inter-Cloud-Token": "expected-token"}
    elif directory == "event-checker":
        module._validate_config = MagicMock()
    elif directory == "persister":
        module._validate_config = MagicMock()
    elif directory == "adt-pusher":
        request = _request(
            body={
                "device_id": "sensor-1",
                "telemetry": {"temperature": 20},
            }
        )
        request.headers = {"X-Inter-Cloud-Token": "expected-token"}
        module._digital_twin_info = {"devices": {}}
        module.create_adt_client = MagicMock()
        module.update_adt_twin = MagicMock(
            side_effect=RuntimeError(
                f"{secret} code=signed-key "
                "/home/site/wwwroot/adt-pusher.py"
            )
        )

    response = getattr(module, function_name)(request)

    _assert_correlated_failure(
        response,
        caplog,
        status_code=502 if directory == "adt-pusher" else 500,
        code=(
            "ADT_DELIVERY_FAILED"
            if directory == "adt-pusher"
            else "INTERNAL_ERROR"
        ),
        message=(
            "Azure Digital Twins update failed."
            if directory == "adt-pusher"
            else "The request could not be completed."
        ),
    )
    assert secret not in response.get_body().decode("utf-8")
    assert secret not in caplog.text
    assert "signed-key" not in caplog.text
    assert "/home/site/wwwroot" not in caplog.text


@pytest.mark.parametrize(
    ("directory", "function_name"),
    CONFIGURATION_ADAPTERS.items(),
)
def test_missing_runtime_configuration_uses_stable_error_code(
    monkeypatch,
    caplog,
    directory,
    function_name,
):
    module = _load_adapter(monkeypatch, directory)
    request = _request(
        failure=module.MissingEnvironmentVariableError(
            "REQUIRED_SETTING is missing"
        )
    )

    if directory in {
        "archive-writer",
        "cold-writer",
        "hot-writer",
        "ingestion",
    }:
        module._inter_cloud_token = "expected-token"
        module.validate_token = MagicMock(return_value=True)
    elif directory == "hot-reader":
        module._get_inter_cloud_token = MagicMock(return_value="")
    elif directory == "hot-reader-last-entry":
        request.headers = {"X-Inter-Cloud-Token": "expected-token"}
    elif directory in {"event-checker", "persister"}:
        module._validate_config = MagicMock()

    response = getattr(module, function_name)(request)

    payload = _body(response)
    assert response.status_code == 500
    assert payload["error"]["code"] == "CONFIGURATION_ERROR"
    correlation_id = payload["error"]["correlation_id"]
    uuid.UUID(correlation_id)
    assert correlation_id in caplog.text


@pytest.mark.parametrize(
    ("directory", "function_name", "status_code"),
    AUTH_ADAPTERS,
)
def test_auth_failures_keep_status_without_internal_diagnostics(
    monkeypatch,
    caplog,
    directory,
    function_name,
    status_code,
):
    module = _load_adapter(monkeypatch, directory)
    request = _request(body={})
    request.headers = {"X-Inter-Cloud-Token": "wrong-token"}
    module.validate_token = MagicMock(return_value=False)
    if hasattr(module, "_inter_cloud_token"):
        module._inter_cloud_token = "expected-token"
    if directory == "hot-reader":
        module._get_inter_cloud_token = MagicMock(return_value="expected-token")

    response = getattr(module, function_name)(request)

    assert response.status_code == status_code
    assert _body(response) == {
        "error": {
            "code": "UNAUTHORIZED",
            "message": "Invalid or missing X-Inter-Cloud-Token"
            if status_code == 401
            else "Invalid X-Inter-Cloud-Token",
        }
    }
    assert "correlation_id" not in response.get_body().decode("utf-8")
    assert "diagnostic=" not in caplog.text


def test_connector_exposes_only_remote_status(monkeypatch, caplog):
    module = _load_adapter(monkeypatch, "connector")
    module._remote_ingestion_url = "https://remote.example.test/ingestion"
    module._inter_cloud_token = "expected-token"
    secret_body = '{"client_secret":"must-not-leak"}'
    module.post_to_remote = MagicMock(
        return_value={"statusCode": 202, "body": secret_body}
    )

    response = module.connector(_request(body={"device_id": "sensor-1"}))

    assert response.status_code == 200
    assert _body(response) == {
        "status": "forwarded",
        "remote_status_code": 202,
    }
    assert secret_body not in response.get_body().decode("utf-8")
    assert "must-not-leak" not in caplog.text


def test_connector_rejects_non_object_requests(monkeypatch):
    module = _load_adapter(monkeypatch, "connector")
    module.post_to_remote = MagicMock()

    response = module.connector(_request(body=[]))

    assert response.status_code == 400
    assert _body(response) == {
        "error": {
            "code": "INVALID_REQUEST",
            "message": "Request body must be a JSON object",
        }
    }
    module.post_to_remote.assert_not_called()


def test_ingestion_classifies_processor_transport_failure(
    monkeypatch,
    caplog,
):
    secret = "processor-transport-secret"
    monkeypatch.setenv("AZURE_TEST_SECRET", secret)
    module = _load_adapter(monkeypatch, "ingestion")
    module._inter_cloud_token = "expected-token"
    module.validate_token = MagicMock(return_value=True)
    module._invoke_processor = MagicMock(
        side_effect=urllib.error.URLError(secret)
    )

    response = module.ingestion(
        _request(
            body={
                "source_cloud": "aws",
                "payload": {"device_id": "sensor-1", "temperature": 20},
            }
        )
    )

    _assert_correlated_failure(
        response,
        caplog,
        status_code=502,
        code="UPSTREAM_ERROR",
        message="The processing service is unavailable.",
    )
    assert secret not in caplog.text
    assert secret not in response.get_body().decode("utf-8")


def test_ingestion_rejects_non_object_telemetry(monkeypatch):
    module = _load_adapter(monkeypatch, "ingestion")
    module._inter_cloud_token = "expected-token"
    module.validate_token = MagicMock(return_value=True)
    module._invoke_processor = MagicMock()

    response = module.ingestion(
        _request(body={"source_cloud": "aws", "payload": []})
    )

    assert response.status_code == 400
    assert _body(response) == {
        "error": {
            "code": "INVALID_REQUEST",
            "message": "Envelope payload must be a JSON object",
        }
    }
    module._invoke_processor.assert_not_called()


def test_event_feedback_requires_complete_routing_context(monkeypatch):
    module = _load_adapter(monkeypatch, "event_feedback_wrapper")
    module._get_registry_manager = MagicMock()

    response = module.main(
        _request(
            body={
                "detail": {
                    "payload": {"message": "hello"},
                    "iotDeviceId": "sensor-1",
                }
            }
        )
    )

    assert response.status_code == 400
    assert _body(response) == {
        "error": {
            "code": "INVALID_REQUEST",
            "message": (
                "Event detail must contain payload, iotDeviceId, "
                "and digitalTwinName"
            ),
        }
    }
    module._get_registry_manager.assert_not_called()


def test_inter_cloud_retry_logs_never_expose_downstream_diagnostics(
    monkeypatch,
    caplog,
):
    secret = "downstream-response-secret"
    monkeypatch.setenv("AZURE_TEST_SECRET", secret)
    sys.path.insert(0, str(AZURE_FUNCTIONS_ROOT))
    _clear_shared_modules()
    try:
        from _shared import inter_cloud

        error = urllib.error.HTTPError(
            "https://remote.example.test/ingestion?code=function-key",
            500,
            f"provider reason {secret}",
            hdrs=None,
            fp=io.BytesIO(
                json.dumps({"client_secret": secret}).encode("utf-8")
            ),
        )
        monkeypatch.setattr(
            inter_cloud,
            "safe_urlopen",
            MagicMock(side_effect=error),
        )
        with pytest.raises(urllib.error.HTTPError):
            inter_cloud.post_to_remote(
                url="https://remote.example.test/ingestion",
                token="expected-token",
                payload={"device_id": "sensor-1"},
                target_layer="L2",
                max_retries=0,
            )
    finally:
        sys.path.remove(str(AZURE_FUNCTIONS_ROOT))
        _clear_shared_modules()

    assert "status=500" in caplog.text
    assert secret not in caplog.text
    assert "function-key" not in caplog.text
    assert "client_secret" not in caplog.text
    assert "provider reason" not in caplog.text


def test_event_checker_partial_failure_uses_safe_reference(
    monkeypatch,
    caplog,
):
    secret = "event-action-secret"
    monkeypatch.setenv("AZURE_TEST_SECRET", secret)
    module = _load_adapter(monkeypatch, "event-checker")
    module._digital_twin_info = {
        "config_events": [
            {
                "condition": "sensor.temperature > INTEGER(5)",
                "action": {
                    "type": "function",
                    "functionName": "notify",
                    "private": secret,
                },
            }
        ]
    }
    module._invoke_function = MagicMock(
        side_effect=RuntimeError(f"{secret} code=signed-key")
    )

    response = module.event_checker(
        _request(body={"telemetry": {"temperature": 10}})
    )

    payload = _body(response)
    assert response.status_code == 200
    assert payload["checked"] == 1
    assert payload["results"][0]["event_index"] == 0
    assert payload["results"][0]["status"] == "failed"
    assert payload["results"][0]["error_code"] == "EVENT_ACTION_FAILED"
    correlation_id = payload["results"][0]["correlation_id"]
    uuid.UUID(correlation_id)
    assert correlation_id in caplog.text
    assert secret not in response.get_body().decode("utf-8")
    assert secret not in caplog.text
    assert "sensor.temperature" not in response.get_body().decode("utf-8")


def test_last_entry_provider_failure_is_not_reported_as_empty_success(
    monkeypatch,
    caplog,
):
    module = _load_adapter(monkeypatch, "hot-reader-last-entry")
    module._query_last_entry = MagicMock(
        side_effect=RuntimeError("provider failure")
    )
    request = _request(body={})
    request.headers = {"X-Inter-Cloud-Token": "expected-token"}

    response = module.hot_reader_last_entry(request)

    _assert_correlated_failure(response, caplog)
    assert "propertyValues" not in _body(response)


def test_last_entry_requires_configured_token_when_header_is_missing(
    monkeypatch,
):
    module = _load_adapter(monkeypatch, "hot-reader-last-entry")
    request = _request(body={})

    response = module.hot_reader_last_entry(request)

    assert response.status_code == 401
    assert _body(response) == {
        "error": {
            "code": "UNAUTHORIZED",
            "message": "Invalid or missing X-Inter-Cloud-Token",
        }
    }
    request.get_json.assert_not_called()


def test_http_adapters_do_not_embed_exception_values_in_responses():
    forbidden_names = {"e", "ex", "exc", "error", "exception"}
    for directory in HTTP_ADAPTERS:
        path = AZURE_FUNCTIONS_ROOT / directory / "function_app.py"
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for call in (
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "HttpResponse"
        ):
            response_source = ast.dump(call)
            for node in ast.walk(call):
                if isinstance(node, ast.Name):
                    assert node.id not in forbidden_names, (
                        f"{path} embeds exception variable {node.id} in "
                        f"HttpResponse: {response_source}"
                    )


def test_http_adapters_use_static_public_error_codes_and_messages():
    helper_names = {"error_response", "failure_response"}
    for directory in HTTP_ADAPTERS:
        path = AZURE_FUNCTIONS_ROOT / directory / "function_app.py"
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for call in (
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id in helper_names
        ):
            keyword_values = {
                keyword.arg: keyword.value
                for keyword in call.keywords
                if keyword.arg in {"code", "message"}
            }
            for keyword, value in keyword_values.items():
                assert isinstance(value, ast.Constant) and isinstance(
                    value.value, str
                ), (
                    f"{path} uses a dynamic public {keyword} in "
                    f"{call.func.id}: {ast.dump(value)}"
                )


def test_http_adapters_do_not_log_unredacted_tracebacks():
    for directory in HTTP_ADAPTERS:
        path = AZURE_FUNCTIONS_ROOT / directory / "function_app.py"
        source = path.read_text(encoding="utf-8")
        assert "logging.exception" not in source
        assert "logger.exception" not in source
        assert "remote_response" not in source
