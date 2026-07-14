"""Read-only access to deployed Terraform outputs."""

from __future__ import annotations

from pathlib import Path

from logger import logger
from src.core.observability import redact_sensitive
from src.core.paths import resolve_project_context_path
from src.terraform_runner import TerraformRunner


def load_terraform_outputs(project_name: str) -> dict:
    """Return current outputs, or an empty mapping when no state exists."""
    project_path = resolve_project_context_path(project_name)
    state_path = project_path / "terraform" / "terraform.tfstate"
    if not state_path.exists():
        logger.warning(f"Terraform state not found for {project_name}")
        return {}

    terraform_dir = Path(__file__).resolve().parent / "terraform"
    try:
        return TerraformRunner(
            terraform_dir=str(terraform_dir),
            state_path=str(state_path),
        ).output()
    except Exception as exc:
        logger.error(
            "Failed to read Terraform outputs: "
            f"{redact_sensitive(exc)}"
        )
        return {}
