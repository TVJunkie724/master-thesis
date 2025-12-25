from sqlalchemy import Column, String, DateTime, ForeignKey, Text, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
import enum
from src.models.database import Base

class Deployment(Base):
    __tablename__ = "deployments"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    twin_id = Column(String, ForeignKey("digital_twins.id"), nullable=False)
    status = Column(String, default="pending")
    description = Column(String, nullable=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    terraform_outputs = Column(JSON, nullable=True)
    logs = Column(Text, nullable=True)
    
    # Relationships
    twin = relationship("DigitalTwin", back_populates="deployments")


class DeploymentStatus(str, enum.Enum):
    """Deployment status enum (for reference, status column uses string for flexibility)"""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
