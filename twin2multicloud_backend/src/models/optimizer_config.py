from sqlalchemy import Column, String, Text, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
import uuid
from src.models.database import Base


class OptimizerConfiguration(Base):
    """Stores optimizer state for a Digital Twin."""
    __tablename__ = "optimizer_configurations"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    twin_id = Column(String, ForeignKey("digital_twins.id", ondelete="CASCADE"), unique=True, nullable=False)
    
    # ===== CALCULATION PARAMS (input) =====
    params = Column(Text, nullable=True)  # CalcParams as JSON
    
    # ===== CHEAPEST PATH (separate for deployment logic) =====
    cheapest_l1 = Column(String(10), nullable=True)   # "AWS", "AZURE", "GCP"
    cheapest_l2 = Column(String(10), nullable=True)
    cheapest_l3_hot = Column(String(10), nullable=True)
    cheapest_l3_cool = Column(String(10), nullable=True)
    cheapest_l3_archive = Column(String(10), nullable=True)
    cheapest_l4 = Column(String(10), nullable=True)
    cheapest_l5 = Column(String(10), nullable=True)
    
    # ===== FULL RESULT (for UI display) =====
    result_json = Column(Text, nullable=True)  # Full CalcResult as JSON
    
    # ===== PRICING SNAPSHOT (audit trail, ~few KB each) =====
    pricing_aws_updated_at = Column(DateTime(timezone=True), nullable=True)
    pricing_azure_updated_at = Column(DateTime(timezone=True), nullable=True)
    pricing_gcp_updated_at = Column(DateTime(timezone=True), nullable=True)
    pricing_aws_snapshot = Column(Text, nullable=True)
    pricing_azure_snapshot = Column(Text, nullable=True)
    pricing_gcp_snapshot = Column(Text, nullable=True)
    
    # ===== TIMESTAMPS =====
    calculated_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    twin = relationship("DigitalTwin", back_populates="optimizer_config", uselist=False)
