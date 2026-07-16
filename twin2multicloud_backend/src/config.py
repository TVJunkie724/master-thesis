import base64
import binascii
import ipaddress
import re
from enum import StrEnum
from pathlib import Path
from urllib.parse import urlparse

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppEnvironment(StrEnum):
    DEVELOPMENT = "development"
    TEST = "test"
    PRODUCTION = "production"


KNOWN_INSECURE_SECRET_VALUES = {
    "local-development-jwt-secret-change-me",
    "local-development-encryption-key-change-me",
    "your-secret-key-change-in-production",
    "your-fernet-key-here",
    "dev-secret-change-in-production",
    "dev-secret-key",
}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        secrets_dir="/run/secrets" if Path("/run/secrets").is_dir() else None,
    )

    APP_ENV: AppEnvironment = AppEnvironment.PRODUCTION

    # Database
    DATABASE_URL: str = "sqlite:///./data/app.db"
    
    # JWT
    JWT_SECRET_KEY: str = ""
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 60
    
    # Google OAuth
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_REDIRECT_URI: str = "http://localhost:5005/auth/google/callback"
    
    # Frontend callback URL (configurable per environment)
    FRONTEND_CALLBACK_URL: str = "http://localhost:8080/auth/callback"
    
    # UIBK SAML Configuration
    # Enable after ACOnet registration is complete
    SAML_ENABLED: bool = False
    SAML_SP_ENTITY_ID: str = "http://localhost:5005"  # Local dev default
    SAML_ACS_URL: str = "http://localhost:5005/auth/uibk/callback"  # Assertion Consumer Service URL
    SAML_SP_CERT: str = ""  # Base64 encoded SP certificate
    SAML_SP_KEY: str = ""   # Base64 encoded SP private key
    
    # IdP Settings (configurable for mock IdP vs real UIBK)
    SAML_IDP_ENTITY_ID: str = "https://idp.uibk.ac.at/idp/shibboleth"
    SAML_IDP_SSO_URL: str = "https://idp.uibk.ac.at/idp/profile/SAML2/Redirect/SSO"
    SAML_IDP_CERT: str = ""  # From IdP metadata
    
    # CORS
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:8080"
    
    # Server
    HOST: str = "127.0.0.1"
    PORT: int = 5005
    DEBUG: bool = False

    # Credential endpoint controls. A shared Redis-compatible store is
    # mandatory in production; local/test runtimes may use process memory.
    CREDENTIAL_RATE_LIMIT_ENABLED: bool = True
    CREDENTIAL_RATE_LIMIT_STORAGE_URI: str = "memory://"
    CREDENTIAL_WRITE_RATE_LIMIT: str = "10/minute"
    CREDENTIAL_VALIDATION_RATE_LIMIT: str = "6/minute"
    CREDENTIAL_BOOTSTRAP_RATE_LIMIT: str = "5/minute"

    # TLS is terminated by the deployment edge. Forwarded scheme information
    # is accepted only from these direct peer networks.
    REQUIRE_HTTPS: bool | None = None
    TRUSTED_PROXY_CIDRS: str = ""

    # Explicit local/test authentication capability. Never infer this from DEBUG.
    DEV_AUTH_ENABLED: bool = False
    DEV_AUTH_TOKEN: str = ""
    
    # Credential Encryption (Fernet key - 32 bytes base64)
    # Generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    ENCRYPTION_KEY: str = ""
    
    # External APIs
    DEPLOYER_URL: str = "http://localhost:5004"
    OPTIMIZER_URL: str = "http://master-thesis-2twin2clouds-1:8000"
    DEPLOYMENT_PREFLIGHT_MAX_AGE_MINUTES: int = Field(default=1440, gt=0)
    
    # GLB File Storage (for scene.glb uploads)
    UPLOAD_DIR: str = "./uploads"
    MAX_GLB_SIZE_MB: int = 100
    
    # Seed Data (development only)
    SEED_DATA: bool = False
    SEED_CREDENTIALS_FILE: str = "/config/config_credentials.json"
    SEED_GCP_CREDENTIALS_FILE: str = "/config/gcp_credentials.json"
    # Retained only to fail fast for obsolete environments that still set it.
    SEED_LEGACY_TWIN_CREDENTIALS: bool = False

    # Test-only routes (disabled by default)
    ENABLE_TEST_ENDPOINTS: bool = False

    @model_validator(mode="after")
    def validate_security_boundary(self) -> "Settings":
        """Reject unsafe capabilities and invalid runtime secrets."""
        non_production = {AppEnvironment.DEVELOPMENT, AppEnvironment.TEST}
        if self.DEV_AUTH_ENABLED and self.APP_ENV not in non_production:
            raise ValueError("DEV_AUTH_ENABLED is only allowed in development or test")
        if self.ENABLE_TEST_ENDPOINTS and self.APP_ENV not in non_production:
            raise ValueError("ENABLE_TEST_ENDPOINTS is only allowed in development or test")
        if self.SEED_DATA and self.APP_ENV not in non_production:
            raise ValueError("SEED_DATA is only allowed in development or test")
        if self.DEV_AUTH_ENABLED and not self.DEV_AUTH_TOKEN:
            raise ValueError("DEV_AUTH_TOKEN is required when DEV_AUTH_ENABLED is true")

        if len(self.JWT_SECRET_KEY) < 32:
            raise ValueError("JWT_SECRET_KEY must contain at least 32 characters")
        if len(self.ENCRYPTION_KEY) < 32:
            raise ValueError("ENCRYPTION_KEY must contain at least 32 characters")
        if self.JWT_SECRET_KEY != self.JWT_SECRET_KEY.strip():
            raise ValueError("JWT_SECRET_KEY contains surrounding whitespace")
        if self.ENCRYPTION_KEY != self.ENCRYPTION_KEY.strip():
            raise ValueError("ENCRYPTION_KEY contains surrounding whitespace")
        if any(
            ord(character) < 32 or ord(character) == 127
            for value in (self.JWT_SECRET_KEY, self.ENCRYPTION_KEY)
            for character in value
        ):
            raise ValueError("Runtime secrets must not contain control characters")
        if self.JWT_SECRET_KEY in KNOWN_INSECURE_SECRET_VALUES:
            raise ValueError("JWT_SECRET_KEY uses a known insecure placeholder")
        if self.ENCRYPTION_KEY in KNOWN_INSECURE_SECRET_VALUES:
            raise ValueError("ENCRYPTION_KEY uses a known insecure placeholder")
        if self.JWT_SECRET_KEY == self.ENCRYPTION_KEY:
            raise ValueError("JWT_SECRET_KEY and ENCRYPTION_KEY must be different")
        if re.fullmatch(r"[A-Za-z0-9_-]+={0,2}", self.ENCRYPTION_KEY) is None:
            raise ValueError("ENCRYPTION_KEY must be a URL-safe base64 value")
        try:
            decoded_encryption_key = base64.b64decode(
                self.ENCRYPTION_KEY.encode("ascii"),
                altchars=b"-_",
                validate=True,
            )
        except (binascii.Error, UnicodeEncodeError, ValueError) as exc:
            raise ValueError("ENCRYPTION_KEY must be a URL-safe base64 value") from exc
        if len(decoded_encryption_key) != 32:
            raise ValueError("ENCRYPTION_KEY must encode exactly 32 bytes")

        if self.APP_ENV == AppEnvironment.PRODUCTION:
            if self.DEBUG:
                raise ValueError("DEBUG must be false in production")
            if not self.CREDENTIAL_RATE_LIMIT_ENABLED:
                raise ValueError("CREDENTIAL_RATE_LIMIT_ENABLED must be true in production")
            if not self.CREDENTIAL_RATE_LIMIT_STORAGE_URI.startswith(("redis://", "rediss://")):
                raise ValueError(
                    "CREDENTIAL_RATE_LIMIT_STORAGE_URI must use redis:// or rediss:// in production"
                )

        if self.REQUIRE_HTTPS is None:
            self.REQUIRE_HTTPS = self.APP_ENV == AppEnvironment.PRODUCTION
        elif self.APP_ENV == AppEnvironment.PRODUCTION and not self.REQUIRE_HTTPS:
            raise ValueError("REQUIRE_HTTPS must be true in production")

        for field_name in (
            "CREDENTIAL_WRITE_RATE_LIMIT",
            "CREDENTIAL_VALIDATION_RATE_LIMIT",
            "CREDENTIAL_BOOTSTRAP_RATE_LIMIT",
        ):
            if re.fullmatch(r"[1-9][0-9]*/(second|minute|hour|day)s?", getattr(self, field_name)) is None:
                raise ValueError(f"{field_name} must use '<positive integer>/<time unit>' format")

        for raw_cidr in self.trusted_proxy_cidrs:
            try:
                ipaddress.ip_network(raw_cidr, strict=False)
            except ValueError as exc:
                raise ValueError(f"TRUSTED_PROXY_CIDRS contains an invalid network: {raw_cidr}") from exc

        if self.APP_ENV == AppEnvironment.PRODUCTION:
            origins = self.cors_origins
            if not origins:
                raise ValueError("CORS_ORIGINS must contain at least one HTTPS origin in production")
            for origin in origins:
                parsed = urlparse(origin)
                if parsed.scheme != "https" or not parsed.netloc or parsed.path not in ("", "/"):
                    raise ValueError("CORS_ORIGINS must contain only explicit HTTPS origins in production")

        return self

    @property
    def trusted_proxy_cidrs(self) -> tuple[str, ...]:
        return tuple(value.strip() for value in self.TRUSTED_PROXY_CIDRS.split(",") if value.strip())

    @property
    def cors_origins(self) -> tuple[str, ...]:
        return tuple(value.strip() for value in self.CORS_ORIGINS.split(",") if value.strip())


settings = Settings()
