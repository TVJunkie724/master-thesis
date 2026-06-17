from datetime import datetime, timezone
import uuid

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String, Text

from src.models.database import Base


class PricingRefreshRun(Base):
    """Persisted Management API run record for provider pricing refreshes."""

    __tablename__ = "pricing_refresh_runs"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    provider = Column(String, nullable=False, index=True)
    status = Column(String, nullable=False, default="running", index=True)
    pricing_connection_id = Column(
        String,
        ForeignKey("cloud_connections.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    force = Column(Boolean, nullable=False, default=False)
    credential_summary_json = Column(Text, nullable=False)
    result_summary_json = Column(Text, nullable=True)
    error_code = Column(String, nullable=True)
    error_message = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
