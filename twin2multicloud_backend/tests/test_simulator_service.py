"""Tests for simulator download service boundary."""

from __future__ import annotations

import io
import zipfile

import pytest

from src.clients.deployer_client import DeployerSimulatorArchive
from src.models.deployer_config import DeployerConfiguration
from src.models.optimizer_config import OptimizerConfiguration
from src.models.twin import DigitalTwin, TwinState
from src.models.user import User
from src.repositories.twin_repository import TwinRepository
from src.services.service_errors import DownstreamServiceError, EntityNotFoundError, ValidationError
from src.services.simulator_service import SimulatorDownloadService


def _create_user(db) -> User:
    user = User(email="simulator-service@example.test", name="Simulator Service", auth_provider="google")
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _create_twin(db, user: User, state: TwinState = TwinState.DEPLOYED) -> DigitalTwin:
    twin = DigitalTwin(name="Simulator Service Twin", user_id=user.id, state=state)
    db.add(twin)
    db.commit()
    db.refresh(twin)
    return twin


async def _prepare_project(_twin, _user_id):
    return "simulator-project"


def _zip_bytes() -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("README.md", "simulator")
    return buffer.getvalue()


def _archive(provider: str = "gcp") -> DeployerSimulatorArchive:
    classes = {
        "aws": "aws_iot_device_certificate",
        "azure": "azure_iot_hub_device_identity",
        "gcp": "gcp_pubsub_topic_publisher",
    }
    return DeployerSimulatorArchive(
        content=_zip_bytes(),
        filename=f"simulator_simulator-project_{provider}.zip",
        provider=provider,
        credential_class=classes[provider],
    )


async def _fetch_simulator(_resource_name, provider):
    return _archive(provider)


def _service(db, *, project_preparer=_prepare_project, simulator_fetcher=_fetch_simulator):
    return SimulatorDownloadService(
        db=db,
        twin_repository=TwinRepository(db),
        project_preparer=project_preparer,
        simulator_fetcher=simulator_fetcher,
    )


@pytest.mark.asyncio
async def test_download_fetches_deployer_archive_for_optimizer_l1(db_session):
    user = _create_user(db_session)
    twin = _create_twin(db_session, user)
    db_session.add(DeployerConfiguration(twin_id=twin.id, deployer_digital_twin_name="simulator-project"))
    db_session.add(OptimizerConfiguration(twin_id=twin.id, cheapest_l1="GCP"))
    db_session.commit()
    fetch_calls = []

    async def fetcher(resource_name, provider):
        fetch_calls.append((resource_name, provider))
        return _archive(provider)

    archive = await _service(db_session, simulator_fetcher=fetcher).download(
        twin_id=twin.id,
        user_id=user.id,
        test_mode=False,
    )

    assert archive.filename == "simulator_simulator-project_gcp.zip"
    assert archive.content.getvalue() == _zip_bytes()
    assert fetch_calls == [("simulator-project", "gcp")]


@pytest.mark.asyncio
async def test_download_normalizes_google_alias_for_deployer_api(db_session):
    user = _create_user(db_session)
    twin = _create_twin(db_session, user)
    db_session.add(DeployerConfiguration(twin_id=twin.id, deployer_digital_twin_name="simulator-project"))
    db_session.add(OptimizerConfiguration(twin_id=twin.id, cheapest_l1="Google"))
    db_session.commit()
    fetch_calls = []

    async def fetcher(resource_name, provider):
        fetch_calls.append((resource_name, provider))
        return _archive(provider)

    archive = await _service(db_session, simulator_fetcher=fetcher).download(
        twin_id=twin.id,
        user_id=user.id,
        test_mode=False,
    )

    assert archive.filename == "simulator_simulator-project_gcp.zip"
    assert fetch_calls == [("simulator-project", "gcp")]


@pytest.mark.asyncio
async def test_download_rejects_non_deployed_twin(db_session):
    user = _create_user(db_session)
    twin = _create_twin(db_session, user, TwinState.CONFIGURED)

    with pytest.raises(ValidationError):
        await _service(db_session).download(twin_id=twin.id, user_id=user.id, test_mode=False)


@pytest.mark.asyncio
async def test_download_rejects_missing_optimizer_l1(db_session):
    user = _create_user(db_session)
    twin = _create_twin(db_session, user)

    with pytest.raises(EntityNotFoundError):
        await _service(db_session).download(twin_id=twin.id, user_id=user.id, test_mode=False)


@pytest.mark.asyncio
async def test_download_wraps_project_preparation_failure(db_session):
    user = _create_user(db_session)
    twin = _create_twin(db_session, user)
    db_session.add(OptimizerConfiguration(twin_id=twin.id, cheapest_l1="AWS"))
    db_session.commit()

    async def failing_preparer(_twin, _user_id):
        raise RuntimeError("project setup failed")

    with pytest.raises(DownstreamServiceError) as exc:
        await _service(db_session, project_preparer=failing_preparer).download(
            twin_id=twin.id,
            user_id=user.id,
            test_mode=False,
        )

    assert exc.value.status_code == 500


@pytest.mark.asyncio
async def test_download_redacts_project_preparation_failure(db_session):
    user = _create_user(db_session)
    twin = _create_twin(db_session, user)
    db_session.add(OptimizerConfiguration(twin_id=twin.id, cheapest_l1="AWS"))
    db_session.commit()

    async def failing_preparer(_twin, _user_id):
        raise RuntimeError("aws_secret_access_key=SIMULATOR-SECRET-123")

    with pytest.raises(DownstreamServiceError) as exc:
        await _service(db_session, project_preparer=failing_preparer).download(
            twin_id=twin.id,
            user_id=user.id,
            test_mode=False,
        )

    assert "SIMULATOR-SECRET-123" not in exc.value.public_detail
    assert "aws_secret_access_key=[REDACTED]" in exc.value.public_detail


@pytest.mark.asyncio
async def test_download_uses_mock_archive_in_test_mode_without_optimizer(db_session):
    user = _create_user(db_session)
    twin = _create_twin(db_session, user)

    archive = await _service(db_session).download(twin_id=twin.id, user_id=user.id, test_mode=True)

    assert archive.filename == "simulator_simulator-service-twin_gcp.zip"
    assert archive.media_type == "application/zip"


@pytest.mark.asyncio
async def test_download_rejects_mismatched_deployer_provider_metadata(db_session):
    user = _create_user(db_session)
    twin = _create_twin(db_session, user)
    db_session.add(OptimizerConfiguration(twin_id=twin.id, cheapest_l1="AWS"))
    db_session.commit()

    async def fetcher(_resource_name, _provider):
        return _archive("gcp")

    with pytest.raises(DownstreamServiceError, match="mismatched"):
        await _service(db_session, simulator_fetcher=fetcher).download(
            twin_id=twin.id,
            user_id=user.id,
            test_mode=False,
        )


@pytest.mark.asyncio
async def test_download_rejects_mismatched_credential_class_metadata(db_session):
    user = _create_user(db_session)
    twin = _create_twin(db_session, user)
    db_session.add(OptimizerConfiguration(twin_id=twin.id, cheapest_l1="AWS"))
    db_session.commit()

    async def fetcher(_resource_name, _provider):
        archive = _archive("aws")
        return DeployerSimulatorArchive(
            content=archive.content,
            filename=archive.filename,
            provider=archive.provider,
            credential_class="gcp_pubsub_topic_publisher",
        )

    with pytest.raises(DownstreamServiceError, match="credential metadata"):
        await _service(db_session, simulator_fetcher=fetcher).download(
            twin_id=twin.id,
            user_id=user.id,
            test_mode=False,
        )
