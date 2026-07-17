from datetime import datetime, timezone
import uuid

from sqlalchemy import Column, DateTime, Float, ForeignKey, String, Text
from sqlalchemy.orm import relationship

from src.models.database import Base


class CostCalculationRun(Base):
    """Typed optimizer calculation run owned by the Management API."""

    __tablename__ = "cost_calculation_runs"

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
