from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, LargeBinary
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
from src.models.database import Base

class FileVersion(Base):
    __tablename__ = "file_versions"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    twin_id = Column(String, ForeignKey("digital_twins.id"), nullable=False)
    file_path = Column(String, nullable=False)  # e.g., "config.json"
    content = Column(LargeBinary, nullable=False)
    version = Column(Integer, nullable=False)
    description = Column(String, nullable=True)
    created_by = Column(String, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    twin = relationship("DigitalTwin", back_populates="file_versions")
    
    __table_args__ = (
        # Unique constraint: only one version per twin+file_path+version number
        # UniqueConstraint would need import, using Index instead for simplicity
        {},
    )
