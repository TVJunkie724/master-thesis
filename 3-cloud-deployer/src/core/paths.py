"""Central path resolution for project-scoped deployment operations."""

from dataclasses import dataclass
from pathlib import Path

import constants as CONSTANTS


@dataclass(frozen=True)
class DeploymentPaths:
    project_root: Path
    upload_root: Path
    project_path: Path
    terraform_dir: Path
    tfvars_path: Path
    state_path: Path
    plan_path: Path


@dataclass(frozen=True)
class TemplatePaths:
    project_root: Path
    templates_root: Path
    template_path: Path
    legacy_template_path: Path
    active_template_path: Path


def get_project_root() -> Path:
    """Return the deployer project root directory."""
    return Path(__file__).resolve().parents[2]


def get_upload_root(project_root: Path | None = None) -> Path:
    """Return the root directory that contains uploaded project contexts."""
    root = project_root or get_project_root()
    return root / CONSTANTS.PROJECT_UPLOAD_DIR_NAME


def get_templates_root(project_root: Path | None = None) -> Path:
    """Return the root directory that contains versioned deployment templates."""
    root = project_root or get_project_root()
    return root / CONSTANTS.PROJECT_TEMPLATES_DIR_NAME


def validate_path_component(value: str, description: str) -> str:
    """Validate an untrusted value before using it as one filesystem component."""
    if (
        not isinstance(value, str)
        or not value
        or value in {".", ".."}
        or "\x00" in value
        or Path(value).name != value
    ):
        raise ValueError(f"Invalid {description}.")
    return value


def resolve_template_paths(project_root: Path | None = None) -> TemplatePaths:
    """Resolve canonical and legacy paths for the read-only template project."""
    root = project_root or get_project_root()
    templates_root = get_templates_root(root)
    template_path = templates_root / CONSTANTS.DEFAULT_TEMPLATE_DIR_NAME
    legacy_template_path = get_upload_root(root) / CONSTANTS.DEFAULT_PROJECT_NAME
    active_template_path = template_path if template_path.exists() else legacy_template_path

    return TemplatePaths(
        project_root=root,
        templates_root=templates_root,
        template_path=template_path,
        legacy_template_path=legacy_template_path,
        active_template_path=active_template_path,
    )


def resolve_template_project_path(project_root: Path | None = None) -> Path:
    """Return the active read-only template path, preferring the canonical template root."""
    return resolve_template_paths(project_root).active_template_path


def resolve_project_context_path(
    project_name: str,
    project_root: Path | None = None,
) -> Path:
    """Resolve a logical project name to either the template root or runtime upload root."""
    validate_path_component(project_name, "project name")
    if project_name == CONSTANTS.DEFAULT_PROJECT_NAME:
        return resolve_template_project_path(project_root)
    return resolve_deployment_paths(project_name, project_root).project_path


def resolve_deployment_paths(
    project_name: str,
    project_root: Path | None = None,
) -> DeploymentPaths:
    """Resolve all filesystem paths needed for a deployment operation."""
    validate_path_component(project_name, "project name")
    root = project_root or get_project_root()
    upload_root = get_upload_root(root)
    project_path = upload_root / project_name
    terraform_dir = project_path / "terraform"

    return DeploymentPaths(
        project_root=root,
        upload_root=upload_root,
        project_path=project_path,
        terraform_dir=terraform_dir,
        tfvars_path=terraform_dir / "generated.tfvars.json",
        state_path=terraform_dir / "terraform.tfstate",
        plan_path=terraform_dir / "tfplan",
    )
