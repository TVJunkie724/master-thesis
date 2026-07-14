from sqlalchemy import Column, String, DateTime, ForeignKey, Enum, UniqueConstraint
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
import enum
from src.models.database import Base

class TwinState(str, enum.Enum):
    DRAFT = "draft"
    CONFIGURED = "configured"
    DEPLOYING = "deploying"      # Transient: deployment in progress
    DEPLOYED = "deployed"
    DESTROYING = "destroying"    # Transient: destruction in progress
    DESTROYED = "destroyed"
    ERROR = "error"
    INACTIVE = "inactive"

class DigitalTwin(Base):
    __tablename__ = "digital_twins"
    __table_args__ = (
        UniqueConstraint('user_id', 'name', name='uq_user_twin_name'),
    )
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    name = Column(String, nullable=False)
    state = Column(Enum(TwinState), default=TwinState.DRAFT)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Deployment lifecycle timestamps (for cooldown tracking)
    deployed_at = Column(DateTime, nullable=True)
    destroyed_at = Column(DateTime, nullable=True)
    
    # Error tracking
    last_error = Column(String, nullable=True)
    
    # Relationships
    owner = relationship("User", back_populates="twins")
    file_versions = relationship("FileVersion", back_populates="twin")
    deployments = relationship("Deployment", back_populates="twin")
    configuration = relationship("TwinConfiguration", back_populates="twin", uselist=False)
    optimizer_config = relationship(
        "OptimizerConfiguration", 
        back_populates="twin", 
        uselist=False,
        cascade="all, delete-orphan"
    )
    cost_calculation_runs = relationship(
        "CostCalculationRun",
        back_populates="twin",
        cascade="all, delete-orphan",
        order_by="CostCalculationRun.created_at.desc()",
    )
    deployer_config = relationship(
        "DeployerConfiguration",
        back_populates="twin",
        uselist=False,
        cascade="all, delete-orphan"
    )
    deployment_logs = relationship(
        "DeploymentLog",
        back_populates="twin",
        order_by="DeploymentLog.event_id.asc()"
    )
    deployment_preflight_cache = relationship(
        "DeploymentPreflightCache",
        back_populates="twin",
        cascade="all, delete-orphan",
    )
