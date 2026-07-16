"""Small Management API response contracts shared by route modules."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from src.models.twin import TwinState


class MessageResponse(BaseModel):
    """Simple command acknowledgement."""

    message: str


class HealthResponse(BaseModel):
    """Management API health check response."""

    status: str
    database: str


class OperationSessionResponse(BaseModel):
    """Response for operations that continue through the deployment SSE channel."""

    session_id: str
    sse_url: str


class RedeployReadinessResponse(BaseModel):
    """Redeployment cooldown status."""

    ready: bool
    remaining_seconds: int


class ActiveDeploymentSessionResponse(BaseModel):
    """Reconnect metadata for an active deployment stream."""

    session_id: str
    sse_url: str
    operation_type: str


class DeploymentStatusResponse(BaseModel):
    """Current deployment lifecycle status for a twin."""

    state: TwinState
    last_error: str | None = None
    deployed_at: str | None = None
    destroyed_at: str | None = None
    active_session: ActiveDeploymentSessionResponse | None = None
    latest_deployment: dict[str, Any] | None = None


class DeploymentOutputsResponse(BaseModel):
    """Stored Terraform outputs for the latest successful deployment."""

    outputs: dict[str, Any] | None = None
    deployed_at: str | None = None


class DeploymentHistoryItemResponse(BaseModel):
    """Single deployment history record."""

    id: str
    session_id: str | None = None
    operation_id: str | None = None
    operation_type: str | None = None
    status: str | None = None
    started_at: str | None = None
    completed_at: str | None = None
    error_code: str | None = None
    error_message: str | None = None


class DeploymentHistoryResponse(BaseModel):
    """Deployment history response."""

    deployments: list[DeploymentHistoryItemResponse]


class SceneGlbUploadResponse(BaseModel):
    """Scene GLB upload acknowledgement."""

    message: str
    size_mb: float


class ValidationBranchResultResponse(BaseModel):
    """Single downstream branch result in dual credential validation."""

    valid: bool
    message: str
    permissions: Any | None = None


class DualCredentialValidationResponse(BaseModel):
    """Combined Optimizer and Deployer credential validation response."""

    provider: str
    valid: bool
    optimizer: ValidationBranchResultResponse
    deployer: ValidationBranchResultResponse
