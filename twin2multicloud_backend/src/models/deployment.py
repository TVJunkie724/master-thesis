from sqlalchemy import Column, String, DateTime, ForeignKey, Text, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
import enum
from src.models.database import Base

class Deployment(Base):
    """
    Historical record of deployment/destroy operations.
    
    Each deploy/destroy creates one Deployment record linked to DeploymentLog entries
    via session_id for full operation history.
    """
    __tablename__ = "deployments"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    twin_id = Column(String, ForeignKey("digital_twins.id"), nullable=False)
    session_id = Column(String, unique=True, nullable=False)  # Links to DeploymentLog
    operation_type = Column(String, default="deploy")  # "deploy", "destroy", "test"
    status = Column(String, default="running")  # "running", "success", "failed"
    description = Column(String, nullable=True)
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    terraform_outputs = Column(JSON, nullable=True)
    error_message = Column(Text, nullable=True)
    logs = Column(Text, nullable=True)  # Legacy, kept for compatibility
    
    # Relationships
    twin = relationship("DigitalTwin", back_populates="deployments")


class DeploymentStatus(str, enum.Enum):
    """Deployment status enum (for reference, status column uses string for flexibility)"""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
