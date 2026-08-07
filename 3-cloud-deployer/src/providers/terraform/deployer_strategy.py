"""Stable facade for the canonical Terraform deployment lifecycle."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING

from src.api.deployment_trace import sanitize_deployment_message
from src.core.secure_files import atomic_write_private_bytes
from src.core.config_loader import load_credentials, load_providers_config
from src.providers.terraform.deployment_lifecycle import DeploymentLifecycleMixin
from src.providers.terraform.destruction_lifecycle import (
    DestructionLifecycleMixin,
    DestroyResult,
)
from src.providers.terraform.provider_runtime import (
    initialize_providers,
    prepare_shared_identity_capabilities,
    run_post_deployment,
)
from src.providers.terraform.gcp_v2_image_publisher import (
    GcpV2ImagePublisher,
    gcp_v2_container_deployment,
    image_requests as gcp_v2_image_requests,
    image_tfvars as gcp_v2_image_tfvars,
    placeholder_image_tfvars,
)
from src.providers.terraform.aws_v2_image_publisher import (
    AwsV2ImagePublisher,
    aws_v2_container_deployment,
    image_requests as aws_v2_image_requests,
    image_tfvars as aws_v2_image_tfvars,
)
from src.terraform_runner import TerraformRunner
from src.tfvars_generator import ConfigurationError, generate_tfvars
from src.validation.directory_validator import validate_project_directory

if TYPE_CHECKING:
    from src.core.context import DeploymentContext

logger = logging.getLogger(__name__)

PREFLIGHT_VALID_STATUS = "valid"
GCP_V2_IMAGE_FOUNDATION_TARGETS = (
    "google_artifact_registry_repository.gcp_gcp_artifact_registry_if_container_selected",
    "google_storage_bucket.gcp_v2_cloud_build_sources",
    'google_service_account.gcp_v2_runtime["build"]',
    "google_artifact_registry_repository_iam_member.gcp_v2_build_writer",
    "google_storage_bucket_iam_member.gcp_v2_build_source_reader",
    "google_project_iam_member.gcp_v2_build_log_writer",
)
AWS_V2_IMAGE_FOUNDATION_TARGETS = (
    "aws_ecr_repository.aws_aws_ecr_if_container_selected",
    "aws_s3_bucket.aws_aws_ecr_if_container_selected",
    "aws_s3_bucket_lifecycle_configuration.aws_aws_ecr_if_container_selected",
    "aws_s3_bucket_public_access_block.aws_aws_ecr_if_container_selected",
    "aws_s3_bucket_server_side_encryption_configuration.aws_aws_ecr_if_container_selected",
    "aws_iam_role.aws_aws_ecr_if_container_selected",
    "aws_iam_role_policy.aws_aws_ecr_if_container_selected",
    "aws_codebuild_project.aws_aws_ecr_if_container_selected",
)


class TerraformDeployerStrategy(DeploymentLifecycleMixin, DestructionLifecycleMixin):
    """Coordinate Terraform with explicitly SDK-owned lifecycle operations."""

    GCP_V2_IMAGE_FOUNDATION_TARGETS = GCP_V2_IMAGE_FOUNDATION_TARGETS
    AWS_V2_IMAGE_FOUNDATION_TARGETS = AWS_V2_IMAGE_FOUNDATION_TARGETS

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
        self._preplan_tfvars: dict = {}
        self._built_packages: dict[str, Path] = {}

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
        if self._preplan_tfvars:
            generated = json.loads(self.tfvars_path.read_text(encoding="utf-8"))
            generated.update(self._preplan_tfvars)
            self.tfvars_path.write_text(
                json.dumps(generated, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )

    def _read_tfvars(self) -> dict:
        value = json.loads(self.tfvars_path.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise ConfigurationError("Generated Terraform variables are invalid")
        return value

    def _merge_tfvars(self, values: dict) -> dict:
        generated = self._read_tfvars()
        generated.update(values)
        atomic_write_private_bytes(
            self.tfvars_path,
            (json.dumps(generated, indent=2, sort_keys=True) + "\n").encode(),
        )
        return generated

    def _prepare_gcp_v2_image_foundation(self) -> bool:
        generated = self._read_tfvars()
        if not gcp_v2_container_deployment(generated):
            return False
        self._merge_tfvars(placeholder_image_tfvars(generated))
        return True

    def _prepare_aws_v2_image_foundation(self) -> bool:
        return aws_v2_container_deployment(self._read_tfvars())

    def _image_foundation_targets(self) -> tuple[str, ...]:
        values: list[str] = []
        if getattr(self, "_aws_v2_image_foundation_required", False):
            values.extend(self.AWS_V2_IMAGE_FOUNDATION_TARGETS)
        if getattr(self, "_gcp_v2_image_foundation_required", False):
            values.extend(self.GCP_V2_IMAGE_FOUNDATION_TARGETS)
        return tuple(values)

    def _publish_aws_v2_images(self) -> None:
        generated = self._read_tfvars()
        outputs = self.runner.output()
        publisher = AwsV2ImagePublisher.from_tfvars_and_outputs(
            project_path=self.project_path,
            tfvars=generated,
            outputs=outputs,
        )
        images = publisher.publish(aws_v2_image_requests(self.project_path, generated))
        self._merge_tfvars(aws_v2_image_tfvars(images, generated))

    def _publish_gcp_v2_images(self) -> None:
        generated = self._read_tfvars()
        outputs = self.runner.output()
        publisher = GcpV2ImagePublisher.from_tfvars_and_outputs(
            project_path=self.project_path,
            tfvars=generated,
            outputs=outputs,
        )
        images = publisher.publish(gcp_v2_image_requests(self.project_path, generated))
        self._merge_tfvars(gcp_v2_image_tfvars(images, generated))

    def _gcp_kubernetes_state_exists(self) -> bool:
        result = self.runner.state_list()
        return result.returncode == 0 and any(
            line.startswith("kubernetes_") for line in result.stdout.splitlines()
        )

    def _build_packages(self) -> None:
        from src.providers.terraform.package_builder import build_all_packages

        self._built_packages = build_all_packages(
            self.terraform_dir,
            self.project_path,
            self._load_providers_config(),
            operation_id=getattr(self, "_extension_operation_id", None),
            graph=getattr(self, "_resolved_deployment_graph", None),
        )

    def _validate_project(self) -> None:
        validate_project_directory(
            self.project_path,
            require_deployment_manifest=True,
        )

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
                raise ValueError(
                    "AWS is configured but no AWS credentials were provided"
                )
            self._assert_preflight_valid(
                "AWS",
                check_aws_credentials(aws_credentials),
            )

        if "gcp" in used_clouds:
            from src.api.gcp_credentials_checker import check_gcp_credentials

            gcp_credentials = credentials.get("gcp")
            if not gcp_credentials:
                raise ValueError(
                    "GCP is configured but no GCP credentials were provided"
                )
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

    def _prepare_shared_identity_capabilities(
        self,
        context: "DeploymentContext",
    ) -> None:
        self._preplan_tfvars = prepare_shared_identity_capabilities(context)

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
