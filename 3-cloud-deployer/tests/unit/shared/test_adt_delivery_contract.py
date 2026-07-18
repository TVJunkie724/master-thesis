"""Provider contract tests for the canonical Persister-to-ADT-Pusher path."""

import importlib.util
import json
import sys
import uuid
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


DEPLOYER_ROOT = Path(__file__).resolve().parents[3]
PROVIDER_CONFIG_NAMES = {
    "aws": "aws",
    "azure": "azure",
    "gcp": "google",
}
PERSISTER_PATHS = {
    "aws": DEPLOYER_ROOT
    / "src/providers/aws/lambda_functions/persister/lambda_function.py",
    "azure": DEPLOYER_ROOT
    / "src/providers/azure/azure_functions/persister/function_app.py",
    "gcp": DEPLOYER_ROOT
    / "src/providers/gcp/cloud_functions/persister/main.py",
}
FUNCTION_ROOTS = {
    "aws": DEPLOYER_ROOT / "src/providers/aws/lambda_functions",
    "azure": DEPLOYER_ROOT / "src/providers/azure/azure_functions",
    "gcp": DEPLOYER_ROOT / "src/providers/gcp/cloud_functions",
}
PROVIDERS = tuple(PERSISTER_PATHS)


def _clear_shared_modules() -> None:
    for module_name in list(sys.modules):
        if module_name == "_shared" or module_name.startswith("_shared."):
            del sys.modules[module_name]


def _load_persister(
    provider: str,
    monkeypatch: pytest.MonkeyPatch,
    *,
    layer_4_provider: str = "azure",
    include_provider_mapping: bool = True,
    pusher_url: str | None = "https://example.test/api/adt-pusher",
    pusher_token: str | None = "test-token",
):
    provider_name = PROVIDER_CONFIG_NAMES[provider]
    digital_twin_info = {
        "config": {"digital_twin_name": "test-twin"},
    }
    if include_provider_mapping:
        digital_twin_info["config_providers"] = {
            "layer_2_provider": provider_name,
            "layer_3_hot_provider": provider_name,
            "layer_4_provider": layer_4_provider,
        }

    monkeypatch.setenv("DIGITAL_TWIN_INFO", json.dumps(digital_twin_info))
    monkeypatch.setenv("DYNAMODB_TABLE_NAME", "test-table")
    monkeypatch.setenv("COSMOS_DB_ENDPOINT", "https://cosmos.example.test")
    monkeypatch.setenv("COSMOS_DB_KEY", "test-key")
    monkeypatch.setenv("COSMOS_DB_DATABASE", "test-database")
    monkeypatch.setenv("COSMOS_DB_CONTAINER", "test-container")
    monkeypatch.setenv("FIRESTORE_COLLECTION", "hot_data")
    monkeypatch.setenv("USE_EVENT_CHECKING", "false")
    monkeypatch.delenv("REMOTE_WRITER_URL", raising=False)

    if pusher_url is None:
        monkeypatch.delenv("REMOTE_ADT_PUSHER_URL", raising=False)
    else:
        monkeypatch.setenv("REMOTE_ADT_PUSHER_URL", pusher_url)
    if pusher_token is None:
        monkeypatch.delenv("ADT_PUSHER_TOKEN", raising=False)
    else:
        monkeypatch.setenv("ADT_PUSHER_TOKEN", pusher_token)

    function_root = str(FUNCTION_ROOTS[provider])
    _clear_shared_modules()
    sys.path.insert(0, function_root)
    try:
        module_name = f"test_{provider}_persister_{id(monkeypatch)}"
        spec = importlib.util.spec_from_file_location(
            module_name,
            PERSISTER_PATHS[provider],
        )
        module = importlib.util.module_from_spec(spec)
        with patch("boto3.client"), patch("boto3.resource"):
            spec.loader.exec_module(module)
        return module
    finally:
        sys.path.remove(function_root)
        _clear_shared_modules()


@pytest.mark.parametrize("provider", PROVIDERS)
def test_settings_require_azure_l4_and_valid_https_configuration(
    provider,
    monkeypatch,
):
    module = _load_persister(provider, monkeypatch)
    assert module._get_adt_delivery_settings() == (
        "https://example.test/api/adt-pusher",
        "test-token",
    )


@pytest.mark.parametrize("provider", PROVIDERS)
def test_non_azure_l4_skips_stale_pusher_configuration(provider, monkeypatch):
    module = _load_persister(
        provider,
        monkeypatch,
        layer_4_provider="aws",
    )
    assert module._get_adt_delivery_settings() is None

    with patch.object(module, "post_to_remote") as post_to_remote:
        module._push_to_adt(
            {
                "device_id": "sensor-1",
                "timestamp": "2026-01-01T00:00:00Z",
                "telemetry": {"temperature": 20},
            }
        )
    post_to_remote.assert_not_called()


