"""Immutable user-function artifacts, files, dependencies, and Twin bindings."""

from __future__ import annotations

from datetime import datetime, timezone
import uuid

from sqlalchemy import (
    Boolean,
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


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class UserFunctionArtifact(Base):
    """Owner-scoped immutable logical artifact metadata."""

    __tablename__ = "user_function_artifacts"

    id = Column(String, primary_key=True, default=_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    schema_version = Column(String, nullable=False)
    artifact_state = Column(String, nullable=False)
    artifact_digest = Column(String(71), nullable=False)
    slot_id = Column(String(128), nullable=False)
    slot_version = Column(String(10), nullable=False)
    runtime_id = Column(String(32), nullable=False)
    manifest_json = Column(Text, nullable=True)
    configuration_json = Column(Text, nullable=False, default="{}")
    declared_capabilities_json = Column(Text, nullable=False, default="[]")
    validator_version = Column(String(64), nullable=True)
    created_by = Column(String, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_now)

    files = relationship(
        "UserFunctionArtifactFile",
        back_populates="artifact",
        cascade="all, delete-orphan",
        order_by="UserFunctionArtifactFile.relative_path",
    )
    dependencies = relationship(
        "UserFunctionArtifactDependency",
        back_populates="artifact",
        cascade="all, delete-orphan",
        order_by="UserFunctionArtifactDependency.name",
    )

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "artifact_digest",
            name="uq_user_function_artifact_owner_digest",
        ),
        Index("ix_user_function_artifacts_owner_time", "user_id", "created_at"),
        Index(
            "ix_user_function_artifacts_slot",
            "user_id",
            "slot_id",
            "slot_version",
        ),
    )


class UserFunctionArtifactFile(Base):
    """Normalized UTF-8 source file stored outside list/detail responses."""

    __tablename__ = "user_function_artifact_files"

    id = Column(String, primary_key=True, default=_uuid)
    artifact_id = Column(
        String,
        ForeignKey("user_function_artifacts.id", ondelete="CASCADE"),
        nullable=False,
    )
    relative_path = Column(String(240), nullable=False)
    content_text = Column(Text, nullable=False)
    content_digest = Column(String(71), nullable=False)
    size_bytes = Column(Integer, nullable=False)

    artifact = relationship("UserFunctionArtifact", back_populates="files")

    __table_args__ = (
        UniqueConstraint(
            "artifact_id",
            "relative_path",
            name="uq_user_function_artifact_file_path",
        ),
        Index("ix_user_function_artifact_files_artifact", "artifact_id"),
    )


class UserFunctionArtifactDependency(Base):
    """Normalized exact dependency lock entry."""

    __tablename__ = "user_function_artifact_dependencies"

    id = Column(String, primary_key=True, default=_uuid)
    artifact_id = Column(
        String,
        ForeignKey("user_function_artifacts.id", ondelete="CASCADE"),
        nullable=False,
    )
    name = Column(String(128), nullable=False)
    version = Column(String(64), nullable=False)
    hashes_json = Column(Text, nullable=False)
    policy_result = Column(String(32), nullable=False)

    artifact = relationship("UserFunctionArtifact", back_populates="dependencies")

    __table_args__ = (
        UniqueConstraint(
            "artifact_id",
            "name",
            name="uq_user_function_artifact_dependency_name",
        ),
        Index("ix_user_function_artifact_dependencies_artifact", "artifact_id"),
    )


class TwinExtensionBinding(Base):
    """Append-preserving binding with at most one active artifact per slot."""

    __tablename__ = "twin_extension_bindings"

    id = Column(String, primary_key=True, default=_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    twin_id = Column(
        String,
        ForeignKey("digital_twins.id", ondelete="CASCADE"),
        nullable=False,
    )
    slot_id = Column(String(128), nullable=False)
    slot_version = Column(String(10), nullable=False)
    artifact_id = Column(
        String,
        ForeignKey("user_function_artifacts.id"),
        nullable=False,
    )
    binding_digest = Column(String(71), nullable=False)
    active = Column(Boolean, nullable=False, default=True)
    revision = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_now)
    unbound_at = Column(DateTime(timezone=True), nullable=True)

    artifact = relationship("UserFunctionArtifact")
    twin = relationship("DigitalTwin", back_populates="extension_bindings")

    __table_args__ = (
        Index(
            "ix_twin_extension_bindings_owner_twin",
            "user_id",
            "twin_id",
            "created_at",
        ),
        Index(
            "ix_twin_extension_bindings_one_active",
            "twin_id",
            "slot_id",
            "slot_version",
            unique=True,
            sqlite_where=text("active = 1"),
        ),
    )


class UserFunctionAuditEvent(Base):
    """Append-only, source-free extension operation evidence."""

    __tablename__ = "user_function_audit_events"

    id = Column(String, primary_key=True, default=_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    action = Column(String(64), nullable=False)
    outcome = Column(String(32), nullable=False)
    artifact_id = Column(String, nullable=True)
    twin_id = Column(String, nullable=True)
    slot_id = Column(String(128), nullable=True)
    correlation_id = Column(String(128), nullable=False)
    error_code = Column(String(64), nullable=True)
    occurred_at = Column(DateTime(timezone=True), nullable=False, default=_now)

    __table_args__ = (
        Index("ix_user_function_audit_owner_time", "user_id", "occurred_at"),
        Index("ix_user_function_audit_correlation", "correlation_id"),
    )
