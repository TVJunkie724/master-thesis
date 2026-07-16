from fastapi.testclient import TestClient

from rest_api import app


def test_provider_capability_endpoint_returns_complete_contract():
    response = TestClient(app).get("/capabilities/providers")

    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "provider-service-capabilities.v1"
    assert payload["service"] == "optimizer"
    assert [item["provider"] for item in payload["providers"]] == [
        "aws",
        "azure",
        "gcp",
    ]
    assert all(len(item["layers"]) == 7 for item in payload["providers"])
