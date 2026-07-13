from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from src.models.twin import TwinState


DeploymentOperationStatus = Literal["pending", "running", "success", "failed"]
DeploymentOperationType = Literal["deploy", "destroy", "test"]


class ActiveDeploymentSessionResponse(BaseModel):
    session_id: str
    sse_url: str
    operation_type: DeploymentOperationType


class DeploymentOperationSummaryResponse(BaseModel):
    id: str
    session_id: str
    operation_id: str | None = None
    operation_type: DeploymentOperationType
    status: DeploymentOperationStatus
    error_code: str | None = None
    error_message: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None


class DeploymentStatusResponse(BaseModel):
    schema_version: str = "deployment-status.v1"
    state: TwinState
    last_error: str | None = None
    deployed_at: datetime | None = None
    destroyed_at: datetime | None = None
    active_session: ActiveDeploymentSessionResponse | None = None
    latest_deployment: DeploymentOperationSummaryResponse | None = None


class DeploymentOutputsResponse(BaseModel):
    schema_version: str = "deployment-outputs.v1"
    outputs: dict | None = None
    deployed_at: datetime | None = None
    source_deployment: DeploymentOperationSummaryResponse | None = None
    redacted: bool = False


class DeploymentHistoryResponse(BaseModel):
    schema_version: str = "deployment-history.v1"
    deployments: list[DeploymentOperationSummaryResponse] = Field(default_factory=list)
