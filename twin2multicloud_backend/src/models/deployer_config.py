from sqlalchemy import Column, String, Boolean, ForeignKey, DateTime, Text
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
import uuid
from src.models.database import Base


class DeployerConfiguration(Base):
    """
    Stores deployer configuration for a Digital Twin (Step 3 data).
    
    Section 2: Configuration files for deployment
    - config_events_json: Event-driven automation rules
    - config_iot_devices_json: IoT device definitions
    
    Validation state is persisted to gate save operations.
    """
    __tablename__ = "deployer_configurations"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    twin_id = Column(String, ForeignKey("digital_twins.id", ondelete="CASCADE"), unique=True, nullable=False)
    
    # ===== SECTION 2: Configuration Files =====
    config_events_json = Column(Text, nullable=True)        # config_events.json content
    config_iot_devices_json = Column(Text, nullable=True)   # config_iot_devices.json content
    
    # ===== SECTION 2: Validation State (gates save) =====
    config_events_validated = Column(Boolean, default=False)
    config_iot_devices_validated = Column(Boolean, default=False)
    
    # ===== TIMESTAMPS =====
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    # Relationship
    twin = relationship("DigitalTwin", back_populates="deployer_config", uselist=False)
