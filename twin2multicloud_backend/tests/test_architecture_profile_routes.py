"""Authenticated architecture APIs, redaction, ownership, and OpenAPI tests."""

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


def test_profile_routes_expose_only_active_six_layer_profile(
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

    listed = client.get("/architecture-profiles", headers=headers)
    detail = client.get(
        "/architecture-profiles/six-layer-eventing/versions/1",
        headers=headers,
    )
    active_detail = client.get(
        "/architecture-profiles/six-layer-eventing/versions/2",
        headers=headers,
    )
    selection = client.get(
        f"/twins/{twin_id}/architecture-profile",
        headers=headers,
    )

    assert listed.status_code == 200
    assert [
        (item["profile_id"], item["profile_version"]) for item in listed.json()
    ] == [
        ("six-layer-eventing", "1"),
    ]
    assert detail.status_code == 200
    assert detail.json()["profile_version"] == "1"
    assert active_detail.status_code in {404, 409}
    assert selection.status_code == 200
    assert selection.json()["revision"] == 1
    assert selection.json()["profile_version"] == "1"
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

    preview = client.post(
        f"/twins/{twin_id}/architecture-profile/change-preview",
        headers=headers,
        json={
            "profile_id": "six-layer-eventing",
            "profile_version": "1",
            "expected_revision": 1,
        },
    )
    assert preview.status_code == 200

    unresolved = client.get(
        f"/twins/{twin_id}/resolved-architecture",
        headers=headers,
    )
    assert unresolved.status_code == 404
    assert unresolved.json()["error_code"] == "ARCH_RESOLUTION_NOT_SELECTED"


def test_profile_routes_require_auth_and_reject_client_authored_state(
    client,
    auth_headers,
):
    assert client.get("/architecture-profiles").status_code == 401
    twin = client.post(
        "/twins/",
        json={"name": "Strict Request Twin"},
        headers=auth_headers,
    )
    assert twin.status_code == 200
    twin_id = twin.json()["id"]

    preview = client.post(
        f"/twins/{twin_id}/architecture-profile/change-preview",
        headers=auth_headers,
        json={
            "profile_id": "six-layer-eventing",
            "profile_version": "1",
            "expected_revision": 1,
            "profile_digest": "sha256:" + ("0" * 64),
        },
    )
    select = client.put(
        f"/twins/{twin_id}/architecture-profile",
        headers=auth_headers,
        json={
            "profile_id": "six-layer-eventing",
            "profile_version": "1",
            "expected_revision": 1,
            "invalidation_digest": "sha256:" + ("0" * 64),
            "components": [{"provider": "aws"}],
        },
    )
    traversal = client.post(
        f"/twins/{twin_id}/architecture-profile/change-preview",
        headers=auth_headers,
        json={
            "profile_id": "../provider-implementations",
            "profile_version": "1",
            "expected_revision": 1,
        },
    )
    unknown = client.get(
        "/architecture-profiles/unknown-profile/versions/1",
        headers=auth_headers,
    )

    assert preview.status_code == 422
    assert select.status_code == 422
    assert traversal.status_code == 422
    assert unknown.status_code == 404
    assert unknown.json()["error_code"] == "ARCH_PROFILE_NOT_FOUND"


def test_profile_routes_hide_cross_owner_resources(
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

    selection = client.get(
        f"/twins/{twin.id}/architecture-profile",
        headers=headers,
    )
    resolution = client.get(
        f"/twins/{twin.id}/resolved-architecture",
        headers=headers,
    )

    assert current_user.id != other.id
    assert selection.status_code == 404
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


def test_architecture_openapi_contract_is_strict(client):
    openapi = client.get("/openapi.json").json()
    paths = openapi["paths"]

    assert "/architecture-profiles" in paths
    assert "/architecture-profiles/{profile_id}/versions/{profile_version}" in paths
    assert "/twins/{twin_id}/architecture-profile" in paths
    assert "/twins/{twin_id}/resolved-architecture" in paths
    assert "/optimizer-runs/{run_id}/resolved-architecture" in paths

    schemas = openapi["components"]["schemas"]
    preview_request = schemas["ArchitectureProfileChangeRequest"]
    selection_request = schemas["ArchitectureProfileSelectionRequest"]
    resolution = schemas["ResolvedTwinArchitectureContractV2"]
    assert preview_request["additionalProperties"] is False
    assert selection_request["additionalProperties"] is False
    assert "invalidation_digest" in selection_request["required"]
    assert {
        "schema_version",
        "resolution_id",
        "component_assignments",
        "resolved_edges",
        "content_digest",
    }.issubset(resolution["required"])
    conflict_schema = paths["/twins/{twin_id}/architecture-profile"]["put"][
        "responses"
    ]["409"]["content"]["application/json"]["schema"]
    assert conflict_schema["$ref"].endswith("/ArchitectureErrorResponse")
    assert "request_id" in schemas["ArchitectureErrorResponse"]["required"]
