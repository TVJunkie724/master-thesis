"""Strict portable Twin archive contracts."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

ContentDigest = Annotated[str, Field(pattern=r"^sha256:[0-9a-f]{64}$")]
PortableText = Annotated[str, Field(max_length=2_000_000)]


class PortableTwinManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["twin2multicloud-portable.v1"]
    files: dict[str, ContentDigest] = Field(min_length=1, max_length=3)


class PortableProviderSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    aws_region: str = Field(default="eu-central-1", min_length=1, max_length=64)
    aws_sso_region: str | None = Field(default=None, min_length=1, max_length=64)
    azure_region: str = Field(default="westeurope", min_length=1, max_length=64)
    azure_region_iothub: str | None = Field(default=None, min_length=1, max_length=64)
    azure_region_digital_twin: str | None = Field(
        default=None,
        min_length=1,
        max_length=64,
    )
    gcp_project_id: str | None = Field(default=None, min_length=1, max_length=128)
    gcp_region: str = Field(default="europe-west1", min_length=1, max_length=64)


class PortableDeployerDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    deployer_digital_twin_name: str | None = Field(
        default=None,
        min_length=1,
        max_length=15,
    )
    config_events_json: PortableText | None = None
    config_iot_devices_json: PortableText | None = None
    payloads_json: PortableText | None = None
    processor_contents: PortableText | None = None
    processor_requirements: PortableText | None = None
    event_feedback_content: PortableText | None = None
    event_feedback_requirements: PortableText | None = None
    event_action_contents: PortableText | None = None
    event_action_requirements: PortableText | None = None
    state_machine_content: PortableText | None = None
    hierarchy_content: PortableText | None = None
    scene_config_content: PortableText | None = None
    user_config_content: PortableText | None = None


class PortableTwinDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["twin-definition.v1"]
    source_name: str = Field(min_length=1, max_length=120)
    debug_mode: bool = False
    provider_settings: PortableProviderSettings = Field(
        default_factory=PortableProviderSettings
    )
    optimizer_params: dict[str, Any] | None = None
    deployer: PortableDeployerDefinition | None = None

    @field_validator("optimizer_params")
    @classmethod
    def reject_secret_like_optimizer_fields(
        cls,
        value: dict[str, Any] | None,
    ) -> dict[str, Any] | None:
        if value is None:
            return None
        secret_fragments = {"secret", "token", "password", "private_key", "credential"}
        pending: list[Any] = [value]
        while pending:
            item = pending.pop()
            if isinstance(item, dict):
                for key, nested in item.items():
                    normalized = str(key).lower()
                    if any(fragment in normalized for fragment in secret_fragments):
                        raise ValueError("optimizer parameters contain a secret-like field")
                    pending.append(nested)
            elif isinstance(item, list):
                pending.extend(item)
        return value


class TwinDuplicateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=120)
