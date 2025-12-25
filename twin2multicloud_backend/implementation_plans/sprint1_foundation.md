# Sprint 1: Foundation Implementation Plan

## Overview

This plan covers the initial setup to get a working Flutter ↔ Backend connection with:
- **Backend**: FastAPI + SQLite + Google OAuth (fully implemented)
- **Flutter**: Scaffold + Mock Auth + Dashboard (real auth deferred)

**Estimated time:** 5-6 days (padded for debugging/iteration)
**Reference:** See `FRONTEND_ARCHITECTURE.md` for full architecture details.

> [!IMPORTANT]
> **For AI Agent:** Execute files in order shown. Each section is a complete, copy-paste ready implementation. 
> Use `Bearer dev-token` for testing API without OAuth setup.

---

## Phase 1: Project Scaffold (0.5 days)

### 1.1 Rename CLI folder to Backend

```bash
# From repository root
git mv twin2multicloud_cli twin2multicloud_backend
```

### 1.2 Create Backend Directory Structure

```
twin2multicloud_backend/
├── src/
│   ├── api/
│   │   ├── __init__.py
│   │   ├── routes/
│   │   │   ├── __init__.py
│   │   │   ├── auth.py           # OAuth endpoints
│   │   │   ├── twins.py          # Digital Twin CRUD
│   │   │   └── health.py         # Health check
│   │   └── dependencies.py       # Auth dependencies
│   ├── auth/
│   │   ├── __init__.py
│   │   ├── providers/
│   │   │   ├── __init__.py
│   │   │   ├── base.py           # OAuthProvider ABC
│   │   │   └── google.py         # Google OAuth
│   │   ├── jwt.py                # JWT creation/validation
│   │   └── config.py             # OAuth config
│   ├── models/
│   │   ├── __init__.py
│   │   ├── database.py           # SQLAlchemy engine/session
│   │   ├── user.py               # User model
│   │   ├── twin.py               # DigitalTwin model
│   │   ├── file_version.py       # FileVersion model
│   │   └── deployment.py         # Deployment model
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── user.py               # Pydantic schemas
│   │   ├── twin.py
│   │   └── auth.py
│   ├── services/
│   │   ├── __init__.py
│   │   ├── twin_service.py       # Business logic
│   │   └── user_service.py
│   ├── config.py                 # App configuration
│   └── main.py                   # FastAPI app entry
├── data/                         # SQLite DB location (gitignored)
│   └── .gitkeep
├── tests/
│   ├── __init__.py
│   ├── conftest.py               # Pytest fixtures
│   └── test_twins.py             # API tests
├── .env.example                  # Environment template
├── requirements.txt
├── Dockerfile
└── DEVELOPMENT_GUIDE.md
```

### 1.3 Create requirements.txt

```txt
# Web Framework
fastapi>=0.104.0
uvicorn[standard]>=0.24.0

# Database
sqlalchemy>=2.0.0
aiosqlite>=0.19.0

# Authentication
python-jose[cryptography]>=3.3.0
authlib>=1.2.0
httpx>=0.25.0

# Utilities
python-dotenv>=1.0.0
pydantic>=2.5.0
pydantic-settings>=2.1.0

# Testing
pytest>=7.4.0
pytest-asyncio>=0.21.0
httpx>=0.25.0
```

### 1.4 Create .env.example

```env
# Database
DATABASE_URL=sqlite:///./data/app.db

# JWT
JWT_SECRET_KEY=your-secret-key-change-in-production
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=60

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
```

### 1.5 Update docker-compose.yml

Add to existing docker-compose.yml in repository root:

```yaml
  management-api:
    build:
      context: ./twin2multicloud_backend
      dockerfile: Dockerfile
    ports:
      - "5005:5005"
    volumes:
      - ./twin2multicloud_backend:/app
      - management-data:/app/data
    environment:
      - DATABASE_URL=sqlite:///./data/app.db
      - JWT_SECRET_KEY=${JWT_SECRET_KEY:-dev-secret-key}
      - GOOGLE_CLIENT_ID=${GOOGLE_CLIENT_ID:-}
      - GOOGLE_CLIENT_SECRET=${GOOGLE_CLIENT_SECRET:-}
    depends_on:
      - optimizer
      - deployer

volumes:
  management-data:
```

