from datetime import datetime, timezone
import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String

from src.models.database import Base


class CredentialSecurityEvent(Base):
    """Append-only, secret-free audit evidence for credential operations."""

    __tablename__ = "credential_security_events"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    action = Column(String, nullable=False)
    outcome = Column(String, nullable=False)
    resource_type = Column(String, nullable=False)
    resource_id = Column(String, nullable=True)
    provider = Column(String, nullable=True)
    purpose = Column(String, nullable=True)
    http_status = Column(Integer, nullable=False)
    request_id = Column(String, nullable=False)
    occurred_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        Index("ix_credential_security_events_user_time", "user_id", "occurred_at"),
        Index("ix_credential_security_events_request_id", "request_id"),
        Index("ix_credential_security_events_action", "action"),
        Index("ix_credential_security_events_resource", "resource_type", "resource_id"),
    )
