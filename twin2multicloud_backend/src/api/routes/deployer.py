from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import httpx

from src.models.database import get_db
from src.models.twin import DigitalTwin
from src.models.deployer_config import DeployerConfiguration
from src.models.user import User
from src.api.dependencies import get_current_user
from src.schemas.deployer_config import (
    DeployerConfigUpdate,
    DeployerConfigResponse,
    ConfigValidationRequest,
    ConfigValidationResponse,
)
from src.config import settings

router = APIRouter(prefix="/twins/{twin_id}/deployer", tags=["deployer"])


async def get_user_twin(twin_id: str, user: User, db: Session) -> DigitalTwin:
    """Helper to verify twin ownership."""
    twin = db.query(DigitalTwin).filter(
        DigitalTwin.id == twin_id,
        DigitalTwin.user_id == user.id
    ).first()
    if not twin:
        raise HTTPException(status_code=404, detail="Twin not found")
    return twin


@router.get("/config", response_model=DeployerConfigResponse)
async def get_deployer_config(
    twin_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get deployer configuration for a twin. Creates default if none exists."""
    twin = await get_user_twin(twin_id, current_user, db)
    
    if not twin.deployer_config:
        config = DeployerConfiguration(twin_id=twin_id)
        db.add(config)
        db.commit()
        db.refresh(config)
    else:
        config = twin.deployer_config
    
    return DeployerConfigResponse.from_db(config)


@router.put("/config", response_model=DeployerConfigResponse)
async def update_deployer_config(
    twin_id: str,
    update: DeployerConfigUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update deployer configuration for a twin.
    Validation state is persisted to gate save operations.
    """
    twin = await get_user_twin(twin_id, current_user, db)
    
    if not twin.deployer_config:
        config = DeployerConfiguration(twin_id=twin_id)
        db.add(config)
    else:
        config = twin.deployer_config
    
    # Update fields
    if update.deployer_digital_twin_name is not None:
        config.deployer_digital_twin_name = update.deployer_digital_twin_name
    if update.config_events_json is not None:
        config.config_events_json = update.config_events_json
    if update.config_iot_devices_json is not None:
        config.config_iot_devices_json = update.config_iot_devices_json
    if update.config_json_validated is not None:
        config.config_json_validated = update.config_json_validated
    if update.config_events_validated is not None:
        config.config_events_validated = update.config_events_validated
    if update.config_iot_devices_validated is not None:
        config.config_iot_devices_validated = update.config_iot_devices_validated
    # Section 3: L1 Payloads
    if update.payloads_json is not None:
        config.payloads_json = update.payloads_json
    if update.payloads_validated is not None:
        config.payloads_validated = update.payloads_validated
    
    db.commit()
    db.refresh(config)
    return DeployerConfigResponse.from_db(config)


@router.post("/validate/{config_type}", response_model=ConfigValidationResponse)
async def validate_config(
    twin_id: str,
    config_type: str,
    request: ConfigValidationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Validate config content via Deployer API.
    
    config_type: 'events', 'iot', 'config', or 'payloads'
    
    Proxies to Deployer API: POST /validate/config/{config_type}
    Updates validation state in DB on success.
    """
    # Map Flutter config types to Deployer endpoint paths
    config_type_map = {
        "events": "config/events",
        "iot": "config/iot",
        "config": "config/config",
        "payloads": "simulator/payloads",  # Section 3 L1
    }
    
    if config_type not in config_type_map:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid config_type. Use: {list(config_type_map.keys())}"
        )
    
    twin = await get_user_twin(twin_id, current_user, db)
    deployer_config_type = config_type_map[config_type]
    
    try:
        # Send content as file upload to match Deployer API signature
        async with httpx.AsyncClient() as client:
            # The Deployer expects a file upload, but we can send raw JSON
            # Create a multipart form with the content as a file
            files = {
                "file": (f"config_{config_type}.json", request.content.encode(), "application/json")
            }
            response = await client.post(
                f"{settings.DEPLOYER_URL}/validate/{deployer_config_type}",
                files=files,
                timeout=30.0
            )
            
            if response.status_code == 200:
                result = response.json()
                valid = True
                message = result.get("message", "Validation successful")
                
                # Update validation state in DB
                config = twin.deployer_config
                if not config:
                    config = DeployerConfiguration(twin_id=twin_id)
                    db.add(config)
                
                if config_type == "config":
                    config.config_json_validated = True
                elif config_type == "events":
                    config.config_events_validated = True
                elif config_type == "iot":
                    config.config_iot_devices_validated = True
                elif config_type == "payloads":
                    config.payloads_validated = True
                
                db.commit()
                
                return ConfigValidationResponse(
                    valid=valid,
                    message=message
                )
            else:
                # Parse error detail from Deployer
                try:
                    error_detail = response.json().get("detail", str(response.text))
                except Exception:
                    error_detail = response.text
                
                return ConfigValidationResponse(
                    valid=False,
                    message=f"Validation failed: {error_detail}"
                )
                
    except httpx.ConnectError:
        return ConfigValidationResponse(
            valid=False,
            message="Cannot connect to Deployer API. Is it running on port 5004?"
        )
    except httpx.RequestError as e:
        return ConfigValidationResponse(
            valid=False,
            message=f"Request error: {str(e)}"
        )