### 1.6 Create src/config.py (CRITICAL - Referenced everywhere)

```python
from pydantic_settings import BaseSettings
from typing import Optional

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
    
    # CORS
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:8080"
    
    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 5005
    DEBUG: bool = True
    
    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()
```

### 1.7 Create Dockerfile

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 5005

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "5005", "--reload"]
```

---

## Phase 2: Backend Implementation (2 days)

### 2.1 Database Models

#### `src/models/database.py`
```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from src.config import settings

engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False}  # SQLite specific
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

#### `src/models/user.py`
```python
from sqlalchemy import Column, String, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
from src.models.database import Base

class User(Base):
    __tablename__ = "users"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String, unique=True, nullable=False, index=True)
    name = Column(String, nullable=True)
    picture_url = Column(String, nullable=True)
    google_id = Column(String, unique=True, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    twins = relationship("DigitalTwin", back_populates="owner")
```

#### `src/models/twin.py`
```python
from sqlalchemy import Column, String, DateTime, ForeignKey, Enum
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
import enum
from src.models.database import Base

class TwinState(str, enum.Enum):
    DRAFT = "draft"
    CONFIGURED = "configured"
    DEPLOYED = "deployed"
    DESTROYED = "destroyed"
    ERROR = "error"
    INACTIVE = "inactive"

class DigitalTwin(Base):
    __tablename__ = "digital_twins"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    name = Column(String, nullable=False)
    state = Column(Enum(TwinState), default=TwinState.DRAFT)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    owner = relationship("User", back_populates="twins")
    file_versions = relationship("FileVersion", back_populates="twin")
    deployments = relationship("Deployment", back_populates="twin")
```

#### `src/models/file_version.py`
```python
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, LargeBinary
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
from src.models.database import Base

class FileVersion(Base):
    __tablename__ = "file_versions"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    twin_id = Column(String, ForeignKey("digital_twins.id"), nullable=False)
    file_path = Column(String, nullable=False)  # e.g., "config.json"
    content = Column(LargeBinary, nullable=False)
    version = Column(Integer, nullable=False)
    description = Column(String, nullable=True)
    created_by = Column(String, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    twin = relationship("DigitalTwin", back_populates="file_versions")
    
    __table_args__ = (
        # Unique constraint on twin_id + file_path + version
        {"sqlite_autoincrement": True},
    )
```

#### `src/models/deployment.py`
```python
from sqlalchemy import Column, String, DateTime, ForeignKey, Text, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
from src.models.database import Base

class DeploymentStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"

class Deployment(Base):
    __tablename__ = "deployments"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    twin_id = Column(String, ForeignKey("digital_twins.id"), nullable=False)
    status = Column(String, default="pending")
    description = Column(String, nullable=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    terraform_outputs = Column(JSON, nullable=True)
    logs = Column(Text, nullable=True)
    
    # Relationships
    twin = relationship("DigitalTwin", back_populates="deployments")


class DeploymentStatus(str, enum.Enum):
    """Deployment status enum (for reference, status column uses string for flexibility)"""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
```

#### `src/models/__init__.py`
```python
from src.models.database import Base, get_db, engine
from src.models.user import User
from src.models.twin import DigitalTwin, TwinState
from src.models.file_version import FileVersion
from src.models.deployment import Deployment, DeploymentStatus

__all__ = [
    "Base", "get_db", "engine",
    "User", "DigitalTwin", "TwinState",
    "FileVersion", "Deployment", "DeploymentStatus"
]
```

---

### 2.2 Authentication

