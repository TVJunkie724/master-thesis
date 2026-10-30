"""Host-side PoC authentication must not become an implicit Azure deployment."""
import json

import pytest

from src.tfvars_generator import ConfigurationError, _load_auxiliary_azure_auth


@pytest.fixture
def configured_file(tmp_path, monkeypatch):
    path = tmp_path / "provider-auth.json"
    payload = {"azure": {
        "azure_subscription_id": "test-subscription",
        "azure_client_id": "test-client",
        "azure_client_secret": "test-secret-not-real",
        "azure_tenant_id": "test-tenant",
        "azure_region": "must-not-override-placement",
    }, "aws": {"aws_secret_access_key": "must-not-propagate"}}
    path.write_text(json.dumps(payload))
    monkeypatch.setenv("TF_AZURE_PROVIDER_AUTH_FILE", str(path))
    return path, payload


def test_disabled_by_default(monkeypatch):
    monkeypatch.delenv("TF_AZURE_PROVIDER_AUTH_FILE", raising=False)
    assert _load_auxiliary_azure_auth(azure_selected=False, tfvars={}) == {}


def test_only_auth_fields_without_mutating_inputs(configured_file):
    _, payload = configured_file
    values = {"layer_1_provider": "aws", "azure_region": "westeurope"}
    result = _load_auxiliary_azure_auth(azure_selected=False, tfvars=values)
    assert set(result) == {"azure_subscription_id", "azure_client_id",
                           "azure_client_secret", "azure_tenant_id"}
    assert result["azure_client_id"] == payload["azure"]["azure_client_id"]
    assert values == {"layer_1_provider": "aws", "azure_region": "westeurope"}


@pytest.mark.parametrize("selected,values", [
    (True, {}), (False, {"azure_client_secret": "project-owned"}),
])
def test_never_replace_graph_or_project_credentials(configured_file, selected, values):
    path, _ = configured_file
    path.unlink()  # Must not even open the unrelated host credential file.
    assert _load_auxiliary_azure_auth(azure_selected=selected, tfvars=values) == {}


@pytest.mark.parametrize("content", ["not json", "{}", "null", "[]",
    '{"azure": null}', '{"azure": {}}', "x" * 65537])
def test_invalid_file_fails_without_exposing_content(configured_file, content):
    path, _ = configured_file
    path.write_text(content)
    with pytest.raises(ConfigurationError) as caught:
        _load_auxiliary_azure_auth(azure_selected=False, tfvars={})
    assert str(caught.value).startswith("TF_AZURE_PROVIDER_AUTH_FILE requires")
    assert str(path) not in str(caught.value)


@pytest.mark.parametrize("value", [None, "", "  ", 42, {}])
def test_nonempty_strings_required(configured_file, value):
    path, payload = configured_file
    payload["azure"]["azure_client_secret"] = value
    path.write_text(json.dumps(payload))
    with pytest.raises(ConfigurationError):
        _load_auxiliary_azure_auth(azure_selected=False, tfvars={})


def test_missing_file_has_safe_error(configured_file):
    path, _ = configured_file
    path.unlink()
    with pytest.raises(ConfigurationError, match="TF_AZURE_PROVIDER_AUTH_FILE requires"):
        _load_auxiliary_azure_auth(azure_selected=False, tfvars={})
