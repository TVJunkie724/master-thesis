from pydantic import BaseModel, Field
from typing import Literal, Optional
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
    twin_state: Optional[str] = None
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
    has_config_artifacts: bool = False
    has_l1_payloads: bool = False
    has_l2_artifacts: bool = False
    has_l4_l5_artifacts: bool = False
    validation_summary: dict[str, bool] = Field(default_factory=dict)
    updated_at: Optional[datetime] = None
    
    @classmethod
    def from_db(cls, config, twin_state: Optional[str] = None):
        """Convert DB model to response."""
        if config is None:
            return None
        
        def parse_json_dict(json_str):
            if json_str is None:
                return None
            try:
                return json.loads(json_str)
            except (json.JSONDecodeError, TypeError):
                return None
        
        return cls(
            twin_id=config.twin_id,
            twin_state=twin_state,
            deployer_digital_twin_name=config.deployer_digital_twin_name,
            config_events_json=config.config_events_json,
            config_iot_devices_json=config.config_iot_devices_json,
            config_json_validated=bool(config.config_json_validated),
            config_events_validated=bool(config.config_events_validated),
            config_iot_devices_validated=bool(config.config_iot_devices_validated),
            payloads_json=config.payloads_json,
            payloads_validated=bool(config.payloads_validated),
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
            has_config_artifacts=bool(
                config.deployer_digital_twin_name
                or config.config_events_json
                or config.config_iot_devices_json
            ),
            has_l1_payloads=bool(config.payloads_json),
            has_l2_artifacts=bool(
                config.processor_contents
                or config.event_feedback_content
                or config.event_action_contents
                or config.state_machine_content
            ),
            has_l4_l5_artifacts=bool(
                config.hierarchy_content
                or config.scene_glb_uploaded
                or config.scene_config_content
                or config.user_config_content
            ),
            validation_summary={
                "config": bool(config.config_json_validated),
                "events": bool(config.config_events_validated),
                "iot_devices": bool(config.config_iot_devices_validated),
                "payloads": bool(config.payloads_validated),
                "event_feedback": bool(config.event_feedback_validated),
                "state_machine": bool(config.state_machine_validated),
                "hierarchy": bool(config.hierarchy_validated),
                "scene_config": bool(config.scene_config_validated),
                "user_config": bool(config.user_config_validated),
            },
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


DeployerConfigSectionId = Literal[
    "configuration",
    "payloads",
    "user_logic",
    "digital_twin_assets",
]


class DeployerConfigArtifact(BaseModel):
    artifact_id: str
    section_id: DeployerConfigSectionId
    label: str
    content: str | None = None
    has_content: bool
    validated: bool
    required: bool = False
    validation_key: str | None = None
    requirements: str | None = None


class DeployerConfigSection(BaseModel):
    section_id: DeployerConfigSectionId
    label: str
    artifacts: list[DeployerConfigArtifact] = Field(default_factory=list)
    has_content: bool
    validated: bool
    missing_required_artifacts: list[str] = Field(default_factory=list)
    invalid_artifacts: list[str] = Field(default_factory=list)


class DeployerConfigReadModelResponse(BaseModel):
    schema_version: str = "deployer-config-read-model.v1"
    twin_id: str
    twin_state: str | None = None
    sections: list[DeployerConfigSection]
    validation_summary: dict[str, bool] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    updated_at: datetime | None = None

    @classmethod
    def from_db(cls, config, twin_state: Optional[str] = None):
        warnings: list[str] = []
        processor_contents = _parse_json_dict(config.processor_contents, "processor_contents", warnings)
        processor_validated = _parse_json_dict(config.processor_validated, "processor_validated", warnings)
        processor_requirements = _parse_json_dict(config.processor_requirements, "processor_requirements", warnings)
        event_action_contents = _parse_json_dict(
            config.event_action_contents,
            "event_action_contents",
            warnings,
        )
        event_action_validated = _parse_json_dict(
            config.event_action_validated,
            "event_action_validated",
            warnings,
        )
        event_action_requirements = _parse_json_dict(
            config.event_action_requirements,
            "event_action_requirements",
            warnings,
        )

        sections = [
            _section(
                "configuration",
                "Deployment Configuration",
                [
                    _artifact(
                        "deployer_digital_twin_name",
                        "configuration",
                        "Digital Twin Name",
                        config.deployer_digital_twin_name,
                        bool(config.config_json_validated),
                        required=True,
                        validation_key="config",
                    ),
                    _artifact(
                        "config_events_json",
                        "configuration",
                        "Event Rules",
                        config.config_events_json,
                        bool(config.config_events_validated),
                        required=True,
                        validation_key="events",
                    ),
                    _artifact(
                        "config_iot_devices_json",
                        "configuration",
                        "IoT Devices",
                        config.config_iot_devices_json,
                        bool(config.config_iot_devices_validated),
                        required=True,
                        validation_key="iot_devices",
                    ),
                ],
            ),
            _section(
                "payloads",
                "L1 Payloads",
                [
                    _artifact(
                        "payloads_json",
                        "payloads",
                        "Payload Definitions",
                        config.payloads_json,
                        bool(config.payloads_validated),
                        validation_key="payloads",
                    )
                ],
            ),
            _section(
                "user_logic",
                "L2 User Logic",
                _keyed_artifacts(
                    processor_contents,
                    processor_validated,
                    processor_requirements,
                    section_id="user_logic",
                    artifact_prefix="processor",
                    label_prefix="Processor",
                    validation_key_prefix="processor",
                )
                + [
                    _artifact(
                        "event_feedback",
                        "user_logic",
                        "Event Feedback",
                        config.event_feedback_content,
                        bool(config.event_feedback_validated),
                        validation_key="event_feedback",
                        requirements=config.event_feedback_requirements,
                    ),
                    _artifact(
                        "state_machine",
                        "user_logic",
                        "State Machine",
                        config.state_machine_content,
                        bool(config.state_machine_validated),
                        validation_key="state_machine",
                    ),
                ]
                + _keyed_artifacts(
                    event_action_contents,
                    event_action_validated,
                    event_action_requirements,
                    section_id="user_logic",
                    artifact_prefix="event_action",
                    label_prefix="Event Action",
                    validation_key_prefix="event_action",
                ),
            ),
            _section(
                "digital_twin_assets",
                "L4/L5 Digital Twin Assets",
                [
                    _artifact(
                        "hierarchy_content",
                        "digital_twin_assets",
                        "Hierarchy",
                        config.hierarchy_content,
                        bool(config.hierarchy_validated),
                        validation_key="hierarchy",
                    ),
                    _artifact(
                        "scene_glb",
                        "digital_twin_assets",
                        "3D Scene GLB",
                        "uploaded" if config.scene_glb_uploaded else None,
                        bool(config.scene_glb_uploaded),
                        validation_key="scene_glb",
                    ),
                    _artifact(
                        "scene_config_content",
                        "digital_twin_assets",
                        "Scene Configuration",
                        config.scene_config_content,
                        bool(config.scene_config_validated),
                        validation_key="scene_config",
                    ),
                    _artifact(
                        "user_config_content",
                        "digital_twin_assets",
                        "User Configuration",
                        config.user_config_content,
                        bool(config.user_config_validated),
                        validation_key="user_config",
                    ),
                ],
            ),
        ]

        return cls(
            twin_id=config.twin_id,
            twin_state=twin_state,
            sections=sections,
            validation_summary={
                artifact.validation_key: artifact.validated
                for section in sections
                for artifact in section.artifacts
                if artifact.validation_key
            },
            warnings=warnings,
            updated_at=config.updated_at,
        )


def _parse_json_dict(value: str | None, field_name: str, warnings: list[str]) -> dict:
    if not value:
        return {}
    try:
        parsed = json.loads(value)
    except (json.JSONDecodeError, TypeError):
        warnings.append(f"{field_name} contains invalid JSON and was treated as empty.")
        return {}
    if not isinstance(parsed, dict):
        warnings.append(f"{field_name} is not an object and was treated as empty.")
        return {}
    return parsed


def _artifact(
    artifact_id: str,
    section_id: DeployerConfigSectionId,
    label: str,
    content: str | None,
    validated: bool,
    *,
    required: bool = False,
    validation_key: str | None = None,
    requirements: str | None = None,
) -> DeployerConfigArtifact:
    has_content = bool(content)
    return DeployerConfigArtifact(
        artifact_id=artifact_id,
        section_id=section_id,
        label=label,
        content=content,
        has_content=has_content,
        validated=validated,
        required=required,
        validation_key=validation_key,
        requirements=requirements,
    )


def _keyed_artifacts(
    contents: dict,
    validated: dict,
    requirements: dict,
    *,
    section_id: DeployerConfigSectionId,
    artifact_prefix: str,
    label_prefix: str,
    validation_key_prefix: str,
) -> list[DeployerConfigArtifact]:
    artifacts = []
    for key in sorted(contents.keys()):
        safe_key = str(key)
        artifacts.append(
            _artifact(
                f"{artifact_prefix}:{safe_key}",
                section_id,
                f"{label_prefix}: {safe_key}",
                str(contents.get(key) or ""),
                bool(validated.get(key)),
                validation_key=f"{validation_key_prefix}:{safe_key}",
                requirements=(
                    str(requirements.get(key))
                    if requirements.get(key) is not None
                    else None
                ),
            )
        )
    return artifacts


def _section(
    section_id: DeployerConfigSectionId,
    label: str,
    artifacts: list[DeployerConfigArtifact],
) -> DeployerConfigSection:
    missing = [
        artifact.artifact_id
        for artifact in artifacts
        if artifact.required and not artifact.has_content
    ]
    invalid = [
        artifact.artifact_id
        for artifact in artifacts
        if artifact.has_content and not artifact.validated
    ]
    return DeployerConfigSection(
        section_id=section_id,
        label=label,
        artifacts=artifacts,
        has_content=any(artifact.has_content for artifact in artifacts),
        validated=bool(artifacts) and not missing and not invalid,
        missing_required_artifacts=missing,
        invalid_artifacts=invalid,
    )
