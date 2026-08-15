"""Public Management API models for immutable user-function extensions."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


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


class UserFunctionArtifactResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str
    artifact_id: str
    artifact_state: Literal["valid", "legacy_unvalidated"]
    artifact_digest: str
    slot_id: str
    slot_version: str
    runtime_id: str
    configuration: dict[str, Any]
    declared_capabilities: list[str]
    validator_version: str | None
    source_files: list[str]
    dependency_count: int
    created_at: datetime


class UserFunctionArtifactListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["user-function-artifact-list.v1"] = (
        "user-function-artifact-list.v1"
    )
    items: list[UserFunctionArtifactResponse]
    total: int
    limit: int
    offset: int


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


class TwinExtensionBindingUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    artifact_id: str = Field(min_length=36, max_length=36)
    slot_version: str = Field(pattern="^[1-9][0-9]*$", max_length=10)
    expected_revision: int | None = Field(default=None, ge=1)


class TwinExtensionBindingResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["twin-extension-binding.v1"] = (
        "twin-extension-binding.v1"
    )
    binding_id: str
    twin_id: str
    slot_id: str
    slot_version: str
    artifact_id: str
    artifact_digest: str
    binding_digest: str
    active: bool
    revision: int
    created_at: datetime
    unbound_at: datetime | None


class TwinExtensionBindingListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["twin-extension-binding-list.v1"] = (
        "twin-extension-binding-list.v1"
    )
    items: list[TwinExtensionBindingResponse]
