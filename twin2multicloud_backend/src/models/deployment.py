import enum
import uuid
from datetime import datetime

from sqlalchemy import JSON, Column, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import relationship

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
    idempotency_key = Column(String(128), nullable=True)
    operation_type = Column(String, default="deploy")  # "deploy", "destroy", "test"
    operation_id = Column(String, nullable=True)  # Deployer operation id for log correlation
    status = Column(String, default="running")  # "running", "success", "failed"
    description = Column(String, nullable=True)
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    terraform_outputs = Column(JSON, nullable=True)
    deployment_access_evidence = Column(JSON, nullable=True)
    layer_access_credential_rotated_at = Column(DateTime, nullable=True)
    layer_access_credential_fingerprint = Column(String(64), nullable=True)
    error_code = Column(String, nullable=True)
    error_message = Column(Text, nullable=True)
    architecture_digest = Column(String(71), nullable=True)
    graph_digest = Column(String(71), nullable=True)
    profile_id = Column(String(128), nullable=True)
    profile_version = Column(String(32), nullable=True)
    catalog_id = Column(String(128), nullable=True)
    catalog_version = Column(String(32), nullable=True)
    completed_stage = Column(String(32), nullable=True)
    graph_validation = Column(JSON, nullable=True)
    logs = Column(Text, nullable=True)  # Legacy, kept for compatibility
    
    # Relationships
    twin = relationship("DigitalTwin", back_populates="deployments")

    __table_args__ = (
        Index(
            "ux_deployments_twin_operation_idempotency",
            "twin_id",
            "operation_type",
            "idempotency_key",
            unique=True,
        ),
    )


class DeploymentStatus(str, enum.Enum):
    """Deployment status enum (for reference, status column uses string for flexibility)"""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
