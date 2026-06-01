from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import httpx

from src.models.database import get_db
from src.models.twin_config import TwinConfiguration
from src.models.user import User
from src.api.dependencies import get_current_user
from src.schemas.twin_config import (
    TwinConfigUpdate, TwinConfigResponse, CredentialValidationResult,
    InlineValidationRequest
)
from src.config import settings
from src.services.twin_helpers import get_user_twin
from src.services.cloud_credential_validation_service import perform_dual_validation
from src.services.credential_resolution_service import CredentialResolutionService
from src.services.errors import CredentialResolutionFailed
from src.services.wizard_configuration_service import WizardConfigurationService
from src.api.routes.error_models import ERROR_RESPONSES

router = APIRouter(prefix="/twins/{twin_id}/config", tags=["configuration"])
inline_router = APIRouter(prefix="/config", tags=["configuration"])


def _credential_resolution_detail(exc: CredentialResolutionFailed) -> dict:
    return {
        "code": "CREDENTIAL_RESOLUTION_FAILED",
        "message": exc.message,
        "errors": exc.errors,
    }



@router.get(
    "/",
    response_model=TwinConfigResponse,
    operation_id="getTwinConfig",
    summary="Get configuration for a twin",
    description=(
        "**Purpose:** Retrieve CloudConnection bindings and validation status for Step 1 (Credentials) screen.\n\n"
        "**When to call:** When loading Step 1 to show selected CloudConnections and validation indicators.\n\n"
        "**Response fields:**\n"
        "- `{provider}_cloud_connection_id`: selected provider CloudConnection id\n"
        "- `cloud_connections`: secret-safe summaries of bound CloudConnections\n"
        "- `{provider}_configured`: whether a usable CloudConnection is bound\n"
        "- `debug_mode`: Whether debug logging is enabled\n"
        "- `highest_step_reached`: Wizard progress indicator (1-5)\n\n"
        "**Note:** Creates empty config if none exists. Secrets are never returned."
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
    twin = await get_user_twin(twin_id, current_user, db)
    
    if not twin.configuration:
        config = TwinConfiguration(twin_id=twin_id)
        db.add(config)
        db.commit()
        db.refresh(config)
    else:
        config = twin.configuration
    
    return TwinConfigResponse.from_db(config, twin.optimizer_config, twin_state=twin.state.value)


@router.put(
    "/",
    response_model=TwinConfigResponse,
    operation_id="updateTwinConfig",
    summary="Update configuration for a twin",
    description=(
        "**Purpose:** Save CloudConnection bindings and non-secret configuration for a Digital Twin.\n\n"
        "**When to call:** When user selects/unbinds CloudConnections or saves wizard progress.\n\n"
        "**Request body fields:**\n"
        "- `cloud_connections`: {aws, azure, gcp} CloudConnection ids or nulls\n"
        "- `aws`/`azure`/`gcp`: null clears that provider; direct credential storage is disabled\n"
        "- `debug_mode`: Enable verbose logging for deployment\n"
        "- `highest_step_reached`: Track wizard progress\n\n"
        "**Security:** Provider secrets are stored only in user-scoped CloudConnections.\n\n"
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
    twin = await get_user_twin(twin_id, current_user, db)
    config = WizardConfigurationService(db).apply_twin_config_update(
        twin,
        update,
        current_user.id,
    )
    
    db.commit()
    db.refresh(config)
    db.refresh(twin)

    # Include twin_state in response for frontend sync
    return TwinConfigResponse.from_db(config, twin.optimizer_config, twin_state=twin.state.value)


@router.post(
    "/validate/{provider}",
    response_model=CredentialValidationResult,
    operation_id="validateStoredCredentials",
    summary="Validate bound CloudConnection via Deployer API",
    description=(
        "**Purpose:** Validate credentials from a bound CloudConnection via Deployer API.\n\n"
        "**When to call:** When user clicks Validate button for a selected CloudConnection.\n\n"
        "**Path parameter:** provider = 'aws', 'azure', or 'gcp'\n\n"
        "**Flow:**\n"
        "1. Decrypts the bound CloudConnection payload\n"
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
    current_user: User = Depends(get_current_user)
):
    """
    Validate credentials by calling the Deployer API.
    DECRYPTS credentials with user+twin-specific key, sends to Deployer, never exposes to client.
    """
    if provider not in ["aws", "azure", "gcp"]:
        raise HTTPException(status_code=400, detail="Invalid provider. Use: aws, azure, gcp")
    
    twin = await get_user_twin(twin_id, current_user, db)
    config = twin.configuration
    
    if not config:
        raise HTTPException(status_code=400, detail="No configuration found. Save credentials first.")
    
    try:
        credentials = CredentialResolutionService().resolve_provider_credentials(
            twin,
            current_user.id,
            provider,
        ).deployer_validation_payload
    except CredentialResolutionFailed as exc:
        raise HTTPException(status_code=400, detail=_credential_resolution_detail(exc)) from exc
    
    # Call Deployer API
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{settings.DEPLOYER_URL}/permissions/verify/{provider}",
                json=credentials,
                timeout=30.0
            )
            
            if response.status_code == 200:
                result = response.json()
                valid = result.get("valid", False)
                
                # Update validation status in DB
                if provider == "aws":
                    config.aws_validated = valid
                elif provider == "azure":
                    config.azure_validated = valid
                elif provider == "gcp":
                    config.gcp_validated = valid
                
                db.commit()
                
                return CredentialValidationResult(
                    provider=provider,
                    valid=valid,
                    message=result.get("message", "Validation complete"),
                    permissions=result.get("missing_permissions")
                )
            else:
                return CredentialValidationResult(
                    provider=provider,
                    valid=False,
                    message=f"Deployer API error: {response.status_code}"
                )
    except httpx.ConnectError:
        return CredentialValidationResult(
            provider=provider,
            valid=False,
            message="Cannot connect to Deployer API. Is it running on port 5004?"
        )
    except httpx.RequestError as e:
        return CredentialValidationResult(
            provider=provider,
            valid=False,
            message=f"Request error: {str(e)}"
        )


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
    current_user: User = Depends(get_current_user)
):
    """
    Validate credentials WITHOUT storing them.
    Useful for checking credentials before saving a twin.
    Credentials are sent directly to Deployer API, never stored.
    """
    try:
        resolved = CredentialResolutionService().resolve_plaintext_credentials(
            request.provider,
            getattr(request, request.provider, None),
        )
    except CredentialResolutionFailed as exc:
        raise HTTPException(status_code=400, detail=_credential_resolution_detail(exc)) from exc

    provider = resolved.provider
    credentials = resolved.deployer_validation_payload
    
    # Call Deployer API
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{settings.DEPLOYER_URL}/permissions/verify/{provider}",
                json=credentials,
                timeout=30.0
            )
            
            if response.status_code == 200:
                result = response.json()
                return CredentialValidationResult(
                    provider=provider,
                    valid=result.get("valid", False),
                    message=result.get("message", "Validation complete"),
                    permissions=result.get("missing_permissions")
                )
            else:
                return CredentialValidationResult(
                    provider=provider,
                    valid=False,
                    message=f"Deployer API error: {response.status_code}"
                )
    except httpx.ConnectError:
        return CredentialValidationResult(
            provider=provider,
            valid=False,
            message="Cannot connect to Deployer API"
        )
    except httpx.RequestError as e:
        return CredentialValidationResult(
            provider=provider,
            valid=False,
            message=f"Request error: {str(e)}"
        )


@inline_router.post(
    "/validate-dual",
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
    current_user: User = Depends(get_current_user)
):
    """
    Validate credentials against BOTH Optimizer and Deployer APIs.
    - Optimizer: Checks pricing API permissions (simpler schema)
    - Deployer: Checks infrastructure deployment permissions (requires extra fields)
    Returns separate results for each.
    """
    try:
        resolved = CredentialResolutionService().resolve_plaintext_credentials(
            request.provider,
            getattr(request, request.provider, None),
        )
    except CredentialResolutionFailed as exc:
        raise HTTPException(status_code=400, detail=_credential_resolution_detail(exc)) from exc

    provider = resolved.provider
    optimizer_creds = resolved.optimizer_payload
    deployer_creds = resolved.deployer_validation_payload

    # Use shared helper
    return await _perform_dual_validation(provider, optimizer_creds, deployer_creds)


@router.post(
    "/validate-stored/{provider}",
    operation_id="validateStoredCredentialsDual",
    summary="Validate bound CloudConnection against both APIs",
    description=(
        "**Purpose:** Same as `validateCredentialsDual` but uses the bound CloudConnection.\n\n"
        "**When to call:** When user clicks Validate for a selected CloudConnection.\n\n"
        "**Path parameter:** provider = 'aws', 'azure', or 'gcp'\n\n"
        "**Flow:**\n"
        "1. Decrypts the bound CloudConnection payload\n"
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
    current_user: User = Depends(get_current_user)
):
    """
    Validate bound CloudConnection credentials against BOTH Optimizer and Deployer APIs.
    """
    if provider not in ["aws", "azure", "gcp"]:
        raise HTTPException(status_code=400, detail="Invalid provider. Use: aws, azure, gcp")
    
    twin = await get_user_twin(twin_id, current_user, db)
    config = twin.configuration
    
    if not config:
        raise HTTPException(status_code=400, detail="No configuration found.")
    
    try:
        resolved = CredentialResolutionService().resolve_provider_credentials(
            twin,
            current_user.id,
            provider,
        )
    except CredentialResolutionFailed as exc:
        raise HTTPException(status_code=400, detail=_credential_resolution_detail(exc)) from exc

    optimizer_creds = resolved.optimizer_payload
    deployer_creds = resolved.deployer_validation_payload

    # Use shared helper
    result = await _perform_dual_validation(provider, optimizer_creds, deployer_creds)
    
    # Update validation status in DB
    valid = result.get("valid", False)
    if provider == "aws":
        config.aws_validated = valid
    elif provider == "azure":
        config.azure_validated = valid
    elif provider == "gcp":
        config.gcp_validated = valid
    db.commit()
    
    return result


async def _perform_dual_validation(provider: str, optimizer_creds: dict, deployer_creds: dict) -> dict:
    """Helper to call both APIs in parallel."""
    return await perform_dual_validation(provider, optimizer_creds, deployer_creds)