#### `src/auth/providers/base.py`
```python
from abc import ABC, abstractmethod
from dataclasses import dataclass

@dataclass
class UserInfo:
    email: str
    name: str | None
    picture_url: str | None
    provider_id: str  # e.g., Google user ID

class OAuthProvider(ABC):
    @abstractmethod
    def get_authorize_url(self, state: str) -> str:
        """Return the OAuth authorization URL."""
        ...
    
    @abstractmethod
    async def handle_callback(self, code: str) -> UserInfo:
        """Exchange code for tokens and return user info."""
        ...
```

#### `src/auth/providers/google.py`
```python
from authlib.integrations.httpx_client import AsyncOAuth2Client
from src.auth.providers.base import OAuthProvider, UserInfo
from src.config import settings

class GoogleOAuth(OAuthProvider):
    def __init__(self):
        self.client_id = settings.GOOGLE_CLIENT_ID
        self.client_secret = settings.GOOGLE_CLIENT_SECRET
        self.redirect_uri = settings.GOOGLE_REDIRECT_URI
        
    def get_authorize_url(self, state: str) -> str:
        client = AsyncOAuth2Client(
            client_id=self.client_id,
            redirect_uri=self.redirect_uri,
            scope="openid email profile"
        )
        url, _ = client.create_authorization_url(
            "https://accounts.google.com/o/oauth2/auth",
            state=state
        )
        return url
    
    async def handle_callback(self, code: str) -> UserInfo:
        async with AsyncOAuth2Client(
            client_id=self.client_id,
            client_secret=self.client_secret,
            redirect_uri=self.redirect_uri
        ) as client:
            token = await client.fetch_token(
                "https://oauth2.googleapis.com/token",
                code=code
            )
            
            # Get user info
            resp = await client.get(
                "https://www.googleapis.com/oauth2/v3/userinfo"
            )
            data = resp.json()
            
            return UserInfo(
                email=data["email"],
                name=data.get("name"),
                picture_url=data.get("picture"),
                provider_id=data["sub"]
            )
```

#### `src/auth/jwt.py`
```python
from datetime import datetime, timedelta
from jose import jwt, JWTError
from src.config import settings

def create_access_token(user_id: str) -> str:
    expire = datetime.utcnow() + timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
    payload = {
        "sub": user_id,
        "exp": expire,
        "iat": datetime.utcnow()
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)

def verify_token(token: str) -> str | None:
    """Returns user_id if valid, None otherwise."""
    try:
        payload = jwt.decode(
            token, 
            settings.JWT_SECRET_KEY, 
            algorithms=[settings.JWT_ALGORITHM]
        )
        return payload.get("sub")
    except JWTError:
        return None
```

---

### 2.3 API Routes

#### `src/api/routes/auth.py`
```python
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
import secrets

from src.models.database import get_db
from src.models.user import User
from src.auth.providers.google import GoogleOAuth
from src.auth.jwt import create_access_token
from src.schemas.auth import TokenResponse

router = APIRouter(prefix="/auth", tags=["auth"])

# In-memory state storage (use Redis in production)
oauth_states: dict[str, str] = {}

@router.get("/google/login")
async def google_login():
    """Initiate Google OAuth flow."""
    state = secrets.token_urlsafe(32)
    oauth_states[state] = "pending"
    
    provider = GoogleOAuth()
    auth_url = provider.get_authorize_url(state)
    
    return {"auth_url": auth_url}

@router.get("/google/callback")
async def google_callback(
    code: str = Query(...),
    state: str = Query(...),
    db: Session = Depends(get_db)
):
    """Handle Google OAuth callback."""
    # Verify state
    if state not in oauth_states:
        raise HTTPException(status_code=400, detail="Invalid state")
    del oauth_states[state]
    
    # Exchange code for user info
    provider = GoogleOAuth()
    user_info = await provider.handle_callback(code)
    
    # Find or create user
    user = db.query(User).filter(User.email == user_info.email).first()
    if not user:
        user = User(
            email=user_info.email,
            name=user_info.name,
            picture_url=user_info.picture_url,
            google_id=user_info.provider_id
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    
    # Generate JWT
    token = create_access_token(user.id)
    
    # Redirect to frontend with token
    # In production, use a more secure method
    return RedirectResponse(
        url=f"http://localhost:8080/auth/callback?token={token}"
    )

@router.get("/me", response_model=dict)
async def get_me(
    current_user: User = Depends(get_current_user)
):
    """Get current authenticated user."""
    return {
        "id": current_user.id,
        "email": current_user.email,
        "name": current_user.name,
        "picture_url": current_user.picture_url
    }
```

