from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from src.api.dependencies import get_current_user
from src.api.routes.error_models import ERROR_RESPONSES
from src.models.database import get_db
from src.models.user import User
from src.schemas.cloud_connection import (
    CloudConnectionCreate,
    CloudConnectionPreflightResponse,
    CloudConnectionResponse,
    CloudConnectionUpdate,
    CloudConnectionValidationResponse,
)
from src.services.cloud_connection_service import CloudConnectionService
from src.services.cloud_credential_validation_service import (
    build_preflight_result,
    perform_dual_validation,
    perform_optimizer_validation,
    redact_validation_result,
)
from src.services.errors import CloudConnectionConflict
from src.services.permission_sets import compare_permission_set_version
from src.schemas.credential_security_event import (
    CredentialSecurityAction,
    CredentialSecurityEventDraft,
    CredentialSecurityOutcome,
)
from src.security.rate_limit import CredentialRateClass, credential_rate_limit
from src.security.request_context import current_request_id
from src.services.credential_security_audit_service import CredentialSecurityAuditService

router = APIRouter(prefix="/cloud-connections", tags=["cloud-connections"])


@router.get(
    "/",
    response_model=list[CloudConnectionResponse],
    operation_id="listCloudConnections",
    summary="List the current user's cloud connections",
    responses={401: ERROR_RESPONSES[401]},
)
async def list_cloud_connections(
    provider: str | None = Query(default=None, pattern="^(aws|azure|gcp)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = CloudConnectionService(db)
    connections = service.list_connections(current_user.id)
    if provider is None:
        return connections
    return [connection for connection in connections if connection.provider == provider]


@router.post(
    "/",
    response_model=CloudConnectionResponse,
    operation_id="createCloudConnection",
    summary="Create a user-scoped cloud connection",
    responses={
        400: ERROR_RESPONSES[400],
        401: ERROR_RESPONSES[401],
    },
)
async def create_cloud_connection(
    request: CloudConnectionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        credential_rate_limit(
            CredentialRateClass.WRITE,
            CredentialSecurityAction.CONNECTION_CREATE,
        )
    ),
):
    service = CloudConnectionService(db)
    try:
        return service.create_connection(
            current_user.id,
            request,
            _audit(current_user, CredentialSecurityAction.CONNECTION_CREATE, request.provider, request.purpose, 200),
        )
    except CloudConnectionConflict as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get(
    "/{connection_id}",
    response_model=CloudConnectionResponse,
    operation_id="getCloudConnection",
    summary="Get a cloud connection without exposing its secret payload",
    responses={
        401: ERROR_RESPONSES[401],
        404: ERROR_RESPONSES[404],
    },
)
async def get_cloud_connection(
    connection_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = CloudConnectionService(db)
    connection = service.get_connection(connection_id, current_user.id)
    if not connection:
        raise HTTPException(status_code=404, detail="Cloud connection not found")
    return service.to_response(connection, current_user.id)


@router.patch(
    "/{connection_id}",
    response_model=CloudConnectionResponse,
    operation_id="updateCloudConnection",
    summary="Update cloud connection metadata",
    responses={
        401: ERROR_RESPONSES[401],
        404: ERROR_RESPONSES[404],
    },
)
async def update_cloud_connection(
    connection_id: str,
    request: CloudConnectionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        credential_rate_limit(
            CredentialRateClass.WRITE,
            CredentialSecurityAction.CONNECTION_UPDATE,
        )
    ),
):
    service = CloudConnectionService(db)
    connection = service.get_connection(connection_id, current_user.id)
    if not connection:
        raise HTTPException(status_code=404, detail="Cloud connection not found")
    try:
        return service.update_connection(
            connection,
            current_user.id,
            request,
            _audit(current_user, CredentialSecurityAction.CONNECTION_UPDATE, connection.provider, connection.purpose, 200),
        )
    except CloudConnectionConflict as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete(
    "/{connection_id}",
    status_code=204,
    operation_id="deleteCloudConnection",
    summary="Delete a cloud connection owned by the current user",
    responses={
        401: ERROR_RESPONSES[401],
        409: ERROR_RESPONSES[409],
        404: ERROR_RESPONSES[404],
    },
)
async def delete_cloud_connection(
    connection_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        credential_rate_limit(
            CredentialRateClass.WRITE,
            CredentialSecurityAction.CONNECTION_DELETE,
        )
    ),
):
    service = CloudConnectionService(db)
    connection = service.get_connection(connection_id, current_user.id)
    if not connection:
        raise HTTPException(status_code=404, detail="Cloud connection not found")
    if service.count_twin_bindings(connection_id) > 0:
        raise HTTPException(
            status_code=409,
            detail="Cloud connection is still bound to one or more twins",
        )
    service.delete_connection(
        connection,
        _audit(current_user, CredentialSecurityAction.CONNECTION_DELETE, connection.provider, connection.purpose, 204),
    )


