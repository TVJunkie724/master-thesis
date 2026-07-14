"""Contracts for aggregate deployer configuration validation."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


MAX_CONFIG_LENGTH = 5 * 1024 * 1024
MAX_CODE_LENGTH = 1024 * 1024
MAX_FUNCTIONS = 1_000


class ValidationError(BaseModel):
    """Stable field-level validation error."""

    code: str
    field: str
    message: str


class DeployerCompleteValidation(BaseModel):
    """Bounded input for complete deployer configuration validation."""

    model_config = ConfigDict(extra="forbid")

    deployer_digital_twin_name: str | None = Field(None, max_length=128)
    config_events: str | None = Field(None, max_length=MAX_CONFIG_LENGTH)
    config_iot_devices: str | None = Field(None, max_length=MAX_CONFIG_LENGTH)
    payloads: str | None = Field(None, max_length=MAX_CONFIG_LENGTH)
    processors: dict[str, str] | None = Field(None, max_length=MAX_FUNCTIONS)
    event_feedback: str | None = Field(None, max_length=MAX_CODE_LENGTH)
    event_actions: dict[str, str] | None = Field(None, max_length=MAX_FUNCTIONS)
    hierarchy: str | None = Field(None, max_length=MAX_CONFIG_LENGTH)
    scene_config: str | None = Field(None, max_length=MAX_CONFIG_LENGTH)
    scene_glb_uploaded: bool = False
    state_machine: str | None = Field(None, max_length=MAX_CONFIG_LENGTH)
    user_config: str | None = Field(None, max_length=MAX_CONFIG_LENGTH)
    optimizer_params: dict[str, Any] | None = Field(None, max_length=200)
    cheapest_path: dict[str, str | dict[str, str]] | None = Field(
        None,
        max_length=20,
    )

    @field_validator("processors", "event_actions")
    @classmethod
    def validate_function_maps(cls, value: dict[str, str] | None):
        if value is None:
            return value
        for name, code in value.items():
            if not name or len(name) > 128:
                raise ValueError("function names must contain 1 to 128 characters")
            if len(code) > MAX_CODE_LENGTH:
                raise ValueError("function code exceeds the 1MB limit")
        return value


class DeployerValidationResponse(BaseModel):
    """Aggregate result with deterministic field errors."""

    valid: bool
    errors: list[ValidationError] = Field(default_factory=list)