> [!NOTE]
> **Import fix:** Add `from src.api.dependencies import get_current_user` at the top of `auth.py`

#### `src/api/routes/twins.py`
```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from src.models.database import get_db
from src.models.twin import DigitalTwin, TwinState
from src.models.user import User
from src.api.dependencies import get_current_user
from src.schemas.twin import TwinCreate, TwinUpdate, TwinResponse

router = APIRouter(prefix="/twins", tags=["twins"])

@router.get("/", response_model=List[TwinResponse])
async def list_twins(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List all twins for current user."""
    twins = db.query(DigitalTwin).filter(
        DigitalTwin.user_id == current_user.id,
        DigitalTwin.state != TwinState.INACTIVE
    ).all()
    return twins

@router.post("/", response_model=TwinResponse)
async def create_twin(
    twin: TwinCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a new digital twin."""
    new_twin = DigitalTwin(
        name=twin.name,
        user_id=current_user.id,
        state=TwinState.DRAFT
    )
    db.add(new_twin)
    db.commit()
    db.refresh(new_twin)
    return new_twin

@router.get("/{twin_id}", response_model=TwinResponse)
async def get_twin(
    twin_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get a specific twin."""
    twin = db.query(DigitalTwin).filter(
        DigitalTwin.id == twin_id,
        DigitalTwin.user_id == current_user.id
    ).first()
    if not twin:
        raise HTTPException(status_code=404, detail="Twin not found")
    return twin

@router.put("/{twin_id}", response_model=TwinResponse)
async def update_twin(
    twin_id: str,
    update: TwinUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update a twin."""
    twin = db.query(DigitalTwin).filter(
        DigitalTwin.id == twin_id,
        DigitalTwin.user_id == current_user.id
    ).first()
    if not twin:
        raise HTTPException(status_code=404, detail="Twin not found")
    
    if update.name is not None:
        twin.name = update.name
    if update.state is not None:
        twin.state = update.state
        
    db.commit()
    db.refresh(twin)
    return twin

@router.delete("/{twin_id}")
async def delete_twin(
    twin_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Soft delete a twin (set to inactive)."""
    twin = db.query(DigitalTwin).filter(
        DigitalTwin.id == twin_id,
        DigitalTwin.user_id == current_user.id
    ).first()
    if not twin:
        raise HTTPException(status_code=404, detail="Twin not found")
    
    twin.state = TwinState.INACTIVE
    db.commit()
    return {"message": "Twin deleted"}
```

#### `src/api/dependencies.py`
```python
from fastapi import Depends, HTTPException, Header
from sqlalchemy.orm import Session
from src.models.database import get_db
from src.models.user import User
from src.auth.jwt import verify_token

async def get_current_user(
    authorization: str = Header(...),
    db: Session = Depends(get_db)
) -> User:
    """Extract and validate JWT, return current user."""
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid auth header")
    
    token = authorization.split(" ")[1]
    user_id = verify_token(token)
    
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    
    return user


# DEV BYPASS: For testing without OAuth (DEBUG mode only)
async def get_current_user_dev(
    authorization: str = Header(None),
    db: Session = Depends(get_db)
) -> User:
    """Development-only auth bypass. Uses 'Bearer dev-token' to get first user."""
    from src.config import settings
    
    if settings.DEBUG and authorization == "Bearer dev-token":
        user = db.query(User).first()
        if user:
            return user
        # Create dev user if none exists
        user = User(email="dev@example.com", name="Developer")
        db.add(user)
        db.commit()
        db.refresh(user)
        return user
    
    # Fall back to real auth
    return await get_current_user(authorization, db)
```

