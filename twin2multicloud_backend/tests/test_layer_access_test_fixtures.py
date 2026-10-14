"""Credential-free fixture coverage for the real local Layer Access API."""

from __future__ import annotations

import pytest

from src.models.user import User
from src.repositories.deployment_repository import DeploymentRepository
from src.repositories.twin_repository import TwinRepository
from src.services.deployment_access_service import DeploymentAccessService
from src.services.deployment_operation_read_service import (
    build_deployment_outputs_response,
)
from src.services.service_errors import ConflictError, EntityNotFoundError
from src.services.test_layer_access_service import seed_layer_access_fixtures


def _seed(db):
    owner = User(email="layer-access-owner@example.invalid", name="Owner")
    db.add(owner)
    db.flush()
    payload = seed_layer_access_fixtures(db, owner=owner)
    return owner, payload


def _service(db) -> DeploymentAccessService:
    return DeploymentAccessService(
        twin_repository=TwinRepository(db),
        deployment_repository=DeploymentRepository(db),
    )


def test_fixture_matrix_covers_exact_nine_owner_scoped_placements(db) -> None:
    owner, payload = _seed(db)

    assert payload["schema_version"] == "layer-access-test-fixtures.v1"
    assert set(payload["placements"]) == {
        f"{l4}-{l5}" for l4 in ("aws", "azure", "gcp") for l5 in ("aws", "azure", "gcp")
    }
    for placement, twin_id in payload["placements"].items():
        l4, l5 = placement.split("-")
        snapshot = _service(db).get_access(twin_id, owner.id)
        assert [(surface.layer, surface.provider) for surface in snapshot.surfaces] == [
            ("l4", l4),
            ("l5", l5),
        ]


def test_fixture_edges_are_explicit_and_outputs_remain_redacted(db) -> None:
    owner, payload = _seed(db)
    service = _service(db)

    with pytest.raises(ConflictError, match="PROFILE_NOT_SUPPORTED"):
        service.get_access(payload["unsupported_twin_id"], owner.id)

    blocked = service.get_access(payload["blocked_twin_id"], owner.id)
    assert blocked.surfaces[0].readiness.access_binding == "blocked"
    assert blocked.surfaces[0].limitations == (
        "ACCESS_BINDING_BLOCKED",
        "Grant the thesis researcher access, then retry Layer Access.",
    )
    assert blocked.surfaces[1].readiness.access_binding == "ready"

    with pytest.raises(ConflictError, match="REQUIRES_DEPLOYED_TWIN"):
        service.get_access(payload["destroyed_twin_id"], owner.id)
    with pytest.raises(EntityNotFoundError, match="Twin not found"):
        service.get_access(payload["foreign_owner_twin_id"], owner.id)

    deployment = DeploymentRepository(db).latest_successful_deploy(
        payload["outputs_twin_id"]
    )
    outputs = build_deployment_outputs_response(deployment)
    assert outputs.redacted is True
    assert outputs.outputs is not None
    safe_endpoint = outputs.outputs["safe_endpoint"]
    assert outputs.outputs == {
        "safe_endpoint": safe_endpoint,
        "admin_password": "[REDACTED]",
        "reader_token": "[REDACTED]",
    }
    assert safe_endpoint.startswith("https://outputs-")
    assert "must-not-cross-api" not in outputs.model_dump_json()
