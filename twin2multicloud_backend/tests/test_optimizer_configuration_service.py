"""Tests for optimizer configuration service boundary."""

from __future__ import annotations

import pytest

from src.models.twin import DigitalTwin, TwinState
from src.models.user import User
from src.repositories.twin_repository import TwinRepository
from src.schemas.optimizer_config import OptimizerParamsUpdate, OptimizerResultUpdate
from src.services.optimizer_configuration_service import OptimizerConfigurationService
from src.services.errors import OptimizerContractError
from src.services.service_errors import EntityNotFoundError
from tests.pricing_catalog_test_data import catalog_context


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


class FakePricingCatalogContextService:
    async def resolve_for_user(self, _user_id):
        return catalog_context()


def _service(db, *, with_catalogs=False) -> OptimizerConfigurationService:
    return OptimizerConfigurationService(
        db,
        TwinRepository(db),
        pricing_catalog_contexts=(
            FakePricingCatalogContextService() if with_catalogs else None
        ),
    )


def test_get_config_creates_default_optimizer_config(db_session):
    user = _create_user(db_session)
    twin = _create_twin(db_session, user)

    response = _service(db_session).get_config(twin.id, user.id)

    assert response.twin_id == twin.id
    assert response.params is None
    assert response.result is None
    assert response.cheapest_path is None


def test_update_params_persists_without_calculation(db_session, sample_calc_params):
    user = _create_user(db_session)
    twin = _create_twin(db_session, user)

    response = _service(db_session).update_params(
        twin.id,
        user.id,
        OptimizerParamsUpdate(
            params={**sample_calc_params, "numberOfDevices": 250}
        ),
    )

    assert response.params == {**sample_calc_params, "numberOfDevices": 250}
    assert response.result is None
    assert response.cheapest_path is None


def test_update_params_persists_compatibility_defaults(
    db_session,
    sample_calc_params,
):
    user = _create_user(db_session)
    twin = _create_twin(db_session, user)
    params = {
        key: value
        for key, value in sample_calc_params.items()
        if not key.startswith("averageDigitalTwinQuery")
    }

    response = _service(db_session).update_params(
        twin.id,
        user.id,
        OptimizerParamsUpdate(params=params),
    )

    assert response.params["averageDigitalTwinQueryUnitsPerQuery"] == 1
    assert response.params["averageDigitalTwinQueryResponseSizeInKb"] == 1


@pytest.mark.asyncio
async def test_save_result_persists_catalog_context_and_explicit_cheapest_path(
    db_session,
    sample_calc_params,
):
    user = _create_user(db_session)
    twin = _create_twin(db_session, user)

    response = await _service(db_session, with_catalogs=True).save_result(
        twin.id,
        user.id,
        OptimizerResultUpdate(
            params=sample_calc_params,
            result={
                "calculationResult": {"L1": "GCP"},
                "pricingCatalogs": catalog_context().to_http_dict(),
            },
            cheapest_path={
                "l1": "AWS",
                "l2": "AZURE",
                "l3_hot": "GCP",
                "l3_cool": "AWS",
                "l3_archive": "AZURE",
                "l4": "GCP",
                "l5": "AWS",
            },
        ),
    )

    assert response.cheapest_path is not None
    assert response.cheapest_path.l1 == "aws"
    assert response.cheapest_path.l2 == "azure"
    assert response.pricing_catalog_context == catalog_context()
    assert response.calculated_at is not None


@pytest.mark.asyncio
async def test_save_result_derives_missing_cheapest_path_from_calculation_result(
    db_session,
    sample_calc_params,
):
    user = _create_user(db_session)
    twin = _create_twin(db_session, user)

    response = await _service(db_session, with_catalogs=True).save_result(
        twin.id,
        user.id,
        OptimizerResultUpdate(
            params=sample_calc_params,
            result={
                "calculationResult": {
                    "L1": "GCP",
                    "L2": "AWS",
                    "L3": {"Hot": "AZURE", "Cool": "GCP", "Archive": "AWS"},
                    "L4": "AZURE",
                    "L5": "GCP",
                },
                "pricingCatalogs": catalog_context().to_http_dict(),
            },
            cheapest_path={},
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


@pytest.mark.asyncio
async def test_save_result_rejects_client_result_with_different_catalogs(
    db_session,
    sample_calc_params,
):
    user = _create_user(db_session)
    twin = _create_twin(db_session, user)

    with pytest.raises(OptimizerContractError):
        await _service(db_session, with_catalogs=True).save_result(
            twin.id,
            user.id,
            OptimizerResultUpdate(
                params=sample_calc_params,
                result={
                    "calculationResult": {"L1": "GCP"},
                    "pricingCatalogs": {
                        **catalog_context().to_http_dict(),
                        "schemaVersion": "tampered",
                    },
                },
                cheapest_path={"l1": "GCP"},
            ),
        )


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
