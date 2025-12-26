# Sprint 2: Create/Edit Twin Wizard - Step 1 Configuration

## Overview

This sprint implements the first step of the Digital Twin creation wizard:
- **Backend**: Credential encryption, twin configuration model, Deployer API integration
- **Flutter**: Wizard UI (Step 1), credential forms, validation feedback

**Estimated time:** 5-6 days
**Prerequisite:** Sprint 1 complete (backend running, Flutter scaffold working)

> [!IMPORTANT]
> **For AI Agent:** Execute files in order shown. Each section is copy-paste ready.
> Test with `Bearer dev-token` for backend calls.

---

## Phase 1.0: Credential Encryption Setup (0.5 days)

### 1.0.1 Add cryptography Dependency

Update `requirements.txt` - add to existing:

```txt
# Encryption
cryptography>=41.0.0
```

Run: `pip install -r requirements.txt`

---

### 1.0.2 Update Config with Encryption Key

Replace `src/config.py`:

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "sqlite:///./data/app.db"
    
    # JWT
    JWT_SECRET_KEY: str = "dev-secret-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 60
    
    # Credential Encryption (Fernet key - 32 bytes base64)
    # Generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    ENCRYPTION_KEY: str = "your-fernet-key-here-generate-new-one"
    
    # Google OAuth
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_REDIRECT_URI: str = "http://localhost:5005/auth/google/callback"
    
    # CORS
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:8080"
    
    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 5005
    DEBUG: bool = True
    
    # External APIs
    DEPLOYER_URL: str = "http://localhost:5004"
    
    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()
```

---

### 1.0.3 Update .env.example

Add to `twin2multicloud_backend/.env.example`:

```env
# Database
DATABASE_URL=sqlite:///./data/app.db

# JWT
JWT_SECRET_KEY=your-secret-key-change-in-production
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=60

# Credential Encryption
# Generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
ENCRYPTION_KEY=your-fernet-key-here

# Google OAuth
GOOGLE_CLIENT_ID=your-google-client-id
GOOGLE_CLIENT_SECRET=your-google-client-secret
GOOGLE_REDIRECT_URI=http://localhost:5005/auth/google/callback

# CORS
CORS_ORIGINS=http://localhost:3000,http://localhost:8080

# Server
HOST=0.0.0.0
PORT=5005
DEBUG=true

# External APIs
DEPLOYER_URL=http://localhost:5004
```

---

### 1.0.4 Generate Encryption Key for .env

Run this command to generate a Fernet key:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Copy the output to your `.env` file as `ENCRYPTION_KEY=<generated-key>`.

---

### 1.0.5 Create Crypto Utility Module

Create directory: `src/utils/`

Create `src/utils/__init__.py`:

```python
from src.utils.crypto import encrypt, decrypt

__all__ = ["encrypt", "decrypt"]
```

Create `src/utils/crypto.py`:

```python
"""
Per-User-Per-Twin Fernet Encryption for credentials at rest.

Each user+twin combination gets a unique encryption key derived from:
- Master key (ENCRYPTION_KEY in .env)
- User ID + Twin ID (used as salt)

This provides double isolation:
- Compromising one user's data doesn't expose other users
- Compromising one twin's data doesn't expose sibling twins

Uses PBKDF2 for key derivation + Fernet (AES-128-CBC) for encryption.
"""
import base64
from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from src.config import settings

# Cache derived keys to avoid repeated derivation (key = "user_id:twin_id")
_key_cache: dict[str, Fernet] = {}


def _derive_key(user_id: str, twin_id: str) -> bytes:
    """
    Derive a unique Fernet key for a specific user+twin combination.
    
    Uses PBKDF2 with:
    - Master key as input
    - User ID + Twin ID as salt (ensures unique key per user per twin)
    - 100,000 iterations (OWASP recommendation)
    """
    salt = f"{user_id}:{twin_id}".encode()
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100_000,
    )
    derived = kdf.derive(settings.ENCRYPTION_KEY.encode())
    return base64.urlsafe_b64encode(derived)


def _get_fernet(user_id: str, twin_id: str) -> Fernet:
    """Get or create Fernet instance for a user+twin combination."""
    cache_key = f"{user_id}:{twin_id}"
    if cache_key not in _key_cache:
        try:
            key = _derive_key(user_id, twin_id)
            _key_cache[cache_key] = Fernet(key)
        except Exception as e:
            raise ValueError(
                f"Invalid ENCRYPTION_KEY. Generate with: "
                f"python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
            ) from e
    return _key_cache[cache_key]


def encrypt(plaintext: str, user_id: str, twin_id: str) -> str:
    """
    Encrypt a plaintext string using user+twin-specific key.
    
    Args:
        plaintext: The secret to encrypt
        user_id: The user ID (from current_user.id)
        twin_id: The twin ID
        
    Returns:
        Base64-encoded ciphertext (safe for DB storage)
    """
    if not plaintext:
        return ""
    if not user_id or not twin_id:
        raise ValueError("user_id and twin_id required for encryption")
    return _get_fernet(user_id, twin_id).encrypt(plaintext.encode()).decode()


def decrypt(ciphertext: str, user_id: str, twin_id: str) -> str:
    """
    Decrypt a ciphertext string using user+twin-specific key.
    
    Args:
        ciphertext: The encrypted value from DB
        user_id: The user ID (from current_user.id)
        twin_id: The twin ID
        
    Returns:
        Original plaintext secret
        
    Raises:
        ValueError: If decryption fails (wrong key or corrupted data)
    """
    if not ciphertext:
        return ""
    if not user_id or not twin_id:
        raise ValueError("user_id and twin_id required for decryption")
    try:
        return _get_fernet(user_id, twin_id).decrypt(ciphertext.encode()).decode()
    except InvalidToken:
        raise ValueError("Decryption failed - invalid key or corrupted data")


def clear_key_cache():
    """Clear cached keys (useful for testing or key rotation)."""
    _key_cache.clear()
```

> [!NOTE]
> **Per-User-Per-Twin Key Benefits:**
> - Each user+twin combination has a unique derived key
> - Compromising one user's data doesn't expose other users
> - Compromising one twin's data doesn't expose sibling twins
> - Same single master key in `.env` (simple operations)
> - Key derivation is deterministic (no key storage needed)

        
    Returns:
        Original plaintext secret
        
    Raises:
        ValueError: If decryption fails (wrong key or corrupted data)
    """
    if not ciphertext:
        return ""
    if not twin_id:
        raise ValueError("twin_id required for decryption")
    try:
        return _get_fernet(twin_id).decrypt(ciphertext.encode()).decode()
    except InvalidToken:
        raise ValueError("Decryption failed - invalid key or corrupted data")


def clear_key_cache():
    """Clear cached keys (useful for testing or key rotation)."""
    _key_cache.clear()
```

