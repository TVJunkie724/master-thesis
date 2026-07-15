"""User-defined processor, event-action, and feedback package construction."""

from __future__ import annotations

from dataclasses import dataclass
import json
import logging
from pathlib import Path

from src.core.paths import validate_path_component
from src.function_metadata import (
    canonical_provider,
    hash_bytes,
    hash_directory,
    reconcile_function_metadata,
    record_function_build,
)
from src.providers.terraform.package_builders.aws import _create_lambda_zip
from src.providers.terraform.package_builders.azure import _create_azure_function_zip
from src.providers.terraform.package_builders.gcp import _create_gcp_function_zip

logger = logging.getLogger(__name__)
PROVIDERS_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW_ACTION_TYPES = frozenset({"step_function", "logic_app", "workflow"})


@dataclass(frozen=True)
class _UserPackageLayout:
    provider: str
    build_provider: str
    source_root: Path
    shared_dir: Path | None
    build_dir: Path

    @property
    def event_actions_dir(self) -> Path:
        return self.source_root / "event_actions"

    @property
    def processors_dir(self) -> Path:
        return self.source_root / "processors"

    @property
    def feedback_dir(self) -> Path:
        return self.source_root / "event-feedback"


def _compute_source_hash(dir_path: Path) -> str:
    """Compute the canonical source hash used by function metadata."""
    return hash_directory(dir_path)


def _save_user_hash_metadata(
    project_path: Path,
    function_name: str,
    provider: str,
    source_hash: str,
    artifact_hash: str,
) -> None:
    """Atomically save package build evidence for one user function."""
    record_function_build(
        project_path,
        function_name,
        provider,
        source_hash,
        artifact_hash,
    )


def _reconcile_user_hash_metadata(
    project_path: Path,
    provider: str,
    active_function_names: set[str],
) -> None:
    """Keep metadata only for functions active on the current L2 provider."""
    reconcile_function_metadata(project_path, provider, active_function_names)


def _resolve_layout(project_path: Path, providers_config: dict) -> _UserPackageLayout:
    if not project_path.is_dir():
        raise ValueError(f"Project path not found: {project_path}")
    configured = providers_config.get("layer_2_provider")
    if not isinstance(configured, str):
        raise ValueError("Missing required provider config: layer_2_provider")
    provider = canonical_provider(configured)
    provider_layouts = {
        "aws": (
            "aws",
            project_path / "lambda_functions",
            PROVIDERS_ROOT / "aws" / "lambda_functions" / "_shared",
        ),
        "azure": ("azure", project_path / "azure_functions", None),
        "gcp": (
            "gcp",
            project_path / "cloud_functions",
            PROVIDERS_ROOT / "gcp" / "cloud_functions" / "_shared",
        ),
    }
    if provider not in provider_layouts:
        raise ValueError(f"Invalid layer_2_provider: {provider}")
    build_provider, source_root, shared_dir = provider_layouts[provider]
    build_dir = project_path / ".build" / build_provider
    build_dir.mkdir(parents=True, exist_ok=True)
    return _UserPackageLayout(
        provider=provider,
        build_provider=build_provider,
        source_root=source_root,
        shared_dir=shared_dir,
        build_dir=build_dir,
    )


def _load_json_list(path: Path, label: str) -> list[dict]:
    if not path.is_file():
        raise ValueError(f"Missing required config: {path.name}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in {path.name}: {exc.msg}") from exc
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise ValueError(f"{label} must be an array of objects")
    return value


def _load_twin_name(project_path: Path) -> str:
    config_path = project_path / "config.json"
    if not config_path.is_file():
        raise ValueError("Missing required config: config.json")
    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in config.json: {exc.msg}") from exc
    twin_name = config.get("digital_twin_name") if isinstance(config, dict) else None
    if not isinstance(twin_name, str) or not twin_name:
        raise ValueError("config.json requires a non-empty digital_twin_name")
    return twin_name


def _build_archive(
    layout: _UserPackageLayout,
    source_dir: Path,
    target: Path,
    *,
    twin_name: str | None = None,
    device_id: str | None = None,
) -> None:
    if layout.provider == "aws":
        _create_lambda_zip(
            source_dir,
            layout.shared_dir,
            target,
            digital_twin_name=twin_name,
            device_id=device_id,
        )
    elif layout.provider == "gcp":
        _create_gcp_function_zip(
            source_dir,
            layout.shared_dir,
            target,
            digital_twin_name=twin_name,
            device_id=device_id,
        )
    else:
        _create_azure_function_zip(source_dir, target)


