"""Tests for the Management API deployment read boundary."""

from __future__ import annotations

from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from src.models.deployment import Deployment
from src.models.optimizer_config import OptimizerConfiguration
from src.models.twin import DigitalTwin, TwinState
from src.models.user import User
from src.repositories.deployment_repository import DeploymentRepository
from src.repositories.twin_repository import TwinRepository
from src.services.deployment_read_service import DeploymentReadService
from src.services.service_errors import EntityNotFoundError


class FakeDeployerClient:
    """Test double for cooldown checks without network calls."""

    def __init__(self):
        self.calls = []

    async def check_cooldown(self, destroyed_at, uses_gcp_firestore):
        self.calls.append((destroyed_at, uses_gcp_firestore))
        return {"ready": False, "remaining_seconds": 123}


def _create_user(db, email: str = "reader@example.test") -> User:
    user = User(email=email, name="Reader", auth_provider="google")
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _create_twin(db, user: User, *, state: TwinState = TwinState.DRAFT) -> DigitalTwin:
    twin = DigitalTwin(name=f"Twin {id(db)}", user_id=user.id, state=state)
    db.add(twin)
    db.commit()
    db.refresh(twin)
    return twin


def _service(db, deployer_client=None) -> DeploymentReadService:
    return DeploymentReadService(
        twin_repository=TwinRepository(db),
        deployment_repository=DeploymentRepository(db),
        deployer_client=deployer_client,
    )


@pytest.mark.asyncio
async def test_can_redeploy_skips_deployer_for_non_gcp_twin(db_session):
    user = _create_user(db_session)
    twin = _create_twin(db_session, user)
    fake_client = FakeDeployerClient()

    result = await _service(db_session, fake_client).can_redeploy(twin.id, user.id)

    assert result == {"ready": True, "remaining_seconds": 0}
    assert fake_client.calls == []


@pytest.mark.asyncio
async def test_can_redeploy_uses_optimizer_l3_hot_for_gcp_cooldown(db_session):
    user = _create_user(db_session)
    twin = _create_twin(db_session, user, state=TwinState.DESTROYED)
    twin.destroyed_at = datetime.utcnow() - timedelta(minutes=1)
    db_session.add(
        OptimizerConfiguration(
            twin_id=twin.id,
            cheapest_l3_hot="GCP",
        )
    )
    db_session.commit()
    fake_client = FakeDeployerClient()

    result = await _service(db_session, fake_client).can_redeploy(twin.id, user.id)

    assert result == {"ready": False, "remaining_seconds": 123}
    assert fake_client.calls == [(twin.destroyed_at, True)]


@pytest.mark.asyncio
async def test_get_status_includes_active_session_for_running_twin(db_session):
    user = _create_user(db_session)
    twin = _create_twin(db_session, user, state=TwinState.DEPLOYING)

    async def active_sessions(_twin_id):
        return [SimpleNamespace(session_id="session-123", operation_type="deploy")]

    result = await _service(db_session).get_status(
        twin_id=twin.id,
        user_id=user.id,
        active_session_provider=active_sessions,
    )

    assert result["state"] == TwinState.DEPLOYING
    assert result["active_session"] == {
        "session_id": "session-123",
        "sse_url": "/sse/deploy/session-123",
        "operation_type": "deploy",
    }


def test_get_outputs_returns_latest_successful_deployment(db_session):
    user = _create_user(db_session)
    twin = _create_twin(db_session, user)
    older = Deployment(
        twin_id=twin.id,
        session_id="older",
        operation_type="deploy",
        status="success",
        completed_at=datetime.utcnow() - timedelta(minutes=5),
        terraform_outputs={"endpoint": "old"},
    )
    newer = Deployment(
        twin_id=twin.id,
        session_id="newer",
        operation_type="test",
        status="success",
        completed_at=datetime.utcnow(),
        terraform_outputs={"endpoint": "new"},
    )
    failed = Deployment(
        twin_id=twin.id,
        session_id="failed",
        operation_type="deploy",
        status="failed",
        completed_at=datetime.utcnow() + timedelta(minutes=1),
        terraform_outputs={"endpoint": "failed"},
    )
    db_session.add_all([older, newer, failed])
    db_session.commit()

    result = _service(db_session).get_outputs(twin.id, user.id)

    assert result["outputs"] == {"endpoint": "new"}
    assert result["deployed_at"] == newer.completed_at.isoformat()


def test_get_history_orders_by_started_at_and_respects_limit(db_session):
    user = _create_user(db_session)
    twin = _create_twin(db_session, user)
    first = Deployment(
        twin_id=twin.id,
        session_id="first",
        operation_type="deploy",
        status="success",
        started_at=datetime.utcnow() - timedelta(minutes=2),
    )
    second = Deployment(
        twin_id=twin.id,
        session_id="second",
        operation_type="destroy",
        status="running",
        started_at=datetime.utcnow(),
    )
    db_session.add_all([first, second])
    db_session.commit()

    result = _service(db_session).get_history(twin.id, user.id, limit=1)

    assert [item["session_id"] for item in result["deployments"]] == ["second"]


def test_unknown_twin_raises_typed_not_found(db_session):
    user = _create_user(db_session)

    with pytest.raises(EntityNotFoundError):
        _service(db_session).get_outputs("missing-twin", user.id)

