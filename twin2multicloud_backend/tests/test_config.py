import pytest
from fastapi.testclient import TestClient
from src.main import app
from src.models.database import Base, engine

client = TestClient(app)
HEADERS = {"Authorization": "Bearer dev-token"}


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    client.get("/twins/", headers=HEADERS)


def test_get_config_creates_default():
    """GET config should auto-create if missing."""
    twin_resp = client.post("/twins/", json={"name": "Test"}, headers=HEADERS)
    twin_id = twin_resp.json()["id"]
    
    config_resp = client.get(f"/twins/{twin_id}/config/", headers=HEADERS)
    assert config_resp.status_code == 200
    assert config_resp.json()["aws_configured"] == False


def test_direct_twin_credentials_are_rejected():
    """Direct per-twin credential storage is disabled."""
    
    twin_resp = client.post("/twins/", json={"name": "Test"}, headers=HEADERS)
    twin_id = twin_resp.json()["id"]
    response = client.put(f"/twins/{twin_id}/config/",
        json={"aws": {
            "access_key_id": "AKIAIOSFODNN7EXAMPLE",
            "secret_access_key": "wJalrXUtnFEMI/K7MDENG",
            "region": "us-east-1"
        }},
        headers=HEADERS
    )

    assert response.status_code == 400
    assert "Cloud Connection" in response.json()["detail"]


def test_response_never_exposes_credentials():
    """API response should never contain actual credentials."""
    twin_resp = client.post("/twins/", json={"name": "Test"}, headers=HEADERS)
    twin_id = twin_resp.json()["id"]
    
    response = client.put(f"/twins/{twin_id}/config/",
        json={"aws": {
            "access_key_id": "AKIAIOSFODNN7EXAMPLE",
            "secret_access_key": "wJalrXUtnFEMI/K7MDENG",
            "region": "us-east-1"
        }},
        headers=HEADERS
    )
    assert response.status_code == 400
    
    config_resp = client.get(f"/twins/{twin_id}/config/", headers=HEADERS)
    data = config_resp.json()
    
    assert "aws_configured" in data
    assert "AKIAIOSFODNN7EXAMPLE" not in str(data)
