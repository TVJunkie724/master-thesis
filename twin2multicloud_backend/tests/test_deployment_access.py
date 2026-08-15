"""Layer Access persistence, owner scope, and strict read-model tests."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import hashlib
from types import SimpleNamespace

import pytest
from pydantic import ValidationError as PydanticValidationError

from src.models.deployment import Deployment
from src.models.twin import DigitalTwin, TwinState
from src.models.user import User
from src.repositories.deployment_repository import DeploymentRepository
from src.repositories.twin_repository import TwinRepository
from src.schemas.deployment_access import DeploymentAccessEvidence
from src.services.deployment_access_service import DeploymentAccessService
from src.services.service_errors import (
    ConflictError,
    EntityNotFoundError,
    ValidationError,
)


NOW = datetime(2026, 7, 31, 12, 0, tzinfo=timezone.utc)
SURFACES = {
    ("l4", "aws"): ("aws_iot_twinmaker", "aws_identity_center", "none"),
    ("l4", "azure"): ("azure_digital_twins", "azure_entra", "none"),
    ("l4", "gcp"): ("gcp_twin_explorer", "gcp_iap", "none"),
    ("l5", "aws"): ("aws_managed_grafana", "aws_identity_center", "none"),
    ("l5", "azure"): ("azure_managed_grafana", "azure_entra", "none"),
    ("l5", "gcp"): ("gcp_grafana_oss", "generated_viewer", "rotate"),
}


def _surface(layer: str, provider: str) -> dict:
    service, auth, action = SURFACES[(layer, provider)]
    return {
        "layer": layer,
        "provider": provider,
        "service_id": service,
        "display_name": f"{provider} {layer}",
        "url": f"https://{provider}-{layer}.example.invalid/access",
        "auth": {
            "mode": auth,
            "principal_label": "researcher@example.invalid",
            "credential_action": action,
        },
        "readiness": {
            "resource": "ready",
            "access_binding": "ready",
            "content": "pending",
            "data_probe": "pending",
            "browser_sign_in": "unverified",
        },
        "capabilities": ["bounded-inspection"],
        "limitations": ["poc"],
    }


def _evidence(
    l4: str,
    l5: str,
    *,
    profile_id: str = "five-layer-baseline",
    profile_version: str = "2",
) -> dict:
    return {
        "schema_version": "deployment-access-evidence.v1",
        "profile_id": profile_id,
        "profile_version": profile_version,
        "generated_at": NOW.isoformat().replace("+00:00", "Z"),
        "surfaces": [_surface("l4", l4), _surface("l5", l5)],
    }


def _seed(
    db,
    *,
    profile_id: str = "five-layer-baseline",
    profile_version: str = "2",
    l4: str = "aws",
    l5: str = "aws",
    state: TwinState = TwinState.DEPLOYED,
):
    user = User(email=f"owner-{id(db)}@example.invalid", name="Owner")
    db.add(user)
    db.flush()
    twin = DigitalTwin(name=f"Twin {l4}/{l5}", user_id=user.id, state=state)
    db.add(twin)
    db.flush()
    deployment = Deployment(
        twin_id=twin.id,
        session_id=f"session-{l4}-{l5}-{id(db)}",
        operation_type="deploy",
        status="success",
        started_at=NOW,
        completed_at=NOW,
        profile_id=profile_id,
        profile_version=profile_version,
        deployment_access_evidence=(
            _evidence(
                l4,
                l5,
                profile_id=profile_id,
                profile_version=profile_version,
            )
            if (profile_id, profile_version)
            in {
                ("five-layer-baseline", "2"),
                ("six-layer-eventing", "1"),
            }
            else None
        ),
        terraform_outputs={"unrelated_password": "must-not-be-read"},
    )
    db.add(deployment)
    db.commit()
    return user, twin, deployment


def _service(db) -> DeploymentAccessService:
    return DeploymentAccessService(
        TwinRepository(db),
        DeploymentRepository(db),
    )


class _FakeDeployer:
    def __init__(self, *, payload: dict | None = None):
        self.calls = []
        self.payload = payload or {
            "schema_version": "deployment-access-credential.v1",
            "layer": "l5",
            "provider": "gcp",
            "username": "researcher@example.invalid",
            "password": "rotated-fixture-password-123456",
            "issued_at": "2026-07-31T12:00:00Z",
        }

    async def rotate_gcp_grafana_viewer_credential(self, resource_name, token):
        self.calls.append((resource_name, token))
        return dict(self.payload)


def _rotation_service(db, deployer, *, blocker=None) -> DeploymentAccessService:
    async def prepare(_twin, _user_id, *, frozen_graph_evidence=None):
        assert frozen_graph_evidence is not None
        if blocker is not None:
            blocker["prepared"].set()
        return SimpleNamespace(
            resource_name="fixture-resource",
            operation_token="fixture-operation-token",
            graph_evidence=frozen_graph_evidence,
        )

    return DeploymentAccessService(
        TwinRepository(db),
        DeploymentRepository(db),
        db=db,
        deployer_client=deployer,
        project_preparer=prepare,
    )


@pytest.mark.parametrize("l4", ["aws", "azure", "gcp"])
@pytest.mark.parametrize("l5", ["aws", "azure", "gcp"])
@pytest.mark.parametrize(
    ("profile_id", "profile_version"),
    [("five-layer-baseline", "2"), ("six-layer-eventing", "1")],
)
def test_all_nine_placements_return_exact_l4_l5(
    db,
    l4: str,
    l5: str,
    profile_id: str,
    profile_version: str,
) -> None:
    user, twin, deployment = _seed(
        db,
        l4=l4,
        l5=l5,
        profile_id=profile_id,
        profile_version=profile_version,
    )

    snapshot = _service(db).get_access(twin.id, user.id)

    assert snapshot.availability == "available"
    assert snapshot.deployment_id == deployment.id
    assert [(item.layer, item.provider) for item in snapshot.surfaces] == [
        ("l4", l4),
        ("l5", l5),
    ]
    serialized = snapshot.model_dump_json()
    assert "must-not-be-read" not in serialized
    assert "password" not in serialized


def test_historical_profile_returns_explicit_unsupported_snapshot(db) -> None:
    user, twin, deployment = _seed(db, profile_version="1")

    snapshot = _service(db).get_access(twin.id, user.id)

    assert snapshot.deployment_id == deployment.id
    assert snapshot.availability == "unsupported"
    assert snapshot.reason_code == "unsupported_historical_profile"
    assert snapshot.surfaces == ()


def test_cross_owner_access_is_not_found(db) -> None:
    _owner, twin, _deployment = _seed(db)
    stranger = User(email="stranger@example.invalid", name="Stranger")
    db.add(stranger)
    db.commit()

    with pytest.raises(EntityNotFoundError, match="Twin not found"):
        _service(db).get_access(twin.id, stranger.id)


def test_destroyed_twin_returns_no_active_links(db) -> None:
    user, twin, _deployment = _seed(db, state=TwinState.DESTROYED)

    with pytest.raises(ConflictError, match="REQUIRES_DEPLOYED_TWIN"):
        _service(db).get_access(twin.id, user.id)


def test_invalid_persisted_evidence_fails_closed_without_output_fallback(db) -> None:
    user, twin, deployment = _seed(db)
    evidence = _evidence("aws", "aws")
    evidence["surfaces"][0]["access_token"] = "secret"
    deployment.deployment_access_evidence = evidence
    db.commit()

    with pytest.raises(ValidationError, match="EVIDENCE_INVALID"):
        _service(db).get_access(twin.id, user.id)


def test_persisted_evidence_must_match_the_deployment_profile(db) -> None:
    user, twin, deployment = _seed(
        db,
        profile_id="six-layer-eventing",
        profile_version="1",
    )
    deployment.deployment_access_evidence = _evidence("aws", "aws")
    db.commit()

    with pytest.raises(ValidationError, match="EVIDENCE_PROFILE_MISMATCH"):
        _service(db).get_access(twin.id, user.id)


def test_schema_rejects_provider_auth_mismatch_and_secret_field() -> None:
    evidence = _evidence("aws", "gcp")
    evidence["surfaces"][0]["auth"]["mode"] = "azure_entra"
    evidence["surfaces"][1]["password"] = "secret"

    with pytest.raises(PydanticValidationError):
        DeploymentAccessEvidence.model_validate(evidence)


def test_schema_rejects_crossed_active_profile_versions() -> None:
    evidence = _evidence(
        "aws",
        "aws",
        profile_id="six-layer-eventing",
        profile_version="2",
    )

    with pytest.raises(PydanticValidationError, match="profile/version"):
        DeploymentAccessEvidence.model_validate(evidence)


def test_owner_scoped_endpoint_returns_contract(auth_client, db) -> None:
    user = db.query(User).first()
    assert user is not None
    twin = DigitalTwin(name="Endpoint twin", user_id=user.id, state=TwinState.DEPLOYED)
    db.add(twin)
    db.flush()
    deployment = Deployment(
        twin_id=twin.id,
        session_id="endpoint-session",
        operation_type="deploy",
        status="success",
        started_at=NOW,
        completed_at=NOW,
        profile_id="five-layer-baseline",
        profile_version="2",
        deployment_access_evidence=_evidence("azure", "gcp"),
    )
    db.add(deployment)
    db.commit()

    response = auth_client.get(f"/twins/{twin.id}/deployment-access")

    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "deployment-access.v1"
    assert [item["provider"] for item in payload["surfaces"]] == ["azure", "gcp"]
    assert payload["reason_code"] is None


@pytest.mark.asyncio
async def test_gcp_rotation_reveals_once_and_persists_only_metadata(db) -> None:
    user, twin, deployment = _seed(db, l4="azure", l5="gcp")
    deployment.graph_validation = {"graph_digest": "sha256:" + ("1" * 64)}
    db.commit()
    deployer = _FakeDeployer()

    credential = await _rotation_service(db, deployer).rotate_gcp_grafana_viewer(
        twin.id, user.id
    )

    db.refresh(deployment)
    assert credential.password == "rotated-fixture-password-123456"
    assert credential.password not in repr(credential)
    assert deployer.calls == [("fixture-resource", "fixture-operation-token")]
    assert deployment.layer_access_credential_rotated_at == NOW.replace(tzinfo=None)
    assert (
        deployment.layer_access_credential_fingerprint
        == hashlib.sha256(credential.password.encode()).hexdigest()
    )
    assert credential.password not in str(deployment.__dict__)


@pytest.mark.asyncio
async def test_non_gcp_l5_rotation_performs_no_preparation_or_deployer_call(db) -> None:
    user, twin, deployment = _seed(db, l5="aws")
    deployment.graph_validation = {"graph_digest": "sha256:" + ("1" * 64)}
    db.commit()
    deployer = _FakeDeployer()

    with pytest.raises(ConflictError, match="ROTATION_NOT_AVAILABLE"):
        await _rotation_service(db, deployer).rotate_gcp_grafana_viewer(
            twin.id, user.id
        )

    assert deployer.calls == []


@pytest.mark.asyncio
async def test_concurrent_rotation_returns_exact_conflict_without_waiting(db) -> None:
    user, twin, deployment = _seed(db, l5="gcp")
    deployment.graph_validation = {"graph_digest": "sha256:" + ("1" * 64)}
    db.commit()
    started = asyncio.Event()
    release = asyncio.Event()

    class BlockingDeployer(_FakeDeployer):
        async def rotate_gcp_grafana_viewer_credential(self, resource_name, token):
            self.calls.append((resource_name, token))
            started.set()
            await release.wait()
            return dict(self.payload)

    deployer = BlockingDeployer()
    service = _rotation_service(db, deployer)
    first = asyncio.create_task(service.rotate_gcp_grafana_viewer(twin.id, user.id))
    await started.wait()

    with pytest.raises(ConflictError, match="ROTATION_IN_PROGRESS"):
        await service.rotate_gcp_grafana_viewer(twin.id, user.id)

    release.set()
    await first
    assert len(deployer.calls) == 1
