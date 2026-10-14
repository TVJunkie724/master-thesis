"""Public models for bounded, Twin-owned user functions."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict


class ExtensionSlotResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["user-function-extension-slot.v1"]
    slot_id: str
    slot_version: str
    display_name: str
    entrypoint: Literal["process"]
    runtime_id: Literal["python311"]
    configuration_schema: dict[str, Any]
    resource_limits: dict[str, int]
    permission_capabilities: list[str]
    secret_policy: Literal["forbidden"]


class ExtensionSlotListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["user-function-extension-slot-list.v1"] = (
        "user-function-extension-slot-list.v1"
    )
    slots: list[ExtensionSlotResponse]


class TwinUserFunctionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["twin-user-function.v1"] = "twin-user-function.v1"
    function_id: str
    twin_id: str
    artifact_digest: str
    slot_id: str
    slot_version: str
    runtime_id: str
    configuration: dict[str, Any]
    declared_capabilities: list[str]
    validator_version: str
    source_files: list[str]
    dependencies: list[str]
    created_at: datetime
    updated_at: datetime


class TwinUserFunctionListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["twin-user-function-list.v1"] = "twin-user-function-list.v1"
    items: list[TwinUserFunctionResponse]


class UserFunctionValidationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["user-function-validation-result.v1"] = (
        "user-function-validation-result.v1"
    )
    valid: Literal[True] = True
    artifact_digest: str
    slot_id: str
    slot_version: str
    runtime_id: str
    source_files: list[str]
    dependencies: list[str]
    checks: list[str]
