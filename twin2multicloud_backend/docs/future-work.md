# Future Work: Security Considerations

This document outlines security improvements for production deployment of the Twin2MultiCloud Management API.

## Current Implementation (Thesis Scope)

The thesis implementation uses **Fernet symmetric encryption** with per-user and per-twin key derivation:

```
Master Key (ENCRYPTION_KEY in .env)
        │
        ▼
PBKDF2(master_key, salt=user_id:twin_id) → Per-User-Per-Twin Key
        │
        ▼
Credentials encrypted with user+twin-specific key
```

**Benefits:**
- Credentials encrypted at rest in SQLite
- Per-user isolation (compromising one user doesn't expose others)
- Per-twin isolation (compromising one twin doesn't expose sibling twins)
- Single master key simplifies operations
- Demonstrates defense-in-depth principles

**Limitations:**
- Master key in environment variable (manual setup required)
- No automatic key rotation
- No audit trail for credential access
- Single point of failure if master key leaked

---

## Production Recommendations

### Option 1: Cloud Secrets Managers (Recommended)

Replace local encryption with managed secrets services:

| Provider | Service | Features |
|----------|---------|----------|
| AWS | Secrets Manager | Auto-rotation, audit, IAM integration |
| Azure | Key Vault | HSM-backed, RBAC, versioning |
| GCP | Secret Manager | Automatic replication, audit logging |

**Architecture Change:**
```python
# Instead of:
config.aws_secret = encrypt(secret, twin_id)

# Use:
secret_id = secrets_manager.create_secret(f"twin/{twin_id}/aws", secret)
config.aws_secret_ref = secret_id  # Store reference, not value
```

**Cost:** ~$0.40/secret/month + API calls

---

### Option 2: HashiCorp Vault (Enterprise)

For organizations needing:
- Dynamic secrets (auto-generated, auto-rotated)
- Lease-based access with TTL
- Full audit logging
- Multi-region replication

**Integration:**
```python
import hvac

vault = hvac.Client(url=os.getenv("VAULT_ADDR"))
vault.secrets.kv.v2.create_or_update_secret(
    path=f"twins/{twin_id}",
    secret={"aws_access_key": key, "aws_secret": secret}
)
```

---

### Option 3: IAM Role Assumption (Zero-Credential)

Eliminate stored credentials entirely using cloud-native identity federation:

**AWS:**
```python
# User provides: Account ID + Role ARN
# Deployer uses STS AssumeRole with its service identity
sts = boto3.client('sts')
credentials = sts.assume_role(
    RoleArn=f"arn:aws:iam::{account_id}:role/{role_name}",
    RoleSessionName="twin2multicloud"
)
```

**Benefits:**
- No secrets stored anywhere
- Cloud provider handles authentication
- Automatic credential rotation
- Fine-grained IAM policies

**Requirements:**
- Users must configure trust policies in their AWS accounts
- More complex initial setup
- Best suited for enterprise customers

---

### Option 4: OAuth/OIDC Delegation

Let users authenticate directly to cloud providers:

1. User clicks "Connect AWS" button
2. Redirected to AWS Cognito/IAM Identity Center
3. User authenticates with their AWS credentials
4. Management API receives OAuth token with limited scope
5. Token used for Deployer operations (short-lived)

**Benefits:**
- Users manage their own credentials
- No credential storage in Management API
- Follows least-privilege principle

---

## Migration Path

To upgrade from current Fernet implementation:

1. **Phase 1:** Deploy secrets manager alongside current system
2. **Phase 2:** New credentials stored in secrets manager
3. **Phase 3:** Migrate existing encrypted credentials
4. **Phase 4:** Remove Fernet encryption code

```python
# Dual-read pattern during migration
def get_aws_secret(config):
    if config.aws_secret_ref:  # New: stored in secrets manager
        return secrets_manager.get(config.aws_secret_ref)
    else:  # Legacy: Fernet encrypted
        return decrypt(config.aws_secret, config.twin_id)
```

---

## Enhancement: Auto-Generated Encryption Keys

### Current State (Thesis)

The thesis requires manual configuration of `ENCRYPTION_KEY` in `.env`:

```bash
# User must run this and copy to .env
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

### Proposed Enhancement

Auto-generate encryption and JWT keys on first startup, eliminating manual configuration.

#### Implementation

**1. Create `src/utils/key_manager.py`:**

```python
"""
Auto-generate and persist encryption keys on first startup.
Keys are stored in data/ directory and loaded on subsequent startups.
"""
import os
from pathlib import Path
from cryptography.fernet import Fernet
import secrets

DATA_DIR = Path("data")
ENCRYPTION_KEY_FILE = DATA_DIR / "encryption.key"
JWT_SECRET_FILE = DATA_DIR / "jwt.secret"


def _ensure_data_dir():
    """Create data directory if it doesn't exist."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def get_or_create_encryption_key() -> str:
    """
    Get encryption key from file, or generate one if missing.
    
    Returns:
        Fernet-compatible base64-encoded key
    """
    _ensure_data_dir()
    
    if ENCRYPTION_KEY_FILE.exists():
        return ENCRYPTION_KEY_FILE.read_text().strip()
    
    # Generate new key
    key = Fernet.generate_key().decode()
    ENCRYPTION_KEY_FILE.write_text(key)
    
    # Set restrictive permissions (owner read-only)
    os.chmod(ENCRYPTION_KEY_FILE, 0o400)
    
    print(f"🔐 Generated new encryption key: {ENCRYPTION_KEY_FILE}")
    print("⚠️  IMPORTANT: Back up this file! Loss means credential data is unrecoverable.")
    
    return key


def get_or_create_jwt_secret() -> str:
    """
    Get JWT secret from file, or generate one if missing.
    
    Returns:
        256-bit random secret for JWT signing
    """
    _ensure_data_dir()
    
    if JWT_SECRET_FILE.exists():
        return JWT_SECRET_FILE.read_text().strip()
    
    # Generate new secret (256 bits = 32 bytes = 64 hex chars)
    secret = secrets.token_hex(32)
    JWT_SECRET_FILE.write_text(secret)
    
    os.chmod(JWT_SECRET_FILE, 0o400)
    
    print(f"🔑 Generated new JWT secret: {JWT_SECRET_FILE}")
    
    return secret
```

**2. Update `src/config.py`:**

```python
from pydantic_settings import BaseSettings
from src.utils.key_manager import get_or_create_encryption_key, get_or_create_jwt_secret

class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "sqlite:///./data/app.db"
    
    # JWT - auto-generated if not provided
    JWT_SECRET_KEY: str = ""
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 60
    
    # Encryption - auto-generated if not provided
    ENCRYPTION_KEY: str = ""
    
    # ... other settings ...
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        
        # Auto-generate keys if not provided
        if not self.JWT_SECRET_KEY:
            object.__setattr__(self, 'JWT_SECRET_KEY', get_or_create_jwt_secret())
        
        if not self.ENCRYPTION_KEY:
            object.__setattr__(self, 'ENCRYPTION_KEY', get_or_create_encryption_key())

settings = Settings()
```

**3. Update `.env.example`:**

```env
# === REQUIRED: OAuth (get from Google Cloud Console) ===
GOOGLE_CLIENT_ID=your-google-client-id
GOOGLE_CLIENT_SECRET=your-google-client-secret

# === OPTIONAL: Override defaults ===
DEPLOYER_URL=http://localhost:5004
CORS_ORIGINS=http://localhost:3000,http://localhost:8080
DEBUG=true

# === AUTO-GENERATED: Leave blank ===
# These are auto-generated on first startup and saved to data/
# JWT_SECRET_KEY=  
# ENCRYPTION_KEY=
```

**4. Update `compose.yaml` volume:**

```yaml
management-api:
  volumes:
    - ./twin2multicloud_backend:/app
    - management-data:/app/data  # Persists keys across restarts
```

#### Benefits

1. **Zero manual key configuration** - keys generated automatically
2. **Persistent across restarts** - stored in Docker volume
3. **Secure by default** - proper file permissions (0o400)
4. **Backup-friendly** - single `data/` directory to backup
5. **Override possible** - can still set in `.env` if needed

#### Security Considerations

- Keys stored in plaintext files (acceptable for thesis)
- Production should use encrypted storage or secrets manager
- `data/` directory should be excluded from version control
- Regular backups of `data/` directory recommended

---

## Security Audit Checklist

Before production deployment, verify:

- [ ] Master encryption key rotated from development value
- [ ] Key stored in secure secrets manager (not .env file)
- [ ] Database access restricted to API service only
- [ ] TLS enabled for all API endpoints
- [ ] Rate limiting implemented on credential endpoints
- [ ] Audit logging enabled for credential operations
- [ ] Penetration testing completed
- [ ] SOC 2 compliance reviewed (if applicable)

