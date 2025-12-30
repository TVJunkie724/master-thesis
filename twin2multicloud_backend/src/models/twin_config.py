from sqlalchemy import Column, String, Boolean, ForeignKey, DateTime, Text, Integer
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
from src.models.database import Base

class TwinConfiguration(Base):
    """
    Stores configuration for a Digital Twin including cloud credentials.
    
    IMPORTANT: All credential fields are ENCRYPTED using Fernet.
    - Encrypt before saving: crypto.encrypt(secret, user_id, twin_id)
    - Decrypt when reading: crypto.decrypt(encrypted, user_id, twin_id)
    """
    __tablename__ = "twin_configurations"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    twin_id = Column(String, ForeignKey("digital_twins.id"), unique=True, nullable=False)
    
    # Basic settings
    debug_mode = Column(Boolean, default=False)
    
    # Wizard progress tracking
    highest_step_reached = Column(Integer, default=0)
    
    # AWS credentials (ENCRYPTED)
    aws_access_key_id = Column(String, nullable=True)  # Encrypted
    aws_secret_access_key = Column(String, nullable=True)  # Encrypted
    aws_region = Column(String, default="eu-central-1")  # Not encrypted (not sensitive)
    aws_sso_region = Column(String, nullable=True)  # Not encrypted (SSO may be in different region)
    aws_session_token = Column(String, nullable=True)  # Encrypted (optional for STS/SSO)
    aws_validated = Column(Boolean, default=False)
    
    # Azure credentials (ENCRYPTED)
    azure_subscription_id = Column(String, nullable=True)  # Encrypted
    azure_client_id = Column(String, nullable=True)  # Encrypted
    azure_client_secret = Column(String, nullable=True)  # Encrypted
    azure_tenant_id = Column(String, nullable=True)  # Encrypted
    azure_region = Column(String, default="westeurope")  # Not encrypted
    azure_validated = Column(Boolean, default=False)
    
    # GCP credentials (ENCRYPTED - full JSON)
    gcp_project_id = Column(String, nullable=True)  # Not encrypted (usually public)
    gcp_billing_account = Column(String, nullable=True)  # Encrypted
    gcp_region = Column(String, default="europe-west1")  # Not encrypted
    gcp_service_account_json = Column(Text, nullable=True)  # Encrypted (contains private key)
    gcp_validated = Column(Boolean, default=False)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationship
    twin = relationship("DigitalTwin", back_populates="configuration", uselist=False)