def _hash_source(
    name: str,
    source_dir: Path,
) -> str:
    """Validate and hash one source without publishing successful-build evidence."""
    validate_path_component(name, "function name")
    if not source_dir.is_dir():
        raise ValueError(f"Missing code for user function '{name}': {source_dir}")
    return _compute_source_hash(source_dir)


def _publish_build_metadata(
    project_path: Path,
    layout: _UserPackageLayout,
    name: str,
    source_hash: str,
    artifact_path: Path,
    active: set[str],
) -> None:
    """Publish source-version evidence only after its package step succeeds."""
    _save_user_hash_metadata(
        project_path,
        name,
        layout.provider,
        source_hash,
        hash_bytes(artifact_path.read_bytes()),
    )
    active.add(name)


def _build_event_actions(
    project_path: Path,
    layout: _UserPackageLayout,
    events: list[dict],
    packages: dict[str, Path],
    active: set[str],
) -> None:
    built: set[str] = set()
    for event in events:
        action = event.get("action")
        if not isinstance(action, dict):
            raise ValueError("Event config entry requires an action object")
        action_type = action.get("type", "")
        if action_type in WORKFLOW_ACTION_TYPES:
            continue
        name = action.get("functionName")
        if not isinstance(name, str) or not name:
            raise ValueError("Event action requires a non-empty functionName")
        validate_path_component(name, "function name")
        if name in built:
            continue
        source_dir = layout.event_actions_dir / name
        source_hash = _hash_source(name, source_dir)
        target = layout.build_dir / f"{name}.zip"
        _build_archive(layout, source_dir, target)
        _publish_build_metadata(
            project_path,
            layout,
            name,
            source_hash,
            target,
            active,
        )
        packages[name] = target
        built.add(name)


def _build_processors(
    project_path: Path,
    layout: _UserPackageLayout,
    devices: list[dict],
    twin_name: str,
    packages: dict[str, Path],
    active: set[str],
) -> None:
    built: set[str] = set()
    for device in devices:
        device_id = device.get("id")
        if not isinstance(device_id, str) or not device_id:
            raise ValueError("Device config entry requires a non-empty id")
        validate_path_component(device_id, "device id")
        if device_id in built:
            continue
        name = f"processor-{device_id}"
        source_dir = layout.processors_dir / device_id
        source_hash = _hash_source(name, source_dir)
        target = layout.build_dir / f"{name}.zip"
        _build_archive(
            layout,
            source_dir,
            target,
            twin_name=twin_name,
            device_id=device_id,
        )
        packages[name] = target
        _publish_build_metadata(
            project_path,
            layout,
            name,
            source_hash,
            target,
            active,
        )
        built.add(device_id)


def _build_feedback(
    project_path: Path,
    layout: _UserPackageLayout,
    packages: dict[str, Path],
    active: set[str],
) -> None:
    if not layout.feedback_dir.exists():
        return
    name = "event-feedback"
    source_hash = _hash_source(name, layout.feedback_dir)
    target = layout.build_dir / f"{name}.zip"
    _build_archive(layout, layout.feedback_dir, target)
    packages[name] = target
    _publish_build_metadata(
        project_path,
        layout,
        name,
        source_hash,
        target,
        active,
    )


def build_user_packages(
    project_path: Path,
    providers_config: dict,
) -> dict[str, Path]:
    """Build every user function package required by the configured L2 provider."""
    layout = _resolve_layout(project_path, providers_config)
    if layout.provider == "azure":
        return {}
    events = _load_json_list(project_path / "config_events.json", "Event config")
    devices = _load_json_list(project_path / "config_iot_devices.json", "Device config")
    twin_name = _load_twin_name(project_path)
    packages: dict[str, Path] = {}
    active: set[str] = set()

    _build_event_actions(project_path, layout, events, packages, active)
    _build_processors(project_path, layout, devices, twin_name, packages, active)
    _build_feedback(project_path, layout, packages, active)
    _reconcile_user_hash_metadata(project_path, layout.provider, active)
    logger.info("Built %s user packages for %s", len(packages), layout.provider)
    return packages


def get_user_package_path(project_path: Path, function_name: str, provider: str) -> Path:
    """Return the canonical pre-built user package path."""
    validate_path_component(function_name, "function name")
    validate_path_component(provider, "provider name")
    return project_path / ".build" / provider / f"{function_name}.zip"
