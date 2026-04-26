from datetime import datetime
import uuid

from sqlalchemy import Column, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import relationship

from src.models.database import Base


class CloudConnection(Base):
    """User-scoped cloud access credential managed by the Management API."""

    __tablename__ = "cloud_connections"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    provider = Column(String, nullable=False, index=True)
    display_name = Column(String, nullable=False)
    cloud_scope = Column(Text, nullable=False, default="{}")
    auth_type = Column(String, nullable=False)
    encrypted_payload = Column(Text, nullable=False)
    payload_fingerprint = Column(String, nullable=False, index=True)
    validation_status = Column(String, nullable=False, default="untested")
    validation_message = Column(String, nullable=True)
    last_validated_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    owner = relationship("User", back_populates="cloud_connections")
