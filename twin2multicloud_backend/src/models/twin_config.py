from sqlalchemy import Column, String, Boolean, ForeignKey, DateTime, Text, Integer
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
from src.models.database import Base

class TwinConfiguration(Base):
    """
    Stores non-secret Digital Twin configuration and CloudConnection bindings.

    Legacy encrypted credential columns remain nullable for audited migration
    cleanup only. Runtime credential resolution must use the provider
    CloudConnection relationships below.
    """
    __tablename__ = "twin_configurations"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    twin_id = Column(String, ForeignKey("digital_twins.id"), unique=True, nullable=False)
    
    # Basic settings
    debug_mode = Column(Boolean, default=False)
    
    # Wizard progress tracking
    highest_step_reached = Column(Integer, default=0)
    
    # AWS CloudConnection binding plus non-secret provider metadata.
    aws_cloud_connection_id = Column(String, ForeignKey("cloud_connections.id"), nullable=True)
    aws_access_key_id = Column(String, nullable=True)  # Legacy encrypted migration column
    aws_secret_access_key = Column(String, nullable=True)  # Legacy encrypted migration column
    aws_region = Column(String, default="eu-central-1")  # Not encrypted (not sensitive)
    aws_sso_region = Column(String, nullable=True)  # Not encrypted (SSO may be in different region)
    aws_session_token = Column(String, nullable=True)  # Legacy encrypted migration column
    aws_validated = Column(Boolean, default=False)
    
    # Azure CloudConnection binding plus non-secret provider metadata.
    azure_cloud_connection_id = Column(String, ForeignKey("cloud_connections.id"), nullable=True)
    azure_subscription_id = Column(String, nullable=True)  # Legacy encrypted migration column
    azure_client_id = Column(String, nullable=True)  # Legacy encrypted migration column
    azure_client_secret = Column(String, nullable=True)  # Legacy encrypted migration column
    azure_tenant_id = Column(String, nullable=True)  # Legacy encrypted migration column
    # Azure has three independent regions because IoT Hub and Digital Twins
    # are only available in a subset of regions. azure_region is the general
    # region for everything else (Functions, Storage, etc.). The other two
    # fall back to azure_region when not set.
    azure_region = Column(String, default="westeurope")  # Not encrypted
    azure_region_iothub = Column(String, nullable=True)  # Not encrypted, optional
    azure_region_digital_twin = Column(String, nullable=True)  # Not encrypted, optional
    azure_validated = Column(Boolean, default=False)
    
    # GCP CloudConnection binding plus non-secret provider metadata.
    gcp_cloud_connection_id = Column(String, ForeignKey("cloud_connections.id"), nullable=True)
    gcp_project_id = Column(String, nullable=True)  # Not encrypted (usually public)
    gcp_billing_account = Column(String, nullable=True)  # Legacy encrypted migration column
    gcp_region = Column(String, default="europe-west1")  # Not encrypted
    gcp_service_account_json = Column(Text, nullable=True)  # Legacy encrypted migration column
    gcp_validated = Column(Boolean, default=False)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationship
    twin = relationship("DigitalTwin", back_populates="configuration", uselist=False)
    aws_cloud_connection = relationship("CloudConnection", foreign_keys=[aws_cloud_connection_id])
    azure_cloud_connection = relationship("CloudConnection", foreign_keys=[azure_cloud_connection_id])
    gcp_cloud_connection = relationship("CloudConnection", foreign_keys=[gcp_cloud_connection_id])