---

### 2.4 Pydantic Schemas (CRITICAL - Referenced by routes)

#### `src/schemas/user.py`
```python
from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class UserBase(BaseModel):
    email: str
    name: Optional[str] = None

class UserResponse(UserBase):
    id: str
    picture_url: Optional[str] = None
    created_at: datetime
    
    class Config:
        from_attributes = True
```

#### `src/schemas/twin.py`
```python
from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List
from src.models.twin import TwinState

class TwinCreate(BaseModel):
    name: str

class TwinUpdate(BaseModel):
    name: Optional[str] = None
    state: Optional[TwinState] = None

class TwinResponse(BaseModel):
    id: str
    name: str
    state: TwinState
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True
```

#### `src/schemas/auth.py`
```python
from pydantic import BaseModel

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

class AuthUrlResponse(BaseModel):
    auth_url: str
```

---

### 2.5 Health Endpoint (Referenced in main.py)

#### `src/api/routes/health.py`
```python
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
from src.models.database import get_db

router = APIRouter(tags=["health"])

@router.get("/health")
async def health_check(db: Session = Depends(get_db)):
    """Health check endpoint."""
    try:
        # Test DB connection
        db.execute(text("SELECT 1"))
        return {
            "status": "healthy",
            "database": "connected"
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "database": str(e)
        }
```

#### `src/api/routes/__init__.py`
```python
from src.api.routes import auth, twins, health

__all__ = ["auth", "twins", "health"]
```

---

### 2.4 Main Application

#### `src/main.py`
```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.config import settings
from src.models.database import engine, Base
from src.api.routes import auth, twins, health

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

@app.get("/")
async def root():
    return {"message": "Twin2MultiCloud Management API", "version": "1.0.0"}
```

---

## Phase 3: Flutter Scaffold (1.5 days)

### 3.1 Initialize Flutter Project

```bash
cd twin2multicloud_flutter
flutter create . --platforms=web,windows,macos,linux
```

### 3.2 Update pubspec.yaml

```yaml
dependencies:
  flutter:
    sdk: flutter
  
  # State Management
  flutter_riverpod: ^2.4.9
  riverpod_annotation: ^2.3.3
  
  # Routing
  go_router: ^13.0.0
  
  # HTTP
  dio: ^5.4.0
  
  # Local Storage
  shared_preferences: ^2.2.2
  
  # UI
  flex_color_scheme: ^7.3.1

dev_dependencies:
  flutter_test:
    sdk: flutter
  riverpod_generator: ^2.3.9
  build_runner: ^2.4.7
```

### 3.3 Directory Structure

```
lib/
├── main.dart
├── app.dart                    # MaterialApp + Router
├── config/
│   └── api_config.dart         # Base URLs
├── providers/
│   ├── auth_provider.dart      # Auth state (mocked)
│   └── twins_provider.dart     # Twins state
├── services/
│   └── api_service.dart        # Dio HTTP client
├── models/
│   ├── user.dart
│   └── twin.dart
├── screens/
│   ├── login_screen.dart
│   ├── dashboard_screen.dart
│   └── twin_view_screen.dart
└── widgets/
    ├── stat_card.dart
    └── twin_list_item.dart
```

### 3.4 Flutter Models (CRITICAL - Referenced by providers)

#### `lib/models/user.dart`
```dart
class User {
  final String id;
  final String email;
  final String? name;
  final String? pictureUrl;

  User({
    required this.id,
    required this.email,
    this.name,
    this.pictureUrl,
  });

  factory User.fromJson(Map<String, dynamic> json) {
    return User(
      id: json['id'],
      email: json['email'],
      name: json['name'],
      pictureUrl: json['picture_url'],
    );
  }
}
```

