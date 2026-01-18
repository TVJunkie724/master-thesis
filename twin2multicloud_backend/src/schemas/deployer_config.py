from pydantic import BaseModel
from typing import Optional
from datetime import datetime
import json


class DeployerConfigUpdate(BaseModel):
    """Request model for updating deployer configuration."""
    deployer_digital_twin_name: Optional[str] = None
    config_events_json: Optional[str] = None
    config_iot_devices_json: Optional[str] = None
    config_json_validated: Optional[bool] = None
    config_events_validated: Optional[bool] = None
    config_iot_devices_validated: Optional[bool] = None
    # Section 3: L1 Payloads
    payloads_json: Optional[str] = None
    payloads_validated: Optional[bool] = None
    # Section 3: L2 User Functions
    processor_contents: Optional[dict[str, str]] = None
    processor_validated: Optional[dict[str, bool]] = None
    processor_requirements: Optional[dict[str, str]] = None  # {deviceId: requirements.txt}
    event_feedback_content: Optional[str] = None
    event_feedback_validated: Optional[bool] = None
    event_feedback_requirements: Optional[str] = None
    event_action_contents: Optional[dict[str, str]] = None
    event_action_validated: Optional[dict[str, bool]] = None
    event_action_requirements: Optional[dict[str, str]] = None  # {funcName: requirements.txt}
    state_machine_content: Optional[str] = None
    state_machine_validated: Optional[bool] = None
    # Section 2: L4 Hierarchy
    hierarchy_content: Optional[str] = None
    hierarchy_validated: Optional[bool] = None
    # Section 3: L4 Scene
    scene_glb_uploaded: Optional[bool] = None
    scene_config_content: Optional[str] = None
    scene_config_validated: Optional[bool] = None
    # Section 3: L4/L5 User Config
    user_config_content: Optional[str] = None
    user_config_validated: Optional[bool] = None


class DeployerConfigResponse(BaseModel):
    """Response model for deployer configuration."""
    twin_id: str
    deployer_digital_twin_name: Optional[str] = None
    config_events_json: Optional[str] = None
    config_iot_devices_json: Optional[str] = None
    config_json_validated: bool = False
    config_events_validated: bool = False
    config_iot_devices_validated: bool = False
    # Section 3: L1 Payloads
    payloads_json: Optional[str] = None
    payloads_validated: bool = False
    # Section 3: L2 User Functions
    processor_contents: Optional[dict[str, str]] = None
    processor_validated: Optional[dict[str, bool]] = None
    processor_requirements: Optional[dict[str, str]] = None
    event_feedback_content: Optional[str] = None
    event_feedback_validated: bool = False
    event_feedback_requirements: Optional[str] = None
    event_action_contents: Optional[dict[str, str]] = None
    event_action_validated: Optional[dict[str, bool]] = None
    event_action_requirements: Optional[dict[str, str]] = None
    state_machine_content: Optional[str] = None
    state_machine_validated: bool = False
    # Section 2: L4 Hierarchy
    hierarchy_content: Optional[str] = None
    hierarchy_validated: bool = False
    # Section 3: L4 Scene
    scene_glb_uploaded: bool = False
    scene_config_content: Optional[str] = None
    scene_config_validated: bool = False
    # Section 3: L4/L5 User Config
    user_config_content: Optional[str] = None
    user_config_validated: bool = False
    updated_at: Optional[datetime] = None
    
    @classmethod
    def from_db(cls, config):
        """Convert DB model to response."""
        if config is None:
            return None
        
        def parse_json_dict(json_str):
            if json_str is None:
                return None
            try:
                return json.loads(json_str)
            except:
                return None
        
        return cls(
            twin_id=config.twin_id,
            deployer_digital_twin_name=config.deployer_digital_twin_name,
            config_events_json=config.config_events_json,
            config_iot_devices_json=config.config_iot_devices_json,
            config_json_validated=config.config_json_validated,
            config_events_validated=config.config_events_validated,
            config_iot_devices_validated=config.config_iot_devices_validated,
            payloads_json=config.payloads_json,
            payloads_validated=config.payloads_validated,
            # L2 fields (parse JSON strings to dicts)
            processor_contents=parse_json_dict(config.processor_contents),
            processor_validated=parse_json_dict(config.processor_validated),
            processor_requirements=parse_json_dict(config.processor_requirements),
            event_feedback_content=config.event_feedback_content,
            event_feedback_validated=config.event_feedback_validated or False,
            event_feedback_requirements=config.event_feedback_requirements,
            event_action_contents=parse_json_dict(config.event_action_contents),
            event_action_validated=parse_json_dict(config.event_action_validated),
            event_action_requirements=parse_json_dict(config.event_action_requirements),
            state_machine_content=config.state_machine_content,
            state_machine_validated=config.state_machine_validated or False,
            # L4 Hierarchy
            hierarchy_content=config.hierarchy_content,
            hierarchy_validated=config.hierarchy_validated or False,
            # L4 Scene
            scene_glb_uploaded=config.scene_glb_uploaded or False,
            scene_config_content=config.scene_config_content,
            scene_config_validated=config.scene_config_validated or False,
            # L4/L5 User Config
            user_config_content=config.user_config_content,
            user_config_validated=config.user_config_validated or False,
            updated_at=config.updated_at,
        )


class ConfigValidationRequest(BaseModel):
    """Request model for validating config content."""
    content: str
    provider: Optional[str] = None  # Required for L2 types (aws, azure, google)


class ConfigValidationResponse(BaseModel):
    """Response model for config validation."""
    valid: bool
    message: str
    errors: Optional[list[str]] = None