> [!NOTE]
> **Per-Twin Key Benefits:**
> - Each twin has a unique derived key
> - Compromising one twin's data doesn't expose others
> - Same single master key in `.env` (simple operations)
> - Key derivation is deterministic (no key storage needed)


---

## Phase 1.1: TwinConfiguration Model (0.5 days)

### 1.1.1 Create TwinConfiguration Model

Create `src/models/twin_config.py`:

```python
from sqlalchemy import Column, String, Boolean, ForeignKey, DateTime, Text
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
from src.models.database import Base

class TwinConfiguration(Base):
    """
    Stores configuration for a Digital Twin including cloud credentials.
    
    IMPORTANT: All credential fields are ENCRYPTED using Fernet.
    - Encrypt before saving: crypto.encrypt(secret)
    - Decrypt when reading: crypto.decrypt(encrypted)
    """
    __tablename__ = "twin_configurations"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    twin_id = Column(String, ForeignKey("digital_twins.id"), unique=True, nullable=False)
    
    # Basic settings
    debug_mode = Column(Boolean, default=False)
    
    # AWS credentials (ENCRYPTED)
    aws_access_key_id = Column(String, nullable=True)  # Encrypted
    aws_secret_access_key = Column(String, nullable=True)  # Encrypted
    aws_region = Column(String, default="us-east-1")  # Not encrypted (not sensitive)
    aws_validated = Column(Boolean, default=False)
    
    # Azure credentials (ENCRYPTED)
    azure_subscription_id = Column(String, nullable=True)  # Encrypted
    azure_client_id = Column(String, nullable=True)  # Encrypted
    azure_client_secret = Column(String, nullable=True)  # Encrypted
    azure_tenant_id = Column(String, nullable=True)  # Encrypted
    azure_validated = Column(Boolean, default=False)
    
    # GCP credentials (ENCRYPTED - full JSON)
    gcp_project_id = Column(String, nullable=True)  # Not encrypted (usually public)
    gcp_service_account_json = Column(Text, nullable=True)  # Encrypted (contains private key)
    gcp_validated = Column(Boolean, default=False)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationship
    twin = relationship("DigitalTwin", back_populates="configuration", uselist=False)
```

---

### 1.1.2 Update DigitalTwin Model

In `src/models/twin.py`, add the relationship after line 28 (after deployments):

```python
# Add this line:
configuration = relationship("TwinConfiguration", back_populates="twin", uselist=False)
```

---

### 1.1.3 Update Models __init__.py

Replace `src/models/__init__.py`:

```python
from src.models.database import Base, get_db, engine
from src.models.user import User
from src.models.twin import DigitalTwin, TwinState
from src.models.twin_config import TwinConfiguration
from src.models.file_version import FileVersion
from src.models.deployment import Deployment, DeploymentStatus

__all__ = [
    "Base", "get_db", "engine",
    "User", "DigitalTwin", "TwinState", "TwinConfiguration",
    "FileVersion", "Deployment", "DeploymentStatus"
]
```

---

## Phase 1.2: Configuration Schemas (0.25 days)

### 1.2.1 Create Configuration Schemas

Create `src/schemas/twin_config.py`:

```python
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class AWSCredentials(BaseModel):
    access_key_id: str = Field(..., min_length=16, max_length=128)
    secret_access_key: str = Field(..., min_length=16)
    region: str = "us-east-1"

class AzureCredentials(BaseModel):
    subscription_id: str
    client_id: str
    client_secret: str
    tenant_id: str

class GCPCredentials(BaseModel):
    project_id: str
    service_account_json: str  # Full JSON as string

class TwinConfigCreate(BaseModel):
    debug_mode: bool = False
    aws: Optional[AWSCredentials] = None
    azure: Optional[AzureCredentials] = None
    gcp: Optional[GCPCredentials] = None

class TwinConfigUpdate(BaseModel):
    debug_mode: Optional[bool] = None
    aws: Optional[AWSCredentials] = None
    azure: Optional[AzureCredentials] = None
    gcp: Optional[GCPCredentials] = None

class TwinConfigResponse(BaseModel):
    """Response model - NEVER returns actual credentials, only status."""
    id: str
    twin_id: str
    debug_mode: bool
    aws_configured: bool
    aws_validated: bool
    aws_region: Optional[str] = None
    azure_configured: bool
    azure_validated: bool
    gcp_configured: bool
    gcp_validated: bool
    gcp_project_id: Optional[str] = None
    updated_at: datetime
    
    class Config:
        from_attributes = True
    
    @classmethod
    def from_db(cls, config):
        """Convert DB model to response (no secrets exposed)."""
        return cls(
            id=config.id,
            twin_id=config.twin_id,
            debug_mode=config.debug_mode,
            aws_configured=bool(config.aws_access_key_id),
            aws_validated=config.aws_validated,
            aws_region=config.aws_region,
            azure_configured=bool(config.azure_subscription_id),
            azure_validated=config.azure_validated,
            gcp_configured=bool(config.gcp_project_id),
            gcp_validated=config.gcp_validated,
            gcp_project_id=config.gcp_project_id,
            updated_at=config.updated_at
        )

class CredentialValidationResult(BaseModel):
    provider: str  # "aws", "azure", "gcp"
    valid: bool
    message: str
    permissions: Optional[list[str]] = None
```

---

### 1.2.2 Create Schemas __init__.py

Create `src/schemas/__init__.py`:

```python
from src.schemas.user import UserBase, UserResponse
from src.schemas.twin import TwinCreate, TwinUpdate, TwinResponse
from src.schemas.auth import TokenResponse, AuthUrlResponse
from src.schemas.twin_config import (
    AWSCredentials, AzureCredentials, GCPCredentials,
    TwinConfigCreate, TwinConfigUpdate, TwinConfigResponse,
    CredentialValidationResult
)

__all__ = [
    "UserBase", "UserResponse",
    "TwinCreate", "TwinUpdate", "TwinResponse",
    "TokenResponse", "AuthUrlResponse",
    "AWSCredentials", "AzureCredentials", "GCPCredentials",
    "TwinConfigCreate", "TwinConfigUpdate", "TwinConfigResponse",
    "CredentialValidationResult"
]
```

