import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, String
from sqlalchemy.orm import relationship

from src.models.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String, unique=True, nullable=False, index=True)
    name = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    theme_preference = Column(String, nullable=True, default="dark")  # "light" | "dark"

    # Relationships
    twins = relationship("DigitalTwin", back_populates="owner")
    cloud_connections = relationship(
        "CloudConnection", back_populates="owner", cascade="all, delete-orphan"
    )
