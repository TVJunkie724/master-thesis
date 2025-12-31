from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class DeployerConfigUpdate(BaseModel):
    """Request model for updating deployer configuration."""
    config_events_json: Optional[str] = None
    config_iot_devices_json: Optional[str] = None
    config_events_validated: Optional[bool] = None
    config_iot_devices_validated: Optional[bool] = None


class DeployerConfigResponse(BaseModel):
    """Response model for deployer configuration."""
    twin_id: str
    config_events_json: Optional[str] = None
    config_iot_devices_json: Optional[str] = None
    config_events_validated: bool = False
    config_iot_devices_validated: bool = False
    updated_at: Optional[datetime] = None
    
    @classmethod
    def from_db(cls, config):
        """Convert DB model to response."""
        if config is None:
            return None
        return cls(
            twin_id=config.twin_id,
            config_events_json=config.config_events_json,
            config_iot_devices_json=config.config_iot_devices_json,
            config_events_validated=config.config_events_validated,
            config_iot_devices_validated=config.config_iot_devices_validated,
            updated_at=config.updated_at,
        )


class ConfigValidationRequest(BaseModel):
    """Request model for validating config content."""
    content: str


class ConfigValidationResponse(BaseModel):
    """Response model for config validation."""
    valid: bool
    message: str
    errors: Optional[list[str]] = None
