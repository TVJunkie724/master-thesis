from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.models.database import get_db
from src.models.user import User
from src.api.dependencies import get_current_user
from src.schemas.twin_config import (
    TwinConfigUpdate, TwinConfigResponse, CredentialValidationResult,
    InlineValidationRequest
)
from src.schemas.management_contracts import DualCredentialValidationResponse
from src.schemas.credential_security_event import (
    CredentialSecurityAction,
    CredentialSecurityEventDraft,
    CredentialSecurityOutcome,
)
from src.repositories.twin_repository import TwinRepository
from src.services.cloud_credential_validation_service import perform_dual_validation
from src.services.credential_resolution_service import CredentialResolutionService
from src.services.credential_validation_service import CredentialValidationService
from src.services.errors import CredentialResolutionFailed
from src.services.provider_contract import normalize_provider_id
from src.services.service_errors import EntityNotFoundError, ValidationError
from src.services.twin_configuration_service import TwinConfigurationService
from src.api.routes.error_models import ERROR_RESPONSES
from src.security.rate_limit import CredentialRateClass, credential_rate_limit
from src.security.request_context import current_request_id
from src.services.credential_security_audit_service import CredentialSecurityAuditService

router = APIRouter(prefix="/twins/{twin_id}/config", tags=["configuration"])
inline_router = APIRouter(prefix="/config", tags=["configuration"])


def _twin_configuration_service(db: Session) -> TwinConfigurationService:
    """Build the twin configuration service for this request."""
    return TwinConfigurationService(db=db, twin_repository=TwinRepository(db))


def _credential_validation_service(db: Session) -> CredentialValidationService:
    """Build the credential validation service for this request."""
    return CredentialValidationService(db=db, twin_repository=TwinRepository(db))


def _raise_service_http_error(exc: Exception) -> None:
    """Map typed service errors to the existing configuration HTTP contract."""
    if isinstance(exc, EntityNotFoundError):
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if isinstance(exc, ValidationError):
        raise HTTPException(status_code=400, detail=getattr(exc, "detail", None) or str(exc)) from exc
    raise exc


def _credential_resolution_failed_detail(exc: CredentialResolutionFailed) -> dict:
    return {
        "code": "CREDENTIAL_RESOLUTION_FAILED",
        "message": exc.message,
        "errors": exc.errors,
    }


async def _perform_dual_validation(
    provider: str,
    optimizer_creds: dict,
    deployer_creds: dict,
) -> dict:
    return await perform_dual_validation(provider, optimizer_creds, deployer_creds)


def _set_provider_validated(config, provider: str, valid: bool) -> None:
    if provider == "aws":
        config.aws_validated = valid
    elif provider == "azure":
        config.azure_validated = valid
    elif provider == "gcp":
        config.gcp_validated = valid


def _normalize_route_provider(provider: str) -> str:
    try:
        return normalize_provider_id(provider)
    except ValueError as exc:
        raise ValidationError("Invalid provider. Use: aws, azure, gcp") from exc


