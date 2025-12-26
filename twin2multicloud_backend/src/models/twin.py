from sqlalchemy import Column, String, DateTime, ForeignKey, Enum
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
import enum
from src.models.database import Base

class TwinState(str, enum.Enum):
    DRAFT = "draft"
    CONFIGURED = "configured"
    DEPLOYED = "deployed"
    DESTROYED = "destroyed"
    ERROR = "error"
    INACTIVE = "inactive"

class DigitalTwin(Base):
    __tablename__ = "digital_twins"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    name = Column(String, nullable=False)
    state = Column(Enum(TwinState), default=TwinState.DRAFT)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    owner = relationship("User", back_populates="twins")
    file_versions = relationship("FileVersion", back_populates="twin")
    deployments = relationship("Deployment", back_populates="twin")
    configuration = relationship("TwinConfiguration", back_populates="twin", uselist=False)

