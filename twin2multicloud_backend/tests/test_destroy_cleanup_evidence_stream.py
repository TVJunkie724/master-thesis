"""Destroy stream persistence coverage for first-class cleanup evidence."""

from __future__ import annotations

import json

import pytest
from sqlalchemy.orm import sessionmaker

from src.models.deployment import Deployment
from src.models.twin import DigitalTwin, TwinState
from src.models.user import User
from src.services.deployment_service import run_real_destroy_stream
from src.services.deployment_stream_service import (
    cleanup_session,
    create_session,
    get_session,
)
from tests.cleanup_evidence_test_data import complete_cleanup_evidence


class CompleteDestroyClient:
    def __init__(self, evidence: dict) -> None:
        self.evidence = evidence

    async def destroy_stream(self, provider, resource_name, operation_token):
        assert (provider, resource_name, operation_token) == (
            "aws",
            "factory-twin",
            "operation-package",
        )
        yield "event: complete"
        yield "data: " + json.dumps(
            {
                "event": "complete",
                "operation": "destroy",
                "success": True,
                "operation_id": "deployer-destroy-1",
                "cleanup_evidence": self.evidence,
            }
        )


@pytest.mark.asyncio
async def test_successful_destroy_persists_and_replays_cleanup_evidence(
    db_session,
    monkeypatch,
):
    user = User(email="destroy-evidence@example.test")
    db_session.add(user)
    db_session.flush()
    twin = DigitalTwin(
        name="Destroy Evidence Twin",
        user_id=user.id,
        state=TwinState.DESTROYING,
    )
    db_session.add(twin)
    db_session.flush()
    deployment = Deployment(
        twin_id=twin.id,
        session_id="destroy-evidence-session",
        operation_type="destroy",
        status="running",
    )
    db_session.add(deployment)
    db_session.commit()

    runtime_session_factory = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=db_session.get_bind(),
    )
    monkeypatch.setattr(
        "src.models.database.SessionLocal",
        runtime_session_factory,
    )
    evidence = complete_cleanup_evidence()
    await create_session(twin.id, deployment.session_id, "destroy")
    try:
        await run_real_destroy_stream(
            session_id=deployment.session_id,
            twin_id=twin.id,
            resource_name="factory-twin",
            provider="aws",
            operation_token="operation-package",
            deployer_client=CompleteDestroyClient(evidence),
        )

        db_session.expire_all()
        persisted_twin = db_session.get(DigitalTwin, twin.id)
        persisted_deployment = db_session.get(Deployment, deployment.id)
        replay_session = await get_session(deployment.session_id)

        assert persisted_twin.state == TwinState.DESTROYED
        assert persisted_deployment.status == "success"
        assert persisted_deployment.operation_id == "deployer-destroy-1"
        assert persisted_deployment.cleanup_evidence == evidence
        assert replay_session.logs[-1]["type"] == "complete"
        assert replay_session.logs[-1]["outputs"] == {"cleanup_evidence": evidence}
    finally:
        await cleanup_session(deployment.session_id)
