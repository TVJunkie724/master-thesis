from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.api.routes.error_models import ERROR_RESPONSES
from src.models.database import get_db
from src.models.user import User
from src.schemas.cloud_bootstrap import (
    CloudBootstrapImportRequest,
    CloudBootstrapImportResponse,
    CloudBootstrapPlanRequest,
    CloudBootstrapPlanResponse,
)
from src.services.cloud_bootstrap_service import CloudBootstrapService
from src.services.cloud_connection_service import CloudConnectionService
from src.schemas.credential_security_event import (
    CredentialSecurityAction,
    CredentialSecurityEventDraft,
    CredentialSecurityOutcome,
)
from src.security.rate_limit import CredentialRateClass, credential_rate_limit
from src.security.request_context import current_request_id
from src.services.credential_security_audit_service import CredentialSecurityAuditService

router = APIRouter(prefix="/cloud-bootstrap", tags=["cloud-bootstrap"])


@router.post(
    "/{provider}/plan",
    response_model=CloudBootstrapPlanResponse,
    operation_id="createCloudBootstrapPlan",
    summary="Create a safe manual provider bootstrap plan",
    responses={
        400: ERROR_RESPONSES[400],
        401: ERROR_RESPONSES[401],
        422: ERROR_RESPONSES[422],
    },
)
async def create_cloud_bootstrap_plan(
    provider: str,
    request: CloudBootstrapPlanRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        credential_rate_limit(
            CredentialRateClass.BOOTSTRAP,
            CredentialSecurityAction.BOOTSTRAP_PLAN,
        )
    ),
):
    try:
        result = CloudBootstrapService().build_plan(provider, request)
        CredentialSecurityAuditService.commit_standalone(
            db,
            _audit(current_user, CredentialSecurityAction.BOOTSTRAP_PLAN, result.provider, 200),
        )
        return result
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post(
    "/import",
    response_model=CloudBootstrapImportResponse,
    operation_id="importCloudBootstrapConnection",
    summary="Import generated bootstrap output as a CloudConnection",
    responses={
        400: ERROR_RESPONSES[400],
        401: ERROR_RESPONSES[401],
        422: ERROR_RESPONSES[422],
    },
)
async def import_cloud_bootstrap_connection(
    request: CloudBootstrapImportRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        credential_rate_limit(
            CredentialRateClass.BOOTSTRAP,
            CredentialSecurityAction.BOOTSTRAP_IMPORT,
        )
    ),
):
    service = CloudConnectionService(db)
    try:
        connection = service.create_connection(
            current_user.id,
            request.connection,
            _audit(
                current_user,
                CredentialSecurityAction.BOOTSTRAP_IMPORT,
                request.connection.provider,
                200,
            ),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return CloudBootstrapImportResponse(connection=connection)


def _audit(
    user: User,
    action: CredentialSecurityAction,
    provider: str,
    status: int,
) -> CredentialSecurityEventDraft:
    return CredentialSecurityEventDraft(
        user_id=user.id,
        action=action,
        outcome=CredentialSecurityOutcome.SUCCEEDED,
        resource_type="cloud_bootstrap",
        provider=provider,
        purpose="bootstrap",
        http_status=status,
        request_id=current_request_id(),
    )
