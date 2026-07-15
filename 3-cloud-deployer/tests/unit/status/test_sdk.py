from types import SimpleNamespace

from src.status import sdk


class _Provider:
    def __init__(self, name):
        self.name = name
        self.initialized = False

    def initialize_clients(self, credentials, twin_name):
        assert credentials
        assert twin_name == "factory"
        self.initialized = True

    def info_l1(self, context):
        assert self.initialized
        return {"devices": {"device-1": True}}

    def info_l4(self, context):
        assert self.initialized
        return {"twins": {"factory": True}}

    def info_l5(self, context):
        assert self.initialized
        return {"workspace": True}


def _context():
    return SimpleNamespace(
        config=SimpleNamespace(
            digital_twin_name="factory",
            providers={
                "layer_1_provider": "aws",
                "layer_4_provider": "azure",
                "layer_5_provider": "none",
            },
        ),
        credentials={"aws": {"key": "aws"}, "azure": {"key": "azure"}},
        providers={},
    )


def test_sdk_status_uses_each_configured_layer_owner(monkeypatch):
    instances = {}
    monkeypatch.setattr(sdk, "create_context", lambda project_name: _context())

    def provider(name):
        instances[name] = _Provider(name)
        return instances[name]

    monkeypatch.setattr(sdk.ProviderRegistry, "get", provider)

    result = sdk.check_sdk_managed("factory", "aws")

    assert result["status"] == "all_deployed"
    assert result["iot_devices"]["provider"] == "aws"
    assert result["twin_management"]["provider"] == "azure"
    assert result["visualization"]["status"] == "not_configured"
    assert set(instances) == {"aws", "azure"}


def test_sdk_errors_are_redacted(monkeypatch):
    context = _context()
    context.config.providers["layer_4_provider"] = "none"
    monkeypatch.setattr(sdk, "create_context", lambda project_name: context)

    def fail(name):
        raise RuntimeError("api_key=sensitive-value")

    monkeypatch.setattr(sdk.ProviderRegistry, "get", fail)

    result = sdk.check_sdk_managed("factory")

    assert result["status"] == "error"
    assert "sensitive-value" not in result["iot_devices"]["message"]
    assert "<redacted>" in result["iot_devices"]["message"]


def test_sdk_details_redact_structured_secret_fields(monkeypatch):
    class SecretProvider(_Provider):
        def info_l1(self, context):
            return {"api_key": "structured-secret", "devices": {}}

    context = _context()
    context.config.providers["layer_4_provider"] = "none"
    monkeypatch.setattr(sdk, "create_context", lambda project_name: context)
    monkeypatch.setattr(sdk.ProviderRegistry, "get", lambda name: SecretProvider(name))

    result = sdk.check_sdk_managed("factory")

    details = result["iot_devices"]["details"]
    assert details["api_key"] == "<redacted>"