@router.get(
    "/",
    response_model=TwinConfigResponse,
    operation_id="getTwinConfig",
    summary="Get configuration for a twin",
    description=(
        "**Purpose:** Retrieve cloud provider credentials and validation status for Step 1 (Credentials) screen.\n\n"
        "**When to call:** When loading Step 1 to show saved credentials (masked) and validation indicators.\n\n"
        "**Response fields:**\n"
        "- `aws`: Object with masked credentials, region, and `validated` boolean\n"
        "- `azure`: Object with masked credentials, region, and `validated` boolean\n"
        "- `gcp`: Object with masked credentials, region, and `validated` boolean\n"
        "- `debug_mode`: Whether debug logging is enabled\n"
        "- `highest_step_reached`: Wizard progress indicator (1-5)\n\n"
        "**Note:** Creates empty config if none exists. Credentials are masked in response."
    ),
    responses={
        401: ERROR_RESPONSES[401],
        404: ERROR_RESPONSES[404],
    }
)
async def get_config(
    twin_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get configuration for a twin. Creates default if none exists."""
    try:
        return _twin_configuration_service(db).get_config(twin_id=twin_id, user_id=current_user.id)
    except EntityNotFoundError as exc:
        _raise_service_http_error(exc)


@router.put(
    "/",
    response_model=TwinConfigResponse,
    operation_id="updateTwinConfig",
    summary="Update configuration for a twin",
    description=(
        "**Purpose:** Save cloud provider credentials and configuration for a Digital Twin.\n\n"
        "**When to call:** When user saves credentials in Step 1, or when auto-saving on field blur.\n\n"
        "**Request body fields:**\n"
        "- `aws`: {access_key_id, secret_access_key, region, session_token(optional)}\n"
        "- `azure`: {subscription_id, client_id, client_secret, tenant_id, region}\n"
        "- `gcp`: {project_id, billing_account, service_account_json, region}\n"
        "- `debug_mode`: Enable verbose logging for deployment\n"
        "- `highest_step_reached`: Track wizard progress\n\n"
        "**Security:** Credentials are encrypted with user+twin-specific key before storage.\n\n"
        "**Blocked states:** Returns 400 if twin is DEPLOYED, DEPLOYING, or DESTROYING.\n\n"
        "**Side effect:** If twin was in CONFIGURED/ERROR/DESTROYED state, regresses to DRAFT."
    ),
    responses={
        400: ERROR_RESPONSES[400],
        401: ERROR_RESPONSES[401],
        404: ERROR_RESPONSES[404],
    }
)
async def update_config(
    twin_id: str,
    update: TwinConfigUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update configuration for a twin.
    Credentials are ENCRYPTED with user+twin-specific key.
    """
    try:
        return _twin_configuration_service(db).update_config(
            twin_id=twin_id,
            user_id=current_user.id,
            update=update,
        )
    except (EntityNotFoundError, ValidationError) as exc:
        _raise_service_http_error(exc)


@router.post(
    "/validate/{provider}",
    response_model=CredentialValidationResult,
    operation_id="validateStoredCredentials",
    summary="Validate stored credentials via Deployer API",
    description=(
        "**Purpose:** Validate credentials that were previously saved to the twin configuration.\n\n"
        "**When to call:** When user clicks Validate button and credentials are already saved (masked in UI).\n\n"
        "**Path parameter:** provider = 'aws', 'azure', or 'gcp'\n\n"
        "**Flow:**\n"
        "1. Decrypts stored credentials using user+twin-specific key\n"
        "2. Forwards to Deployer's `/permissions/verify/{provider}` endpoint\n"
        "3. Updates `{provider}_validated` flag in database\n"
        "4. Returns validation result (credentials never exposed to client)\n\n"
        "**Response fields:**\n"
        "- `valid`: Boolean - whether credentials can access required cloud resources\n"
        "- `message`: Human-readable validation result\n"
        "- `permissions`: List of missing permissions (if any)"
    ),
    responses={
        400: ERROR_RESPONSES[400],
        401: ERROR_RESPONSES[401],
        404: ERROR_RESPONSES[404],
    }
)
async def validate_credentials(
    twin_id: str,
    provider: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        credential_rate_limit(
            CredentialRateClass.VALIDATION,
            CredentialSecurityAction.STORED_VALIDATE,
        )
    )
):
    """
    Validate credentials by calling the Deployer API.
    DECRYPTS credentials with user+twin-specific key, sends to Deployer, never exposes to client.
    """
    try:
        result = await _credential_validation_service(db).validate_stored_with_deployer(
            twin_id=twin_id,
            user_id=current_user.id,
            provider=provider,
        )
        _commit_validation_audit(
            db,
            current_user,
            CredentialSecurityAction.STORED_VALIDATE,
            provider,
            valid=result.valid,
        )
        return result
    except (EntityNotFoundError, ValidationError) as exc:
        _raise_service_http_error(exc)


@inline_router.post(
    "/validate-inline",
    response_model=CredentialValidationResult,
    operation_id="validateInlineCredentials",
    summary="Validate credentials without storing",
    description=(
        "**Purpose:** Validate credentials provided in request body without saving them to database.\n\n"
        "**When to call:** When user wants to test credentials before saving a new twin, or preview validation.\n\n"
        "**Request body:**\n"
        "- `provider`: 'aws', 'azure', or 'gcp'\n"
        "- `aws`/`azure`/`gcp`: Credential object matching the provider\n\n"
        "**Flow:**\n"
        "1. Takes plaintext credentials from request body\n"
        "2. Forwards to Deployer's `/permissions/verify/{provider}` endpoint\n"
        "3. Returns result without storing anything\n\n"
        "**Use case:** Validate credentials → get result → if valid, decide to save via `updateTwinConfig`."
    ),
    responses={
        400: ERROR_RESPONSES[400],
        401: ERROR_RESPONSES[401],
    }
)
async def validate_credentials_inline(
    request: InlineValidationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        credential_rate_limit(
            CredentialRateClass.VALIDATION,
            CredentialSecurityAction.INLINE_VALIDATE,
        )
    )
):
    """
    Validate credentials WITHOUT storing them.
    Useful for checking credentials before saving a twin.
    Credentials are sent directly to Deployer API, never stored.
    """
    try:
        result = await _credential_validation_service(db).validate_inline_with_deployer(request)
        _commit_validation_audit(
            db,
            current_user,
            CredentialSecurityAction.INLINE_VALIDATE,
            request.provider,
            valid=result.valid,
        )
        return result
    except ValidationError as exc:
        _raise_service_http_error(exc)


