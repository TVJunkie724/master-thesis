"""Tests for optimizer pricing refresh service boundary."""

from __future__ import annotations

import pytest

from src.models.twin import DigitalTwin
from src.models.twin_config import TwinConfiguration
from src.models.user import User
from src.repositories.twin_repository import TwinRepository
from src.services.errors import ExternalServiceError, ExternalServiceUnavailable
from src.services.optimizer_pricing_refresh_service import OptimizerPricingRefreshService
from src.services.service_errors import DownstreamServiceError, EntityNotFoundError, ValidationError
from src.utils.crypto import encrypt
from tests.conftest import create_test_twin


def _create_user(db) -> User:
    user = User(email="optimizer-refresh-service@example.test", name="Optimizer Refresh", auth_provider="google")
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _create_twin(db, user: User) -> DigitalTwin:
    twin = DigitalTwin(name="Refresh Twin", user_id=user.id)
    db.add(twin)
    db.commit()
    db.refresh(twin)
    return twin


class FakeOptimizerClient:
    def __init__(self, payload=None, exc=None):
        self.payload = payload or {}
        self.exc = exc
        self.azure_calls = 0
        self.credential_calls = []

    async def refresh_azure_pricing(self):
        self.azure_calls += 1
        if self.exc:
            raise self.exc
        return self.payload

    async def refresh_pricing_with_credentials(self, provider, credentials):
        self.credential_calls.append((provider, credentials))
        if self.exc:
            raise self.exc
        return self.payload


def _service(db, optimizer_client=None) -> OptimizerPricingRefreshService:
    return OptimizerPricingRefreshService(
        db=db,
        twin_repository=TwinRepository(db),
        optimizer_client=optimizer_client,
    )


@pytest.mark.asyncio
async def test_refresh_azure_uses_public_optimizer_endpoint_without_credentials(db_session):
    user = _create_user(db_session)
    twin = _create_twin(db_session, user)
    fake = FakeOptimizerClient({"provider": "azure", "refreshed": True})

    result = await _service(db_session, fake).refresh_pricing("azure", twin.id, user.id)

    assert result == {"provider": "azure", "refreshed": True}
    assert fake.azure_calls == 1
    assert fake.credential_calls == []


@pytest.mark.asyncio
async def test_refresh_aws_decrypts_and_forwards_credentials(db_session):
    user = _create_user(db_session)
    twin = _create_twin(db_session, user)
    db_session.add(
        TwinConfiguration(
            twin_id=twin.id,
            aws_access_key_id=encrypt("AKIA_TEST", user.id, twin.id),
            aws_secret_access_key=encrypt("secret-test", user.id, twin.id),
            aws_region="eu-west-1",
        )
    )
    db_session.commit()
    db_session.refresh(twin)
    fake = FakeOptimizerClient({"provider": "aws", "refreshed": True})

    result = await _service(db_session, fake).refresh_pricing("aws", twin.id, user.id)

    assert result["refreshed"] is True
    assert fake.credential_calls == [
        (
            "aws",
            {
                "aws_access_key_id": "AKIA_TEST",
                "aws_secret_access_key": "secret-test",
                "aws_region": "eu-west-1",
            },
        )
    ]


@pytest.mark.asyncio
async def test_refresh_gcp_decrypts_and_forwards_service_account(db_session):
    user = _create_user(db_session)
    twin = _create_twin(db_session, user)
    db_session.add(
        TwinConfiguration(
            twin_id=twin.id,
            gcp_service_account_json=encrypt(
                '{"type":"service_account","project_id":"pricing-project"}',
                user.id,
                twin.id,
            ),
            gcp_region="europe-west3",
        )
    )
    db_session.commit()
    db_session.refresh(twin)
    fake = FakeOptimizerClient({"provider": "gcp", "refreshed": True})

    await _service(db_session, fake).refresh_pricing("gcp", twin.id, user.id)

    assert fake.credential_calls == [
        (
            "gcp",
            {
                "gcp_service_account_json": '{"type":"service_account","project_id":"pricing-project"}',
                "gcp_project_id": "pricing-project",
                "gcp_region": "europe-west3",
            },
        )
    ]


@pytest.mark.asyncio
async def test_refresh_rejects_invalid_provider_before_downstream_call(db_session):
    user = _create_user(db_session)
    twin = _create_twin(db_session, user)
    fake = FakeOptimizerClient()

    with pytest.raises(ValidationError, match="Invalid provider: digitalocean"):
        await _service(db_session, fake).refresh_pricing("digitalocean", twin.id, user.id)

    assert fake.azure_calls == 0
    assert fake.credential_calls == []


