from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import httpx
import json

from src.models.database import get_db
from src.models.twin import DigitalTwin, TwinState
from src.models.twin_config import TwinConfiguration
from src.models.optimizer_config import OptimizerConfiguration
from src.models.user import User
from src.api.dependencies import get_current_user
from src.schemas.twin_config import (
    TwinConfigUpdate, TwinConfigResponse, CredentialValidationResult,
    InlineValidationRequest
)
from src.config import settings
from src.utils.crypto import encrypt, decrypt
from src.services.twin_helpers import get_user_twin
from src.services.cloud_credential_validation_service import perform_dual_validation
from src.api.routes.error_models import ERROR_RESPONSES

router = APIRouter(prefix="/twins/{twin_id}/config", tags=["configuration"])
inline_router = APIRouter(prefix="/config", tags=["configuration"])


def _populate_cheapest_columns(opt_config: OptimizerConfiguration, optimizer_result: dict | None) -> None:
    """
    Derive cheapest_l* column values from an optimizer result payload and assign
    them to the SQLAlchemy model.

    Used by the wizard's bulk-save flow which only sends `optimizer_result` (not
    a separate `cheapest_path` field). Without this, downstream consumers like
    deploy/simulator/upload-zip see NULL columns even though result_json holds
    the calculation, and have to write their own fallback logic.

    Source of truth is `result.cheapestPath` (a list of "L<n>_<provider>" or
    "L3_<tier>_<provider>" strings, e.g. ["L1_GCP", "L3_hot_AWS", ...]).
    Falls back to `result.calculationResult` for L1/L2/L4/L5 if cheapestPath
    isn't a list (older response shapes).
    """
    if not optimizer_result or not isinstance(optimizer_result, dict):
        return

    def _from_path(prefix: str) -> str | None:
        path = optimizer_result.get("cheapestPath")
        if not isinstance(path, list):
            return None
        for segment in path:
            if isinstance(segment, str) and segment.startswith(prefix):
                return segment[len(prefix):].lower() or None
        return None

    def _from_calc(*keys: str) -> str | None:
        node = optimizer_result.get("calculationResult")
        for key in keys:
            if not isinstance(node, dict):
                return None
            node = node.get(key)
        return node.lower() if isinstance(node, str) and node else None

    opt_config.cheapest_l1 = _from_path("L1_") or _from_calc("L1")
    opt_config.cheapest_l2 = _from_path("L2_") or _from_calc("L2")
    opt_config.cheapest_l3_hot = _from_path("L3_hot_") or _from_calc("L3", "Hot")
    opt_config.cheapest_l3_cool = _from_path("L3_cool_") or _from_calc("L3", "Cool")
    opt_config.cheapest_l3_archive = _from_path("L3_archive_") or _from_calc("L3", "Archive")
    opt_config.cheapest_l4 = _from_path("L4_") or _from_calc("L4")
    opt_config.cheapest_l5 = _from_path("L5_") or _from_calc("L5")



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
    twin = await get_user_twin(twin_id, current_user, db)
    
    if not twin.configuration:
        config = TwinConfiguration(twin_id=twin_id)
        db.add(config)
        db.commit()
        db.refresh(config)
    else:
        config = twin.configuration
    
    return TwinConfigResponse.from_db(config, twin.optimizer_config)


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
    twin = await get_user_twin(twin_id, current_user, db)
    
    # Block modifications for deployed/deploying/destroying twins
    BLOCKED_STATES = {TwinState.DEPLOYED, TwinState.DEPLOYING, TwinState.DESTROYING}
    if twin.state in BLOCKED_STATES:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot modify twin in '{twin.state.value}' state"
        )
    
    # Track if we need to regress state
    REGRESS_STATES = {TwinState.CONFIGURED, TwinState.ERROR, TwinState.DESTROYED}
    should_regress = twin.state in REGRESS_STATES
    
    if not twin.configuration:
        config = TwinConfiguration(twin_id=twin_id)
        db.add(config)
    else:
        config = twin.configuration
    
    # Update fields
    if update.debug_mode is not None:
        config.debug_mode = update.debug_mode
    
    # AWS - ENCRYPT with user+twin-specific key
    if update.aws:
        config.aws_access_key_id = encrypt(update.aws.access_key_id, current_user.id, twin_id)
        config.aws_secret_access_key = encrypt(update.aws.secret_access_key, current_user.id, twin_id)
        config.aws_region = update.aws.region
        config.aws_sso_region = update.aws.sso_region  # SSO may be in different region
        if update.aws.session_token:
            config.aws_session_token = encrypt(update.aws.session_token, current_user.id, twin_id)
        else:
            config.aws_session_token = None
        config.aws_validated = False
    
    # Azure - ENCRYPT with user+twin-specific key
    if update.azure:
        config.azure_subscription_id = encrypt(update.azure.subscription_id, current_user.id, twin_id)
        config.azure_client_id = encrypt(update.azure.client_id, current_user.id, twin_id)
        config.azure_client_secret = encrypt(update.azure.client_secret, current_user.id, twin_id)
        config.azure_tenant_id = encrypt(update.azure.tenant_id, current_user.id, twin_id)
        config.azure_region = update.azure.region  # Not encrypted
        # Optional region overrides; None means "fall back to azure_region at deploy time"
        config.azure_region_iothub = update.azure.region_iothub or None
        config.azure_region_digital_twin = update.azure.region_digital_twin or None
        config.azure_validated = False
    
    # GCP - ENCRYPT with user+twin-specific key
    if update.gcp:
        config.gcp_project_id = update.gcp.project_id  # Not encrypted (public)
        if update.gcp.billing_account:
            config.gcp_billing_account = encrypt(update.gcp.billing_account, current_user.id, twin_id)
        else:
            config.gcp_billing_account = None
        config.gcp_region = update.gcp.region  # Not encrypted
        if update.gcp.service_account_json:
            config.gcp_service_account_json = encrypt(update.gcp.service_account_json, current_user.id, twin_id)
        config.gcp_validated = False
    
    # Wizard progress tracking
    if update.highest_step_reached is not None:
        config.highest_step_reached = update.highest_step_reached
    
    # Optimizer data - save to OptimizerConfiguration table
    if update.optimizer_params is not None or update.optimizer_result is not None:
        opt_config = twin.optimizer_config
        if not opt_config:
            opt_config = OptimizerConfiguration(twin_id=twin_id)
            db.add(opt_config)

        if update.optimizer_params is not None:
            opt_config.params = json.dumps(update.optimizer_params)
        if update.optimizer_result is not None:
            opt_config.result_json = json.dumps(update.optimizer_result)
            # Also populate the cheapest_l* columns from result.cheapestPath so
            # downstream endpoints (deploy, simulator/download, _build_providers_config,
            # etc.) get consistent data without needing per-call fallbacks. The
            # dedicated /optimizer-config/result endpoint already does this from an
            # explicit cheapest_path payload; we mirror the same derivation here for
            # the wizard's bulk-save flow which only sends optimizer_result.
            _populate_cheapest_columns(opt_config, update.optimizer_result)
    
    # Regress to draft if editing configured/error/destroyed twin
    if should_regress:
        twin.state = TwinState.DRAFT
    
    db.commit()
    db.refresh(config)
    db.refresh(twin)

    # Include twin_state in response for frontend sync
    response = TwinConfigResponse.from_db(config, twin.optimizer_config)
    return {**response.dict(), "twin_state": twin.state.value}


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
    
    # Build credentials payload - DECRYPT with user+twin-specific key
    credentials = {}
    if provider == "aws":
        if not config.aws_access_key_id:
            return CredentialValidationResult(
                provider="aws", valid=False, message="AWS credentials not configured"
            )
        credentials = {
            "aws_access_key_id": decrypt(config.aws_access_key_id, current_user.id, twin_id),
            "aws_secret_access_key": decrypt(config.aws_secret_access_key, current_user.id, twin_id),
            "aws_region": config.aws_region
        }
        if config.aws_session_token:
            credentials["aws_session_token"] = decrypt(config.aws_session_token, current_user.id, twin_id)
    elif provider == "azure":
        if not config.azure_subscription_id:
            return CredentialValidationResult(
                provider="azure", valid=False, message="Azure credentials not configured"
            )
        credentials = {
            "azure_subscription_id": decrypt(config.azure_subscription_id, current_user.id, twin_id),
            "azure_client_id": decrypt(config.azure_client_id, current_user.id, twin_id),
            "azure_client_secret": decrypt(config.azure_client_secret, current_user.id, twin_id),
            "azure_tenant_id": decrypt(config.azure_tenant_id, current_user.id, twin_id),
            "azure_region": config.azure_region,
            # Deployer requires these additional region fields
            "azure_region_iothub": config.azure_region,  # Use same region for now
            "azure_region_digital_twin": config.azure_region,  # Use same region for now
        }
    elif provider == "gcp":
        if not config.gcp_project_id and not config.gcp_billing_account:
            return CredentialValidationResult(
                provider="gcp", valid=False, message="GCP credentials not configured (need project_id or billing_account)"
            )
        credentials = {
            "gcp_project_id": config.gcp_project_id,
            "gcp_billing_account": decrypt(config.gcp_billing_account, current_user.id, twin_id) if config.gcp_billing_account else None,
            "gcp_region": config.gcp_region,
            "gcp_credentials_file": decrypt(config.gcp_service_account_json, current_user.id, twin_id) if config.gcp_service_account_json else None,
        }
    
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
    provider = request.provider
    if provider not in ["aws", "azure", "gcp"]:
        raise HTTPException(status_code=400, detail="Invalid provider. Use: aws, azure, gcp")
    
    # Build credentials payload from request (not from DB)
    credentials = {}
    if provider == "aws" and request.aws:
        credentials = {
            "aws_access_key_id": request.aws.access_key_id,
            "aws_secret_access_key": request.aws.secret_access_key,
            "aws_region": request.aws.region
        }
        if request.aws.session_token:
            credentials["aws_session_token"] = request.aws.session_token
    elif provider == "azure" and request.azure:
        credentials = {
            "azure_subscription_id": request.azure.subscription_id,
            "azure_client_id": request.azure.client_id,
            "azure_client_secret": request.azure.client_secret,
            "azure_tenant_id": request.azure.tenant_id,
            "azure_region": request.azure.region,
            # Deployer requires these additional region fields
            # TODO: Add separate UI fields for these in Step 1
            "azure_region_iothub": request.azure.region,  # Use same region for now
            "azure_region_digital_twin": request.azure.region,  # Use same region for now
        }
    elif provider == "gcp" and request.gcp:
        credentials = {
            "gcp_project_id": request.gcp.project_id,
            "gcp_billing_account": request.gcp.billing_account,
            "gcp_region": request.gcp.region,
            # Deployer expects gcp_credentials_file, but we pass the actual JSON content
            # The checker will need to handle this - either parse the content or save to temp file
            "gcp_credentials_file": request.gcp.service_account_json,
        }
    else:
        return CredentialValidationResult(
            provider=provider,
            valid=False,
            message=f"No {provider} credentials provided"
        )
    
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
    import asyncio
    
    provider = request.provider
    if provider not in ["aws", "azure", "gcp"]:
        raise HTTPException(status_code=400, detail="Invalid provider. Use: aws, azure, gcp")
    
    # Build SEPARATE credential payloads for Optimizer vs Deployer
    # They have different schema requirements
    optimizer_creds = {}
    deployer_creds = {}
    
    if provider == "aws" and request.aws:
        # AWS: Same schema for both
        base_creds = {
            "aws_access_key_id": request.aws.access_key_id,
            "aws_secret_access_key": request.aws.secret_access_key,
            "aws_region": request.aws.region
        }
        if request.aws.session_token:
            base_creds["aws_session_token"] = request.aws.session_token
        optimizer_creds = base_creds.copy()
        deployer_creds = base_creds.copy()
        
    elif provider == "azure" and request.azure:
        # Optimizer: Simple schema (just subscription + region, optional SP creds)
        optimizer_creds = {
            "azure_subscription_id": request.azure.subscription_id,
            "azure_region": request.azure.region,
            "azure_client_id": request.azure.client_id,
            "azure_client_secret": request.azure.client_secret,
            "azure_tenant_id": request.azure.tenant_id,
        }
        # Deployer: Requires extra region fields
        deployer_creds = {
            "azure_subscription_id": request.azure.subscription_id,
            "azure_client_id": request.azure.client_id,
            "azure_client_secret": request.azure.client_secret,
            "azure_tenant_id": request.azure.tenant_id,
            "azure_region": request.azure.region,
            "azure_region_iothub": request.azure.region,  # Use same region for now
            "azure_region_digital_twin": request.azure.region,  # Use same region for now
        }
        
    elif provider == "gcp" and request.gcp:
        # Optimizer: Requires gcp_project_id (not billing_account), gcp_credentials_file
        optimizer_creds = {
            "gcp_project_id": request.gcp.project_id or "placeholder-project",  # Required by Optimizer
            "gcp_credentials_file": request.gcp.service_account_json,  # File content, not path
            "gcp_region": request.gcp.region,
        }
        # Deployer: Uses billing_account, gcp_credentials_file
        deployer_creds = {
            "gcp_project_id": request.gcp.project_id,
            "gcp_billing_account": request.gcp.billing_account,
            "gcp_region": request.gcp.region,
            "gcp_credentials_file": request.gcp.service_account_json,
        }
    else:
        return {
            "provider": provider,
            "valid": False,
            "optimizer": {"valid": False, "message": f"No {provider} credentials provided"},
            "deployer": {"valid": False, "message": f"No {provider} credentials provided"}
        }
    
    
    # Use shared helper
    return await _perform_dual_validation(provider, optimizer_creds, deployer_creds)


