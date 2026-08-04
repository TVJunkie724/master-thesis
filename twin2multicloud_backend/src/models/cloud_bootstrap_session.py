"""Durable, secret-free guided cloud-bootstrap session state."""

from __future__ import annotations

from datetime import datetime, timezone
import uuid

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import relationship

from src.models.database import Base


ACTIVE_BOOTSTRAP_STATES = (
    "draft",
    "bootstrap_running",
    "generated_connection_ready",
    "disposal_running",
    "manual_revocation_required",
    "credential_reentry_required",
)


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class CloudBootstrapSession(Base):
    """Owner-scoped bootstrap lifecycle without provider credential material."""

    __tablename__ = "cloud_bootstrap_sessions"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "create_idempotency_key",
            name="uq_cloud_bootstrap_create_idempotency",
        ),
        CheckConstraint("revision > 0", name="ck_cloud_bootstrap_revision"),
        CheckConstraint(
            "provider IN ('aws', 'azure', 'gcp')",
            name="ck_cloud_bootstrap_provider",
        ),
        CheckConstraint(
            "entry_point IN ('settings', 'twin_prepare')",
            name="ck_cloud_bootstrap_entry_point",
        ),
        CheckConstraint(
            "state IN ("
            "'draft', 'bootstrap_running', 'generated_connection_ready', "
            "'disposal_running', 'manual_revocation_required', "
            "'credential_reentry_required', 'ready', 'failed', "
            "'cancelled', 'expired')",
            name="ck_cloud_bootstrap_state",
        ),
        Index(
            "uq_cloud_bootstrap_active_scope",
            "user_id",
            "provider",
            "target_scope_digest",
            unique=True,
            sqlite_where=text(
                "state IN ('draft', 'bootstrap_running', "
                "'generated_connection_ready', 'disposal_running', "
                "'manual_revocation_required', 'credential_reentry_required')"
            ),
            postgresql_where=text(
                "state IN ('draft', 'bootstrap_running', "
                "'generated_connection_ready', 'disposal_running', "
                "'manual_revocation_required', 'credential_reentry_required')"
            ),
        ),
        Index("ix_cloud_bootstrap_owner_provider", "user_id", "provider"),
        Index("ix_cloud_bootstrap_connection", "connection_id"),
    )

    id = Column(String, primary_key=True, default=_uuid)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    provider = Column(String(16), nullable=False)
    target_scope_digest = Column(String(71), nullable=False)
    target_json = Column(Text, nullable=False)
    entry_point = Column(String(32), nullable=False)
    twin_id = Column(
        String,
        ForeignKey("digital_twins.id", ondelete="SET NULL"),
        nullable=True,
    )
    display_name = Column(String(120), nullable=False)
    revision = Column(Integer, nullable=False, default=1)
    state = Column(String(48), nullable=False, default="draft")
    guide_digest = Column(String(71), nullable=False)
    bootstrap_authority_pack_id = Column(String(128), nullable=False)
    bootstrap_authority_pack_version = Column(String(32), nullable=False)
    bootstrap_authority_pack_digest = Column(String(71), nullable=False)
    generated_deployment_pack_id = Column(String(128), nullable=False)
    generated_deployment_pack_version = Column(String(32), nullable=False)
    generated_deployment_pack_digest = Column(String(71), nullable=False)
    create_idempotency_key = Column(String(128), nullable=False)
    create_request_digest = Column(String(71), nullable=False)
    execute_idempotency_key = Column(String(128), nullable=True)
    credential_origin = Column(String(32), nullable=True)
    disposal_status = Column(String(48), nullable=True)
    credential_expires_at = Column(DateTime(timezone=True), nullable=True)
    safe_credential_identifier = Column(String(160), nullable=True)
    finding_json = Column(Text, nullable=True)
    connection_id = Column(
        String,
        ForeignKey("cloud_connections.id", ondelete="SET NULL"),
        nullable=True,
    )
    lease_started_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_now)
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=_now,
        onupdate=_now,
    )

    owner = relationship("User", back_populates="cloud_bootstrap_sessions")
    twin = relationship("DigitalTwin")
    connection = relationship("CloudConnection")
