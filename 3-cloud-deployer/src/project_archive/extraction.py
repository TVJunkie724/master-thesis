"""Credential-free project archive extraction for wizard auto-population."""

from __future__ import annotations

import base64
import io
import zipfile

from src.api.models.zip_extraction import (
    AssetExtractionResult,
    FileExtractionResult,
    FunctionExtractionResult,
    ValidationContextInput,
    ZipExtractionResponse,
)
from src.project_archive.policy import validate_archive
from src.validation.accessors import ZipFileAccessor
from src.validation.core import (
    PROVIDER_FUNCTION_DIRS,
    PROVIDER_USER_CODE_FILES,
    ValidationContext,
    run_all_checks_aggregated,
)


CONFIG_FILES = (
    "config.json",
    "config_events.json",
    "config_iot_devices.json",
    "config_providers.json",
    "config_optimization.json",
    "config_user.json",
    "iot_device_simulator/payloads.json",
    "twin_hierarchy/aws_hierarchy.json",
    "twin_hierarchy/azure_hierarchy.json",
    "scene_assets/aws/scene.json",
    "scene_assets/azure/3DScenesConfiguration.json",
    "state_machines/aws_step_function.json",
    "state_machines/azure_logic_app.json",
    "state_machines/google_cloud_workflow.yaml",
)
SCENE_PATHS = (
    "scene_assets/aws/scene.glb",
    "scene_assets/azure/scene.glb",
    "scene_assets/scene.glb",
)


def extract_project_archive(
    content: bytes,
    context_input: ValidationContextInput,
) -> ZipExtractionResponse:
    """Validate one bounded archive and return only non-secret wizard fields."""
    with zipfile.ZipFile(io.BytesIO(content)) as zf:
        validate_archive(zf)
        accessor = ZipFileAccessor(zf)
        context = ValidationContext(
            skip_credentials=True,
            skip_config_files=list(context_input.skip_config_files),
        )
        validation = run_all_checks_aggregated(accessor, context)
        project_root = accessor.get_project_root()
        config_files = _extract_config_files(accessor, project_root)
        provider = context_input.l2_provider or context.prov_config.get(
            "layer_2_provider",
            "",
        )
        functions = _extract_functions(accessor, project_root, provider)
        assets = _extract_scene(accessor, project_root)
        warnings = list(validation.warnings)
        if accessor.file_exists(project_root + "config_credentials.json"):
            warnings.append(
                "Credential content was excluded; import cloud accounts through Cloud Connections."
            )
        return ZipExtractionResponse(
            success=validation.is_valid,
            files=config_files,
            functions=functions,
            assets=assets,
            validation_errors=validation.errors,
            warnings=warnings,
        )


def _extract_config_files(
    accessor: ZipFileAccessor,
    project_root: str,
) -> dict[str, FileExtractionResult]:
    return {
        filename: _extract_text(accessor, project_root + filename)
        if accessor.file_exists(project_root + filename)
        else FileExtractionResult(exists=False)
        for filename in CONFIG_FILES
    }


def _extract_functions(
    accessor: ZipFileAccessor,
    project_root: str,
    provider: str | None,
) -> FunctionExtractionResult:
    normalized = "gcp" if str(provider).lower() == "google" else str(provider).lower()
    function_dir = PROVIDER_FUNCTION_DIRS.get(normalized, "")
    user_file = PROVIDER_USER_CODE_FILES.get(normalized)
    result = FunctionExtractionResult()
    if not function_dir or not user_file:
        return result

    all_files = accessor.list_files()
    processor_prefix = f"{project_root}{function_dir}/processors/"
    action_prefix = f"{project_root}{function_dir}/event_actions/"
    for filepath in all_files:
        if filepath.startswith(processor_prefix) and filepath.endswith(f"/{user_file}"):
            name = filepath[len(processor_prefix) :].split("/", 1)[0]
            if name:
                result.processors[name] = _extract_text(accessor, filepath)
        elif filepath.startswith(action_prefix) and filepath.endswith(f"/{user_file}"):
            name = filepath[len(action_prefix) :].split("/", 1)[0]
            if name:
                result.event_actions[name] = _extract_text(accessor, filepath)

    feedback_path = f"{project_root}{function_dir}/event-feedback/{user_file}"
    if accessor.file_exists(feedback_path):
        result.event_feedback = _extract_text(accessor, feedback_path)
    return result


def _extract_scene(
    accessor: ZipFileAccessor,
    project_root: str,
) -> AssetExtractionResult:
    for relative_path in SCENE_PATHS:
        path = project_root + relative_path
        if not accessor.file_exists(path):
            continue
        content = accessor.read_binary(path)
        return AssetExtractionResult(
            scene_glb=FileExtractionResult(
                exists=True,
                content=base64.b64encode(content).decode("ascii"),
                is_binary=True,
            )
        )
    return AssetExtractionResult()


def _extract_text(accessor: ZipFileAccessor, path: str) -> FileExtractionResult:
    try:
        return FileExtractionResult(
            exists=True,
            content=accessor.read_text(path),
        )
    except UnicodeDecodeError:
        return FileExtractionResult(
            exists=True,
            validation_error="File content must be valid UTF-8",
        )
