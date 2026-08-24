from fastapi import APIRouter, Depends, Header, HTTPException, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from src.api.routes.error_models import ERROR_RESPONSES
from src.models.database import get_db
from src.models.user import User
from src.schemas.cloud_bootstrap import (
    CloudBootstrapImportRequest,
    CloudBootstrapImportResponse,
    CloudBootstrapExecuteRequest,
    CloudBootstrapGuideRequest,
    CloudBootstrapGuideResponse,
    CloudBootstrapPlanRequest,
    CloudBootstrapPlanResponse,
    CloudBootstrapRevisionRequest,
    CloudBootstrapSessionCreateRequest,
    CloudBootstrapSessionListResponse,
    CloudBootstrapSessionResponse,
    CloudBootstrapSetupCleanupRequest,
    CloudBootstrapSetupCleanupResponse,
    CloudBootstrapSetupReceiptResponse,
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
from src.services.credential_security_audit_service import (
    CredentialSecurityAuditService,
)
from src.services.guided_cloud_bootstrap_service import GuidedCloudBootstrapService

router = APIRouter(prefix="/cloud-bootstrap", tags=["cloud-bootstrap"])


@router.post(
    "/{provider}/guide",
    response_model=CloudBootstrapGuideResponse,
    response_model_exclude_none=True,
    operation_id="getCloudBootstrapGuide",
    summary="Build safe provider-specific guided bootstrap instructions",
    responses={
        400: ERROR_RESPONSES[400],
        401: ERROR_RESPONSES[401],
        422: ERROR_RESPONSES[422],
    },
)
async def get_cloud_bootstrap_guide(
    provider: str,
    request: CloudBootstrapGuideRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        credential_rate_limit(
            CredentialRateClass.BOOTSTRAP,
            CredentialSecurityAction.BOOTSTRAP_GUIDE,
        )
    ),
):
    result = GuidedCloudBootstrapService(db).guide(provider, request.target)
    CredentialSecurityAuditService.commit_standalone(
        db,
        _audit(
            current_user, CredentialSecurityAction.BOOTSTRAP_GUIDE, result.provider, 200
        ),
    )
    payload = result.model_dump(mode="json", exclude_none=True)
    # The strict cross-client guide contract keeps this provider-conditional
    # field explicit: null for AWS/Azure and an object for GCP. Returning a
    # Response bypasses FastAPI's route-wide exclude_none pass, which would
    # otherwise silently remove the required null marker.
    payload["api_baseline"] = (
        result.api_baseline.model_dump(mode="json")
        if result.api_baseline is not None
        else None
    )
    return JSONResponse(content=payload)


@router.post(
    "/sessions",
    response_model=CloudBootstrapSessionResponse,
    response_model_exclude_none=True,
    operation_id="createCloudBootstrapSession",
    summary="Create or resume one owner-scoped guided bootstrap session",
    responses={
        401: ERROR_RESPONSES[401],
        409: ERROR_RESPONSES[409],
        422: ERROR_RESPONSES[422],
    },
)
async def create_cloud_bootstrap_session(
    request: CloudBootstrapSessionCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        credential_rate_limit(
            CredentialRateClass.BOOTSTRAP,
            CredentialSecurityAction.BOOTSTRAP_SESSION_CREATE,
        )
    ),
):
    return GuidedCloudBootstrapService(db).create_session(
        current_user.id,
        request,
        _audit(
            current_user,
            CredentialSecurityAction.BOOTSTRAP_SESSION_CREATE,
            request.provider,
            200,
        ),
    )


@router.get(
    "/sessions",
    response_model=CloudBootstrapSessionListResponse,
    response_model_exclude_none=True,
    operation_id="listCloudBootstrapSessions",
    summary="List safe owner-scoped bootstrap sessions",
)
async def list_cloud_bootstrap_sessions(
    provider: str | None = Query(default=None),
    active: bool | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(
        credential_rate_limit(
            CredentialRateClass.BOOTSTRAP,
            CredentialSecurityAction.BOOTSTRAP_GUIDE,
        )
    ),
):
    return GuidedCloudBootstrapService(db).list_sessions(
        current_user.id,
        provider=provider,
        active=active,
    )


@router.get(
    "/sessions/{session_id}",
    response_model=CloudBootstrapSessionResponse,
    response_model_exclude_none=True,
    operation_id="getCloudBootstrapSession",
    summary="Read one safe owner-scoped bootstrap session",
)
async def get_cloud_bootstrap_session(
    session_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        credential_rate_limit(
            CredentialRateClass.BOOTSTRAP,
            CredentialSecurityAction.BOOTSTRAP_GUIDE,
        )
    ),
):
    return GuidedCloudBootstrapService(db).get_session(current_user.id, session_id)


