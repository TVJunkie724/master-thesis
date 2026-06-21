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


def get_project_root() -> Path:
    """Return the deployer project root directory."""
    return Path(__file__).resolve().parents[2]


def get_upload_root(project_root: Path | None = None) -> Path:
    """Return the root directory that contains uploaded project contexts."""
    root = project_root or get_project_root()
    return root / CONSTANTS.PROJECT_UPLOAD_DIR_NAME


def resolve_deployment_paths(
    project_name: str,
    project_root: Path | None = None,
) -> DeploymentPaths:
    """Resolve all filesystem paths needed for a deployment operation."""
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
