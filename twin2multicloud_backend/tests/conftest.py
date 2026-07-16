"""
Pytest fixtures and configuration for twin2multicloud_backend tests.

Provides:
- Authenticated test client fixture
- Database setup/teardown
- Reusable test helpers
"""

import base64
import asyncio
import os

os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("DEBUG", "true")
os.environ.setdefault("DEV_AUTH_ENABLED", "true")
os.environ.setdefault("DEV_AUTH_TOKEN", "dev-token")
os.environ.setdefault("JWT_SECRET_KEY", "test-jwt-secret-with-at-least-32-characters")
os.environ.setdefault(
    "ENCRYPTION_KEY",
    base64.urlsafe_b64encode(b"t" * 32).decode("ascii"),
)

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from src.main import app
from src.models.database import Base, create_database_engine, get_db
from src.security.rate_limit import reset_rate_limiter_for_tests
from src.security.auth_rate_limit import reset_auth_rate_limiter_for_tests


# Test database (separate from production)
TEST_DATABASE_URL = "sqlite:///./test.db"
test_engine = create_database_engine(TEST_DATABASE_URL)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(autouse=True)
def isolate_credential_rate_limiter():
    asyncio.run(reset_rate_limiter_for_tests())
    asyncio.run(reset_auth_rate_limiter_for_tests())
    yield
    asyncio.run(reset_rate_limiter_for_tests())
    asyncio.run(reset_auth_rate_limiter_for_tests())


def override_get_db():
    """Provide test database session."""
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(scope="function")
def db_session():
    """Create fresh database for each test."""
    Base.metadata.create_all(bind=test_engine)
    session = TestingSessionLocal()
    yield session
    session.close()
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture(scope="function")
def client(db_session):
    """Test client with fresh database and isolated dependency override."""
    # Override only for this test
    app.dependency_overrides[get_db] = override_get_db
    Base.metadata.create_all(bind=test_engine)
    
    yield TestClient(app)
    
    # CRITICAL: Clean up override after test to not affect production
    Base.metadata.drop_all(bind=test_engine)
    app.dependency_overrides.clear()


@pytest.fixture
def auth_headers():
    """Authentication headers for API requests."""
    return {"Authorization": "Bearer dev-token"}


@pytest.fixture
def authenticated_client(client, auth_headers):
    """Client with auth headers pre-configured."""
    # First request triggers dev user creation
    client.get("/twins/", headers=auth_headers)
    return client, auth_headers


# ============================================================
# Test Data Fixtures
# ============================================================

@pytest.fixture
def sample_twin_data():
    """Sample twin creation data."""
    return {"name": "Test Digital Twin"}


@pytest.fixture
def sample_aws_credentials():
    """Sample AWS credentials for testing."""
    return {
        "access_key_id": "AKIAIOSFODNN7EXAMPLE",
        "secret_access_key": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
        "region": "eu-central-1"
    }


@pytest.fixture
def sample_azure_credentials():
    """Sample Azure credentials for testing."""
    return {
        "subscription_id": "sub-12345678-1234-1234-1234-123456789abc",
        "client_id": "client-12345678-1234-1234-1234-123456789abc",
        "client_secret": "secret-value-12345",
        "tenant_id": "tenant-12345678-1234-1234-1234-123456789abc",
        "region": "westeurope"
    }


@pytest.fixture
def sample_gcp_credentials():
    """Sample GCP credentials for testing."""
    return {
        "project_id": "my-project-12345",
        "billing_account": "012345-6789AB-CDEF01",
        "service_account_json": '{"type":"service_account","project_id":"my-project-12345","client_email":"deployer@my-project-12345.iam.gserviceaccount.com","private_key":"-----BEGIN PRIVATE KEY-----\\nsecret\\n-----END PRIVATE KEY-----\\n"}',
        "region": "europe-west1"
    }


@pytest.fixture
def sample_calc_params():
    """Sample optimizer calculation parameters."""
    return {
        "numberOfDevices": 100,
        "deviceSendingIntervalInMinutes": 2.0,
        "averageSizeOfMessageInKb": 0.25,
        "numberOfDeviceTypes": 1,
        "useEventChecking": False,
        "eventsPerMessage": 0,
        "triggerNotificationWorkflow": False,
        "orchestrationActionsPerMessage": 0,
        "returnFeedbackToDevice": False,
        "numberOfEventActions": 0,
        "integrateErrorHandling": False,
        "hotStorageDurationInMonths": 1,
        "coolStorageDurationInMonths": 3,
        "archiveStorageDurationInMonths": 12,
        "needs3DModel": False,
        "entityCount": 0,
        "average3DModelSizeInMB": 0,
        "dashboardRefreshesPerHour": 2,
        "apiCallsPerDashboardRefresh": 3,
        "dashboardActiveHoursPerDay": 8,
        "amountOfActiveEditors": 1,
        "amountOfActiveViewers": 5,
        "debugMode": False,
        "scenarioSettings": {},
        "currency": "USD"
    }


# ============================================================
# Helper Functions
# ============================================================

def create_test_twin(client, headers, name="Test Twin"):
    """Helper to create a twin and return its ID."""
    response = client.post("/twins/", json={"name": name}, headers=headers)
    assert response.status_code == 200
    return response.json()["id"]


# ============================================================
# Fixture Aliases for state transition tests
# ============================================================

@pytest.fixture
def auth_client(client, auth_headers):
    """Authenticated client for state transition tests.
    
    Unlike authenticated_client, this returns a pre-configured TestClient
    with headers automatically included (uses custom request method).
    """
    
    # First request triggers dev user creation
    client.get("/twins/", headers=auth_headers)
    
    # Store headers on client for convenience
    original_request = client.request
    def auth_request(method, url, **kwargs):
        headers = kwargs.pop("headers", {})
        headers.update(auth_headers)
        return original_request(method, url, headers=headers, **kwargs)
    
    client.request = auth_request
    client.get = lambda url, **kwargs: auth_request("GET", url, **kwargs)
    client.post = lambda url, **kwargs: auth_request("POST", url, **kwargs)
    client.put = lambda url, **kwargs: auth_request("PUT", url, **kwargs)
    client.delete = lambda url, **kwargs: auth_request("DELETE", url, **kwargs)
    
    return client


@pytest.fixture
def db(db_session):
    """Alias for db_session for tests using 'db' name."""
    return db_session


@pytest.fixture
def test_twin(auth_client, db):
    """Create a test twin owned by the dev user created by auth_client."""
    from src.models.twin import DigitalTwin, TwinState
    from src.models.user import User
    
    # Get the dev user created by auth_client (first user in DB)
    user = db.query(User).first()
    if not user:
        raise RuntimeError("No user found - auth_client should have created one")
    
    # Create twin owned by this user
    twin = DigitalTwin(
        name=f"Test Twin {id(db)}",
        user_id=user.id,
        state=TwinState.DRAFT
    )
    db.add(twin)
    db.commit()
    db.refresh(twin)
    
    return twin