@pytest.mark.parametrize("provider", PROVIDERS)
def test_missing_provider_mapping_fails_closed(provider, monkeypatch):
    module = _load_persister(
        provider,
        monkeypatch,
        include_provider_mapping=False,
    )
    with pytest.raises(module.ConfigurationError, match="config_providers"):
        module._get_adt_delivery_settings()


@pytest.mark.parametrize("provider", PROVIDERS)
@pytest.mark.parametrize(
    ("pusher_url", "pusher_token", "message"),
    [
        (None, "test-token", "REMOTE_ADT_PUSHER_URL"),
        ("https://example.test/api/adt-pusher", None, "ADT_PUSHER_TOKEN"),
        ("http://example.test/api/adt-pusher", "test-token", "HTTPS"),
    ],
)
def test_azure_l4_rejects_incomplete_or_unsafe_configuration(
    provider,
    monkeypatch,
    pusher_url,
    pusher_token,
    message,
):
    module = _load_persister(
        provider,
        monkeypatch,
        pusher_url=pusher_url,
        pusher_token=pusher_token,
    )
    with pytest.raises(module.ConfigurationError, match=message):
        module._get_adt_delivery_settings()


@pytest.mark.parametrize("provider", PROVIDERS)
def test_payload_contract_is_identical_across_providers(provider, monkeypatch):
    module = _load_persister(provider, monkeypatch)
    event = {
        "device_id": "sensor-1",
        "device_type": "temperature-sensor",
        "timestamp": "2026-01-01T00:00:00Z",
        "telemetry": {"temperature": 20.5},
    }

    assert module._build_adt_payload(event) == {
        "device_id": "sensor-1",
        "device_type": "temperature-sensor",
        "timestamp": "2026-01-01T00:00:00Z",
        "telemetry": {"temperature": 20.5},
    }


@pytest.mark.parametrize("provider", PROVIDERS)
def test_payload_contract_normalizes_root_telemetry(provider, monkeypatch):
    module = _load_persister(provider, monkeypatch)
    payload = module._build_adt_payload(
        {
            "device_id": "sensor-1",
            "timestamp": "2026-01-01T00:00:00Z",
            "temperature": 20.5,
            "humidity": 55,
        }
    )
    assert payload["telemetry"] == {"temperature": 20.5, "humidity": 55}


@pytest.mark.parametrize("provider", PROVIDERS)
@pytest.mark.parametrize("telemetry", [None, {}, [], "invalid"])
def test_payload_contract_rejects_empty_or_non_object_telemetry(
    provider,
    monkeypatch,
    telemetry,
):
    module = _load_persister(provider, monkeypatch)
    event = {
        "device_id": "sensor-1",
        "timestamp": "2026-01-01T00:00:00Z",
        "telemetry": telemetry,
    }
    with pytest.raises(ValueError, match="non-empty object"):
        module._build_adt_payload(event)


@pytest.mark.parametrize("provider", PROVIDERS)
def test_delivery_failure_is_stable_and_does_not_log_raw_error(
    provider,
    monkeypatch,
    caplog,
    capsys,
):
    module = _load_persister(provider, monkeypatch)
    event = {
        "device_id": "sensor-1",
        "timestamp": "2026-01-01T00:00:00Z",
        "telemetry": {"temperature": 20.5},
    }
    leaked_text = "secret-token-should-not-leak"

    with patch.object(
        module,
        "post_to_remote",
        side_effect=RuntimeError(leaked_text),
    ):
        with pytest.raises(
            module.AdtDeliveryError,
            match="Azure Digital Twins update failed",
        ):
            module._push_to_adt(event)

    diagnostics = capsys.readouterr().out + caplog.text
    assert leaked_text not in diagnostics


def test_aws_retry_reuses_the_same_storage_key(monkeypatch):
    module = _load_persister("aws", monkeypatch)
    table = MagicMock()
    module._get_dynamodb_table = MagicMock(return_value=table)
    module.post_to_remote = MagicMock(side_effect=RuntimeError("unavailable"))
    event = {
        "device_id": "sensor-1",
        "timestamp": "2026-01-01T00:00:00Z",
        "telemetry": {"temperature": 20.5},
    }

    for _ in range(2):
        with pytest.raises(module.AdtDeliveryError):
            module.lambda_handler(event, None)

    items = [call.kwargs["Item"] for call in table.put_item.call_args_list]
    assert [item["id"] for item in items] == [
        "sensor-1_2026-01-01T00:00:00Z",
        "sensor-1_2026-01-01T00:00:00Z",
    ]


