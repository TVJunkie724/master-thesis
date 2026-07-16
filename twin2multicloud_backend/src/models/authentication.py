from __future__ import annotations

from datetime import datetime, timezone
import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship

from src.models.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ExternalIdentity(Base):
    """Provider-neutral binding between an application user and an IdP subject."""

    __tablename__ = "external_identities"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(
        String,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    provider = Column(String, nullable=False)
    subject = Column(String, nullable=False)
    email_at_login = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    last_login_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)

    user = relationship("User", back_populates="external_identities")

    __table_args__ = (
        UniqueConstraint("provider", "subject", name="uq_external_identity_provider_subject"),
        Index("ix_external_identities_user_provider", "user_id", "provider", unique=True),
    )


class AuthLoginTransaction(Base):
    """Short-lived, durable state for one external browser authentication flow."""

    __tablename__ = "auth_login_transactions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    provider = Column(String, nullable=False)
    purpose = Column(String, nullable=False, default="login")
    state_digest = Column(String(64), nullable=False, unique=True)
    poll_verifier_digest = Column(String(64), nullable=False)
    pkce_verifier_encrypted = Column(Text, nullable=True)
    provider_request_id = Column(String, nullable=True)
    status = Column(String, nullable=False, default="pending")
    user_id = Column(String, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    error_code = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    callback_consumed_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    exchange_consumed_at = Column(DateTime(timezone=True), nullable=True)
    cancelled_at = Column(DateTime(timezone=True), nullable=True)

    user = relationship("User")

    __table_args__ = (
        Index("ix_auth_login_transactions_status_expiry", "status", "expires_at"),
        Index("ix_auth_login_transactions_poll_digest", "poll_verifier_digest"),
    )


class AuthSession(Base):
    """Server-side revocation record backing one issued JWT."""

    __tablename__ = "auth_sessions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(
        String,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    issued_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    revocation_reason = Column(String, nullable=True)

    user = relationship("User", back_populates="auth_sessions")

    __table_args__ = (
        Index("ix_auth_sessions_user_expiry", "user_id", "expires_at"),
        Index("ix_auth_sessions_active", "expires_at", "revoked_at"),
    )


class AuthenticationEvent(Base):
    """Append-only, secret-free authentication security evidence."""

    __tablename__ = "authentication_events"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    action = Column(String, nullable=False)
    outcome = Column(String, nullable=False)
    provider = Column(String, nullable=True)
    transaction_id = Column(String, nullable=True)
    user_id = Column(String, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    http_status = Column(Integer, nullable=False)
    request_id = Column(String, nullable=False)
    occurred_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)

    __table_args__ = (
        Index("ix_authentication_events_request_id", "request_id"),
        Index("ix_authentication_events_transaction", "transaction_id"),
        Index("ix_authentication_events_user_time", "user_id", "occurred_at"),
    )
