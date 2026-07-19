"""Architecture-profile selection and immutable resolved-architecture records."""

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
    event,
    inspect,
)
from sqlalchemy.orm import relationship

from src.models.database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class TwinArchitectureSelection(Base):
    """Pinned repository profile selected for one Digital Twin."""

    __tablename__ = "twin_architecture_selections"
    __table_args__ = (
        UniqueConstraint("twin_id", name="uq_twin_architecture_selection_twin"),
        CheckConstraint("revision > 0", name="ck_architecture_selection_revision"),
        Index(
            "ix_architecture_selection_owner_twin",
            "user_id",
            "twin_id",
        ),
    )

    id = Column(String, primary_key=True, default=_uuid)
    twin_id = Column(
        String,
        ForeignKey("digital_twins.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    profile_id = Column(String(128), nullable=False)
    profile_version = Column(String(32), nullable=False)
    profile_digest = Column(String(71), nullable=False)
    revision = Column(Integer, nullable=False, default=1)
    selected_at = Column(DateTime(timezone=True), nullable=False, default=_now)
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=_now,
        onupdate=_now,
    )
    selected_by_user_id = Column(
        String,
        ForeignKey("users.id"),
        nullable=False,
    )
    __mapper_args__ = {
        "version_id_col": revision,
        "version_id_generator": False,
    }

    twin = relationship("DigitalTwin", back_populates="architecture_selection")


class ResolvedTwinArchitectureRecord(Base):
    """Immutable canonical resolution owned by one optimizer calculation run."""

    __tablename__ = "resolved_twin_architectures"
    __table_args__ = (
        UniqueConstraint(
            "calculation_run_id",
            name="uq_resolved_architecture_calculation_run",
        ),
        UniqueConstraint(
            "content_digest",
            name="uq_resolved_architecture_content_digest",
        ),
        CheckConstraint(
            "functional_completeness_status = 'complete'",
            name="ck_resolved_architecture_complete",
        ),
        CheckConstraint(
            "origin IN ('native_v1', 'reconstructed_v1')",
            name="ck_resolved_architecture_origin",
        ),
        Index(
            "ix_resolved_architecture_owner_twin",
            "user_id",
            "twin_id",
        ),
    )

    id = Column(String, primary_key=True)
    calculation_run_id = Column(
        String,
        ForeignKey("cost_calculation_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    twin_id = Column(
        String,
        ForeignKey("digital_twins.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    schema_version = Column(String(64), nullable=False)
    profile_id = Column(String(128), nullable=False)
    profile_version = Column(String(32), nullable=False)
    profile_digest = Column(String(71), nullable=False)
    optimization_bundle_digest = Column(String(71), nullable=False)
    workload_contract_id = Column(String(128), nullable=False)
    workload_contract_version = Column(String(32), nullable=False)
    workload_digest = Column(String(71), nullable=False)
    deployment_specification_version = Column(String(64), nullable=False)
    deployment_specification_digest = Column(String(71), nullable=False)
    total_monthly_cost = Column(String(128), nullable=False)
    currency = Column(String(3), nullable=False)
    functional_completeness_status = Column(String(32), nullable=False)
    canonical_json = Column(Text, nullable=False)
    content_digest = Column(String(71), nullable=False, index=True)
    origin = Column(String(32), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_now)

    calculation_run = relationship(
        "CostCalculationRun",
        back_populates="resolved_architecture",
    )
    components = relationship(
        "ResolvedArchitectureComponentAssignment",
        back_populates="resolved_architecture",
        cascade="all, delete-orphan",
        order_by="ResolvedArchitectureComponentAssignment.ordinal",
    )
    edges = relationship(
        "ResolvedArchitectureEdge",
        back_populates="resolved_architecture",
        cascade="all, delete-orphan",
        order_by="ResolvedArchitectureEdge.ordinal",
    )


class ResolvedArchitectureComponentAssignment(Base):
    """Queryable projection of one canonical component assignment."""

    __tablename__ = "resolved_architecture_component_assignments"
    __table_args__ = (
        UniqueConstraint(
            "resolved_architecture_id",
            "assignment_id",
            name="uq_resolved_component_assignment",
        ),
        UniqueConstraint(
            "resolved_architecture_id",
            "ordinal",
            name="uq_resolved_component_ordinal",
        ),
        Index(
            "ix_resolved_component_responsibility",
            "resolved_architecture_id",
            "responsibility_id",
        ),
        Index(
            "ix_resolved_component_provider",
            "resolved_architecture_id",
            "provider",
        ),
        Index(
            "ix_resolved_component_deployment_component",
            "deployment_component_id",
        ),
        Index("ix_resolved_component_service", "service_id"),
    )

    id = Column(String, primary_key=True, default=_uuid)
    resolved_architecture_id = Column(
        String,
        ForeignKey("resolved_twin_architectures.id", ondelete="CASCADE"),
        nullable=False,
    )
    assignment_id = Column(String(128), nullable=False)
    responsibility_id = Column(String(128), nullable=False)
    logical_component_id = Column(String(128), nullable=False)
    provider = Column(String(16), nullable=False)
    deployment_component_id = Column(String(160), nullable=False)
    deployment_component_version = Column(String(32), nullable=False)
    service_id = Column(String(160), nullable=False)
    provider_profile_id = Column(String(160), nullable=False)
    provider_profile_version = Column(String(32), nullable=False)
    provider_profile_digest = Column(String(71), nullable=False)
    region = Column(String(64), nullable=False)
    deployment_specification_component_ids_json = Column(Text, nullable=False)
    cost_contribution = Column(String(128), nullable=False)
    capability_refs_json = Column(Text, nullable=False)
    pricing_refs_json = Column(Text, nullable=False)
    formula_refs_json = Column(Text, nullable=False)
    evidence_refs_json = Column(Text, nullable=False)
    ordinal = Column(Integer, nullable=False)

    resolved_architecture = relationship(
        "ResolvedTwinArchitectureRecord",
        back_populates="components",
    )


class ResolvedArchitectureEdge(Base):
    """Queryable projection of one canonical resolved edge."""

    __tablename__ = "resolved_architecture_edges"
    __table_args__ = (
        UniqueConstraint(
            "resolved_architecture_id",
            "resolved_edge_id",
            name="uq_resolved_architecture_edge",
        ),
        UniqueConstraint(
            "resolved_architecture_id",
            "ordinal",
            name="uq_resolved_edge_ordinal",
        ),
        Index(
            "ix_resolved_edge_logical",
            "resolved_architecture_id",
            "logical_edge_id",
        ),
        Index(
            "ix_resolved_edge_source",
            "resolved_architecture_id",
            "source_assignment_id",
        ),
        Index(
            "ix_resolved_edge_destination",
            "resolved_architecture_id",
            "destination_assignment_id",
        ),
    )

    id = Column(String, primary_key=True, default=_uuid)
    resolved_architecture_id = Column(
        String,
        ForeignKey("resolved_twin_architectures.id", ondelete="CASCADE"),
        nullable=False,
    )
    resolved_edge_id = Column(String(160), nullable=False)
    logical_edge_id = Column(String(160), nullable=False)
    source_assignment_id = Column(String(160), nullable=False)
    source_port_id = Column(String(160), nullable=False)
    destination_assignment_id = Column(String(160), nullable=False)
    destination_port_id = Column(String(160), nullable=False)
    edge_implementation_id = Column(String(200), nullable=False)
    mechanism = Column(String(64), nullable=False)
    transfer_route_id = Column(String(64), nullable=False)
    cost_contribution = Column(String(128), nullable=False)
    delivery_semantics_json = Column(Text, nullable=False)
    binding_refs_json = Column(Text, nullable=False)
    trust_ref_json = Column(Text, nullable=False)
    observability_ref_json = Column(Text, nullable=False)
    formula_refs_json = Column(Text, nullable=False)
    evidence_refs_json = Column(Text, nullable=False)
    ordinal = Column(Integer, nullable=False)

    resolved_architecture = relationship(
        "ResolvedTwinArchitectureRecord",
        back_populates="edges",
    )


class ArchitectureAuditEvent(Base):
    """Append-only, payload-free architecture operation evidence."""

    __tablename__ = "architecture_audit_events"
    __table_args__ = (
        Index("ix_architecture_audit_owner_time", "user_id", "occurred_at"),
        Index("ix_architecture_audit_correlation", "correlation_id"),
        Index("ix_architecture_audit_twin_run", "twin_id", "calculation_run_id"),
    )

    id = Column(String, primary_key=True, default=_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    action = Column(String(64), nullable=False)
    outcome = Column(String(32), nullable=False)
    profile_id = Column(String(128), nullable=True)
    profile_version = Column(String(32), nullable=True)
    profile_digest = Column(String(71), nullable=True)
    twin_id = Column(String, nullable=True)
    calculation_run_id = Column(String, nullable=True)
    resolution_digest = Column(String(71), nullable=True)
    result_code = Column(String(64), nullable=True)
    correlation_id = Column(String(128), nullable=False)
    occurred_at = Column(DateTime(timezone=True), nullable=False, default=_now)


_IMMUTABLE_MODELS = (
    ResolvedTwinArchitectureRecord,
    ResolvedArchitectureComponentAssignment,
    ResolvedArchitectureEdge,
    ArchitectureAuditEvent,
)


def _reject_semantic_update(_mapper, _connection, target) -> None:
    state = inspect(target)
    if any(attribute.history.has_changes() for attribute in state.attrs):
        raise ValueError(f"{target.__class__.__name__} is immutable after insert")


def _reject_audit_delete(_mapper, _connection, _target) -> None:
    raise ValueError("ArchitectureAuditEvent is append-only")


for _model in _IMMUTABLE_MODELS:
    event.listen(_model, "before_update", _reject_semantic_update)

event.listen(ArchitectureAuditEvent, "before_delete", _reject_audit_delete)