@inline_router.post(
    "/validate-dual",
    response_model=DualCredentialValidationResponse,
    operation_id="validateCredentialsDual",
    summary="Validate against both Optimizer and Deployer APIs",
    description=(
        "**Purpose:** Validate credentials against BOTH Optimizer and Deployer APIs in parallel.\n\n"
        "**Why two APIs?** Each service has different permission requirements:\n"
        "- **Optimizer:** Checks pricing API access (e.g., AWS Pricing API, GCP Cloud Billing API)\n"
        "- **Deployer:** Checks infrastructure permissions (e.g., create Lambda, Terraform apply)\n\n"
        "**When to call:** On Step 1 Validate button click to show dual validation status.\n\n"
        "**Response fields:**\n"
        "- `valid`: Boolean - true only if BOTH APIs pass\n"
        "- `optimizer`: {valid, message} - Optimizer-specific result\n"
        "- `deployer`: {valid, message, permissions} - Deployer-specific result with missing permissions"
    ),
    responses={
        400: ERROR_RESPONSES[400],
        401: ERROR_RESPONSES[401],
    }
)
async def validate_credentials_dual(
    request: InlineValidationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        credential_rate_limit(
            CredentialRateClass.VALIDATION,
            CredentialSecurityAction.INLINE_VALIDATE,
        )
    )
):
    """
    Validate credentials against BOTH Optimizer and Deployer APIs.
    - Optimizer: Checks pricing API permissions (simpler schema)
    - Deployer: Checks infrastructure deployment permissions (requires extra fields)
    Returns separate results for each.
    """
    try:
        provider = _normalize_route_provider(request.provider)
        resolved = CredentialResolutionService().resolve_plaintext_credentials(
            provider,
            getattr(request, provider, None),
        )
        result = await _perform_dual_validation(
            provider,
            resolved.optimizer_payload,
            resolved.deployer_validation_payload,
        )
        _commit_validation_audit(
            db,
            current_user,
            CredentialSecurityAction.INLINE_VALIDATE,
            provider,
            valid=result.get("valid", False),
        )
        return result
    except CredentialResolutionFailed as exc:
        raise HTTPException(status_code=400, detail=_credential_resolution_failed_detail(exc)) from exc
    except ValidationError as exc:
        _raise_service_http_error(exc)


@router.post(
    "/validate-stored/{provider}",
    response_model=DualCredentialValidationResponse,
    operation_id="validateStoredCredentialsDual",
    summary="Validate stored credentials against both APIs",
    description=(
        "**Purpose:** Same as `validateCredentialsDual` but uses credentials already stored in database.\n\n"
        "**When to call:** When user clicks Validate and credentials are masked (already saved previously).\n\n"
        "**Path parameter:** provider = 'aws', 'azure', or 'gcp'\n\n"
        "**Flow:**\n"
        "1. Decrypts stored credentials using user+twin-specific key\n"
        "2. Validates against Optimizer API (pricing permissions)\n"
        "3. Validates against Deployer API (infrastructure permissions)\n"
        "4. Updates `{provider}_validated` flag based on combined result\n\n"
        "**Response:**\n"
        "- `valid`: true only if BOTH APIs pass\n"
        "- `optimizer`: {valid, message}\n"
        "- `deployer`: {valid, message, permissions}"
    ),
    responses={
        400: ERROR_RESPONSES[400],
        401: ERROR_RESPONSES[401],
        404: ERROR_RESPONSES[404],
    }
)
async def validate_stored_credentials_dual(
    twin_id: str,
    provider: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        credential_rate_limit(
            CredentialRateClass.VALIDATION,
            CredentialSecurityAction.STORED_VALIDATE,
        )
    )
):
    """
    Validate STORED credentials against BOTH Optimizer and Deployer APIs.
    Used when frontend fields are empty (hidden secrets).
    """
    try:
        provider = _normalize_route_provider(provider)
        twin = TwinRepository(db).get_for_user(twin_id, current_user.id)
        if not twin:
            raise EntityNotFoundError("Twin not found")
        resolved = CredentialResolutionService().resolve_provider_credentials(
            twin,
            current_user.id,
            provider,
        )
        result = await _perform_dual_validation(
            provider,
            resolved.optimizer_payload,
            resolved.deployer_validation_payload,
        )
        _set_provider_validated(twin.configuration, provider, result.get("valid", False))
        db.commit()
        _commit_validation_audit(
            db,
            current_user,
            CredentialSecurityAction.STORED_VALIDATE,
            provider,
            valid=result.get("valid", False),
        )
        return result
    except CredentialResolutionFailed as exc:
        raise HTTPException(status_code=400, detail=_credential_resolution_failed_detail(exc)) from exc
    except (EntityNotFoundError, ValidationError) as exc:
        _raise_service_http_error(exc)


def _commit_validation_audit(
    db: Session,
    user: User,
    action: CredentialSecurityAction,
    provider: str,
    *,
    valid: bool,
) -> None:
    CredentialSecurityAuditService.commit_standalone(
        db,
        CredentialSecurityEventDraft(
            user_id=user.id,
            action=action,
            outcome=(
                CredentialSecurityOutcome.SUCCEEDED
                if valid
                else CredentialSecurityOutcome.REJECTED
            ),
            resource_type="credential_validation",
            provider=provider.lower(),
            http_status=200,
            request_id=current_request_id(),
        ),
    )
