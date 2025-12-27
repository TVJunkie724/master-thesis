import pytest
from fastapi.testclient import TestClient
from src.main import app
from src.models.database import Base, engine, SessionLocal
from src.models.user import User
from src.utils.crypto import decrypt

client = TestClient(app)
HEADERS = {"Authorization": "Bearer dev-token"}


def get_dev_user_id():
    """Get the dev user's ID from database."""
    db = SessionLocal()
    user = db.query(User).filter(User.email == "dev@example.com").first()
    user_id = user.id if user else None
    db.close()
    return user_id


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


def test_credentials_stored_encrypted():
    """Credentials should be encrypted in DB with user+twin-specific key."""
    from src.models.twin_config import TwinConfiguration
    
    twin_resp = client.post("/twins/", json={"name": "Test"}, headers=HEADERS)
    twin_id = twin_resp.json()["id"]
    dev_user_id = get_dev_user_id()
    
    client.put(f"/twins/{twin_id}/config/", 
        json={"aws": {
            "access_key_id": "AKIAIOSFODNN7EXAMPLE",
            "secret_access_key": "wJalrXUtnFEMI/K7MDENG",
            "region": "us-east-1"
        }},
        headers=HEADERS
    )
    
    db = SessionLocal()
    config = db.query(TwinConfiguration).filter_by(twin_id=twin_id).first()
    
    assert config.aws_access_key_id != "AKIAIOSFODNN7EXAMPLE"
    assert config.aws_access_key_id.startswith("gAAAAA")
    assert decrypt(config.aws_access_key_id, dev_user_id, twin_id) == "AKIAIOSFODNN7EXAMPLE"
    
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
    
    assert "aws_configured" in data
    assert "AKIAIOSFODNN7EXAMPLE" not in str(data)
