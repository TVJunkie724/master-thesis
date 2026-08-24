import pytest
from pydantic import ValidationError

from src.config import Settings, settings


def _settings(**overrides):
    values = settings.model_dump()
    values.update(overrides)
    return Settings(**values)


def test_supervised_aws_is_explicit_and_disabled_mode_has_no_provider():
    live = _settings(
        CLOUD_BOOTSTRAP_ADAPTER_MODE="supervised_live",
        CLOUD_BOOTSTRAP_SUPERVISED_PROVIDERS="aws",
    )
    disabled = _settings(
        CLOUD_BOOTSTRAP_ADAPTER_MODE="disabled",
        CLOUD_BOOTSTRAP_SUPERVISED_PROVIDERS="",
    )

    assert live.cloud_bootstrap_supervised_providers == ("aws",)
    assert disabled.cloud_bootstrap_supervised_providers == ()


def test_supervised_providers_can_be_enabled_independently_or_together():
    azure = _settings(
        CLOUD_BOOTSTRAP_ADAPTER_MODE="supervised_live",
        CLOUD_BOOTSTRAP_SUPERVISED_PROVIDERS="azure",
    )
    all_providers = _settings(
        CLOUD_BOOTSTRAP_ADAPTER_MODE="supervised_live",
        CLOUD_BOOTSTRAP_SUPERVISED_PROVIDERS="aws,azure,gcp",
    )

    assert azure.cloud_bootstrap_supervised_providers == ("azure",)
    assert all_providers.cloud_bootstrap_supervised_providers == (
        "aws",
        "azure",
        "gcp",
    )


@pytest.mark.parametrize("providers", ["oracle", "aws,aws", "azure,azure", "gcp,gcp"])
def test_unimplemented_or_duplicate_supervised_provider_fails_startup(providers):
    with pytest.raises(ValidationError, match="SUPERVISED_PROVIDERS"):
        _settings(
            CLOUD_BOOTSTRAP_ADAPTER_MODE="supervised_live",
            CLOUD_BOOTSTRAP_SUPERVISED_PROVIDERS=providers,
        )


def test_provider_allowlist_cannot_be_ignored_by_an_offline_mode():
    with pytest.raises(ValidationError, match="requires supervised_live"):
        _settings(
            CLOUD_BOOTSTRAP_ADAPTER_MODE="deterministic_fake",
            CLOUD_BOOTSTRAP_SUPERVISED_PROVIDERS="aws",
        )


def test_setup_gate_defaults_closed_and_cannot_be_enabled_in_ci(monkeypatch):
    assert _settings().CLOUD_BOOTSTRAP_SETUP_GATE_ENABLED is False
    monkeypatch.setenv("CI", "true")
    with pytest.raises(ValidationError, match="forbidden in CI"):
        _settings(CLOUD_BOOTSTRAP_SETUP_GATE_ENABLED=True)
