from enum import StrEnum

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppEnvironment(StrEnum):
    DEVELOPMENT = "development"
    TEST = "test"
    PRODUCTION = "production"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

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
        """Reject development capabilities and weak secrets in production."""
        non_production = {AppEnvironment.DEVELOPMENT, AppEnvironment.TEST}
        if self.DEV_AUTH_ENABLED and self.APP_ENV not in non_production:
            raise ValueError("DEV_AUTH_ENABLED is only allowed in development or test")
        if self.ENABLE_TEST_ENDPOINTS and self.APP_ENV not in non_production:
            raise ValueError("ENABLE_TEST_ENDPOINTS is only allowed in development or test")
        if self.SEED_DATA and self.APP_ENV not in non_production:
            raise ValueError("SEED_DATA is only allowed in development or test")
        if self.DEV_AUTH_ENABLED and not self.DEV_AUTH_TOKEN:
            raise ValueError("DEV_AUTH_TOKEN is required when DEV_AUTH_ENABLED is true")

        if self.APP_ENV == AppEnvironment.PRODUCTION:
            if self.DEBUG:
                raise ValueError("DEBUG must be false in production")
            if len(self.JWT_SECRET_KEY) < 32:
                raise ValueError("JWT_SECRET_KEY must contain at least 32 characters in production")
            if len(self.ENCRYPTION_KEY) < 32:
                raise ValueError("ENCRYPTION_KEY must contain at least 32 characters in production")

        return self


settings = Settings()
