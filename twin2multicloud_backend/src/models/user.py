from sqlalchemy import Column, String, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
from src.models.database import Base

class User(Base):
    __tablename__ = "users"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String, unique=True, nullable=False, index=True)
    name = Column(String, nullable=True)
    picture_url = Column(String, nullable=True)
    auth_provider = Column(String, nullable=False, default="development")
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login_at = Column(DateTime, nullable=True)
    theme_preference = Column(String, nullable=True, default="dark")  # "light" | "dark"
    
    # Relationships
    twins = relationship("DigitalTwin", back_populates="owner")
    cloud_connections = relationship("CloudConnection", back_populates="owner", cascade="all, delete-orphan")
    external_identities = relationship(
        "ExternalIdentity",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    auth_sessions = relationship(
        "AuthSession",
        back_populates="user",
        cascade="all, delete-orphan",
    )
