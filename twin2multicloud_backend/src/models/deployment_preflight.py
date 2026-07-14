"""Persisted, secret-free deployment preflight cache."""

from __future__ import annotations

from datetime import datetime
import uuid

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship

from src.models.database import Base


class DeploymentPreflightCache(Base):
    """Latest reviewed provider preflight for one Digital Twin binding."""

    __tablename__ = "deployment_preflight_cache"
    __table_args__ = (
        UniqueConstraint(
            "twin_id",
            "provider",
            name="uq_deployment_preflight_cache_twin_provider",
        ),
    )

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    twin_id = Column(
        String,
        ForeignKey("digital_twins.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    provider = Column(String, nullable=False, index=True)
    cloud_connection_id = Column(String, nullable=False, index=True)
    connection_payload_fingerprint = Column(String, nullable=False)
    supplied_permission_set_version = Column(String, nullable=True)
    expected_permission_set_version = Column(String, nullable=False)
    ready = Column(Boolean, nullable=False, default=False)
    summary = Column(String, nullable=False)
    checks_json = Column(Text, nullable=False, default="[]")
    checked_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    twin = relationship("DigitalTwin", back_populates="deployment_preflight_cache")
