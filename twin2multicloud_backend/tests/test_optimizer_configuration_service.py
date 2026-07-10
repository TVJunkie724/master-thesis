"""Tests for optimizer configuration service boundary."""

from __future__ import annotations

import pytest

from src.models.twin import DigitalTwin, TwinState
from src.models.user import User
from src.repositories.twin_repository import TwinRepository
from src.schemas.optimizer_config import OptimizerParamsUpdate, OptimizerResultUpdate
from src.services.optimizer_configuration_service import OptimizerConfigurationService
from src.services.service_errors import EntityNotFoundError


def _create_user(db, email: str = "optimizer-config-service@example.test") -> User:
    user = User(email=email, name="Optimizer Config", auth_provider="google")
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _create_twin(db, user: User, state: TwinState = TwinState.DRAFT) -> DigitalTwin:
    twin = DigitalTwin(name="Optimizer Config Twin", user_id=user.id, state=state)
    db.add(twin)
    db.commit()
    db.refresh(twin)
    return twin


def _service(db) -> OptimizerConfigurationService:
    return OptimizerConfigurationService(db, TwinRepository(db))


def test_get_config_creates_default_optimizer_config(db_session):
    user = _create_user(db_session)
    twin = _create_twin(db_session, user)

    response = _service(db_session).get_config(twin.id, user.id)

    assert response.twin_id == twin.id
    assert response.params is None
    assert response.result is None
    assert response.cheapest_path is None


def test_update_params_persists_without_calculation(db_session):
    user = _create_user(db_session)
    twin = _create_twin(db_session, user)

    response = _service(db_session).update_params(
        twin.id,
        user.id,
        OptimizerParamsUpdate(params={"numberOfDevices": 250, "currency": "USD"}),
    )

    assert response.params == {"numberOfDevices": 250, "currency": "USD"}
    assert response.result is None
    assert response.cheapest_path is None


def test_save_result_persists_pricing_evidence_and_explicit_cheapest_path(db_session):
    user = _create_user(db_session)
    twin = _create_twin(db_session, user)

    response = _service(db_session).save_result(
        twin.id,
        user.id,
        OptimizerResultUpdate(
            params={"numberOfDevices": 100},
            result={"calculationResult": {"L1": "GCP"}},
            cheapest_path={
                "l1": "AWS",
                "l2": "AZURE",
                "l3_hot": "GCP",
                "l3_cool": "AWS",
                "l3_archive": "AZURE",
                "l4": "GCP",
                "l5": "AWS",
            },
            pricing_snapshots={
                "aws": {"source": "aws"},
                "azure": {"source": "azure"},
                "gcp": {"source": "gcp"},
            },
            pricing_timestamps={
                "aws": "2026-06-21T08:15:00Z",
                "azure": "invalid timestamp",
                "gcp": "2026-06-21T08:20:00+00:00",
            },
        ),
    )

    assert response.cheapest_path is not None
    assert response.cheapest_path.l1 == "aws"
    assert response.cheapest_path.l2 == "azure"
    assert response.pricing_aws_snapshot == {"source": "aws"}
    assert response.pricing_azure_snapshot == {"source": "azure"}
    assert response.pricing_gcp_snapshot == {"source": "gcp"}
    assert response.pricing_aws_updated_at is not None
    assert response.pricing_azure_updated_at is None
    assert response.pricing_gcp_updated_at is not None
    assert response.calculated_at is not None


def test_save_result_derives_missing_cheapest_path_from_calculation_result(db_session):
    user = _create_user(db_session)
    twin = _create_twin(db_session, user)

    response = _service(db_session).save_result(
        twin.id,
        user.id,
        OptimizerResultUpdate(
            params={"numberOfDevices": 100},
            result={
                "calculationResult": {
                    "L1": "GCP",
                    "L2": "AWS",
                    "L3": {"Hot": "AZURE", "Cool": "GCP", "Archive": "AWS"},
                    "L4": "AZURE",
                    "L5": "GCP",
                }
            },
            cheapest_path={},
            pricing_snapshots={},
            pricing_timestamps={},
        ),
    )

    assert response.cheapest_path is not None
    assert response.cheapest_path.l1 == "gcp"
    assert response.cheapest_path.l2 == "aws"
    assert response.cheapest_path.l3_hot == "azure"
    assert response.cheapest_path.l3_cool == "gcp"
    assert response.cheapest_path.l3_archive == "aws"
    assert response.cheapest_path.l4 == "azure"
    assert response.cheapest_path.l5 == "gcp"


def test_get_cheapest_path_rejects_missing_result(db_session):
    user = _create_user(db_session)
    twin = _create_twin(db_session, user)
    _service(db_session).get_config(twin.id, user.id)

    with pytest.raises(EntityNotFoundError, match="No optimizer result found"):
        _service(db_session).get_cheapest_path(twin.id, user.id)


def test_service_rejects_inactive_twin(db_session):
    user = _create_user(db_session)
    twin = _create_twin(db_session, user, TwinState.INACTIVE)

    with pytest.raises(EntityNotFoundError, match="Twin not found"):
        _service(db_session).get_config(twin.id, user.id)
