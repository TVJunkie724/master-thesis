from datetime import datetime, timezone
import uuid

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    String,
    Text,
    event,
    text,
)
from sqlalchemy import inspect
from sqlalchemy.orm import relationship

from src.models.database import Base


class CostCalculationRun(Base):
    """Typed optimizer calculation run owned by the Management API."""

    __tablename__ = "cost_calculation_runs"
    __table_args__ = (
        CheckConstraint(
            "deployment_compatibility_status IN "
            "('ready', 'legacy_not_deployable')",
            name="ck_cost_runs_deployment_compatibility_status",
        ),
        Index(
            "ix_cost_runs_deployment_specification_digest",
            "deployment_specification_digest",
        ),
        Index(
            "ix_cost_runs_one_selected_per_twin",
            "twin_id",
            "user_id",
            unique=True,
            sqlite_where=text("selected_for_deployment_at IS NOT NULL"),
            postgresql_where=text("selected_for_deployment_at IS NOT NULL"),
        ),
    )

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    twin_id = Column(String, ForeignKey("digital_twins.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    optimizer_config_id = Column(
        String,
        ForeignKey("optimizer_configurations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    status = Column(String, nullable=False, default="succeeded", index=True)
    params_json = Column(Text, nullable=False)
    result_summary_json = Column(Text, nullable=True)
    cheapest_path_json = Column(Text, nullable=True)
    total_monthly_cost = Column(Float, nullable=True)
    currency = Column(String, nullable=False, default="USD")
    optimization_profile_id = Column(String, nullable=False, index=True)
    optimization_profile_version = Column(String, nullable=True)
    scoring_strategy_id = Column(String, nullable=False)
    calculation_model_version = Column(String, nullable=True)
    pricing_registry_version = Column(String, nullable=True)
    pricing_evidence_version = Column(String, nullable=True)
    pricing_run_reference = Column(String, nullable=True)
    pricing_catalog_context_json = Column(Text, nullable=True)
    deployment_specification_json = Column(Text, nullable=True)
    deployment_specification_digest = Column(String(71), nullable=True)
    deployment_specification_version = Column(String(64), nullable=True)
    deployment_compatibility_status = Column(
        String(32),
        nullable=False,
        default="legacy_not_deployable",
        server_default="legacy_not_deployable",
    )
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    selected_for_deployment_at = Column(DateTime(timezone=True), nullable=True)
    error_code = Column(String, nullable=True)
    error_message = Column(String, nullable=True)

    twin = relationship("DigitalTwin", back_populates="cost_calculation_runs")
    optimizer_config = relationship("OptimizerConfiguration", back_populates="cost_calculation_runs")
    result_items = relationship(
        "CostCalculationResultItem",
        back_populates="run",
        cascade="all, delete-orphan",
        order_by="CostCalculationResultItem.created_at.asc()",
    )


class CostCalculationResultItem(Base):
    """Queryable cost item derived from an optimizer result."""

    __tablename__ = "cost_calculation_result_items"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    run_id = Column(
        String,
        ForeignKey("cost_calculation_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    layer = Column(String, nullable=False, index=True)
    component = Column(String, nullable=True)
    provider = Column(String, nullable=True, index=True)
    service_intent_id = Column(String, nullable=True, index=True)
    cost_amount = Column(Float, nullable=True)
    currency = Column(String, nullable=False, default="USD")
    unit = Column(String, nullable=True)
    quantity = Column(Float, nullable=True)
    unit_price = Column(Float, nullable=True)
    evidence_id = Column(String, nullable=True, index=True)
    service_model_id = Column(String, nullable=True)
    calculation_notes_json = Column(Text, nullable=True)
    review_status = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    run = relationship("CostCalculationRun", back_populates="result_items")


_IMMUTABLE_DEPLOYMENT_SPECIFICATION_FIELDS = (
    "deployment_specification_json",
    "deployment_specification_digest",
    "deployment_specification_version",
    "deployment_compatibility_status",
)


@event.listens_for(CostCalculationRun, "before_update")
def _prevent_deployment_specification_mutation(_mapper, _connection, target) -> None:
    """Keep deployment evidence immutable after the run row is inserted."""

    state = inspect(target)
    changed = [
        field
        for field in _IMMUTABLE_DEPLOYMENT_SPECIFICATION_FIELDS
        if state.attrs[field].history.has_changes()
    ]
    if changed:
        raise ValueError(
            "Resolved deployment specification fields are immutable after creation"
        )
