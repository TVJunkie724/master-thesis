"""Security boundary tests for Management API runtime settings."""

import base64
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from src.config import AppEnvironment, Settings


VALID_ENCRYPTION_KEY = base64.urlsafe_b64encode(b"e" * 32).decode("ascii")


def _settings(**overrides) -> Settings:
    values = {
        "APP_ENV": AppEnvironment.PRODUCTION,
        "DEBUG": False,
        "POC_AUTH_TOKEN": "opaque-poc-token",
        "ENABLE_TEST_ENDPOINTS": False,
        "SEED_DATA": False,
        "ENCRYPTION_KEY": VALID_ENCRYPTION_KEY,
        "CREDENTIAL_RATE_LIMIT_STORAGE_URI": "rediss://rate-limit.example.test:6379/0",
        "CORS_ORIGINS": "https://app.example.test",
        "REQUIRE_HTTPS": True,
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


@pytest.mark.parametrize(
    ("override", "message"),
    [
        ({"DEBUG": True}, "DEBUG must be false"),
        ({"ENABLE_TEST_ENDPOINTS": True}, "ENABLE_TEST_ENDPOINTS"),
        ({"SEED_DATA": True}, "SEED_DATA"),
        ({"POC_AUTH_TOKEN": ""}, "POC_AUTH_TOKEN"),
        ({"POC_AUTH_TOKEN": "bad token"}, "opaque value"),
        ({"POC_USER_EMAIL": "not-an-email"}, "POC_USER_EMAIL"),
        ({"POC_USER_NAME": "  "}, "POC_USER_NAME"),
        ({"ENCRYPTION_KEY": "short"}, "ENCRYPTION_KEY"),
        (
            {"ENCRYPTION_KEY": "local-development-encryption-key-change-me"},
            "known insecure placeholder",
        ),
        ({"ENCRYPTION_KEY": "x" * 44}, "exactly 32 bytes"),
        (
            {"ENCRYPTION_KEY": base64.b64encode(bytes([251]) * 32).decode("ascii")},
            "URL-safe base64",
        ),
    ],
)
def test_production_rejects_insecure_runtime_configuration(override, message):
    with pytest.raises(ValidationError, match=message):
        _settings(**override)


def test_production_accepts_hardened_transport_and_credential_storage():
    configured = _settings()

    assert configured.APP_ENV == AppEnvironment.PRODUCTION
    assert configured.DEBUG is False
    assert configured.ENABLE_TEST_ENDPOINTS is False
    assert configured.REQUIRE_HTTPS is True


@pytest.mark.parametrize(
    ("override", "message"),
    [
        ({"CREDENTIAL_RATE_LIMIT_ENABLED": False}, "must be true"),
        ({"CREDENTIAL_RATE_LIMIT_STORAGE_URI": "memory://"}, "must use redis"),
        ({"REQUIRE_HTTPS": False}, "REQUIRE_HTTPS must be true"),
        ({"CORS_ORIGINS": "http://app.example.test"}, "only explicit HTTPS origins"),
        ({"CORS_ORIGINS": "*"}, "only explicit HTTPS origins"),
        ({"TRUSTED_PROXY_CIDRS": "not-a-network"}, "invalid network"),
        ({"CREDENTIAL_WRITE_RATE_LIMIT": "zero"}, "positive integer"),
    ],
)
def test_production_rejects_disabled_or_unsafe_credential_controls(override, message):
    with pytest.raises(ValidationError, match=message):
        _settings(**override)


def test_every_environment_requires_encryption_key_and_poc_bearer():
    for field in ("ENCRYPTION_KEY", "POC_AUTH_TOKEN"):
        values = {
            "APP_ENV": AppEnvironment.DEVELOPMENT,
            "POC_AUTH_TOKEN": "opaque-poc-token",
            "ENCRYPTION_KEY": VALID_ENCRYPTION_KEY,
        }
        values[field] = ""
        with pytest.raises(ValidationError, match=field):
            Settings(_env_file=None, **values)


def test_encryption_key_loads_from_file_secret_directory():
    with tempfile.TemporaryDirectory() as temp_dir:
        secrets_dir = Path(temp_dir)
        (secrets_dir / "ENCRYPTION_KEY").write_text(
            f"{VALID_ENCRYPTION_KEY}\n", encoding="utf-8"
        )
        with patch.dict(os.environ, {}, clear=True):
            configured = Settings(
                _env_file=None,
                _secrets_dir=secrets_dir,
                APP_ENV=AppEnvironment.DEVELOPMENT,
                POC_AUTH_TOKEN="opaque-poc-token",
            )

    assert configured.ENCRYPTION_KEY == VALID_ENCRYPTION_KEY
