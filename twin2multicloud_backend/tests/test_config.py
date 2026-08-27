def test_get_config_creates_default(authenticated_client):
    """GET config should auto-create if missing."""
    client, headers = authenticated_client
    twin_resp = client.post("/twins/", json={"name": "Test"}, headers=headers)
    twin_id = twin_resp.json()["id"]
    
    config_resp = client.get(f"/twins/{twin_id}/config/", headers=headers)
    assert config_resp.status_code == 200
    assert config_resp.json()["aws_configured"] is False


def test_direct_twin_credentials_are_rejected(authenticated_client):
    """Direct per-twin credential storage is disabled."""
    client, headers = authenticated_client
    twin_resp = client.post("/twins/", json={"name": "Test"}, headers=headers)
    twin_id = twin_resp.json()["id"]
    response = client.put(f"/twins/{twin_id}/config/",
        json={"aws": {
            "access_key_id": "AKIAIOSFODNN7EXAMPLE",
            "secret_access_key": "wJalrXUtnFEMI/K7MDENG",
            "region": "us-east-1"
        }},
        headers=headers
    )

    assert response.status_code == 400
    assert "Cloud Connection" in response.json()["detail"]


def test_response_never_exposes_credentials(authenticated_client):
    """API response should never contain actual credentials."""
    client, headers = authenticated_client
    twin_resp = client.post("/twins/", json={"name": "Test"}, headers=headers)
    twin_id = twin_resp.json()["id"]
    
    response = client.put(f"/twins/{twin_id}/config/",
        json={"aws": {
            "access_key_id": "AKIAIOSFODNN7EXAMPLE",
            "secret_access_key": "wJalrXUtnFEMI/K7MDENG",
            "region": "us-east-1"
        }},
        headers=headers
    )
    assert response.status_code == 400
    
    config_resp = client.get(f"/twins/{twin_id}/config/", headers=headers)
    data = config_resp.json()
    
    assert "aws_configured" in data
    assert "AKIAIOSFODNN7EXAMPLE" not in str(data)