@pytest.mark.asyncio
async def test_refresh_rejects_missing_twin(db_session):
    user = _create_user(db_session)

    with pytest.raises(EntityNotFoundError, match="Twin not found"):
        await _service(db_session).refresh_pricing("aws", "missing", user.id)


@pytest.mark.asyncio
async def test_refresh_rejects_missing_configuration(db_session):
    user = _create_user(db_session)
    twin = _create_twin(db_session, user)

    with pytest.raises(ValidationError, match="Twin has no configuration"):
        await _service(db_session).refresh_pricing("aws", twin.id, user.id)


@pytest.mark.asyncio
async def test_refresh_rejects_incomplete_aws_credentials(db_session):
    user = _create_user(db_session)
    twin = _create_twin(db_session, user)
    db_session.add(TwinConfiguration(twin_id=twin.id, aws_access_key_id=encrypt("AKIA_TEST", user.id, twin.id)))
    db_session.commit()

    with pytest.raises(ValidationError, match="AWS credentials not configured"):
        await _service(db_session).refresh_pricing("aws", twin.id, user.id)


@pytest.mark.asyncio
async def test_refresh_maps_optimizer_non_200(db_session):
    user = _create_user(db_session)
    twin = _create_twin(db_session, user)

    with pytest.raises(DownstreamServiceError) as exc_info:
        await _service(
            db_session,
            FakeOptimizerClient(
                exc=ExternalServiceError(
                    "Optimizer API returned 500: optimizer failed",
                    upstream_status_code=500,
                    public_detail="optimizer failed",
                )
            ),
        ).refresh_pricing("azure", twin.id, user.id)

    assert exc_info.value.status_code == 500
    assert exc_info.value.public_detail == "optimizer failed"


@pytest.mark.asyncio
async def test_refresh_redacts_credentials_from_optimizer_error(db_session):
    user = _create_user(db_session)
    twin = _create_twin(db_session, user)
    db_session.add(
        TwinConfiguration(
            twin_id=twin.id,
            aws_access_key_id=encrypt("AKIA_TEST", user.id, twin.id),
            aws_secret_access_key=encrypt("secret-test", user.id, twin.id),
            aws_region="eu-west-1",
        )
    )
    db_session.commit()

    with pytest.raises(DownstreamServiceError) as exc_info:
        await _service(
            db_session,
            FakeOptimizerClient(
                exc=ExternalServiceError(
                    "Optimizer API returned 400: optimizer echoed secret-test",
                    upstream_status_code=400,
                    public_detail="optimizer echoed secret-test",
                )
            ),
        ).refresh_pricing("aws", twin.id, user.id)

    assert exc_info.value.public_detail == "optimizer echoed [REDACTED]"


@pytest.mark.asyncio
async def test_refresh_maps_timeout(db_session):
    user = _create_user(db_session)
    twin = _create_twin(db_session, user)

    with pytest.raises(DownstreamServiceError) as exc_info:
        await _service(
            db_session,
            FakeOptimizerClient(exc=ExternalServiceUnavailable("Optimizer API timed out")),
        ).refresh_pricing("azure", twin.id, user.id)

    assert exc_info.value.status_code == 504
    assert exc_info.value.public_detail == "Optimizer service timed out"


def test_refresh_pricing_route_maps_validation_error(authenticated_client):
    client, headers = authenticated_client
    twin_id = create_test_twin(client, headers)

    response = client.post(
        f"/optimizer/refresh-pricing/digitalocean?twin_id={twin_id}",
        headers=headers,
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid provider: digitalocean. Must be aws, azure, or gcp"


def test_refresh_pricing_route_maps_missing_twin(authenticated_client):
    client, headers = authenticated_client

    response = client.post("/optimizer/refresh-pricing/aws?twin_id=missing", headers=headers)

    assert response.status_code == 404
    assert response.json()["detail"] == "Twin not found"


def test_refresh_pricing_route_maps_downstream_timeout(authenticated_client):
    client, headers = authenticated_client
    twin_id = create_test_twin(client, headers)

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(
            "src.api.routes.optimizer._optimizer_pricing_refresh_service",
            lambda db: _service(
                db,
                FakeOptimizerClient(
                    exc=ExternalServiceUnavailable("Optimizer API timed out")
                ),
            ),
        )
        response = client.post(f"/optimizer/refresh-pricing/azure?twin_id={twin_id}", headers=headers)

    assert response.status_code == 504
    assert response.json()["detail"] == "Optimizer service timed out"