@router.post(
    "/validate-stored/{provider}",
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
    current_user: User = Depends(get_current_user)
):
    """
    Validate STORED credentials against BOTH Optimizer and Deployer APIs.
    Used when frontend fields are empty (hidden secrets).
    """
    if provider not in ["aws", "azure", "gcp"]:
        raise HTTPException(status_code=400, detail="Invalid provider. Use: aws, azure, gcp")
    
    twin = await get_user_twin(twin_id, current_user, db)
    config = twin.configuration
    
    if not config:
        raise HTTPException(status_code=400, detail="No configuration found.")
    
    optimizer_creds = {}
    deployer_creds = {}
    
    if provider == "aws":
        if not config.aws_access_key_id:
             raise HTTPException(status_code=400, detail="AWS credentials not configured")
        
        # AWS: Same schema for both
        base_creds = {
            "aws_access_key_id": decrypt(config.aws_access_key_id, current_user.id, twin_id),
            "aws_secret_access_key": decrypt(config.aws_secret_access_key, current_user.id, twin_id),
            "aws_region": config.aws_region
        }
        if config.aws_session_token:
            base_creds["aws_session_token"] = decrypt(config.aws_session_token, current_user.id, twin_id)
            
        optimizer_creds = base_creds.copy()
        deployer_creds = base_creds.copy()
        
    elif provider == "azure":
        if not config.azure_subscription_id:
             raise HTTPException(status_code=400, detail="Azure credentials not configured")
             
        decrypted_sub = decrypt(config.azure_subscription_id, current_user.id, twin_id)
        decrypted_client = decrypt(config.azure_client_id, current_user.id, twin_id)
        decrypted_secret = decrypt(config.azure_client_secret, current_user.id, twin_id)
        decrypted_tenant = decrypt(config.azure_tenant_id, current_user.id, twin_id)
        
        # Optimizer
        optimizer_creds = {
            "azure_subscription_id": decrypted_sub,
            "azure_region": config.azure_region,
            "azure_client_id": decrypted_client,
            "azure_client_secret": decrypted_secret,
            "azure_tenant_id": decrypted_tenant,
        }
        # Deployer
        deployer_creds = {
            "azure_subscription_id": decrypted_sub,
            "azure_client_id": decrypted_client,
            "azure_client_secret": decrypted_secret,
            "azure_tenant_id": decrypted_tenant,
            "azure_region": config.azure_region,
            "azure_region_iothub": config.azure_region,
            "azure_region_digital_twin": config.azure_region,
        }
        
    elif provider == "gcp":
        if not config.gcp_project_id and not config.gcp_billing_account:
             raise HTTPException(status_code=400, detail="GCP credentials not configured")
             
        decrypted_json = decrypt(config.gcp_service_account_json, current_user.id, twin_id) if config.gcp_service_account_json else None
        decrypted_billing = decrypt(config.gcp_billing_account, current_user.id, twin_id) if config.gcp_billing_account else None
        
        # Optimizer
        optimizer_creds = {
            "gcp_project_id": config.gcp_project_id or "placeholder-project",
            "gcp_credentials_file": decrypted_json,
            "gcp_region": config.gcp_region,
        }
        # Deployer
        deployer_creds = {
            "gcp_project_id": config.gcp_project_id,
            "gcp_billing_account": decrypted_billing,
            "gcp_region": config.gcp_region,
            "gcp_credentials_file": decrypted_json,
        }

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
