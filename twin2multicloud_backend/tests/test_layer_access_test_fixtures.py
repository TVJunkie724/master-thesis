"""Credential-free fixture coverage for the real local Layer Access API."""

from __future__ import annotations

import hashlib

import pytest

from src.models.user import User
from src.repositories.deployment_repository import DeploymentRepository
from src.repositories.twin_repository import TwinRepository
from src.services.deployment_access_service import DeploymentAccessService
from src.services.deployment_operation_read_service import (
    build_deployment_outputs_response,
)
from src.services.service_errors import ConflictError, EntityNotFoundError
from src.services.test_layer_access_service import (
    TestLayerAccessDeployerClient,
    prepare_test_layer_access_rotation,
    seed_layer_access_fixtures,
    test_rotation_count as rotation_count,
)


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
        db=db,
        deployer_client=TestLayerAccessDeployerClient(),
        project_preparer=prepare_test_layer_access_rotation,
    )


def test_fixture_matrix_covers_exact_nine_owner_scoped_placements(db) -> None:
    owner, payload = _seed(db)

    assert payload["schema_version"] == "layer-access-test-fixtures.v1"
    assert set(payload["placements"]) == {
        f"{l4}-{l5}"
        for l4 in ("aws", "azure", "gcp")
        for l5 in ("aws", "azure", "gcp")
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

    historical = service.get_access(payload["historical_twin_id"], owner.id)
    assert historical.availability == "unsupported"
    assert historical.surfaces == ()

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


@pytest.mark.asyncio
async def test_fixture_rotation_changes_fingerprint_without_persisting_password(db) -> None:
    owner, payload = _seed(db)
    twin_id = payload["rotation_twin_id"]
    service = _service(db)

    first = await service.rotate_gcp_grafana_viewer(twin_id, owner.id)
    second = await service.rotate_gcp_grafana_viewer(twin_id, owner.id)

    deployment = DeploymentRepository(db).latest_successful_deploy(twin_id)
    assert deployment is not None
    assert rotation_count(twin_id) == 2
    assert first.password != second.password
    assert deployment.layer_access_credential_fingerprint == hashlib.sha256(
        second.password.encode("utf-8")
    ).hexdigest()
    persisted = str(deployment.__dict__)
    assert first.password not in persisted
    assert second.password not in persisted
