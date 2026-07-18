from fastapi.testclient import TestClient

from backend.pricing_catalog_repository import get_pricing_catalog_repository
from rest_api import app


client = TestClient(app)


def test_catalog_api_exposes_reference_then_exact_snapshot():
    baseline_response = client.get("/pricing/catalogs/baseline/azure")

    assert baseline_response.status_code == 200
    reference = baseline_response.json()
    assert reference["provider"] == "azure"
    assert reference["pricingRegion"] == "westeurope"

    published_response = client.get(
        "/pricing/catalogs/azure/westeurope/published"
    )
    assert published_response.status_code == 200
    assert published_response.json()["reference"] == reference

    reference_response = client.get(
        "/pricing/catalogs/azure/westeurope/snapshots/"
        f"{reference['snapshotId']}/reference"
    )
    assert reference_response.status_code == 200
    assert reference_response.json()["reference"] == reference
    assert reference_response.json()["isFresh"] is True

    snapshot_response = client.get(
        "/pricing/catalogs/azure/westeurope/snapshots/"
        f"{reference['snapshotId']}"
    )
    assert snapshot_response.status_code == 200
    assert snapshot_response.json()["reference"] == reference
    assert "azureDigitalTwins" in snapshot_response.json()["pricing"]


def test_catalog_api_rejects_implicit_global_export():
    response = client.get("/pricing/export/aws")

    assert response.status_code == 404


def test_catalog_api_rejects_cross_region_snapshot_lookup():
    reference = get_pricing_catalog_repository().resolve_baseline(
        "azure",
        require_fresh=False,
    ).reference

    response = client.get(
        "/pricing/catalogs/azure/northeurope/snapshots/"
        f"{reference.snapshot_id}"
    )

    assert response.status_code == 404


def test_catalog_api_rejects_invalid_region_before_storage_lookup():
    response = client.get(
        "/pricing/catalogs/aws/not-an-aws-region/published"
    )

    assert response.status_code == 400
    assert response.json()["detail"]["error_code"] == (
        "PRICING_CATALOG_REFERENCE_INVALID"
    )
    assert response.json()["detail"]["message"] == "AWS pricing region is invalid"


def test_catalog_api_rejects_malformed_snapshot_identity_as_not_found():
    response = client.get(
        "/pricing/catalogs/gcp/europe-west1/snapshots/not-a-snapshot"
    )

    assert response.status_code == 404
