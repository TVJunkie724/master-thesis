"""
Pytest fixtures and configuration for twin2multicloud_backend tests.

Provides:
- Authenticated test client fixture
- Database setup/teardown
- Reusable test helpers
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.main import app
from src.models.database import Base, get_db


# Test database (separate from production)
TEST_DATABASE_URL = "sqlite:///./test.db"
test_engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


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
