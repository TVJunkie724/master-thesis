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
    google_id = Column(String, unique=True, nullable=True)
    # UIBK Shibboleth SAML integration
    uibk_id = Column(String, unique=True, nullable=True)  # eduPersonPrincipalName from SAML
    auth_provider = Column(String, nullable=False, default="google")  # "google" | "uibk"
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login_at = Column(DateTime, nullable=True)
    
    # Relationships
    twins = relationship("DigitalTwin", back_populates="owner")

