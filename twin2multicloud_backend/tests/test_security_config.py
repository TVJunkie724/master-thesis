"""Security boundary tests for Management API runtime settings."""

import pytest
from pydantic import ValidationError

from src.config import AppEnvironment, Settings


def _settings(**overrides) -> Settings:
    values = {
        "APP_ENV": AppEnvironment.PRODUCTION,
        "DEBUG": False,
        "DEV_AUTH_ENABLED": False,
        "DEV_AUTH_TOKEN": "",
        "ENABLE_TEST_ENDPOINTS": False,
        "SEED_DATA": False,
        "JWT_SECRET_KEY": "production-jwt-secret-with-at-least-32-characters",
        "ENCRYPTION_KEY": "production-encryption-key-with-at-least-32-characters",
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


@pytest.mark.parametrize(
    ("override", "message"),
    [
        ({"DEBUG": True}, "DEBUG must be false"),
        ({"DEV_AUTH_ENABLED": True, "DEV_AUTH_TOKEN": "token"}, "DEV_AUTH_ENABLED"),
        ({"ENABLE_TEST_ENDPOINTS": True}, "ENABLE_TEST_ENDPOINTS"),
        ({"SEED_DATA": True}, "SEED_DATA"),
        ({"JWT_SECRET_KEY": "short"}, "JWT_SECRET_KEY"),
        ({"ENCRYPTION_KEY": "short"}, "ENCRYPTION_KEY"),
    ],
)
def test_production_rejects_insecure_runtime_configuration(override, message):
    with pytest.raises(ValidationError, match=message):
        _settings(**override)


def test_development_requires_explicit_dev_auth_token():
    with pytest.raises(ValidationError, match="DEV_AUTH_TOKEN"):
        _settings(
            APP_ENV=AppEnvironment.DEVELOPMENT,
            JWT_SECRET_KEY="local",
            ENCRYPTION_KEY="local",
            DEV_AUTH_ENABLED=True,
            DEV_AUTH_TOKEN="",
        )


def test_production_accepts_closed_runtime_with_strong_secrets():
    configured = _settings()

    assert configured.APP_ENV == AppEnvironment.PRODUCTION
    assert configured.DEBUG is False
    assert configured.DEV_AUTH_ENABLED is False
    assert configured.ENABLE_TEST_ENDPOINTS is False
