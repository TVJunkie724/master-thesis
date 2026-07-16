import asyncio
import json

import pytest
from limits.errors import StorageError
from pydantic import ValidationError
from sqlalchemy.exc import OperationalError

from src.models.cloud_connection import CloudConnection
from src.models.credential_security_event import CredentialSecurityEvent
from src.schemas.credential_security_event import (
    CredentialSecurityAction,
    CredentialSecurityEventDraft,
    CredentialSecurityOutcome,
)
from src.security.rate_limit import (
    CredentialRateClass,
    CredentialRateLimitExceeded,
    CredentialRateLimiter,
    reset_rate_limiter_for_tests,
)
from src.services.credential_security_audit_service import CredentialSecurityAuditService


AWS_SECRET = "credential-security-test-secret"


def _aws_connection() -> dict:
    return {
        "provider": "aws",
        "display_name": "Audited AWS",
        "permission_set_version": "thesis-demo-v1",
        "cloud_scope": {"account_id": "123456789012", "region": "eu-central-1"},
        "aws": {
            "access_key_id": "AKIAIOSFODNN7EXAMPLE",
            "secret_access_key": AWS_SECRET,
            "region": "eu-central-1",
        },
    }


def test_create_commits_secret_free_audit_event(authenticated_client, db_session):
    client, headers = authenticated_client

    response = client.post(
        "/cloud-connections/",
        headers={**headers, "X-Request-ID": "credential-create-123"},
        json=_aws_connection(),
    )

    assert response.status_code == 200
    assert response.headers["x-request-id"] == "credential-create-123"
    assert response.headers["ratelimit-limit"] == "10"
    event = db_session.query(CredentialSecurityEvent).one()
    assert event.action == "cloud_connection.create"
    assert event.outcome == "succeeded"
    assert event.resource_id == response.json()["id"]
    assert event.request_id == "credential-create-123"
    assert AWS_SECRET not in json.dumps(event.__dict__, default=str)


def test_audit_failure_rolls_back_connection_creation(
    authenticated_client,
    db_session,
    monkeypatch,
):
    client, headers = authenticated_client

    def fail_append(*_args, **_kwargs):
        raise OperationalError("INSERT", {}, RuntimeError("audit unavailable"))

    monkeypatch.setattr(CredentialSecurityAuditService, "append", fail_append)

    response = client.post("/cloud-connections/", headers=headers, json=_aws_connection())

    assert response.status_code == 503
    assert response.json()["error_code"] == "SECURITY_CONTROL_UNAVAILABLE"
    assert db_session.query(CloudConnection).count() == 0
    assert db_session.query(CredentialSecurityEvent).count() == 0
    assert AWS_SECRET not in response.text


def test_rate_limit_rejects_before_second_mutation_and_is_audited(
    authenticated_client,
    db_session,
    monkeypatch,
):
    client, headers = authenticated_client
    from src.security import rate_limit as rate_limit_module

    monkeypatch.setattr(rate_limit_module.settings, "CREDENTIAL_WRITE_RATE_LIMIT", "1/minute")
    asyncio.run(reset_rate_limiter_for_tests())

    first = client.post("/cloud-connections/", headers=headers, json=_aws_connection())
    second = client.post("/cloud-connections/", headers=headers, json=_aws_connection())

    assert first.status_code == 200
    assert second.status_code == 429
    assert second.json()["error_code"] == "RATE_LIMITED"
    assert int(second.headers["retry-after"]) >= 1
    assert db_session.query(CloudConnection).count() == 1
    outcomes = [row.outcome for row in db_session.query(CredentialSecurityEvent).all()]
    assert outcomes.count("succeeded") == 1
    assert outcomes.count("rate_limited") == 1
    assert AWS_SECRET not in second.text


def test_limiter_storage_failure_fails_closed(
    authenticated_client,
    db_session,
    monkeypatch,
):
    client, headers = authenticated_client
    from src.security import rate_limit as rate_limit_module

    class FailingLimiter:
        async def hit(self, *_args, **_kwargs):
            raise StorageError(RuntimeError("redis unavailable"))

    monkeypatch.setattr(rate_limit_module, "_get_rate_limiter", lambda: FailingLimiter())

    response = client.post("/cloud-connections/", headers=headers, json=_aws_connection())

    assert response.status_code == 503
    assert response.json()["error_code"] == "SECURITY_CONTROL_UNAVAILABLE"
    assert db_session.query(CloudConnection).count() == 0
    event = db_session.query(CredentialSecurityEvent).one()
    assert event.outcome == "control_unavailable"


@pytest.mark.asyncio
async def test_rate_limit_isolates_users_and_operation_classes():
    limiter = CredentialRateLimiter("memory://")

    await limiter.hit("1/minute", CredentialRateClass.WRITE, "user-a")
    with pytest.raises(CredentialRateLimitExceeded):
        await limiter.hit("1/minute", CredentialRateClass.WRITE, "user-a")

    await limiter.hit("1/minute", CredentialRateClass.WRITE, "user-b")
    await limiter.hit("1/minute", CredentialRateClass.VALIDATION, "user-a")


def test_audit_history_is_owner_scoped_and_never_exposes_actor_id(
    authenticated_client,
    db_session,
):
    client, headers = authenticated_client
    created = client.post("/cloud-connections/", headers=headers, json=_aws_connection())
    assert created.status_code == 200

    response = client.get("/credential-security-events/?limit=1&offset=0", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["limit"] == 1
    assert body["items"][0]["resource_id"] == created.json()["id"]
    assert "user_id" not in body["items"][0]
    assert AWS_SECRET not in response.text


def test_rejected_credential_operation_is_audited(authenticated_client, db_session):
    client, headers = authenticated_client

    response = client.delete("/cloud-connections/not-owned", headers=headers)

    assert response.status_code == 404
    event = db_session.query(CredentialSecurityEvent).one()
    assert event.action == "cloud_connection.delete"
    assert event.outcome == "rejected"
    assert event.http_status == 404


def test_schema_rejected_credential_operation_is_audited(authenticated_client, db_session):
    client, headers = authenticated_client

    response = client.post("/cloud-connections/", headers=headers, json={})

    assert response.status_code == 422
    event = db_session.query(CredentialSecurityEvent).one()
    assert event.action == "cloud_connection.create"
    assert event.outcome == "rejected"
    assert event.http_status == 422


def test_audit_draft_forbids_arbitrary_or_secret_fields():
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        CredentialSecurityEventDraft(
            user_id="user",
            action=CredentialSecurityAction.CONNECTION_CREATE,
            outcome=CredentialSecurityOutcome.SUCCEEDED,
            resource_type="cloud_connection",
            http_status=200,
            request_id="request",
            metadata={"secret": AWS_SECRET},
        )