@router.post(
    "/{connection_id}/validate",
    response_model=CloudConnectionValidationResponse,
    operation_id="validateCloudConnection",
    summary="Validate a stored cloud connection at its purpose-specific boundaries",
    responses={
        401: ERROR_RESPONSES[401],
        404: ERROR_RESPONSES[404],
    },
)
async def validate_cloud_connection(
    connection_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        credential_rate_limit(
            CredentialRateClass.VALIDATION,
            CredentialSecurityAction.CONNECTION_VALIDATE,
        )
    ),
):
    service = CloudConnectionService(db)
    connection = service.get_connection(connection_id, current_user.id)
    if not connection:
        raise HTTPException(status_code=404, detail="Cloud connection not found")

    optimizer_creds = service.build_optimizer_credentials(connection, current_user.id)
    if connection.purpose == "pricing":
        result = await perform_optimizer_validation(connection.provider, optimizer_creds)
        result = redact_validation_result(result, optimizer_creds)
    else:
        deployer_creds = service.build_deployer_credentials(connection, current_user.id)
        result = await perform_dual_validation(
            connection.provider,
            optimizer_creds,
            deployer_creds,
        )
        result = redact_validation_result(result, optimizer_creds, deployer_creds)
    service.record_validation_result(
        connection,
        result,
        _audit(
            current_user,
            CredentialSecurityAction.CONNECTION_VALIDATE,
            connection.provider,
            connection.purpose,
            200,
            outcome=(
                CredentialSecurityOutcome.SUCCEEDED
                if result.get("valid", False)
                else CredentialSecurityOutcome.REJECTED
            ),
        ),
    )
    return CloudConnectionValidationResponse(
        id=connection.id,
        provider=connection.provider,
        valid=result.get("valid", False),
        validation_status=connection.validation_status,
        message=connection.validation_message or "Validation complete",
        optimizer=result.get("optimizer"),
        deployer=result.get("deployer"),
    )


@router.post(
    "/{connection_id}/preflight",
    response_model=CloudConnectionPreflightResponse,
    operation_id="preflightCloudConnection",
    summary="Run a deployment preflight for a stored cloud connection",
    responses={
        401: ERROR_RESPONSES[401],
        404: ERROR_RESPONSES[404],
    },
)
async def preflight_cloud_connection(
    connection_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        credential_rate_limit(
            CredentialRateClass.VALIDATION,
            CredentialSecurityAction.CONNECTION_PREFLIGHT,
        )
    ),
):
    service = CloudConnectionService(db)
    connection = service.get_connection(connection_id, current_user.id)
    if not connection:
        raise HTTPException(status_code=404, detail="Cloud connection not found")
    if connection.purpose != "deployment":
        raise HTTPException(
            status_code=400,
            detail="Pricing Cloud Connections cannot run deployment preflight.",
        )

    optimizer_creds = service.build_optimizer_credentials(connection, current_user.id)
    deployer_creds = service.build_deployer_credentials(connection, current_user.id)
    result = await perform_dual_validation(
        connection.provider,
        optimizer_creds,
        deployer_creds,
    )
    result = redact_validation_result(result, optimizer_creds, deployer_creds)
    version_comparison = compare_permission_set_version(
        connection.provider,
        connection.permission_set_version,
    )
    preflight = build_preflight_result(
        connection.provider,
        result,
        version_comparison=version_comparison,
    )
    CredentialSecurityAuditService.commit_standalone(
        db,
        _audit(
            current_user,
            CredentialSecurityAction.CONNECTION_PREFLIGHT,
            connection.provider,
            connection.purpose,
            200,
            resource_id=connection.id,
            outcome=(
                CredentialSecurityOutcome.SUCCEEDED
                if preflight["ready"]
                else CredentialSecurityOutcome.REJECTED
            ),
        ),
    )
    return CloudConnectionPreflightResponse(
        id=connection.id,
        provider=connection.provider,
        expected_permission_set_version=version_comparison.expected_version,
        supplied_permission_set_version=version_comparison.supplied_version,
        permission_set_status=version_comparison.status,
        ready=preflight["ready"],
        summary=preflight["summary"],
        checks=preflight["checks"],
    )


def _audit(
    user: User,
    action: CredentialSecurityAction,
    provider: str,
    purpose: str,
    status: int,
    *,
    resource_id: str | None = None,
    outcome: CredentialSecurityOutcome = CredentialSecurityOutcome.SUCCEEDED,
) -> CredentialSecurityEventDraft:
    return CredentialSecurityEventDraft(
        user_id=user.id,
        action=action,
        outcome=outcome,
        resource_type="cloud_connection",
        resource_id=resource_id,
        provider=provider,
        purpose=purpose,
        http_status=status,
        request_id=current_request_id(),
    )
