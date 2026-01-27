"""DeploymentLog model for SSE log persistence.

Stores deployment logs for real-time streaming and post-hoc debugging.
Each log entry has an event_id for ordering and Last-Event-Id support.
"""
from sqlalchemy import Column, String, Text, DateTime, Integer, ForeignKey, Index
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
import enum
from src.models.database import Base


class OperationType(str, enum.Enum):
    """Type of deployment operation."""
    DEPLOY = "deploy"
    DESTROY = "destroy"
    TEST = "test"


class DeploymentLog(Base):
    """
    Model for storing individual deployment log entries.
    
    Each log entry represents a single line of Terraform output
    or a deployment event. Logs are persisted incrementally to
    allow recovery after connection drops.
    """
    __tablename__ = "deployment_logs"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    twin_id = Column(String, ForeignKey("digital_twins.id"), nullable=False)
    session_id = Column(String, nullable=False)
    event_id = Column(Integer, nullable=False)  # For ordering and Last-Event-Id
    timestamp = Column(DateTime, default=datetime.utcnow)
    level = Column(String, default="info")  # info, error, warning
    message = Column(Text, nullable=False)
    operation_type = Column(String, default=OperationType.DEPLOY.value)

    # Relationships
    twin = relationship("DigitalTwin", back_populates="deployment_logs")

    __table_args__ = (
        # Index for fast twin-specific queries
        Index('ix_deployment_logs_twin_id', 'twin_id'),
        # Index for session-specific queries
        Index('ix_deployment_logs_session_id', 'session_id'),
        # Index for time-based queries
        Index('ix_deployment_logs_timestamp', 'timestamp'),
        # Composite index for efficient log retrieval (catchup queries)
        Index('ix_deployment_logs_twin_session_event', 'twin_id', 'session_id', 'event_id'),
    )

    def __repr__(self):
        return f"<DeploymentLog {self.session_id}:{self.event_id}>"
