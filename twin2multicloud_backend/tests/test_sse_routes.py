"""Owner and canonical-registry coverage for deployment SSE routes."""

from __future__ import annotations

import uuid

import pytest

from src.models.deployment import Deployment
from src.models.deployment_log import DeploymentLog
from src.services.deployment_stream_service import cleanup_session, create_session


@pytest.mark.asyncio
async def test_sse_route_reads_canonical_session_and_replays_terminal_event(
    authenticated_client,
    db_session,
):
    client, headers = authenticated_client
    twin_response = client.post(
        "/twins/",
        headers=headers,
        json={"name": "SSE route twin"},
    )
    twin_id = twin_response.json()["id"]
    session_id = f"sse-route-{uuid.uuid4()}"
    session = await create_session(twin_id, session_id, "deploy")
    session.on_complete(success=True, message="done")

    try:
        response = client.get(f"/sse/deploy/{session_id}", headers=headers)
    finally:
        await cleanup_session(session_id)

    assert response.status_code == 200
    assert '"type": "complete"' in response.text
    assert '"data": "done"' in response.text


@pytest.mark.asyncio
async def test_sse_route_hides_session_for_unowned_twin(authenticated_client):
    client, headers = authenticated_client
    session_id = f"sse-unowned-{uuid.uuid4()}"
    session = await create_session("not-owned", session_id, "deploy")
    session.on_complete(success=False, message="hidden")

    try:
        response = client.get(f"/sse/deploy/{session_id}", headers=headers)
    finally:
        await cleanup_session(session_id)

    assert response.status_code == 404
    assert response.json() == {"detail": "Deployment stream session not found"}


def test_sse_route_rejects_negative_cursor(authenticated_client):
    client, headers = authenticated_client

    response = client.get(
        "/sse/deploy/unknown?last_event_id=-1",
        headers=headers,
    )

    assert response.status_code == 422


def test_sse_route_replays_persisted_progress_and_terminal_result(
    authenticated_client,
    db_session,
):
    client, headers = authenticated_client
    twin_response = client.post(
        "/twins/",
        headers=headers,
        json={"name": "Persisted SSE twin"},
    )
    twin_id = twin_response.json()["id"]
    deployment = Deployment(
        twin_id=twin_id,
        session_id="persisted-session",
        operation_type="deploy",
        status="success",
        idempotency_key="persisted-command-0001",
        terraform_outputs={"inter_cloud_token": "must-not-leak"},
    )
    db_session.add(deployment)
    db_session.add(
        DeploymentLog(
            twin_id=twin_id,
            session_id="persisted-session",
            event_id=1,
            message="Terraform apply completed",
            operation_type="deploy",
        )
    )
    db_session.commit()

    response = client.get("/sse/deploy/persisted-session", headers=headers)

    assert response.status_code == 200
    assert "Terraform apply completed" in response.text
    assert '"type": "complete"' in response.text
    assert "must-not-leak" not in response.text


@pytest.mark.asyncio
async def test_sse_route_rejects_cursor_ahead_of_session_history(
    authenticated_client,
):
    client, headers = authenticated_client
    twin_response = client.post(
        "/twins/",
        headers=headers,
        json={"name": "SSE cursor twin"},
    )
    twin_id = twin_response.json()["id"]
    session_id = f"sse-cursor-{uuid.uuid4()}"
    await create_session(twin_id, session_id, "deploy")

    try:
        response = client.get(
            f"/sse/deploy/{session_id}?last_event_id=1",
            headers=headers,
        )
    finally:
        await cleanup_session(session_id)

    assert response.status_code == 422
    assert response.json() == {
        "detail": "Deployment stream cursor is outside session history"
    }
