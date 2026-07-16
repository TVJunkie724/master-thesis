from datetime import datetime, timedelta, timezone

import pytest

from src.auth.jwt import verify_token
from src.auth.providers.base import VerifiedExternalIdentity
from src.models.authentication import AuthenticationEvent, AuthLoginTransaction, AuthSession
from src.models.user import User
from src.services.auth_flow_service import AuthFlowError, AuthFlowService


IDENTITY = VerifiedExternalIdentity(
    email="person@example.test",
    name="Test Person",
    picture_url=None,
    subject="provider-subject",
)


def _completed_transaction(db_session):
    service = AuthFlowService(db_session)
    started = service.start("google")
    db_session.commit()
    transaction = service.claim_callback("google", started.state)
    service.complete_callback(transaction, IDENTITY)
    return service, started


def test_start_persists_only_digests_and_encrypted_pkce(db_session):
    service = AuthFlowService(db_session)
    started = service.start("google")
    db_session.commit()

    stored = db_session.get(AuthLoginTransaction, started.transaction.id)
    assert stored.state_digest != started.state
    assert stored.poll_verifier_digest != started.poll_verifier
    assert started.state not in stored.state_digest
    assert started.poll_verifier not in stored.poll_verifier_digest
    assert stored.pkce_verifier_encrypted != started.pkce_verifier
    assert started.pkce_verifier not in stored.pkce_verifier_encrypted


def test_callback_is_single_use_and_provider_bound(db_session):
    service = AuthFlowService(db_session)
    started = service.start("google")
    db_session.commit()

    claimed = service.claim_callback("google", started.state)
    assert claimed.callback_consumed_at is not None

    with pytest.raises(AuthFlowError, match="invalid or expired"):
        service.claim_callback("google", started.state)
    with pytest.raises(AuthFlowError, match="invalid or expired"):
        service.claim_callback("uibk", started.state)


def test_exchange_is_pending_then_issues_one_revocable_session(db_session):
    service = AuthFlowService(db_session)
    started = service.start("google")
    db_session.commit()

    assert service.exchange(started.transaction.id, started.poll_verifier) is None
    transaction = service.claim_callback("google", started.state)
    service.complete_callback(transaction, IDENTITY)

    issued = service.exchange(started.transaction.id, started.poll_verifier)
    assert issued is not None
    claims = verify_token(issued.access_token)
    assert claims is not None
    assert claims.user_id == issued.user.id
    assert db_session.get(AuthSession, claims.session_id) is not None

    with pytest.raises(AuthFlowError, match="already consumed"):
        service.exchange(started.transaction.id, started.poll_verifier)


def test_wrong_poll_verifier_does_not_reveal_transaction(db_session):
    service = AuthFlowService(db_session)
    started = service.start("google")
    db_session.commit()

    with pytest.raises(AuthFlowError) as exc_info:
        service.exchange(started.transaction.id, "wrong-verifier-value-that-is-long-enough")

    assert exc_info.value.error_code == "AUTH_TRANSACTION_INVALID"
    assert exc_info.value.http_status == 404


def test_expired_and_cancelled_transactions_cannot_issue_sessions(db_session):
    service = AuthFlowService(db_session)
    started = service.start("google")
    started.transaction.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    db_session.commit()

    with pytest.raises(AuthFlowError) as expired:
        service.exchange(started.transaction.id, started.poll_verifier)
    assert expired.value.error_code == "AUTH_TRANSACTION_EXPIRED"

    active = service.start("uibk")
    db_session.commit()
    service.cancel(active.transaction.id, active.poll_verifier)
    with pytest.raises(AuthFlowError) as cancelled:
        service.exchange(active.transaction.id, active.poll_verifier)
    assert cancelled.value.error_code == "AUTH_TRANSACTION_INACTIVE"


def test_existing_email_is_not_automatically_linked(db_session):
    db_session.add(User(email=IDENTITY.email, name="Existing"))
    db_session.commit()
    service = AuthFlowService(db_session)
    started = service.start("google")
    db_session.commit()
    transaction = service.claim_callback("google", started.state)

    with pytest.raises(AuthFlowError) as exc_info:
        service.complete_callback(transaction, IDENTITY)

    assert exc_info.value.error_code == "IDENTITY_LINK_REQUIRED"
    stored = db_session.get(AuthLoginTransaction, transaction.id)
    assert stored.status == "failed"
    assert db_session.query(AuthSession).count() == 0


def test_security_events_are_closed_and_secret_free(db_session):
    service, started = _completed_transaction(db_session)
    service.exchange(started.transaction.id, started.poll_verifier)

    events = db_session.query(AuthenticationEvent).order_by(AuthenticationEvent.occurred_at).all()
    assert [event.action for event in events] == [
        "login_initiated",
        "callback_verified",
        "session_exchanged",
    ]
    serialized = " ".join(
        f"{event.action} {event.outcome} {event.provider} {event.transaction_id}"
        for event in events
    )
    assert started.state not in serialized
    assert started.poll_verifier not in serialized
    assert started.pkce_verifier not in serialized