#### `lib/models/twin.dart`
```dart
class Twin {
  final String id;
  final String name;
  final String state;
  final List<String> providers;
  final DateTime? createdAt;
  final DateTime? updatedAt;

  Twin({
    required this.id,
    required this.name,
    required this.state,
    required this.providers,
    this.createdAt,
    this.updatedAt,
  });

  factory Twin.fromJson(Map<String, dynamic> json) {
    return Twin(
      id: json['id'],
      name: json['name'],
      state: json['state'],
      providers: [], // Populated later from config
      createdAt: json['created_at'] != null ? DateTime.parse(json['created_at']) : null,
      updatedAt: json['updated_at'] != null ? DateTime.parse(json['updated_at']) : null,
    );
  }

  // State helpers
  bool get isDraft => state == 'draft';
  bool get isConfigured => state == 'configured';
  bool get isDeployed => state == 'deployed';
  bool get isError => state == 'error';
}
```

#### `lib/config/api_config.dart`
```dart
class ApiConfig {
  // Change this when backend is running
  static const String baseUrl = 'http://localhost:5005';
  
  // For Flutter web development
  static const String devToken = 'dev-token';
}
```

### 3.5 Core Files

#### `lib/main.dart`
```dart
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'app.dart';

void main() {
  runApp(
    const ProviderScope(
      child: Twin2MultiCloudApp(),
    ),
  );
}
```

#### `lib/app.dart` (CRITICAL - Referenced by main.dart)
```dart
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'screens/login_screen.dart';
import 'screens/dashboard_screen.dart';
import 'providers/auth_provider.dart';

// Router configuration
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
          // Handle OAuth callback (future implementation)
          final token = state.uri.queryParameters['token'];
          // TODO: Store token and redirect
          return const DashboardScreen();
        },
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

#### `lib/screens/login_screen.dart`
```dart
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../providers/auth_provider.dart';

class LoginScreen extends ConsumerWidget {
  const LoginScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final authState = ref.watch(authProvider);
    
