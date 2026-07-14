"""Stable facade for the canonical Terraform deployment lifecycle."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from src.api.deployment_trace import sanitize_deployment_message
from src.core.config_loader import load_credentials, load_providers_config
from src.providers.terraform.deployment_lifecycle import DeploymentLifecycleMixin
from src.providers.terraform.destruction_lifecycle import (
    DestructionLifecycleMixin,
    DestroyResult,
)
from src.providers.terraform.provider_runtime import (
    initialize_providers,
    run_post_deployment,
)
from src.terraform_runner import TerraformRunner
from src.tfvars_generator import ConfigurationError, generate_tfvars
from src.validation.directory_validator import validate_project_directory

if TYPE_CHECKING:
    from src.core.context import DeploymentContext

logger = logging.getLogger(__name__)

PREFLIGHT_VALID_STATUS = "valid"


class TerraformDeployerStrategy(DeploymentLifecycleMixin, DestructionLifecycleMixin):
    """Coordinate Terraform with explicitly SDK-owned lifecycle operations."""

    def __init__(self, terraform_dir: str, project_path: str):
        if not terraform_dir:
            raise ValueError("terraform_dir is required")
        if not project_path:
            raise ValueError("project_path is required")

        self.terraform_dir = Path(terraform_dir)
        self.project_path = Path(project_path)
        self.tfvars_path = self.project_path / "terraform" / "generated.tfvars.json"
        self.state_path = self.project_path / "terraform" / "terraform.tfstate"
        self._runner: TerraformRunner | None = None
        self._providers_config: dict | None = None
        self._terraform_outputs: dict | None = None

    @property
    def runner(self) -> TerraformRunner:
        if self._runner is None:
            self._runner = TerraformRunner(
                terraform_dir=str(self.terraform_dir),
                state_path=str(self.state_path),
            )
        return self._runner

    def _load_providers_config(self) -> dict:
        if self._providers_config is None:
            self._providers_config = load_providers_config(self.project_path)
        return self._providers_config

    def _load_credentials(self) -> dict:
        credentials = load_credentials(self.project_path)
        if not credentials:
            raise ConfigurationError(
                f"No credentials found for project: {self.project_path}"
            )
        return credentials

    def _generate_tfvars(self) -> None:
        self.tfvars_path.parent.mkdir(parents=True, exist_ok=True)
        generate_tfvars(str(self.project_path), str(self.tfvars_path))

    def _build_packages(self) -> None:
        from src.providers.terraform.package_builder import build_all_packages

        build_all_packages(
            self.terraform_dir,
            self.project_path,
            self._load_providers_config(),
        )

    def _validate_project(self) -> None:
        validate_project_directory(self.project_path)

    def _validate_credentials(self) -> None:
        providers = self._load_providers_config()
        credentials = self._load_credentials()
        used_clouds = {
            "gcp" if cloud == "google" else cloud
            for key, cloud in providers.items()
            if key.startswith("layer_")
            and key.endswith("_provider")
            and isinstance(cloud, str)
            and cloud
        }

        if "azure" in used_clouds:
            from src.api.azure_credentials_checker import check_azure_credentials

            azure_credentials = credentials.get("azure")
            if not azure_credentials:
                raise ValueError(
                    "Azure is configured but no Azure credentials were provided"
                )
            self._assert_preflight_valid(
                "Azure",
                check_azure_credentials(azure_credentials),
            )

        if "aws" in used_clouds:
            from src.api.credentials_checker import check_aws_credentials

            aws_credentials = credentials.get("aws")
            if not aws_credentials:
                raise ValueError("AWS is configured but no AWS credentials were provided")
            self._assert_preflight_valid(
                "AWS",
                check_aws_credentials(aws_credentials),
            )

        if "gcp" in used_clouds:
            from src.api.gcp_credentials_checker import check_gcp_credentials

            gcp_credentials = credentials.get("gcp")
            if not gcp_credentials:
                raise ValueError("GCP is configured but no GCP credentials were provided")
            self._assert_preflight_valid(
                "GCP",
                check_gcp_credentials(gcp_credentials),
            )

    @staticmethod
    def _assert_preflight_valid(provider: str, result: dict) -> None:
        status = result.get("status", "error")
        if status == PREFLIGHT_VALID_STATUS:
            return
        message = sanitize_deployment_message(
            str(result.get("message", "No message provided"))
        )
        raise ValueError(
            f"{provider} credential preflight failed ({status}): {message}"
        )

    def _initialize_providers(self, context: "DeploymentContext") -> None:
        initialize_providers(
            context,
            self._load_providers_config(),
            self._load_credentials(),
        )

    def _run_post_deployment(self, context: "DeploymentContext") -> None:
        run_post_deployment(
            context,
            self.project_path,
            self._load_providers_config(),
            self._terraform_outputs or {},
        )

    @staticmethod
    def _uses_provider(providers_config: dict, cloud: str) -> bool:
        aliases = {cloud}
        if cloud == "gcp":
            aliases.add("google")
        return any(
            value in aliases
            for key, value in providers_config.items()
            if key.startswith("layer_") and key.endswith("_provider")
        )

    def get_outputs(self) -> dict:
        if self._terraform_outputs is None:
            self._terraform_outputs = self.runner.output()
        return self._terraform_outputs


__all__ = ["DestroyResult", "TerraformDeployerStrategy"]
