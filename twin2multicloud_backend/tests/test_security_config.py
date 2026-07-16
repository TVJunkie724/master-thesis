"""Security boundary tests for Management API runtime settings."""

import base64
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from src.config import AppEnvironment, Settings


VALID_JWT_SECRET = "production-jwt-secret-with-at-least-32-characters"
VALID_ENCRYPTION_KEY = base64.urlsafe_b64encode(b"e" * 32).decode("ascii")


def _settings(**overrides) -> Settings:
    values = {
        "APP_ENV": AppEnvironment.PRODUCTION,
        "DEBUG": False,
        "DEV_AUTH_ENABLED": False,
        "DEV_AUTH_TOKEN": "",
        "ENABLE_TEST_ENDPOINTS": False,
        "SEED_DATA": False,
        "JWT_SECRET_KEY": VALID_JWT_SECRET,
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
        ({"DEV_AUTH_ENABLED": True, "DEV_AUTH_TOKEN": "token"}, "DEV_AUTH_ENABLED"),
        ({"ENABLE_TEST_ENDPOINTS": True}, "ENABLE_TEST_ENDPOINTS"),
        ({"SEED_DATA": True}, "SEED_DATA"),
        ({"JWT_SECRET_KEY": "short"}, "JWT_SECRET_KEY"),
        ({"ENCRYPTION_KEY": "short"}, "ENCRYPTION_KEY"),
        (
            {"JWT_SECRET_KEY": "local-development-jwt-secret-change-me"},
            "known insecure placeholder",
        ),
        (
            {"ENCRYPTION_KEY": "local-development-encryption-key-change-me"},
            "known insecure placeholder",
        ),
        (
            {
                "JWT_SECRET_KEY": VALID_ENCRYPTION_KEY,
                "ENCRYPTION_KEY": VALID_ENCRYPTION_KEY,
            },
            "must be different",
        ),
        ({"ENCRYPTION_KEY": "x" * 44}, "exactly 32 bytes"),
        ({"JWT_SECRET_KEY": ("j" * 40) + " "}, "surrounding whitespace"),
        (
            {"ENCRYPTION_KEY": base64.b64encode(bytes([251]) * 32).decode("ascii")},
            "URL-safe base64",
        ),
    ],
)
def test_production_rejects_insecure_runtime_configuration(override, message):
    with pytest.raises(ValidationError, match=message):
        _settings(**override)


def test_development_requires_explicit_dev_auth_token():
    with pytest.raises(ValidationError, match="DEV_AUTH_TOKEN"):
        _settings(
            APP_ENV=AppEnvironment.DEVELOPMENT,
            JWT_SECRET_KEY=VALID_JWT_SECRET,
            ENCRYPTION_KEY=VALID_ENCRYPTION_KEY,
            DEV_AUTH_ENABLED=True,
            DEV_AUTH_TOKEN="",
        )


def test_production_accepts_closed_runtime_with_strong_secrets():
    configured = _settings()

    assert configured.APP_ENV == AppEnvironment.PRODUCTION
    assert configured.DEBUG is False
    assert configured.DEV_AUTH_ENABLED is False
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


@pytest.mark.parametrize(
    ("field", "message"),
    [
        ("JWT_SECRET_KEY", "JWT_SECRET_KEY"),
        ("ENCRYPTION_KEY", "ENCRYPTION_KEY"),
    ],
)
def test_every_environment_requires_runtime_secrets(field, message):
    values = {
        "APP_ENV": AppEnvironment.DEVELOPMENT,
        "JWT_SECRET_KEY": VALID_JWT_SECRET,
        "ENCRYPTION_KEY": VALID_ENCRYPTION_KEY,
    }
    values[field] = ""

    with pytest.raises(ValidationError, match=message):
        Settings(_env_file=None, **values)


def test_runtime_secrets_load_from_file_secret_directory():
    with tempfile.TemporaryDirectory() as temp_dir:
        secrets_dir = Path(temp_dir)
        (secrets_dir / "JWT_SECRET_KEY").write_text(
            f"{VALID_JWT_SECRET}\n",
            encoding="utf-8",
        )
        (secrets_dir / "ENCRYPTION_KEY").write_text(
            f"{VALID_ENCRYPTION_KEY}\n",
            encoding="utf-8",
        )

        with patch.dict(os.environ, {}, clear=True):
            configured = Settings(
                _env_file=None,
                _secrets_dir=secrets_dir,
                APP_ENV=AppEnvironment.DEVELOPMENT,
            )

    assert configured.JWT_SECRET_KEY == VALID_JWT_SECRET
    assert configured.ENCRYPTION_KEY == VALID_ENCRYPTION_KEY


def test_environment_secrets_override_file_secret_directory():
    file_jwt = "file-jwt-secret-with-at-least-32-characters"
    file_encryption = base64.urlsafe_b64encode(b"f" * 32).decode("ascii")
    with tempfile.TemporaryDirectory() as temp_dir:
        secrets_dir = Path(temp_dir)
        (secrets_dir / "JWT_SECRET_KEY").write_text(file_jwt, encoding="utf-8")
        (secrets_dir / "ENCRYPTION_KEY").write_text(
            file_encryption,
            encoding="utf-8",
        )
        with patch.dict(
            os.environ,
            {
                "JWT_SECRET_KEY": VALID_JWT_SECRET,
                "ENCRYPTION_KEY": VALID_ENCRYPTION_KEY,
            },
            clear=False,
        ):
            configured = Settings(
                _env_file=None,
                _secrets_dir=secrets_dir,
                APP_ENV=AppEnvironment.DEVELOPMENT,
            )

    assert configured.JWT_SECRET_KEY == VALID_JWT_SECRET
    assert configured.ENCRYPTION_KEY == VALID_ENCRYPTION_KEY
