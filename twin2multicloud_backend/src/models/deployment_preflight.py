"""Persisted, secret-free deployment preflight cache."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
)
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
    architecture_digest = Column(String(71), nullable=True)
    graph_digest = Column(String(71), nullable=True)
    requirements_digest = Column(String(71), nullable=True)
    ready = Column(Boolean, nullable=False, default=False)
    summary = Column(String, nullable=False)
    checks_json = Column(Text, nullable=False, default="[]")
    requirements_json = Column(Text, nullable=False, default="[]")
    preparation_plan_json = Column(Text, nullable=False, default="{}")
    completed_preparation_actions_json = Column(Text, nullable=False, default="[]")
    manual_acknowledgements_json = Column(Text, nullable=False, default="[]")
    checked_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    twin = relationship("DigitalTwin", back_populates="deployment_preflight_cache")
