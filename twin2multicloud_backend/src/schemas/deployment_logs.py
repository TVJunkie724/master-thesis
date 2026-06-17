from datetime import datetime

from pydantic import BaseModel, Field


class DeploymentLogEntryResponse(BaseModel):
    event_id: int
    session_id: str
    timestamp: datetime
    level: str
    message: str
    operation_type: str


class DeploymentLogPageResponse(BaseModel):
    schema_version: str = "deployment-log-page.v1"
    twin_id: str
    session_id: str | None = None
    after_event_id: int = 0
    limit: int = Field(ge=1, le=500)
    logs: list[DeploymentLogEntryResponse]
    has_more: bool
    next_after_event_id: int | None = None
    latest_event_id: int | None = None
