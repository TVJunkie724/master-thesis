"""
Typed contracts for deployment API responses and stream events.

These models define the public deploy/destroy boundary. Route handlers should
return these contracts rather than assembling ad hoc dictionaries or JSON.
"""

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field
from src.api.deployment_trace import (
    DeploymentErrorCategory,
    classify_deployment_error,
    sanitize_deployment_message,
    sanitize_terraform_outputs,
)


class DeploymentOperation(str, Enum):
    deploy = "deploy"
    destroy = "destroy"


class DeploymentStatus(str, Enum):
    success = "success"
    error = "error"


class DeploymentEventType(str, Enum):
    log = "log"
    complete = "complete"
    error = "error"


class DeploymentRequest(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    project_name: str
    provider: str


class DeploymentResult(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    message: str = "Core and IoT services deployed successfully"
    status: DeploymentStatus = DeploymentStatus.success
    operation: DeploymentOperation = DeploymentOperation.deploy
    project_name: str
    provider: str
    terraform_outputs: dict[str, Any] = Field(default_factory=dict)


class DestroyResult(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    message: str = "Core and IoT services destroyed successfully"
    status: DeploymentStatus = DeploymentStatus.success
    operation: DeploymentOperation = DeploymentOperation.destroy
    project_name: str
    provider: str


class DeploymentStreamEvent(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    event: DeploymentEventType
    operation: DeploymentOperation
    success: bool | None = None
    message: str | None = None
    outputs: dict[str, Any] | None = None
    error: str | None = None
    error_category: DeploymentErrorCategory | None = None

    @classmethod
    def log(cls, operation: DeploymentOperation, message: str) -> "DeploymentStreamEvent":
        return cls(
            event=DeploymentEventType.log,
            operation=operation,
            message=sanitize_deployment_message(message),
        )

    @classmethod
    def complete(
        cls,
        operation: DeploymentOperation,
        outputs: dict[str, Any] | None = None,
    ) -> "DeploymentStreamEvent":
        return cls(
            event=DeploymentEventType.complete,
            operation=operation,
            success=True,
            outputs=sanitize_terraform_outputs(outputs),
        )

    @classmethod
    def failure(cls, operation: DeploymentOperation, error: str) -> "DeploymentStreamEvent":
        return cls(
            event=DeploymentEventType.error,
            operation=operation,
            success=False,
            error=sanitize_deployment_message(error),
            error_category=classify_deployment_error(error),
        )

    def to_sse(self) -> str:
        """Serialize this event to Server-Sent Events wire format."""
        event_prefix = "" if self.event == DeploymentEventType.log else f"event: {self.event}\n"
        payload = self.model_dump_json(exclude_none=True)
        return f"{event_prefix}data: {payload}\n\n"
