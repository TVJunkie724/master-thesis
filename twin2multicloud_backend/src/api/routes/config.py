from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import httpx

from src.models.database import get_db
from src.models.twin import DigitalTwin
from src.models.twin_config import TwinConfiguration
from src.models.user import User
from src.api.dependencies import get_current_user
from src.schemas.twin_config import (
    TwinConfigUpdate, TwinConfigResponse, CredentialValidationResult,
    InlineValidationRequest
)
from src.config import settings
from src.utils.crypto import encrypt, decrypt

router = APIRouter(prefix="/twins/{twin_id}/config", tags=["configuration"])
inline_router = APIRouter(prefix="/config", tags=["configuration"])


async def get_user_twin(twin_id: str, user: User, db: Session) -> DigitalTwin:
    """Helper to verify twin ownership."""
    twin = db.query(DigitalTwin).filter(
        DigitalTwin.id == twin_id,
        DigitalTwin.user_id == user.id
    ).first()
    if not twin:
        raise HTTPException(status_code=404, detail="Twin not found")
    return twin


@router.get("/", response_model=TwinConfigResponse)
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
    
    return TwinConfigResponse.from_db(config)


@router.put("/", response_model=TwinConfigResponse)
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
    
    db.commit()
    db.refresh(config)
    return TwinConfigResponse.from_db(config)


@router.post("/validate/{provider}", response_model=CredentialValidationResult)
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


@inline_router.post("/validate-inline", response_model=CredentialValidationResult)
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


@inline_router.post("/validate-dual")
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


@router.post("/validate-stored/{provider}")
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
    import asyncio
    
    async def call_optimizer():
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{settings.OPTIMIZER_URL}/permissions/verify/{provider}",
                    json=optimizer_creds,
                    timeout=30.0
                )
                if response.status_code == 200:
                    result = response.json()
                    # Translate status: "valid" → valid: true (schema compatibility)
                    is_valid = result.get("valid", False) or result.get("status") == "valid"
                    return {
                        "valid": is_valid,
                        "message": result.get("message", "Validation complete")
                    }
                else:
                    return {
                        "valid": False,
                        "message": f"Optimizer API error: {response.status_code}"
                    }
        except httpx.ConnectError:
            return {
                "valid": False,
                "message": "Cannot connect to Optimizer API (port 5003)"
            }
        except Exception as e:
            return {
                "valid": False,
                "message": f"Optimizer error: {str(e)}"
            }
    
    async def call_deployer():
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{settings.DEPLOYER_URL}/permissions/verify/{provider}",
                    json=deployer_creds,
                    timeout=30.0
                )
                if response.status_code == 200:
                    result = response.json()
                    # Translate status: "valid" → valid: true (schema compatibility)
                    is_valid = result.get("valid", False) or result.get("status") == "valid"
                    return {
                        "valid": is_valid,
                        "message": result.get("message", "Validation complete"),
                        "permissions": result.get("missing_permissions")
                    }
                else:
                    return {
                        "valid": False,
                        "message": f"Deployer API error: {response.status_code}"
                    }
        except httpx.ConnectError:
            return {
                "valid": False,
                "message": "Cannot connect to Deployer API (port 5004)"
            }
        except Exception as e:
            return {
                "valid": False,
                "message": f"Deployer error: {str(e)}"
            }
    
    optimizer_result, deployer_result = await asyncio.gather(
        call_optimizer(),
        call_deployer()
    )
    
    return {
        "provider": provider,
        "valid": optimizer_result.get("valid", False) and deployer_result.get("valid", False),
        "optimizer": optimizer_result,
        "deployer": deployer_result
    }
