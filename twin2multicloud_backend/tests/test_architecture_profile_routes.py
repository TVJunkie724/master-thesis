"""Canonical architecture API, redaction, ownership, and OpenAPI tests."""

from __future__ import annotations

from datetime import datetime, timezone

from src.api.dependencies import get_current_user
from src.main import app
from src.models.architecture_profile import ArchitectureAuditEvent
from src.models.twin import DigitalTwin
from src.models.user import User
from src.services.resolved_architecture_service import ResolvedArchitectureService
from tests.architecture_test_data import linked_architecture_fixture_documents
from tests.test_resolved_architecture_service import _state


def test_canonical_contract_routes_expose_one_fixed_six_layer_contract(
    authenticated_client,
    db_session,
):
    client, headers = authenticated_client
    created = client.post(
        "/twins/",
        json={"name": "Architecture API Twin"},
        headers=headers,
    )
    assert created.status_code == 200
    twin_id = created.json()["id"]

    detail = client.get("/architecture-contract", headers=headers)
    pin = client.get(
        f"/twins/{twin_id}/architecture-contract",
        headers=headers,
    )

    assert detail.status_code == 200
    assert detail.json()["profile_id"] == "six-layer-eventing"
    assert detail.json()["profile_version"] == "1"
    assert len(detail.json()["responsibilities"]) == 6
    assert pin.status_code == 200
    assert pin.json()["profile_id"] == "six-layer-eventing"
    assert pin.json()["profile_version"] == "1"
    assert pin.json()["revision"] == 1

    # Catalog, version selection, preview, and mutation are not PoC capabilities.
    assert client.get("/architecture-profiles", headers=headers).status_code == 404
    assert (
        client.get(
            "/architecture-profiles/six-layer-eventing/versions/1",
            headers=headers,
        ).status_code
        == 404
    )
    assert (
        client.post(
            f"/twins/{twin_id}/architecture-profile/change-preview",
            headers=headers,
            json={},
        ).status_code
        == 404
    )
    assert (
        client.put(
            f"/twins/{twin_id}/architecture-profile",
            headers=headers,
            json={},
        ).status_code
        == 404
    )

    db_session.expire_all()
    default_audit = (
        db_session.query(ArchitectureAuditEvent)
        .filter(
            ArchitectureAuditEvent.twin_id == twin_id,
            ArchitectureAuditEvent.action == "profile.select",
        )
        .one()
    )
    assert default_audit.outcome == "defaulted"

    unresolved = client.get(
        f"/twins/{twin_id}/resolved-architecture",
        headers=headers,
    )
    assert unresolved.status_code == 404
    assert unresolved.json()["error_code"] == "ARCH_RESOLUTION_NOT_SELECTED"


def test_canonical_contract_routes_require_auth(client):
    assert client.get("/architecture-contract").status_code == 401
    assert client.get("/twins/unknown/architecture-contract").status_code == 401


def test_twin_contract_route_hides_cross_owner_resources(
    authenticated_client,
    db_session,
):
    client, headers = authenticated_client
    current_user = db_session.query(User).first()
    other = User(id="other-api-owner", email="other-api@example.test")
    twin = DigitalTwin(
        id="other-api-twin",
        user_id=other.id,
        name="Other API Twin",
    )
    db_session.add_all([other, twin])
    db_session.commit()

    pin = client.get(
        f"/twins/{twin.id}/architecture-contract",
        headers=headers,
    )
    resolution = client.get(
        f"/twins/{twin.id}/resolved-architecture",
        headers=headers,
    )

    assert current_user.id != other.id
    assert pin.status_code == 404
    assert resolution.status_code == 404


def test_resolved_architecture_read_routes_return_same_safe_contract(
    client,
    auth_headers,
    db_session,
):
    user, twin, _config, run, architecture = _state(db_session)
    ResolvedArchitectureService(db_session).persist(
        run=run,
        raw_architecture=architecture,
        linked_documents=linked_architecture_fixture_documents(),
    )
    run.selected_for_deployment_at = datetime.now(timezone.utc)
    db_session.commit()
    app.dependency_overrides[get_current_user] = lambda: user
    try:
        selected = client.get(
            f"/twins/{twin.id}/resolved-architecture",
            headers=auth_headers,
        )
        by_run = client.get(
            f"/optimizer-runs/{run.id}/resolved-architecture",
            headers=auth_headers,
        )
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    assert selected.status_code == 200
    assert by_run.status_code == 200
    assert selected.json() == by_run.json()
    assert (
        selected.json()["architecture"]["content_digest"]
        == architecture["content_digest"]
    )
    assert "canonical_json" not in selected.text
    assert "configuration_json" not in selected.text
    assert "terraform" not in selected.text.lower()


def test_architecture_openapi_contract_is_fixed_and_read_only(client):
    openapi = client.get("/openapi.json").json()
    paths = openapi["paths"]

    assert "/architecture-contract" in paths
    assert set(paths["/architecture-contract"]) == {"get"}
    assert "/twins/{twin_id}/architecture-contract" in paths
    assert set(paths["/twins/{twin_id}/architecture-contract"]) == {"get"}
    assert "/twins/{twin_id}/resolved-architecture" in paths
    assert "/optimizer-runs/{run_id}/resolved-architecture" in paths
    assert "/architecture-profiles" not in paths
    assert "/architecture-profiles/{profile_id}/versions/{profile_version}" not in paths
    assert "/twins/{twin_id}/architecture-profile/change-preview" not in paths
    assert "/twins/{twin_id}/architecture-profile" not in paths

    schemas = openapi["components"]["schemas"]
    assert "ArchitectureProfileChangeRequest" not in schemas
    assert "ArchitectureProfileSelectionRequest" not in schemas
    resolution = schemas["ResolvedTwinArchitectureContractV2"]
    assert {
        "schema_version",
        "resolution_id",
        "component_assignments",
        "resolved_edges",
        "content_digest",
    }.issubset(resolution["required"])
    assert "request_id" in schemas["ArchitectureErrorResponse"]["required"]
