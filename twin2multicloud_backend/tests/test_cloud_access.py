import json

from src.models.cloud_connection import CloudConnection
from src.models.twin import DigitalTwin
from src.models.twin_config import TwinConfiguration


def test_cloud_access_inventory_requires_authentication(client):
    response = client.get("/cloud-access")

    assert response.status_code == 401


def _aws_request(display_name="AWS Deployment"):
    return {
        "provider": "aws",
        "display_name": display_name,
        "permission_set_version": "thesis-demo-v1",
        "cloud_scope": {"account_id": "123456789012", "region": "eu-central-1"},
        "aws": {
            "access_key_id": "AKIAIOSFODNN7EXAMPLE",
            "secret_access_key": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
            "region": "eu-central-1",
        },
    }


def _gcp_request(display_name="GCP Deployment"):
    return {
        "provider": "gcp",
        "display_name": display_name,
        "permission_set_version": "old-permission-set",
        "cloud_scope": {"project_id": "demo-project", "region": "europe-west1"},
        "gcp": {
            "project_id": "demo-project",
            "billing_account": "012345-6789AB-CDEF01",
            "region": "europe-west1",
            "service_account_json": json.dumps(
                {
                    "type": "service_account",
                    "client_email": "deployer@demo-project.iam.gserviceaccount.com",
                    "private_key": "-----BEGIN PRIVATE KEY-----\\nsecret\\n-----END PRIVATE KEY-----\\n",
                }
            ),
        },
    }


def test_cloud_access_inventory_returns_public_azure_and_missing_pricing(authenticated_client):
    client, headers = authenticated_client

    response = client.get("/cloud-access", headers=headers)

    assert response.status_code == 200
    data = response.json()
    assert data["schema_version"] == "cloud-access-inventory.v1"
    assert set(data["providers"]) == {"aws", "azure", "gcp"}

    assert data["providers"]["azure"]["pricing"] == {
        "connection_id": None,
        "provider": "azure",
        "purpose": "pricing",
        "scope": "public",
        "identity_label": "Azure Retail Prices API",
        "status": "active",
        "provider_account_id": None,
        "provider_project_id": None,
        "provider_subscription_id": None,
        "is_default_for_pricing": True,
        "last_validated_at": None,
        "last_used_at": None,
        "permission_set_status": None,
        "bound_twin_count": 0,
        "bound_twin_labels": [],
        "actions": [],
        "primary_message": "Azure pricing uses the public Retail Prices API.",
    }
    assert data["providers"]["aws"]["pricing"]["status"] == "missing"
    assert data["providers"]["gcp"]["pricing"]["status"] == "missing"
    assert data["providers"]["aws"]["deployment"] == []


def test_cloud_access_inventory_lists_deployment_connections_without_secrets(
    authenticated_client,
):
    client, headers = authenticated_client
    created = client.post("/cloud-connections/", json=_aws_request(), headers=headers).json()

    response = client.get("/cloud-access", headers=headers)

    assert response.status_code == 200
    data = response.json()
    aws_deployment = data["providers"]["aws"]["deployment"]
    assert len(aws_deployment) == 1
    entry = aws_deployment[0]
    assert entry["connection_id"] == created["id"]
    assert entry["provider"] == "aws"
    assert entry["purpose"] == "deployment"
    assert entry["scope"] == "user"
    assert entry["identity_label"] == "AWS Deployment"
    assert entry["provider_account_id"] == "123456789012"
    assert entry["permission_set_status"] == "matched"
    assert entry["bound_twin_count"] == 0
    assert entry["actions"] == ["validate", "delete", "review_validation"]

    response_text = response.text
    assert "AKIAIOSFODNN7EXAMPLE" not in response_text
    assert "wJalrXUtnFEMI" not in response_text


def test_cloud_access_inventory_marks_bound_connection_delete_blocked(
    authenticated_client,
    db_session,
):
    client, headers = authenticated_client
    created = client.post("/cloud-connections/", json=_aws_request(), headers=headers).json()
    twin = client.post("/twins/", json={"name": "Factory Twin"}, headers=headers).json()
    db_session.add(
        TwinConfiguration(
            twin_id=twin["id"],
            aws_cloud_connection_id=created["id"],
        )
    )
    db_session.commit()

    response = client.get("/cloud-access", headers=headers)

    assert response.status_code == 200
    entry = response.json()["providers"]["aws"]["deployment"][0]
    assert entry["scope"] == "twin"
    assert entry["bound_twin_count"] == 1
    assert entry["bound_twin_labels"] == ["Factory Twin"]
    assert "delete_blocked" in entry["actions"]
    assert "delete" not in entry["actions"]


def test_cloud_access_inventory_is_user_scoped(authenticated_client, db_session):
    client, headers = authenticated_client
    created = client.post("/cloud-connections/", json=_aws_request(), headers=headers).json()
    db_session.query(CloudConnection).filter_by(
        id=created["id"],
    ).one().user_id = "other-user"
    db_session.commit()

    response = client.get("/cloud-access", headers=headers)

    assert response.status_code == 200
    assert response.json()["providers"]["aws"]["deployment"] == []


def test_cloud_access_inventory_reports_permission_set_status(authenticated_client):
    client, headers = authenticated_client
    client.post("/cloud-connections/", json=_gcp_request(), headers=headers)

    response = client.get("/cloud-access", headers=headers)

    assert response.status_code == 200
    entry = response.json()["providers"]["gcp"]["deployment"][0]
    assert entry["provider_project_id"] == "demo-project"
    assert entry["permission_set_status"] == "outdated"
    assert entry["primary_message"] == "Deployment permission set needs review before use."


def test_cloud_access_inventory_ignores_inactive_twin_bindings(
    authenticated_client,
    db_session,
):
    from src.models.twin import TwinState

    client, headers = authenticated_client
    created = client.post("/cloud-connections/", json=_aws_request(), headers=headers).json()
    twin = client.post("/twins/", json={"name": "Old Twin"}, headers=headers).json()
    db_session.query(DigitalTwin).filter_by(
        id=twin["id"],
    ).one().state = TwinState.INACTIVE
    db_session.add(
        TwinConfiguration(
            twin_id=twin["id"],
            aws_cloud_connection_id=created["id"],
        )
    )
    db_session.commit()

    response = client.get("/cloud-access", headers=headers)

    assert response.status_code == 200
    entry = response.json()["providers"]["aws"]["deployment"][0]
    assert entry["scope"] == "user"
    assert entry["bound_twin_count"] == 0
    assert entry["bound_twin_labels"] == []
