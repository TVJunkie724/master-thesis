from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import httpx
import json

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
    # Section 3: L2 User Functions
    if update.processor_contents is not None:
        config.processor_contents = json.dumps(update.processor_contents)
    if update.processor_validated is not None:
        config.processor_validated = json.dumps(update.processor_validated)
    if update.processor_requirements is not None:
        config.processor_requirements = json.dumps(update.processor_requirements)
    if update.event_feedback_content is not None:
        config.event_feedback_content = update.event_feedback_content
    if update.event_feedback_validated is not None:
        config.event_feedback_validated = update.event_feedback_validated
    if update.event_feedback_requirements is not None:
        config.event_feedback_requirements = update.event_feedback_requirements
    if update.event_action_contents is not None:
        config.event_action_contents = json.dumps(update.event_action_contents)
    if update.event_action_validated is not None:
        config.event_action_validated = json.dumps(update.event_action_validated)
    if update.event_action_requirements is not None:
        config.event_action_requirements = json.dumps(update.event_action_requirements)
    if update.state_machine_content is not None:
        config.state_machine_content = update.state_machine_content
    if update.state_machine_validated is not None:
        config.state_machine_validated = update.state_machine_validated
    
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
    
    Section 2 types: 'events', 'iot', 'config' (persisted to DB)
    Section 3 L1: 'payloads' (persisted to DB)
    Section 3 L2: 'function-code', 'state-machine' (NOT persisted - BLoC handles)
    
    Proxies to Deployer API: POST /validate/{endpoint}
    """
    # Map Flutter config types to Deployer endpoint paths
    config_type_map = {
        # Section 2
        "events": "config/events",
        "iot": "config/iot",
        "config": "config/config",
        # Section 3 L1
        "payloads": "simulator/payloads",
        # Section 3 L2
        "function-code": "function-code",
        "state-machine": "state-machine",
    }
    
    l2_types = {"function-code", "state-machine"}
    
    if config_type not in config_type_map:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid config_type. Use: {list(config_type_map.keys())}"
        )
    
    # L2 types require provider parameter
    if config_type in l2_types and not request.provider:
        raise HTTPException(
            status_code=400,
            detail=f"provider is required for {config_type} validation (aws, azure, google)"
        )
    
    twin = await get_user_twin(twin_id, current_user, db)
    deployer_endpoint = config_type_map[config_type]
    
    try:
        async with httpx.AsyncClient() as client:
            if config_type in l2_types:
                # L2: File upload with provider query param
                if config_type == "function-code":
                    ext = ".py"
                else:
                    # State machine: detect JSON vs YAML
                    ext = ".json" if request.content.strip().startswith(("{", "[")) else ".yaml"
                
                files = {"file": (f"code{ext}", request.content.encode(), "text/plain")}
                response = await client.post(
                    f"{settings.DEPLOYER_URL}/validate/{deployer_endpoint}?provider={request.provider}",
                    files=files,
                    timeout=30.0
                )
            else:
                # Section 2 / L1: JSON file upload
                files = {
                    "file": (f"config_{config_type}.json", request.content.encode(), "application/json")
                }
                response = await client.post(
                    f"{settings.DEPLOYER_URL}/validate/{deployer_endpoint}",
                    files=files,
                    timeout=30.0
                )
            
            if response.status_code == 200:
                result = response.json()
                valid = True
                message = result.get("message", "Valid")
                
                # Only persist validation for Section 2/L1 types, NOT L2
                # L2 per-entity validation is handled by Flutter BLoC
                if config_type not in l2_types:
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
                
                return ConfigValidationResponse(valid=valid, message=message)
            else:
                # Normalize error: Deployer uses "detail" for errors
                try:
                    error_detail = response.json().get("detail", response.text)
                except Exception:
                    error_detail = response.text
                
                return ConfigValidationResponse(
                    valid=False,
                    message=str(error_detail)
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