def test_aws_rejects_invalid_adt_payload_before_storage(monkeypatch):
    module = _load_persister("aws", monkeypatch)
    table = MagicMock()
    module._get_dynamodb_table = MagicMock(return_value=table)

    with pytest.raises(ValueError, match="non-empty object"):
        module.lambda_handler(
            {
                "device_id": "sensor-1",
                "timestamp": "2026-01-01T00:00:00Z",
                "telemetry": {},
            },
            None,
        )

    table.put_item.assert_not_called()


def test_azure_retry_reuses_the_same_storage_key(monkeypatch):
    module = _load_persister("azure", monkeypatch)
    container = MagicMock()
    module._get_cosmos_container = MagicMock(return_value=container)
    module.post_to_remote = MagicMock(side_effect=RuntimeError("unavailable"))
    request = MagicMock()
    request.get_json.return_value = {
        "device_id": "sensor-1",
        "timestamp": "2026-01-01T00:00:00Z",
        "telemetry": {"temperature": 20.5},
    }

    responses = [module.persister(request), module.persister(request)]

    assert [response.status_code for response in responses] == [502, 502]
    items = [call.args[0] for call in container.upsert_item.call_args_list]
    assert [item["id"] for item in items] == [
        "sensor-1_2026-01-01T00:00:00Z",
        "sensor-1_2026-01-01T00:00:00Z",
    ]


def test_azure_rejects_invalid_adt_payload_before_storage(monkeypatch):
    module = _load_persister("azure", monkeypatch)
    container = MagicMock()
    module._get_cosmos_container = MagicMock(return_value=container)
    request = MagicMock()
    request.get_json.return_value = {
        "device_id": "sensor-1",
        "timestamp": "2026-01-01T00:00:00Z",
        "telemetry": {},
    }

    response = module.persister(request)

    assert response.status_code == 400
    assert json.loads(response.get_body()) == {
        "error": {
            "code": "INVALID_REQUEST",
            "message": "Invalid telemetry payload",
        },
    }
    container.upsert_item.assert_not_called()


def test_azure_configuration_error_uses_stable_response(monkeypatch):
    module = _load_persister(
        "azure",
        monkeypatch,
        include_provider_mapping=False,
    )
    container = MagicMock()
    module._get_cosmos_container = MagicMock(return_value=container)
    response = module.persister(MagicMock())

    assert response.status_code == 500
    payload = json.loads(response.get_body())
    assert payload["error"]["code"] == "CONFIGURATION_ERROR"
    assert payload["error"]["message"] == (
        "Persister configuration is unavailable."
    )
    uuid.UUID(payload["error"]["correlation_id"])
    container.upsert_item.assert_not_called()


def test_gcp_retry_reuses_the_same_storage_key(monkeypatch):
    module = _load_persister("gcp", monkeypatch)
    firestore_client = MagicMock()
    document = firestore_client.collection.return_value.document.return_value
    module._get_firestore_client = MagicMock(return_value=firestore_client)
    module.post_to_remote = MagicMock(side_effect=RuntimeError("unavailable"))
    request = MagicMock()
    request.get_json.return_value = {
        "device_id": "sensor-1",
        "timestamp": "2026-01-01T00:00:00Z",
        "telemetry": {"temperature": 20.5},
    }

    responses = [module.main(request), module.main(request)]

    assert [response[1] for response in responses] == [502, 502]
    assert [call.args[0] for call in document.set.call_args_list] == [
        {
            "device_id": "sensor-1",
            "timestamp": "2026-01-01T00:00:00Z",
            "telemetry": {"temperature": 20.5},
            "id": "sensor-1_2026-01-01T00:00:00Z",
        },
        {
            "device_id": "sensor-1",
            "timestamp": "2026-01-01T00:00:00Z",
            "telemetry": {"temperature": 20.5},
            "id": "sensor-1_2026-01-01T00:00:00Z",
        },
    ]


def test_gcp_rejects_invalid_adt_payload_before_storage(monkeypatch):
    module = _load_persister("gcp", monkeypatch)
    firestore_client = MagicMock()
    document = firestore_client.collection.return_value.document.return_value
    module._get_firestore_client = MagicMock(return_value=firestore_client)
    request = MagicMock()
    request.get_json.return_value = {
        "device_id": "sensor-1",
        "timestamp": "2026-01-01T00:00:00Z",
        "telemetry": {},
    }

    response = module.main(request)

    assert response[1] == 400
    assert json.loads(response[0]) == {"error": "Invalid telemetry payload"}
    document.set.assert_not_called()


def test_gcp_configuration_error_uses_stable_response(monkeypatch):
    module = _load_persister(
        "gcp",
        monkeypatch,
        include_provider_mapping=False,
    )
    firestore_client = MagicMock()
    module._get_firestore_client = MagicMock(return_value=firestore_client)
    response = module.main(MagicMock())

    assert response[1] == 500
    assert json.loads(response[0]) == {"error": "Configuration error"}
    firestore_client.collection.assert_not_called()
