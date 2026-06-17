from datetime import datetime, timezone
import uuid

from sqlalchemy import Column, DateTime, ForeignKey, String, Text

from src.models.database import Base


class PricingCandidateReport(Base):
    """Persisted, secret-free candidate review report derived from a refresh run."""

    __tablename__ = "pricing_candidate_reports"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    provider = Column(String, nullable=False, index=True)
    refresh_run_id = Column(
        String,
        ForeignKey("pricing_refresh_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    intent_id = Column(String, nullable=False, index=True)
    review_state = Column(String, nullable=False, index=True)
    report_json = Column(Text, nullable=False)
    trace_json = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)


class PricingReviewDecision(Base):
    """Explicit user-reviewed decision for one candidate report."""

    __tablename__ = "pricing_review_decisions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    report_id = Column(
        String,
        ForeignKey("pricing_candidate_reports.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    provider = Column(String, nullable=False, index=True)
    intent_id = Column(String, nullable=False, index=True)
    decision = Column(String, nullable=False, index=True)
    selected_candidate_id = Column(String, nullable=True)
    rationale = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
