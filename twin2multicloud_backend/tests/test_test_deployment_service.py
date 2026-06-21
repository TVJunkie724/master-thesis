"""Tests for gated test-only deployment service boundaries."""

from __future__ import annotations

import json
import zipfile

import pytest

from src.models.deployer_config import DeployerConfiguration
from src.models.optimizer_config import OptimizerConfiguration
from src.models.twin import DigitalTwin, TwinState
from src.models.user import User
from src.repositories.twin_repository import TwinRepository
from src.services.service_errors import EntityNotFoundError
from src.services.test_deployment_service import TestDeploymentService as GatedTestDeploymentService


def _create_user(db) -> User:
    user = User(email="test-deployment-service@example.test", name="Test Service", auth_provider="google")
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _create_twin(db, user: User, name: str = "Trace Twin") -> DigitalTwin:
    twin = DigitalTwin(name=name, user_id=user.id, state=TwinState.CONFIGURED)
    db.add(twin)
    db.commit()
    db.refresh(twin)
    return twin


def _closing_scheduler(scheduled):
    def schedule(coro):
        scheduled.append(coro)
        coro.close()

    return schedule


def _session_recorder(records):
    async def create(twin_id, session_id, operation_type):
        records.append((twin_id, session_id, operation_type))

    return create


async def _fake_log_trace_runner(**_kwargs):
    return None


def _service(db, *, session_records=None, scheduled=None) -> GatedTestDeploymentService:
    session_records = session_records if session_records is not None else []
    scheduled = scheduled if scheduled is not None else []
    return GatedTestDeploymentService(
        db=db,
        twin_repository=TwinRepository(db),
        session_creator=_session_recorder(session_records),
        task_scheduler=_closing_scheduler(scheduled),
    )


@pytest.mark.asyncio
async def test_start_log_trace_creates_session_and_schedules_runner(db_session):
    user = _create_user(db_session)
    twin = _create_twin(db_session, user)
    session_records = []
    scheduled = []

    result = await _service(db_session, session_records=session_records, scheduled=scheduled).start_log_trace(
        twin_id=twin.id,
        user_id=user.id,
        duration=30,
        should_fail=False,
        test_log_trace_runner=_fake_log_trace_runner,
    )

    assert result["trace_id"].startswith("TRACE-")
    assert result["providers"] == ["aws"]
    assert result["l1_provider"] == "aws"
    assert result["sse_url"].startswith("/sse/deploy/")
    assert session_records[0][0] == twin.id
    assert session_records[0][2] == "log_trace"
    assert len(scheduled) == 1


@pytest.mark.asyncio
async def test_start_log_trace_rejects_missing_twin(db_session):
    user = _create_user(db_session)

    with pytest.raises(EntityNotFoundError):
        await _service(db_session).start_log_trace(
            twin_id="missing",
            user_id=user.id,
            duration=30,
            should_fail=False,
            test_log_trace_runner=_fake_log_trace_runner,
        )


def test_build_mock_simulator_archive_uses_optimizer_and_deployer_names(db_session):
    user = _create_user(db_session)
    twin = _create_twin(db_session, user, name="Simulator Twin")
    db_session.add(OptimizerConfiguration(twin_id=twin.id, cheapest_l1="AZURE"))
    db_session.add(
        DeployerConfiguration(
            twin_id=twin.id,
            deployer_digital_twin_name="canonical-simulator-name",
        )
    )
    db_session.commit()

    archive = _service(db_session).build_mock_simulator_archive(twin_id=twin.id, user_id=user.id)

    assert archive.filename == "simulator_canonical-simulator-name_azure.zip"
    with zipfile.ZipFile(archive.content) as zip_file:
        assert set(zip_file.namelist()) == {
            "config.json",
            "payloads.json",
            "README.md",
            "requirements.txt",
            "src/main.py",
        }
        config = json.loads(zip_file.read("config.json"))
        assert config["digital_twin_name"] == "canonical-simulator-name"
        assert config["topic_name"] == "projects/mock-project/topics/canonical-simulator-name-telemetry"
        assert "AZURE" in zip_file.read("README.md").decode("utf-8")


def test_build_mock_simulator_archive_rejects_missing_twin(db_session):
    user = _create_user(db_session)

    with pytest.raises(EntityNotFoundError):
        _service(db_session).build_mock_simulator_archive(twin_id="missing", user_id=user.id)