---

## Phase 1.3: Configuration API Routes with Encryption (0.75 days)

### 1.3.1 Create Configuration Routes

Create `src/api/routes/config.py`:

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import httpx

from src.models.database import get_db
from src.models.twin import DigitalTwin
from src.models.twin_config import TwinConfiguration
from src.models.user import User
from src.api.dependencies import get_current_user
from src.schemas.twin_config import (
    TwinConfigUpdate, TwinConfigResponse, CredentialValidationResult
)
from src.config import settings
from src.utils.crypto import encrypt, decrypt  # Encryption utilities

router = APIRouter(prefix="/twins/{twin_id}/config", tags=["configuration"])


async def get_user_twin(twin_id: str, user: User, db: Session) -> DigitalTwin:
    """Helper to verify twin ownership."""
    twin = db.query(DigitalTwin).filter(
        DigitalTwin.id == twin_id,
        DigitalTwin.user_id == user.id
    ).first()
    if not twin:
        raise HTTPException(status_code=404, detail="Twin not found")
    return twin


@router.get("/", response_model=TwinConfigResponse)
async def get_config(
    twin_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get configuration for a twin. Creates default if none exists."""
    twin = await get_user_twin(twin_id, current_user, db)
    
    if not twin.configuration:
        config = TwinConfiguration(twin_id=twin_id)
        db.add(config)
        db.commit()
        db.refresh(config)
    else:
        config = twin.configuration
    
    return TwinConfigResponse.from_db(config)


@router.put("/", response_model=TwinConfigResponse)
async def update_config(
    twin_id: str,
    update: TwinConfigUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update configuration for a twin.
    Credentials are ENCRYPTED with user+twin-specific key.
    """
    twin = await get_user_twin(twin_id, current_user, db)
    
    if not twin.configuration:
        config = TwinConfiguration(twin_id=twin_id)
        db.add(config)
    else:
        config = twin.configuration
    
    # Update fields
    if update.debug_mode is not None:
        config.debug_mode = update.debug_mode
    
    # AWS - ENCRYPT with user+twin-specific key
    if update.aws:
        config.aws_access_key_id = encrypt(update.aws.access_key_id, current_user.id, twin_id)
        config.aws_secret_access_key = encrypt(update.aws.secret_access_key, current_user.id, twin_id)
        config.aws_region = update.aws.region  # Not encrypted
        config.aws_validated = False  # Reset validation
    
    # Azure - ENCRYPT with user+twin-specific key
    if update.azure:
        config.azure_subscription_id = encrypt(update.azure.subscription_id, current_user.id, twin_id)
        config.azure_client_id = encrypt(update.azure.client_id, current_user.id, twin_id)
        config.azure_client_secret = encrypt(update.azure.client_secret, current_user.id, twin_id)
        config.azure_tenant_id = encrypt(update.azure.tenant_id, current_user.id, twin_id)
        config.azure_validated = False
    
    # GCP - ENCRYPT with user+twin-specific key
    if update.gcp:
        config.gcp_project_id = update.gcp.project_id  # Not encrypted (public)
        config.gcp_service_account_json = encrypt(update.gcp.service_account_json, current_user.id, twin_id)
        config.gcp_validated = False
    
    db.commit()
    db.refresh(config)
    return TwinConfigResponse.from_db(config)


@router.post("/validate/{provider}", response_model=CredentialValidationResult)
async def validate_credentials(
    twin_id: str,
    provider: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Validate credentials by calling the Deployer API.
    DECRYPTS credentials from DB, sends to Deployer, never exposes to client.
    """
    if provider not in ["aws", "azure", "gcp"]:
        raise HTTPException(status_code=400, detail="Invalid provider. Use: aws, azure, gcp")
    
    twin = await get_user_twin(twin_id, current_user, db)
    config = twin.configuration
    
    if not config:
        raise HTTPException(status_code=400, detail="No configuration found. Save credentials first.")
    
    # Build credentials payload - DECRYPT with user+twin-specific key
    credentials = {}
    if provider == "aws":
        if not config.aws_access_key_id:
            return CredentialValidationResult(
                provider="aws", valid=False, message="AWS credentials not configured"
            )
        credentials = {
            "aws_access_key_id": decrypt(config.aws_access_key_id, current_user.id, twin_id),
            "aws_secret_access_key": decrypt(config.aws_secret_access_key, current_user.id, twin_id),
            "aws_region": config.aws_region
        }
    elif provider == "azure":
        if not config.azure_subscription_id:
            return CredentialValidationResult(
                provider="azure", valid=False, message="Azure credentials not configured"
            )
        credentials = {
            "azure_subscription_id": decrypt(config.azure_subscription_id, current_user.id, twin_id),
            "azure_client_id": decrypt(config.azure_client_id, current_user.id, twin_id),
            "azure_client_secret": decrypt(config.azure_client_secret, current_user.id, twin_id),
            "azure_tenant_id": decrypt(config.azure_tenant_id, current_user.id, twin_id)
        }
    elif provider == "gcp":
        if not config.gcp_project_id:
            return CredentialValidationResult(
                provider="gcp", valid=False, message="GCP credentials not configured"
            )
        credentials = {
            "gcp_project_id": config.gcp_project_id,
            "gcp_service_account_json": decrypt(config.gcp_service_account_json, current_user.id, twin_id)
        }
    
    # Call Deployer API
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{settings.DEPLOYER_URL}/api/credentials/validate/{provider}",
                json=credentials,
                timeout=30.0
            )
            
            if response.status_code == 200:
                result = response.json()
                valid = result.get("valid", False)
                
                # Update validation status in DB
                if provider == "aws":
                    config.aws_validated = valid
                elif provider == "azure":
                    config.azure_validated = valid
                elif provider == "gcp":
                    config.gcp_validated = valid
                
                db.commit()
                
                return CredentialValidationResult(
                    provider=provider,
                    valid=valid,
                    message=result.get("message", "Validation complete"),
                    permissions=result.get("missing_permissions")
                )
            else:
                return CredentialValidationResult(
                    provider=provider,
                    valid=False,
                    message=f"Deployer API error: {response.status_code}"
                )
    except httpx.ConnectError:
        return CredentialValidationResult(
            provider=provider,
            valid=False,
            message="Cannot connect to Deployer API. Is it running on port 5004?"
        )
    except httpx.RequestError as e:
        return CredentialValidationResult(
            provider=provider,
            valid=False,
            message=f"Request error: {str(e)}"
        )
```

---

### 1.3.2 Register Config Routes

Update `src/api/routes/__init__.py`:

```python
from src.api.routes import auth, twins, health, config

__all__ = ["auth", "twins", "health", "config"]
```

Update `src/main.py` - add config router:

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.config import settings
from src.models.database import engine, Base
from src.api.routes import auth, twins, health, config  # Added config

# Create tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Twin2MultiCloud Management API",
    version="1.0.0",
    description="Management API for Digital Twin multi-cloud deployments"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes
app.include_router(auth.router)
app.include_router(twins.router)
app.include_router(health.router)
app.include_router(config.router)  # NEW

@app.get("/")
async def root():
    return {"message": "Twin2MultiCloud Management API", "version": "1.0.0"}
```

---

## Phase 2: Flutter - Wizard Step 1 UI (2.5 days)

### 2.1 Add file_picker Dependency

Update `pubspec.yaml` - add to dependencies:

```yaml
dependencies:
  # ... existing deps ...
  file_picker: ^6.1.1  # For GCP JSON file upload
```

Run: `flutter pub get`

---

### 2.2 Create Wizard Screen

Create directory: `lib/screens/wizard/`

Create `lib/screens/wizard/wizard_screen.dart`:

```dart
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'step1_configuration.dart';
import '../../services/api_service.dart';
import '../../providers/twins_provider.dart';

class WizardScreen extends ConsumerStatefulWidget {
  final String? twinId; // null for new, set for edit
  
  const WizardScreen({super.key, this.twinId});
  
  @override
  ConsumerState<WizardScreen> createState() => _WizardScreenState();
}

class _WizardScreenState extends ConsumerState<WizardScreen> {
  int _currentStep = 0;
  String? _activeTwinId;
  bool _isCreatingTwin = false;
  
  @override
  void initState() {
    super.initState();
    _activeTwinId = widget.twinId;
  }
  
  Future<String> _createTwinIfNeeded(String name) async {
    if (_activeTwinId != null) return _activeTwinId!;
    
    setState(() => _isCreatingTwin = true);
    try {
      final api = ref.read(apiServiceProvider);
      final result = await api.createTwin(name);
      _activeTwinId = result['id'];
      return _activeTwinId!;
    } finally {
      setState(() => _isCreatingTwin = false);
    }
  }
  
  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text(_activeTwinId == null ? 'Create Digital Twin' : 'Edit Digital Twin'),
        leading: IconButton(
          icon: const Icon(Icons.close),
          onPressed: () => context.go('/dashboard'),
        ),
      ),
      body: Column(
        children: [
          _buildStepIndicator(),
          const Divider(height: 1),
          Expanded(child: _buildStepContent()),
        ],
      ),
    );
  }
  
  Widget _buildStepIndicator() {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 16),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          _buildStep(0, 'Configuration', Icons.settings),
          _buildConnector(0),
          _buildStep(1, 'Optimizer', Icons.analytics),
          _buildConnector(1),
          _buildStep(2, 'Deployer', Icons.cloud_upload),
        ],
      ),
    );
  }
  
  Widget _buildStep(int index, String label, IconData icon) {
    final isActive = _currentStep == index;
    final isCompleted = _currentStep > index;
    
    return Column(
      children: [
        Container(
          width: 40,
          height: 40,
          decoration: BoxDecoration(
            shape: BoxShape.circle,
            color: isCompleted 
              ? Colors.green 
              : isActive 
                ? Theme.of(context).colorScheme.primary 
                : Colors.grey.shade300,
          ),
          child: Icon(
            isCompleted ? Icons.check : icon,
            color: Colors.white,
            size: 20,
          ),
        ),
        const SizedBox(height: 4),
        Text(
          label,
          style: TextStyle(
            fontSize: 12,
            fontWeight: isActive ? FontWeight.bold : FontWeight.normal,
          ),
        ),
      ],
    );
  }
  
  Widget _buildConnector(int afterIndex) {
    final isActive = _currentStep > afterIndex;
    return Container(
      width: 60,
      height: 2,
      margin: const EdgeInsets.only(bottom: 20),
      color: isActive ? Colors.green : Colors.grey.shade300,
    );
  }
  
  Widget _buildStepContent() {
    switch (_currentStep) {
      case 0:
        return Step1Configuration(
          twinId: _activeTwinId,
          isCreatingTwin: _isCreatingTwin,
          onCreateTwin: _createTwinIfNeeded,
          onNext: () => setState(() => _currentStep = 1),
          onSaveDraft: () {
            ScaffoldMessenger.of(context).showSnackBar(
              const SnackBar(content: Text('Draft saved!')),
            );
          },
        );
      case 1:
        return const Center(child: Text('Step 2: Optimizer (Sprint 3)'));
      case 2:
        return const Center(child: Text('Step 3: Deployer (Sprint 4)'));
      default:
        return const SizedBox();
    }
  }
}
```

---

### 2.3 Create Step 1 Configuration Screen

Create `lib/screens/wizard/step1_configuration.dart`:

```dart
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../widgets/credential_section.dart';
import '../../services/api_service.dart';
import '../../providers/twins_provider.dart';

class Step1Configuration extends ConsumerStatefulWidget {
  final String? twinId;
  final bool isCreatingTwin;
  final Future<String> Function(String name) onCreateTwin;
  final VoidCallback onNext;
  final VoidCallback onSaveDraft;
  
  const Step1Configuration({
    super.key,
    required this.twinId,
    required this.isCreatingTwin,
    required this.onCreateTwin,
    required this.onNext,
    required this.onSaveDraft,
  });
  
  @override
  ConsumerState<Step1Configuration> createState() => _Step1ConfigurationState();
}

class _Step1ConfigurationState extends ConsumerState<Step1Configuration> {
  final _nameController = TextEditingController();
  bool _debugMode = false;
  bool _isSaving = false;
  String? _error;
  
  bool _awsValid = false;
  bool _azureValid = false;
  bool _gcpValid = false;
  
  Map<String, String> _awsCredentials = {};
  Map<String, String> _azureCredentials = {};
  Map<String, String> _gcpCredentials = {};
  String? _gcpServiceAccountJson;
  
  bool get _canProceed {
    return _nameController.text.isNotEmpty && 
           (_awsValid || _azureValid || _gcpValid);
  }
  
  Future<void> _saveConfig() async {
    if (_nameController.text.isEmpty) {
      setState(() => _error = 'Please enter a name for your Digital Twin');
      return;
    }
    
    setState(() {
      _isSaving = true;
      _error = null;
    });
    
    try {
      final twinId = await widget.onCreateTwin(_nameController.text);
      final api = ref.read(apiServiceProvider);
      final configData = <String, dynamic>{'debug_mode': _debugMode};
      
      if (_awsCredentials.isNotEmpty && 
          _awsCredentials['access_key_id']?.isNotEmpty == true) {
        configData['aws'] = {
          'access_key_id': _awsCredentials['access_key_id'],
          'secret_access_key': _awsCredentials['secret_access_key'],
          'region': _awsCredentials['region'] ?? 'us-east-1',
        };
      }
      
      if (_azureCredentials.isNotEmpty &&
          _azureCredentials['subscription_id']?.isNotEmpty == true) {
        configData['azure'] = {
          'subscription_id': _azureCredentials['subscription_id'],
          'client_id': _azureCredentials['client_id'],
          'client_secret': _azureCredentials['client_secret'],
          'tenant_id': _azureCredentials['tenant_id'],
        };
      }
      
      if (_gcpCredentials['project_id']?.isNotEmpty == true || 
          _gcpServiceAccountJson != null) {
        configData['gcp'] = {
          'project_id': _gcpCredentials['project_id'] ?? '',
          'service_account_json': _gcpServiceAccountJson ?? '',
        };
      }
      
      await api.updateTwinConfig(twinId, configData);
      widget.onSaveDraft();
      
    } catch (e) {
      setState(() => _error = 'Failed to save: $e');
    } finally {
      setState(() => _isSaving = false);
    }
  }
  
  @override
  void dispose() {
    _nameController.dispose();
    super.dispose();
  }
  
  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(24),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Error banner
          if (_error != null)
            Container(
              padding: const EdgeInsets.all(12),
              margin: const EdgeInsets.only(bottom: 16),
              decoration: BoxDecoration(
                color: Colors.red.shade50,
                borderRadius: BorderRadius.circular(8),
              ),
              child: Row(
                children: [
                  const Icon(Icons.error, color: Colors.red),
                  const SizedBox(width: 8),
                  Expanded(child: Text(_error!, style: const TextStyle(color: Colors.red))),
                  IconButton(
                    icon: const Icon(Icons.close, size: 18),
                    onPressed: () => setState(() => _error = null),
                  ),
                ],
              ),
            ),
          
          // Twin Name
          Text('Digital Twin Name', style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: 8),
          TextField(
            controller: _nameController,
            decoration: const InputDecoration(
              hintText: 'e.g., Smart Home IoT',
              border: OutlineInputBorder(),
            ),
            onChanged: (_) => setState(() {}),
          ),
          
          const SizedBox(height: 24),
          
          // Mode toggle
          Row(
            children: [
              Text('Mode:', style: Theme.of(context).textTheme.titleMedium),
              const SizedBox(width: 16),
              ChoiceChip(
                label: const Text('Production'),
                selected: !_debugMode,
                onSelected: (selected) => setState(() => _debugMode = false),
              ),
              const SizedBox(width: 8),
              ChoiceChip(
                label: const Text('Debug'),
                selected: _debugMode,
                onSelected: (selected) => setState(() => _debugMode = true),
              ),
            ],
          ),
          
          const SizedBox(height: 32),
          const Divider(),
          const SizedBox(height: 16),
          
          // AWS Section
          CredentialSection(
            title: 'AWS Credentials',
            provider: 'aws',
            twinId: widget.twinId,
            icon: Icons.cloud,
            color: Colors.orange,
            onValidationChanged: (valid) => setState(() => _awsValid = valid),
            onCredentialsChanged: (creds) => _awsCredentials = creds,
            fields: const [
              CredentialField(name: 'access_key_id', label: 'Access Key ID'),
              CredentialField(name: 'secret_access_key', label: 'Secret Access Key', obscure: true),
              CredentialField(name: 'region', label: 'Region', defaultValue: 'us-east-1'),
            ],
          ),
          
          const SizedBox(height: 16),
          
          // Azure Section
          CredentialSection(
            title: 'Azure Credentials',
            provider: 'azure',
            twinId: widget.twinId,
            icon: Icons.cloud_circle,
            color: Colors.blue,
            onValidationChanged: (valid) => setState(() => _azureValid = valid),
            onCredentialsChanged: (creds) => _azureCredentials = creds,
            fields: const [
              CredentialField(name: 'subscription_id', label: 'Subscription ID'),
              CredentialField(name: 'client_id', label: 'Client ID'),
              CredentialField(name: 'client_secret', label: 'Client Secret', obscure: true),
              CredentialField(name: 'tenant_id', label: 'Tenant ID'),
            ],
          ),
          
          const SizedBox(height: 16),
          
          // GCP Section
          CredentialSection(
            title: 'GCP Credentials',
            provider: 'gcp',
            twinId: widget.twinId,
            icon: Icons.cloud_queue,
            color: Colors.red,
            onValidationChanged: (valid) => setState(() => _gcpValid = valid),
            onCredentialsChanged: (creds) => _gcpCredentials = creds,
            onJsonUploaded: (json) => _gcpServiceAccountJson = json,
            fields: const [
              CredentialField(name: 'project_id', label: 'Project ID'),
            ],
            supportsJsonUpload: true,
          ),
          
          const SizedBox(height: 32),
          const Divider(),
          const SizedBox(height: 16),
          
          // Action buttons
          Row(
            mainAxisAlignment: MainAxisAlignment.end,
            children: [
              OutlinedButton(
                onPressed: (_isSaving || widget.isCreatingTwin) ? null : _saveConfig,
                child: _isSaving 
                  ? const SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2))
                  : const Text('Save Draft'),
              ),
              const SizedBox(width: 16),
              FilledButton(
                onPressed: _canProceed ? () async {
                  await _saveConfig();
                  widget.onNext();
                } : null,
                child: const Text('Next Step →'),
              ),
            ],
          ),
          
          if (!_canProceed) ...[
            const SizedBox(height: 8),
            Text(
              'To proceed: Give your twin a name and validate at least one provider\'s credentials.',
              style: Theme.of(context).textTheme.bodySmall?.copyWith(
                color: Theme.of(context).colorScheme.outline,
              ),
            ),
          ],
        ],
      ),
    );
  }
}
```

---

### 2.4 Create Credential Section Widget

Create `lib/widgets/credential_section.dart`:

```dart
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:file_picker/file_picker.dart';
import 'dart:convert';
import '../services/api_service.dart';
import '../providers/twins_provider.dart';

class CredentialField {
  final String name;
  final String label;
  final bool obscure;
  final String? defaultValue;
  
  const CredentialField({
    required this.name,
    required this.label,
    this.obscure = false,
    this.defaultValue,
  });
}

class CredentialSection extends ConsumerStatefulWidget {
  final String title;
  final String provider;
  final String? twinId;
  final IconData icon;
  final Color color;
  final List<CredentialField> fields;
  final bool supportsJsonUpload;
  final Function(bool) onValidationChanged;
  final Function(Map<String, String>) onCredentialsChanged;
  final Function(String)? onJsonUploaded;
  
  const CredentialSection({
    super.key,
    required this.title,
    required this.provider,
    required this.twinId,
    required this.icon,
    required this.color,
    required this.fields,
    required this.onValidationChanged,
    required this.onCredentialsChanged,
    this.onJsonUploaded,
    this.supportsJsonUpload = false,
  });
  
  @override
  ConsumerState<CredentialSection> createState() => _CredentialSectionState();
}

class _CredentialSectionState extends ConsumerState<CredentialSection> {
  bool _expanded = false;
  bool _isValidating = false;
  String? _validationStatus;
  String? _validationMessage;
  String? _uploadedFileName;
  
  final Map<String, TextEditingController> _controllers = {};
  
  @override
  void initState() {
    super.initState();
    for (final field in widget.fields) {
      _controllers[field.name] = TextEditingController(
        text: field.defaultValue ?? '',
      );
    }
  }
  
  @override
  void dispose() {
    for (final controller in _controllers.values) {
      controller.dispose();
    }
    super.dispose();
  }
  
  void _notifyCredentialsChanged() {
    final creds = <String, String>{};
    for (final entry in _controllers.entries) {
      if (entry.value.text.isNotEmpty) {
        creds[entry.key] = entry.value.text;
      }
    }
    widget.onCredentialsChanged(creds);
  }
  
  Future<void> _uploadJson() async {
    final result = await FilePicker.platform.pickFiles(
      type: FileType.custom,
      allowedExtensions: ['json'],
      withData: true,
    );
    
    if (result != null && result.files.single.bytes != null) {
      final content = utf8.decode(result.files.single.bytes!);
      try {
        final json = jsonDecode(content);
        
        if (json['project_id'] != null) {
          _controllers['project_id']?.text = json['project_id'];
        }
        
        widget.onJsonUploaded?.call(content);
        
        setState(() {
          _uploadedFileName = result.files.single.name;
          _validationStatus = null;
        });
        
        _notifyCredentialsChanged();
        
      } catch (e) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Invalid JSON file: $e'), backgroundColor: Colors.red),
        );
      }
    }
  }
  
  Future<void> _validateCredentials() async {
    if (widget.twinId == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Save draft first to validate credentials')),
      );
      return;
    }
    
    setState(() {
      _isValidating = true;
      _validationStatus = null;
      _validationMessage = null;
    });
    
    try {
      final api = ref.read(apiServiceProvider);
      final result = await api.validateCredentials(widget.twinId!, widget.provider);
      
      setState(() {
        _isValidating = false;
        _validationStatus = result['valid'] == true ? 'valid' : 'invalid';
        _validationMessage = result['message'] ?? 'Validation complete';
      });
      
      widget.onValidationChanged(_validationStatus == 'valid');
      
    } catch (e) {
      setState(() {
        _isValidating = false;
        _validationStatus = 'error';
        _validationMessage = 'Validation failed: $e';
      });
      widget.onValidationChanged(false);
    }
  }
  
  void _onCredentialChanged() {
    _notifyCredentialsChanged();
    if (_validationStatus != null) {
      setState(() {
        _validationStatus = null;
        _validationMessage = null;
      });
      widget.onValidationChanged(false);
    }
  }
  
  @override
  Widget build(BuildContext context) {
    return Card(
      child: Column(
        children: [
          ListTile(
            leading: Icon(widget.icon, color: widget.color),
            title: Text(widget.title),
            trailing: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                _buildStatusBadge(),
                Icon(_expanded ? Icons.expand_less : Icons.expand_more),
              ],
            ),
            onTap: () => setState(() => _expanded = !_expanded),
          ),
          
          if (_expanded) ...[
            const Divider(height: 1),
            Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                children: [
                  for (final field in widget.fields) ...[
                    TextField(
                      controller: _controllers[field.name],
                      obscureText: field.obscure,
                      decoration: InputDecoration(
                        labelText: field.label,
                        border: const OutlineInputBorder(),
                      ),
                      onChanged: (_) => _onCredentialChanged(),
                    ),
                    const SizedBox(height: 12),
                  ],
                  
                  if (widget.supportsJsonUpload && _uploadedFileName != null)
                    Container(
                      padding: const EdgeInsets.all(8),
                      margin: const EdgeInsets.only(bottom: 12),
                      decoration: BoxDecoration(
                        color: Colors.green.shade50,
                        borderRadius: BorderRadius.circular(4),
                      ),
                      child: Row(
                        children: [
                          const Icon(Icons.check_circle, color: Colors.green, size: 16),
                          const SizedBox(width: 8),
                          Expanded(child: Text('Uploaded: $_uploadedFileName')),
                        ],
                      ),
                    ),
                  
                  Row(
                    children: [
                      if (widget.supportsJsonUpload)
                        OutlinedButton.icon(
                          onPressed: _uploadJson,
                          icon: const Icon(Icons.upload_file),
                          label: const Text('Upload JSON'),
                        ),
                      const Spacer(),
                      FilledButton.icon(
                        onPressed: _isValidating ? null : _validateCredentials,
                        icon: _isValidating 
                          ? const SizedBox(
                              width: 16, height: 16,
                              child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
                            )
                          : const Icon(Icons.check),
                        label: Text(_isValidating ? 'Validating...' : 'Check'),
                      ),
                    ],
                  ),
                  
                  if (_validationMessage != null) ...[
                    const SizedBox(height: 12),
                    Container(
                      padding: const EdgeInsets.all(12),
                      decoration: BoxDecoration(
                        color: _validationStatus == 'valid' 
                          ? Colors.green.shade50 
                          : Colors.red.shade50,
                        borderRadius: BorderRadius.circular(8),
                      ),
                      child: Row(
                        children: [
                          Icon(
                            _validationStatus == 'valid' ? Icons.check_circle : Icons.error,
                            color: _validationStatus == 'valid' ? Colors.green : Colors.red,
                          ),
                          const SizedBox(width: 8),
                          Expanded(child: Text(_validationMessage!)),
                        ],
                      ),
                    ),
                  ],
                ],
              ),
            ),
          ],
        ],
      ),
    );
  }
  
  Widget _buildStatusBadge() {
    if (_validationStatus == null) return const SizedBox(width: 8);
    
    return Container(
      margin: const EdgeInsets.only(right: 8),
      child: Icon(
        _validationStatus == 'valid' ? Icons.check_circle : Icons.error,
        color: _validationStatus == 'valid' ? Colors.green : Colors.red,
        size: 20,
      ),
    );
  }
}
```

---

### 2.5 Update API Service

Update `lib/services/api_service.dart`:

```dart
import 'package:dio/dio.dart';
import '../config/api_config.dart';

class ApiService {
  final Dio _dio;
  
  ApiService() : _dio = Dio(BaseOptions(
    baseUrl: ApiConfig.baseUrl,
    headers: {
      'Content-Type': 'application/json',
      'Authorization': 'Bearer ${ApiConfig.devToken}',
    },
  ));
  
  // Twins
  Future<List<dynamic>> getTwins() async {
    final response = await _dio.get('/twins/');
    return response.data;
  }
  
  Future<Map<String, dynamic>> createTwin(String name) async {
    final response = await _dio.post('/twins/', data: {'name': name});
    return response.data;
  }
  
  Future<Map<String, dynamic>> getTwin(String id) async {
    final response = await _dio.get('/twins/$id');
    return response.data;
  }
  
  // Configuration
  Future<Map<String, dynamic>> getTwinConfig(String twinId) async {
    final response = await _dio.get('/twins/$twinId/config/');
    return response.data;
  }
  
  Future<Map<String, dynamic>> updateTwinConfig(String twinId, Map<String, dynamic> config) async {
    final response = await _dio.put('/twins/$twinId/config/', data: config);
    return response.data;
  }
  
  Future<Map<String, dynamic>> validateCredentials(String twinId, String provider) async {
    final response = await _dio.post('/twins/$twinId/config/validate/$provider');
    return response.data;
  }
}
```

---

### 2.6 Update Router

Update `lib/app.dart` - add wizard routes:

```dart
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'screens/login_screen.dart';
import 'screens/dashboard_screen.dart';
import 'screens/wizard/wizard_screen.dart';
import 'providers/auth_provider.dart';

final routerProvider = Provider<GoRouter>((ref) {
  final authState = ref.watch(authProvider);
  
  return GoRouter(
    initialLocation: '/login',
    redirect: (context, state) {
      final isLoggedIn = authState.isAuthenticated;
      final isLoggingIn = state.matchedLocation == '/login';
      
      if (!isLoggedIn && !isLoggingIn) return '/login';
      if (isLoggedIn && isLoggingIn) return '/dashboard';
      return null;
    },
    routes: [
      GoRoute(
        path: '/login',
        builder: (context, state) => const LoginScreen(),
      ),
      GoRoute(
        path: '/dashboard',
        builder: (context, state) => const DashboardScreen(),
      ),
      GoRoute(
        path: '/auth/callback',
        builder: (context, state) {
          final token = state.uri.queryParameters['token'];
          // TODO: Store token and redirect
          return const DashboardScreen();
        },
      ),
      GoRoute(
        path: '/wizard',
        builder: (context, state) => const WizardScreen(),
      ),
      GoRoute(
        path: '/wizard/:twinId',
        builder: (context, state) => WizardScreen(
          twinId: state.pathParameters['twinId'],
        ),
      ),
    ],
  );
});

class Twin2MultiCloudApp extends ConsumerWidget {
  const Twin2MultiCloudApp({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final router = ref.watch(routerProvider);
    
    return MaterialApp.router(
      title: 'Twin2MultiCloud',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(
          seedColor: Colors.blue,
          brightness: Brightness.light,
        ),
        useMaterial3: true,
      ),
      darkTheme: ThemeData(
        colorScheme: ColorScheme.fromSeed(
          seedColor: Colors.blue,
          brightness: Brightness.dark,
        ),
        useMaterial3: true,
      ),
      themeMode: ThemeMode.system,
      routerConfig: router,
    );
  }
}
```

---

### 2.7 Update Dashboard Button

In `lib/screens/dashboard_screen.dart`, update the New Twin button:

```dart
FilledButton.icon(
  onPressed: () => context.go('/wizard'),
  icon: const Icon(Icons.add),
  label: const Text('New Twin'),
),
```

---

## Phase 3: Testing (0.5 days)

### 3.1 Encryption Tests

Create `tests/test_crypto.py`:

```python
import pytest
from src.utils.crypto import encrypt, decrypt, clear_key_cache

# Test user and twin IDs
TEST_USER = "user-123"
TEST_TWIN = "twin-456"

@pytest.fixture(autouse=True)
def reset_cache():
    """Clear key cache between tests."""
    clear_key_cache()

def test_encrypt_decrypt_roundtrip():
    """Encrypted value should decrypt back to original."""
    secret = "my-super-secret-password"
    encrypted = encrypt(secret, TEST_USER, TEST_TWIN)
    
    assert encrypted != secret  # Should be different
    assert encrypted.startswith("gAAAAA")  # Fernet prefix
    assert decrypt(encrypted, TEST_USER, TEST_TWIN) == secret  # Should roundtrip

def test_empty_string():
    """Empty strings should pass through unchanged."""
    assert encrypt("", TEST_USER, TEST_TWIN) == ""
    assert decrypt("", TEST_USER, TEST_TWIN) == ""

def test_unicode():
    """Unicode characters should work."""
    secret = "пароль-中文-🔐"
    encrypted = encrypt(secret, TEST_USER, TEST_TWIN)
    assert decrypt(encrypted, TEST_USER, TEST_TWIN) == secret

def test_different_users_different_keys():
    """Different users should produce different ciphertexts."""
    secret = "shared-secret"
    user1_encrypted = encrypt(secret, "user-1", TEST_TWIN)
    user2_encrypted = encrypt(secret, "user-2", TEST_TWIN)
    
    assert user1_encrypted != user2_encrypted  # Different keys
    
    # Each user can only decrypt their own
    assert decrypt(user1_encrypted, "user-1", TEST_TWIN) == secret
    assert decrypt(user2_encrypted, "user-2", TEST_TWIN) == secret
    
    # Cross-decryption should fail
    with pytest.raises(ValueError, match="Decryption failed"):
        decrypt(user1_encrypted, "user-2", TEST_TWIN)

def test_different_twins_different_keys():
    """Different twins should produce different ciphertexts."""
    secret = "shared-secret"
    twin1_encrypted = encrypt(secret, TEST_USER, "twin-1")
    twin2_encrypted = encrypt(secret, TEST_USER, "twin-2")
    
    assert twin1_encrypted != twin2_encrypted  # Different keys
```


### 3.2 Config API Tests

Create `tests/test_config.py`:

```python
import pytest
from fastapi.testclient import TestClient
from src.main import app
from src.models.database import Base, engine
from src.utils.crypto import decrypt

client = TestClient(app)
HEADERS = {"Authorization": "Bearer dev-token"}

# Dev user ID (from dev bypass in dependencies.py)
DEV_USER_ID = "dev-user-id"

@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

def test_get_config_creates_default():
    """GET config should auto-create if missing."""
    twin_resp = client.post("/twins/", json={"name": "Test"}, headers=HEADERS)
    twin_id = twin_resp.json()["id"]
    
    config_resp = client.get(f"/twins/{twin_id}/config/", headers=HEADERS)
    assert config_resp.status_code == 200
    assert config_resp.json()["aws_configured"] == False

def test_credentials_stored_encrypted():
    """Credentials should be encrypted in DB with user+twin-specific key."""
    from src.models.database import SessionLocal
    from src.models.twin_config import TwinConfiguration
    
    twin_resp = client.post("/twins/", json={"name": "Test"}, headers=HEADERS)
    twin_id = twin_resp.json()["id"]
    
    # Update with AWS credentials
    client.put(f"/twins/{twin_id}/config/", 
        json={"aws": {
            "access_key_id": "AKIAIOSFODNN7EXAMPLE",
            "secret_access_key": "wJalrXUtnFEMI/K7MDENG",
            "region": "us-east-1"
        }},
        headers=HEADERS
    )
    
    # Check DB directly
    db = SessionLocal()
    config = db.query(TwinConfiguration).filter_by(twin_id=twin_id).first()
    
    # Should be encrypted (not plaintext)
    assert config.aws_access_key_id != "AKIAIOSFODNN7EXAMPLE"
    assert config.aws_access_key_id.startswith("gAAAAA")  # Fernet prefix
    
    # Should decrypt correctly with user+twin key
    assert decrypt(config.aws_access_key_id, DEV_USER_ID, twin_id) == "AKIAIOSFODNN7EXAMPLE"
    
    db.close()

def test_response_never_exposes_credentials():
    """API response should never contain actual credentials."""
    twin_resp = client.post("/twins/", json={"name": "Test"}, headers=HEADERS)
    twin_id = twin_resp.json()["id"]
    
    client.put(f"/twins/{twin_id}/config/", 
        json={"aws": {
            "access_key_id": "AKIAIOSFODNN7EXAMPLE",
            "secret_access_key": "wJalrXUtnFEMI/K7MDENG",
            "region": "us-east-1"
        }},
        headers=HEADERS
    )
    
    config_resp = client.get(f"/twins/{twin_id}/config/", headers=HEADERS)
    data = config_resp.json()
    
    # Response should only have status, not actual credentials
    assert "aws_configured" in data
    assert "access_key_id" not in data
    assert "secret_access_key" not in data
    assert "AKIAIOSFODNN7EXAMPLE" not in str(data)
```

---

## Verification Checklist

### Encryption
- [ ] `ENCRYPTION_KEY` in .env (Fernet key)
- [ ] `encrypt(secret, user_id, twin_id)` returns Fernet ciphertext
- [ ] `decrypt(ciphertext, user_id, twin_id)` returns original plaintext
- [ ] Different users produce different ciphertexts
- [ ] Different twins produce different ciphertexts
- [ ] Credentials encrypted in SQLite
- [ ] API never returns actual credentials

### Backend
- [ ] `GET /twins/{id}/config` creates default
- [ ] `PUT /twins/{id}/config` encrypts with user+twin key
- [ ] `POST /twins/{id}/config/validate/{provider}` decrypts for Deployer
- [ ] 404 for non-owned twins

### Flutter
- [ ] Dashboard "New Twin" opens wizard
- [ ] Twin created on first Save Draft
- [ ] Credential sections expand/collapse
- [ ] JSON upload extracts project_id
- [ ] Validation calls encrypted backend
- [ ] Next button gated properly

---

## File Summary

### Backend (12 files)
| File | Action |
|------|--------|
| `requirements.txt` | UPDATE (add cryptography) |
| `src/config.py` | UPDATE (add ENCRYPTION_KEY, DEPLOYER_URL) |
| `.env.example` | UPDATE (add ENCRYPTION_KEY) |
| `src/utils/__init__.py` | NEW |
| `src/utils/crypto.py` | NEW |
| `src/models/twin_config.py` | NEW |
| `src/models/twin.py` | UPDATE (add relationship) |
| `src/models/__init__.py` | UPDATE (add export) |
| `src/schemas/twin_config.py` | NEW |
| `src/schemas/__init__.py` | NEW |
| `src/api/routes/config.py` | NEW |
| `src/api/routes/__init__.py` | UPDATE |
| `src/main.py` | UPDATE (add router) |
| `tests/test_crypto.py` | NEW |
| `tests/test_config.py` | NEW |

### Flutter (7 files)
| File | Action |
|------|--------|
| `pubspec.yaml` | UPDATE (add file_picker) |
| `lib/screens/wizard/wizard_screen.dart` | NEW |
| `lib/screens/wizard/step1_configuration.dart` | NEW |
| `lib/widgets/credential_section.dart` | UPDATE |
| `lib/services/api_service.dart` | UPDATE |
| `lib/app.dart` | UPDATE |
| `lib/screens/dashboard_screen.dart` | UPDATE |
