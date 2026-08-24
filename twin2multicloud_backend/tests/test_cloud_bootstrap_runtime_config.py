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
    both = _settings(
        CLOUD_BOOTSTRAP_ADAPTER_MODE="supervised_live",
        CLOUD_BOOTSTRAP_SUPERVISED_PROVIDERS="aws,azure",
    )

    assert azure.cloud_bootstrap_supervised_providers == ("azure",)
    assert both.cloud_bootstrap_supervised_providers == ("aws", "azure")


@pytest.mark.parametrize("providers", ["gcp", "aws,aws", "azure,azure"])
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
