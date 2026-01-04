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
    deployer_digital_twin_name = Column(String, nullable=True)  # config.json digital_twin_name
    config_events_json = Column(Text, nullable=True)        # config_events.json content
    config_iot_devices_json = Column(Text, nullable=True)   # config_iot_devices.json content
    
    # ===== SECTION 2: Validation State (gates save) =====
    config_json_validated = Column(Boolean, default=False)       # config.json validation
    config_events_validated = Column(Boolean, default=False)
    config_iot_devices_validated = Column(Boolean, default=False)
    
    # ===== SECTION 3: L1 Payloads =====
    payloads_json = Column(Text, nullable=True)
    payloads_validated = Column(Boolean, default=False)
    
    # ===== SECTION 3: L2 User Functions =====
    # Processor content per device (JSON: {device_id: python_code})
    processor_contents = Column(Text, nullable=True)  # JSON string
    processor_validated = Column(Text, nullable=True)  # JSON string: {device_id: bool}
    
    # Event feedback function
    event_feedback_content = Column(Text, nullable=True)
    event_feedback_validated = Column(Boolean, default=False)
    
    # Event action functions per event (JSON: {functionName: python_code})
    event_action_contents = Column(Text, nullable=True)  # JSON string
    event_action_validated = Column(Text, nullable=True)  # JSON string: {functionName: bool}
    
    # State machine / workflow definition
    state_machine_content = Column(Text, nullable=True)
    state_machine_validated = Column(Boolean, default=False)
    
    # ===== TIMESTAMPS =====
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    # Relationship
    twin = relationship("DigitalTwin", back_populates="deployer_config", uselist=False)
