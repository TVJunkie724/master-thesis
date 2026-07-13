from datetime import datetime, timezone

from src.models.deployment_log import DeploymentLog, OperationType
from src.models.twin import DigitalTwin, TwinState
from src.models.user import User


def _current_user(db_session) -> User:
    user = db_session.query(User).first()
    assert user is not None
    return user


def _create_twin(db_session, user_id: str, *, name: str = "Log Twin") -> DigitalTwin:
    twin = DigitalTwin(name=name, user_id=user_id, state=TwinState.DEPLOYING)
    db_session.add(twin)
    db_session.commit()
    db_session.refresh(twin)
    return twin


def _insert_log(
    db_session,
    twin_id: str,
    *,
    event_id: int,
    session_id: str = "session-1",
    message: str | None = None,
    level: str = "info",
    operation_type: str = OperationType.DEPLOY.value,
) -> DeploymentLog:
    log = DeploymentLog(
        twin_id=twin_id,
        session_id=session_id,
        event_id=event_id,
        timestamp=datetime.now(timezone.utc),
        level=level,
        message=message or f"log {event_id}",
        operation_type=operation_type,
    )
    db_session.add(log)
    db_session.commit()
    db_session.refresh(log)
    return log


def test_deployment_logs_returns_bounded_page_with_next_cursor(
    authenticated_client,
    db_session,
):
    client, headers = authenticated_client
    twin = _create_twin(db_session, _current_user(db_session).id)
    for event_id in range(1, 5):
        _insert_log(db_session, twin.id, event_id=event_id)

    response = client.get(
        f"/twins/{twin.id}/logs?limit=2",
        headers=headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["schema_version"] == "deployment-log-page.v1"
    assert body["twin_id"] == twin.id
    assert body["after_event_id"] == 0
    assert body["limit"] == 2
    assert body["has_more"] is True
    assert body["next_after_event_id"] == 2
    assert body["latest_event_id"] == 4
    assert [log["event_id"] for log in body["logs"]] == [1, 2]


def test_deployment_logs_filters_by_session_and_after_event_id(
    authenticated_client,
    db_session,
):
    client, headers = authenticated_client
    twin = _create_twin(db_session, _current_user(db_session).id)
    _insert_log(db_session, twin.id, event_id=1, session_id="session-1")
    _insert_log(db_session, twin.id, event_id=2, session_id="session-1")
    _insert_log(db_session, twin.id, event_id=3, session_id="session-1")
    _insert_log(db_session, twin.id, event_id=1, session_id="session-2")

    response = client.get(
        f"/twins/{twin.id}/logs?session_id=session-1&after_event_id=1&limit=10",
        headers=headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["session_id"] == "session-1"
    assert body["has_more"] is False
    assert body["next_after_event_id"] == 3
    assert body["latest_event_id"] == 3
    assert [log["event_id"] for log in body["logs"]] == [2, 3]
    assert all(log["session_id"] == "session-1" for log in body["logs"])


def test_deployment_logs_are_owner_scoped(authenticated_client, db_session):
    client, headers = authenticated_client
    twin = _create_twin(db_session, "other-user", name="Other Twin")
    _insert_log(db_session, twin.id, event_id=1)

    response = client.get(f"/twins/{twin.id}/logs", headers=headers)

    assert response.status_code == 404


def test_deployment_logs_redact_secret_like_messages(
    authenticated_client,
    db_session,
):
    client, headers = authenticated_client
    twin = _create_twin(db_session, _current_user(db_session).id)
    _insert_log(
        db_session,
        twin.id,
        event_id=1,
        message=(
            'secret_access_key="very-sensitive" '
            "token=abc123 "
            "AKIA1234567890ABCDEF"
        ),
        level="warning",
    )

    response = client.get(f"/twins/{twin.id}/logs", headers=headers)

    assert response.status_code == 200
    message = response.json()["logs"][0]["message"]
    assert "very-sensitive" not in message
    assert "abc123" not in message
    assert "AKIA1234567890ABCDEF" not in message
    assert "[REDACTED]" in message


def test_deployment_logs_empty_page_is_stable(authenticated_client, db_session):
    client, headers = authenticated_client
    twin = _create_twin(db_session, _current_user(db_session).id)

    response = client.get(f"/twins/{twin.id}/logs?after_event_id=10", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert body["logs"] == []
    assert body["has_more"] is False
    assert body["next_after_event_id"] == 10
    assert body["latest_event_id"] is None
