from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "sqlite:///./data/app.db"
    
    # JWT
    JWT_SECRET_KEY: str = "dev-secret-change-in-production"
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
    HOST: str = "0.0.0.0"
    PORT: int = 5005
    DEBUG: bool = True
    
    # Credential Encryption (Fernet key - 32 bytes base64)
    # Generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    ENCRYPTION_KEY: str = "your-fernet-key-here-generate-new-one"
    
    # External APIs
    DEPLOYER_URL: str = "http://localhost:5004"
    OPTIMIZER_URL: str = "http://master-thesis-2twin2clouds-1:8000"
    
    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()

