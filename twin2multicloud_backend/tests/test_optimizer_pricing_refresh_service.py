"""Tests for optimizer pricing refresh service boundary."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from src.models.twin import DigitalTwin
from src.models.twin_config import TwinConfiguration
from src.models.user import User
from src.repositories.twin_repository import TwinRepository
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


def _service(db) -> OptimizerPricingRefreshService:
    return OptimizerPricingRefreshService(db=db, twin_repository=TwinRepository(db))


def _mock_response(status_code: int, payload: dict, text: str = "") -> MagicMock:
    response = MagicMock()
    response.status_code = status_code
    response.json.return_value = payload
    response.text = text
    return response


@pytest.mark.asyncio
async def test_refresh_azure_uses_public_optimizer_endpoint_without_credentials(db_session):
    user = _create_user(db_session)
    twin = _create_twin(db_session, user)

    with patch("src.services.optimizer_pricing_refresh_service.httpx.AsyncClient") as mock_client:
        post = AsyncMock(return_value=_mock_response(200, {"provider": "azure", "refreshed": True}))
        mock_client.return_value.__aenter__.return_value.post = post

        result = await _service(db_session).refresh_pricing("azure", twin.id, user.id)

    assert result == {"provider": "azure", "refreshed": True}
    assert post.call_args.args[0].endswith("/fetch_pricing/azure")
    assert post.call_args.kwargs["params"] == {"force_fetch": True}
    assert "json" not in post.call_args.kwargs


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

    with patch("src.services.optimizer_pricing_refresh_service.httpx.AsyncClient") as mock_client:
        post = AsyncMock(return_value=_mock_response(200, {"provider": "aws", "refreshed": True}))
        mock_client.return_value.__aenter__.return_value.post = post

        result = await _service(db_session).refresh_pricing("aws", twin.id, user.id)

    assert result["refreshed"] is True
    assert post.call_args.args[0].endswith("/fetch_pricing_with_credentials/aws")
    assert post.call_args.kwargs["json"] == {
        "aws_access_key_id": "AKIA_TEST",
        "aws_secret_access_key": "secret-test",
        "aws_region": "eu-west-1",
    }


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

    with patch("src.services.optimizer_pricing_refresh_service.httpx.AsyncClient") as mock_client:
        post = AsyncMock(return_value=_mock_response(200, {"provider": "gcp", "refreshed": True}))
        mock_client.return_value.__aenter__.return_value.post = post

        await _service(db_session).refresh_pricing("gcp", twin.id, user.id)

    assert post.call_args.args[0].endswith("/fetch_pricing_with_credentials/gcp")
    assert post.call_args.kwargs["json"] == {
        "gcp_service_account_json": '{"type":"service_account","project_id":"pricing-project"}',
        "gcp_project_id": "pricing-project",
        "gcp_region": "europe-west3",
    }


@pytest.mark.asyncio
async def test_refresh_rejects_invalid_provider_before_downstream_call(db_session):
    user = _create_user(db_session)
    twin = _create_twin(db_session, user)

    with patch("src.services.optimizer_pricing_refresh_service.httpx.AsyncClient") as mock_client:
        with pytest.raises(ValidationError, match="Invalid provider: digitalocean"):
            await _service(db_session).refresh_pricing("digitalocean", twin.id, user.id)

    mock_client.assert_not_called()


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

    with patch("src.services.optimizer_pricing_refresh_service.httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.post = AsyncMock(
            return_value=_mock_response(500, {}, "optimizer failed")
        )

        with pytest.raises(DownstreamServiceError) as exc_info:
            await _service(db_session).refresh_pricing("azure", twin.id, user.id)

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

    with patch("src.services.optimizer_pricing_refresh_service.httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.post = AsyncMock(
            return_value=_mock_response(400, {}, "optimizer echoed secret-test")
        )

        with pytest.raises(DownstreamServiceError) as exc_info:
            await _service(db_session).refresh_pricing("aws", twin.id, user.id)

    assert exc_info.value.public_detail == "optimizer echoed [REDACTED]"


@pytest.mark.asyncio
async def test_refresh_maps_timeout(db_session):
    user = _create_user(db_session)
    twin = _create_twin(db_session, user)

    with patch("src.services.optimizer_pricing_refresh_service.httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.post = AsyncMock(
            side_effect=httpx.TimeoutException("read timed out")
        )

        with pytest.raises(DownstreamServiceError) as exc_info:
            await _service(db_session).refresh_pricing("azure", twin.id, user.id)

    assert exc_info.value.status_code == 504
    assert exc_info.value.public_detail == "Optimizer service timed out"


def test_refresh_pricing_route_maps_validation_error(authenticated_client):
    client, headers = authenticated_client
    twin_id = create_test_twin(client, headers)

    with patch("src.services.optimizer_pricing_refresh_service.httpx.AsyncClient") as mock_client:
        response = client.post(
            f"/optimizer/refresh-pricing/digitalocean?twin_id={twin_id}",
            headers=headers,
        )

    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid provider: digitalocean. Must be aws, azure, or gcp"
    mock_client.assert_not_called()


def test_refresh_pricing_route_maps_missing_twin(authenticated_client):
    client, headers = authenticated_client

    response = client.post("/optimizer/refresh-pricing/aws?twin_id=missing", headers=headers)

    assert response.status_code == 404
    assert response.json()["detail"] == "Twin not found"


def test_refresh_pricing_route_maps_downstream_timeout(authenticated_client):
    client, headers = authenticated_client
    twin_id = create_test_twin(client, headers)

    with patch("src.services.optimizer_pricing_refresh_service.httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.post = AsyncMock(
            side_effect=httpx.TimeoutException("read timed out")
        )

        response = client.post(f"/optimizer/refresh-pricing/azure?twin_id={twin_id}", headers=headers)

    assert response.status_code == 504
    assert response.json()["detail"] == "Optimizer service timed out"
