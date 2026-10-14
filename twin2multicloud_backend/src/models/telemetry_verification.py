"""Persisted evidence for one bounded telemetry roundtrip."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import JSON, Column, DateTime, ForeignKey, Index, String, Text

from src.models.database import Base


class TelemetryVerification(Base):
    """Authoritative, secret-free result of one Six-layer telemetry probe."""

    __tablename__ = "telemetry_verifications"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    twin_id = Column(
        String,
        ForeignKey("digital_twins.id", ondelete="CASCADE"),
        nullable=False,
    )
    deployment_id = Column(
        String,
        ForeignKey("deployments.id", ondelete="SET NULL"),
        nullable=True,
    )
    session_id = Column(String, nullable=False, unique=True)
    device_id = Column(String(128), nullable=False)
    status = Column(String(16), nullable=False, default="running")
    trace_id = Column(String(15), nullable=True)
    result = Column(JSON, nullable=True)
    error_code = Column(String(64), nullable=True)
    error_message = Column(Text, nullable=True)
    requested_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    __table_args__ = (
        Index(
            "ix_telemetry_verifications_twin_requested",
            "twin_id",
            "requested_at",
        ),
        Index(
            "ix_telemetry_verifications_twin_status",
            "twin_id",
            "status",
        ),
    )