@router.post(
    "/sessions/{session_id}/execute",
    response_model=CloudBootstrapSessionResponse,
    response_model_exclude_none=True,
    operation_id="executeCloudBootstrapSession",
    summary="Execute one synchronous request-scoped bootstrap command",
    responses={
        401: ERROR_RESPONSES[401],
        409: ERROR_RESPONSES[409],
        422: ERROR_RESPONSES[422],
    },
)
async def execute_cloud_bootstrap_session(
    session_id: str,
    request: CloudBootstrapExecuteRequest,
    setup_confirmation: str | None = Header(
        default=None,
        alias="X-Twin2MC-Setup-Confirmation",
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(
        credential_rate_limit(
            CredentialRateClass.BOOTSTRAP,
            CredentialSecurityAction.BOOTSTRAP_EXECUTE,
        )
    ),
):
    return GuidedCloudBootstrapService(db).execute(
        current_user.id,
        session_id,
        request,
        _audit(
            current_user,
            CredentialSecurityAction.BOOTSTRAP_EXECUTE,
            request.credential.provider,
            200,
        ),
        setup_confirmation=setup_confirmation,
    )


@router.get(
    "/sessions/{session_id}/setup-gate-receipt",
    response_model=CloudBootstrapSetupReceiptResponse,
    operation_id="getCloudBootstrapSetupReceipt",
    summary="Read the secret-free receipt for a setup-only validation session",
    responses={
        401: ERROR_RESPONSES[401],
        409: ERROR_RESPONSES[409],
    },
)
async def get_cloud_bootstrap_setup_receipt(
    session_id: str,
    setup_confirmation: str | None = Header(
        default=None,
        alias="X-Twin2MC-Setup-Confirmation",
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(
        credential_rate_limit(
            CredentialRateClass.BOOTSTRAP,
            CredentialSecurityAction.BOOTSTRAP_GUIDE,
        )
    ),
):
    return GuidedCloudBootstrapService(db).get_setup_receipt(
        current_user.id,
        session_id,
        setup_confirmation,
    )


@router.post(
    "/sessions/{session_id}/setup-gate-cleanup",
    response_model=CloudBootstrapSetupCleanupResponse,
    operation_id="cleanupCloudBootstrapSetupSession",
    summary="Clean provider and local access created by setup-only validation",
    responses={
        401: ERROR_RESPONSES[401],
        409: ERROR_RESPONSES[409],
        422: ERROR_RESPONSES[422],
    },
)
async def cleanup_cloud_bootstrap_setup_session(
    session_id: str,
    request: CloudBootstrapSetupCleanupRequest,
    setup_confirmation: str | None = Header(
        default=None,
        alias="X-Twin2MC-Setup-Confirmation",
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(
        credential_rate_limit(
            CredentialRateClass.BOOTSTRAP,
            CredentialSecurityAction.BOOTSTRAP_SETUP_CLEANUP,
        )
    ),
):
    session = GuidedCloudBootstrapService(db).get_session(
        current_user.id, session_id
    )
    return GuidedCloudBootstrapService(db).cleanup_setup_session(
        current_user.id,
        session_id,
        request,
        setup_confirmation,
        _audit(
            current_user,
            CredentialSecurityAction.BOOTSTRAP_SETUP_CLEANUP,
            session.provider,
            200,
        ),
    )


@router.post(
    "/sessions/{session_id}/acknowledge-manual-revocation",
    response_model=CloudBootstrapSessionResponse,
    response_model_exclude_none=True,
    operation_id="acknowledgeCloudBootstrapManualRevocation",
    summary="Record explicit user acknowledgement of provider-side cleanup",
    responses={
        401: ERROR_RESPONSES[401],
        409: ERROR_RESPONSES[409],
        422: ERROR_RESPONSES[422],
    },
)
async def acknowledge_cloud_bootstrap_manual_revocation(
    session_id: str,
    request: CloudBootstrapRevisionRequest,
    setup_confirmation: str | None = Header(
        default=None,
        alias="X-Twin2MC-Setup-Confirmation",
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(
        credential_rate_limit(
            CredentialRateClass.BOOTSTRAP,
            CredentialSecurityAction.BOOTSTRAP_ACKNOWLEDGE_REVOCATION,
        )
    ),
):
    return GuidedCloudBootstrapService(db).acknowledge_manual_revocation(
        current_user.id,
        session_id,
        request.expected_revision,
        _audit(
            current_user,
            CredentialSecurityAction.BOOTSTRAP_ACKNOWLEDGE_REVOCATION,
            None,
            200,
        ),
        setup_confirmation,
    )


@router.post(
    "/sessions/{session_id}/cancel",
    response_model=CloudBootstrapSessionResponse,
    response_model_exclude_none=True,
    operation_id="cancelCloudBootstrapSession",
    summary="Cancel a bootstrap session that has no generated connection",
    responses={
        401: ERROR_RESPONSES[401],
        409: ERROR_RESPONSES[409],
        422: ERROR_RESPONSES[422],
    },
)
async def cancel_cloud_bootstrap_session(
    session_id: str,
    request: CloudBootstrapRevisionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        credential_rate_limit(
            CredentialRateClass.BOOTSTRAP,
            CredentialSecurityAction.BOOTSTRAP_CANCEL,
        )
    ),
):
    session = GuidedCloudBootstrapService(db).get_session(current_user.id, session_id)
    return GuidedCloudBootstrapService(db).cancel(
        current_user.id,
        session_id,
        request.expected_revision,
        _audit(
            current_user,
            CredentialSecurityAction.BOOTSTRAP_CANCEL,
            session.provider,
            200,
        ),
    )


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
            _audit(
                current_user,
                CredentialSecurityAction.BOOTSTRAP_PLAN,
                result.provider,
                200,
            ),
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
    provider: str | None,
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