    return Scaffold(
      body: Center(
        child: Card(
          elevation: 8,
          child: Container(
            width: 400,
            padding: const EdgeInsets.all(32),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                // Logo
                Icon(
                  Icons.cloud_sync,
                  size: 64,
                  color: Theme.of(context).colorScheme.primary,
                ),
                const SizedBox(height: 16),
                Text(
                  'Twin2MultiCloud',
                  style: Theme.of(context).textTheme.headlineMedium,
                ),
                const SizedBox(height: 8),
                Text(
                  'Multi-cloud Digital Twin Platform',
                  style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                    color: Theme.of(context).colorScheme.onSurfaceVariant,
                  ),
                ),
                const SizedBox(height: 32),
                
                // Google OAuth button (mocked for now)
                if (authState.isLoading)
                  const CircularProgressIndicator()
                else
                  FilledButton.icon(
                    onPressed: () async {
                      // MOCK: Auto-login for development
                      await ref.read(authProvider.notifier).mockLogin();
                      if (context.mounted) {
                        context.go('/dashboard');
                      }
                    },
                    icon: const Icon(Icons.login),
                    label: const Text('Sign in with Google'),
                    style: FilledButton.styleFrom(
                      minimumSize: const Size(double.infinity, 48),
                    ),
                  ),
                
                const SizedBox(height: 16),
                Text(
                  'Development Mode: Mock Login',
                  style: Theme.of(context).textTheme.bodySmall?.copyWith(
                    color: Theme.of(context).colorScheme.outline,
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
```

#### `lib/providers/auth_provider.dart` (Mocked)
```dart
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../models/user.dart';

// Mocked user for development
final mockUser = User(
  id: "mock-user-123",
  email: "developer@example.com",
  name: "Developer",
  pictureUrl: null,
);

final authProvider = StateNotifierProvider<AuthNotifier, AuthState>((ref) {
  return AuthNotifier();
});

class AuthState {
  final User? user;
  final bool isLoading;
  final bool isAuthenticated;
  
  AuthState({this.user, this.isLoading = false, this.isAuthenticated = false});
}

class AuthNotifier extends StateNotifier<AuthState> {
  AuthNotifier() : super(AuthState());
  
  // MOCK: Auto-login for development
  Future<void> mockLogin() async {
    state = AuthState(isLoading: true);
    await Future.delayed(const Duration(milliseconds: 500)); // Simulate delay
    state = AuthState(user: mockUser, isAuthenticated: true);
  }
  
  void logout() {
    state = AuthState();
  }
}
```

#### `lib/screens/dashboard_screen.dart`
```dart
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../providers/twins_provider.dart';
import '../widgets/stat_card.dart';
import '../widgets/twin_list_item.dart';

class DashboardScreen extends ConsumerWidget {
  const DashboardScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final twinsAsync = ref.watch(twinsProvider);
    
    return Scaffold(
      appBar: AppBar(
        title: const Text('Twin2MultiCloud'),
        actions: [
          CircleAvatar(child: Icon(Icons.person)),
          const SizedBox(width: 16),
        ],
      ),
      body: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Stat cards row
            Row(
              children: [
                StatCard(title: 'Deployed', value: '3', icon: Icons.cloud_done),
                StatCard(title: 'Est. Cost', value: '\$142/mo', icon: Icons.attach_money),
                StatCard(title: 'Devices', value: '347', icon: Icons.devices),
                StatCard(title: 'Errors', value: '0', icon: Icons.error_outline),
              ],
            ),
            const SizedBox(height: 32),
            
            // Twins list header
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Text('My Digital Twins', style: Theme.of(context).textTheme.headlineSmall),
                FilledButton.icon(
                  onPressed: () {}, // TODO: Navigate to create wizard
                  icon: const Icon(Icons.add),
                  label: const Text('New Twin'),
                ),
              ],
            ),
            const SizedBox(height: 16),
            
            // Twins list
            Expanded(
              child: twinsAsync.when(
                data: (twins) => ListView.builder(
                  itemCount: twins.length,
                  itemBuilder: (context, index) => TwinListItem(twin: twins[index]),
                ),
                loading: () => const Center(child: CircularProgressIndicator()),
                error: (err, stack) => Center(child: Text('Error: $err')),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
```

---

## Phase 4: Integration (0.5 days)

### 4.1 Connect Flutter to Backend

#### `lib/services/api_service.dart`
```dart
import 'package:dio/dio.dart';
import '../config/api_config.dart';

class ApiService {
  late final Dio _dio;
  String? _token;
  
  ApiService() {
    _dio = Dio(BaseOptions(
      baseUrl: ApiConfig.baseUrl,
      headers: {'Content-Type': 'application/json'},
    ));
    
    _dio.interceptors.add(InterceptorsWrapper(
      onRequest: (options, handler) {
        if (_token != null) {
          options.headers['Authorization'] = 'Bearer $_token';
        }
        return handler.next(options);
      },
    ));
  }
  
  void setToken(String token) => _token = token;
  
  Future<List<dynamic>> getTwins() async {
    final response = await _dio.get('/twins');
    return response.data;
  }
  
  Future<Map<String, dynamic>> createTwin(String name) async {
    final response = await _dio.post('/twins', data: {'name': name});
    return response.data;
  }
}
```

### 4.2 Twins Provider with API

#### `lib/providers/twins_provider.dart`
```dart
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../models/twin.dart';
import '../services/api_service.dart';

final apiServiceProvider = Provider((ref) => ApiService());

final twinsProvider = FutureProvider<List<Twin>>((ref) async {
  final api = ref.read(apiServiceProvider);
  
  // For now, return mock data (swap to real API when backend is running)
  // final data = await api.getTwins();
  // return data.map((json) => Twin.fromJson(json)).toList();
  
  // MOCK DATA for development
  return [
    Twin(id: '1', name: 'Smart Home', state: 'deployed', providers: ['AWS', 'Azure']),
    Twin(id: '2', name: 'Factory Floor', state: 'configured', providers: ['GCP']),
    Twin(id: '3', name: 'Office HVAC', state: 'error', providers: ['AWS']),
    Twin(id: '4', name: 'Test Project', state: 'draft', providers: []),
  ];
});
```

### 4.3 Flutter Widgets (CRITICAL - Referenced by dashboard)

#### `lib/widgets/stat_card.dart`
```dart
import 'package:flutter/material.dart';

class StatCard extends StatelessWidget {
  final String title;
  final String value;
  final IconData icon;
  final Color? color;

  const StatCard({
    super.key,
    required this.title,
    required this.value,
    required this.icon,
    this.color,
  });

  @override
  Widget build(BuildContext context) {
    return Expanded(
      child: Card(
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Icon(icon, color: color ?? Theme.of(context).colorScheme.primary),
                  const SizedBox(width: 8),
                  Text(
                    title,
                    style: Theme.of(context).textTheme.bodySmall,
                  ),
                ],
              ),
              const SizedBox(height: 8),
              Text(
                value,
                style: Theme.of(context).textTheme.headlineMedium?.copyWith(
                  fontWeight: FontWeight.bold,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
```

#### `lib/widgets/twin_list_item.dart`
```dart
import 'package:flutter/material.dart';
import '../models/twin.dart';

class TwinListItem extends StatelessWidget {
  final Twin twin;
  final VoidCallback? onView;
  final VoidCallback? onEdit;

  const TwinListItem({
    super.key,
    required this.twin,
    this.onView,
    this.onEdit,
  });

  @override
  Widget build(BuildContext context) {
    return Card(
      child: ListTile(
        leading: _buildStateIcon(),
        title: Text(twin.name),
        subtitle: Text(twin.providers.isEmpty 
          ? 'No providers configured' 
          : twin.providers.join(', ')),
        trailing: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            IconButton(
              icon: const Icon(Icons.visibility),
              onPressed: onView,
              tooltip: 'View',
            ),
            IconButton(
              icon: const Icon(Icons.edit),
              onPressed: onEdit,
              tooltip: 'Edit',
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildStateIcon() {
    IconData iconData;
    Color color;
    
    switch (twin.state) {
      case 'deployed':
        iconData = Icons.cloud_done;
        color = Colors.green;
        break;
      case 'configured':
        iconData = Icons.cloud_outlined;
        color = Colors.orange;
        break;
      case 'error':
        iconData = Icons.cloud_off;
        color = Colors.red;
        break;
      case 'draft':
      default:
        iconData = Icons.cloud_queue;
        color = Colors.grey;
    }
    
    return Icon(iconData, color: color);
  }
}
```

---

## Phase 5: Empty __init__.py Files (Required for Python imports)

Create these empty files for proper Python module structure:

```bash
# Backend Python __init__.py files (all empty)
touch src/__init__.py
touch src/api/__init__.py
touch src/auth/__init__.py
touch src/auth/providers/__init__.py
touch src/schemas/__init__.py
touch src/services/__init__.py
```

---

## Verification Checklist

### Backend
- [ ] `python -m pytest tests/` passes
- [ ] `GET /health` returns 200
- [ ] `GET /auth/google/login` returns auth URL
- [ ] `GET /twins` (with mock token) returns empty list
- [ ] `POST /twins` creates a twin
- [ ] Database file created in `data/app.db`

### Flutter
- [ ] `flutter run -d chrome` launches dashboard
- [ ] Stat cards display
- [ ] Mock twins list displays
- [ ] No console errors

### Integration
- [ ] Flutter can reach backend at `localhost:5005`
- [ ] CORS allows Flutter origin

---

## Next Sprint Preview

After Sprint 1 is complete, Sprint 2 will cover:
- Wizard Step 1: Configuration + Credentials UI
- Real API integration (remove mocks)
- File upload to backend
