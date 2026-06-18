"""Typed read models for deployment operation endpoints."""

from __future__ import annotations

from typing import Any, cast

from src.models.deployment import Deployment
from src.models.twin import DigitalTwin
from src.schemas.deployment_operations import (
    DeploymentHistoryResponse,
    DeploymentOperationStatus,
    DeploymentOperationSummaryResponse,
    DeploymentOperationType,
    DeploymentOutputsResponse,
    DeploymentStatusResponse,
)


SECRET_KEY_PARTS = (
    "secret",
    "token",
    "password",
    "private_key",
    "credential",
    "credentials",
    "access_key",
)


def build_deployment_status_response(
    twin: DigitalTwin,
    *,
    active_session: dict[str, Any] | None,
    latest_deployment: Deployment | None,
) -> DeploymentStatusResponse:
    return DeploymentStatusResponse(
        state=twin.state,
        last_error=twin.last_error,
        deployed_at=twin.deployed_at,
        destroyed_at=twin.destroyed_at,
        active_session=active_session,
        latest_deployment=deployment_summary(latest_deployment),
    )


def build_deployment_outputs_response(
    deployment: Deployment | None,
) -> DeploymentOutputsResponse:
    if not deployment:
        return DeploymentOutputsResponse(outputs=None, deployed_at=None)

    outputs, redacted = sanitize_output_value(deployment.terraform_outputs)
    return DeploymentOutputsResponse(
        outputs=outputs if isinstance(outputs, dict) else None,
        deployed_at=deployment.completed_at,
        source_deployment=deployment_summary(deployment),
        redacted=redacted,
    )


def build_deployment_history_response(
    deployments: list[Deployment],
) -> DeploymentHistoryResponse:
    return DeploymentHistoryResponse(
        deployments=[
            summary
            for deployment in deployments
            if (summary := deployment_summary(deployment)) is not None
        ]
    )


def deployment_summary(
    deployment: Deployment | None,
) -> DeploymentOperationSummaryResponse | None:
    if not deployment:
        return None
    return DeploymentOperationSummaryResponse(
        id=deployment.id,
        session_id=deployment.session_id,
        operation_id=deployment.operation_id,
        operation_type=cast(DeploymentOperationType, deployment.operation_type),
        status=cast(DeploymentOperationStatus, deployment.status),
        error_code=deployment.error_code,
        error_message=deployment.error_message,
        started_at=deployment.started_at,
        completed_at=deployment.completed_at,
    )


def sanitize_output_value(value: Any) -> tuple[Any, bool]:
    if isinstance(value, dict):
        redacted = False
        sanitized = {}
        for key, raw in value.items():
            if _is_sensitive_key(str(key)):
                sanitized[str(key)] = "[REDACTED]"
                redacted = True
                continue
            sanitized_value, child_redacted = sanitize_output_value(raw)
            sanitized[str(key)] = sanitized_value
            redacted = redacted or child_redacted
        return sanitized, redacted
    if isinstance(value, list):
        redacted = False
        sanitized_items = []
        for item in value:
            sanitized_item, item_redacted = sanitize_output_value(item)
            sanitized_items.append(sanitized_item)
            redacted = redacted or item_redacted
        return sanitized_items, redacted
    return value, False


def _is_sensitive_key(key: str) -> bool:
    normalized = key.lower()
    return any(part in normalized for part in SECRET_KEY_PARTS)
