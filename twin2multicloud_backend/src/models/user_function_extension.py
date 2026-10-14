"""Current validated user-function sources owned by one draft Twin."""

from __future__ import annotations

from datetime import datetime, timezone
import uuid

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from src.models.database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class TwinUserFunction(Base):
    """The single current validated source for one Twin extension slot."""

    __tablename__ = "twin_user_functions"

    id = Column(String, primary_key=True, default=_uuid)
    twin_id = Column(
        String,
        ForeignKey("digital_twins.id", ondelete="CASCADE"),
        nullable=False,
    )
    artifact_digest = Column(String(71), nullable=False)
    slot_id = Column(String(128), nullable=False)
    slot_version = Column(String(10), nullable=False)
    runtime_id = Column(String(32), nullable=False)
    manifest_json = Column(Text, nullable=False)
    configuration_json = Column(Text, nullable=False, default="{}")
    declared_capabilities_json = Column(Text, nullable=False, default="[]")
    validator_version = Column(String(64), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_now)
    updated_at = Column(
        DateTime(timezone=True), nullable=False, default=_now, onupdate=_now
    )

    twin = relationship("DigitalTwin", back_populates="user_functions")
    files = relationship(
        "TwinUserFunctionFile",
        back_populates="user_function",
        cascade="all, delete-orphan",
        order_by="TwinUserFunctionFile.relative_path",
    )
    dependencies = relationship(
        "TwinUserFunctionDependency",
        back_populates="user_function",
        cascade="all, delete-orphan",
        order_by="TwinUserFunctionDependency.name",
    )

    __table_args__ = (
        UniqueConstraint(
            "twin_id",
            "slot_id",
            "slot_version",
            name="uq_twin_user_function_slot",
        ),
        Index("ix_twin_user_functions_twin", "twin_id"),
    )


class TwinUserFunctionFile(Base):
    """One validated UTF-8 source file for the current Twin function."""

    __tablename__ = "twin_user_function_files"

    id = Column(String, primary_key=True, default=_uuid)
    user_function_id = Column(
        String,
        ForeignKey("twin_user_functions.id", ondelete="CASCADE"),
        nullable=False,
    )
    relative_path = Column(String(240), nullable=False)
    content_text = Column(Text, nullable=False)
    content_digest = Column(String(71), nullable=False)
    size_bytes = Column(Integer, nullable=False)

    user_function = relationship("TwinUserFunction", back_populates="files")

    __table_args__ = (
        UniqueConstraint(
            "user_function_id",
            "relative_path",
            name="uq_twin_user_function_file_path",
        ),
    )


class TwinUserFunctionDependency(Base):
    """One exact validated dependency for the current Twin function."""

    __tablename__ = "twin_user_function_dependencies"

    id = Column(String, primary_key=True, default=_uuid)
    user_function_id = Column(
        String,
        ForeignKey("twin_user_functions.id", ondelete="CASCADE"),
        nullable=False,
    )
    name = Column(String(128), nullable=False)
    version = Column(String(64), nullable=False)
    hashes_json = Column(Text, nullable=False)
    policy_result = Column(String(32), nullable=False)

    user_function = relationship("TwinUserFunction", back_populates="dependencies")

    __table_args__ = (
        UniqueConstraint(
            "user_function_id",
            "name",
            name="uq_twin_user_function_dependency_name",
        ),
    )
