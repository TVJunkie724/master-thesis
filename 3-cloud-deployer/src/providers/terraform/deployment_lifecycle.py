"""Canonical synchronous and streaming Terraform deployment lifecycle."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, AsyncIterator

from src.providers.terraform.deployment_metadata import mark_built_packages_deployed

if TYPE_CHECKING:
    from src.core.context import DeploymentContext

logger = logging.getLogger(__name__)
STAGE_COMPLETED_MARKER = "T2MC_STAGE_COMPLETED:"


class DeploymentLifecycleMixin:
    """Deployment behavior shared by the stable strategy facade."""

    def _prepare_deployment(
        self,
        context: "DeploymentContext",
        *,
        skip_credential_check: bool,
    ) -> None:
        if not skip_credential_check:
            self._validate_credentials()
        self._initialize_providers(context)
        self._validate_project()
        self._extension_operation_id = context.operation_id
        self._resolved_deployment_graph = getattr(
            context,
            "resolved_deployment_graph",
            None,
        )
        self._prepare_shared_identity_capabilities(context)
        self._build_packages()
        self._generate_tfvars()
        self._gcp_v2_image_foundation_required = (
            self._prepare_gcp_v2_image_foundation()
        )

    def _apply_infrastructure(self) -> None:
        """Apply the reviewed GCP image/Kubernetes stages or one normal apply."""

        if not getattr(self, "_gcp_v2_image_foundation_required", False):
            self.runner.apply(var_file=str(self.tfvars_path))
            return
        kubernetes_already_applied = self._gcp_kubernetes_state_exists()
        self.runner.apply_targets(
            str(self.tfvars_path),
            self.GCP_V2_IMAGE_FOUNDATION_TARGETS,
        )
        self._publish_gcp_v2_images()
        if not kubernetes_already_applied:
            self.runner.apply(var_file=str(self.tfvars_path))
        self._merge_tfvars({"gcp_v2_kubernetes_stage_enabled": True})
        self.runner.apply(var_file=str(self.tfvars_path))

    def _record_applied_packages(self) -> int:
        return mark_built_packages_deployed(self.project_path)

    def deploy_all(
        self,
        context: "DeploymentContext | None" = None,
        skip_credential_check: bool = False,
    ) -> dict:
        """Deploy infrastructure and complete SDK-owned post-deployment work."""
        if context is None:
            raise ValueError("DeploymentContext is required for SDK operations")

        logger.info("Terraform deployment starting")
        self._prepare_deployment(
            context,
            skip_credential_check=skip_credential_check,
        )
        self.runner.init()
        self._apply_infrastructure()
        self._terraform_outputs = self.runner.output()
        deployed_packages = self._record_applied_packages()
        logger.info("Recorded %d applied user function packages", deployed_packages)
        self._run_post_deployment(context)
        logger.info("Terraform deployment complete")
        return self._terraform_outputs

    async def deploy_all_async(
        self,
        context: "DeploymentContext | None" = None,
        skip_credential_check: bool = False,
    ) -> AsyncIterator[str]:
        """Deploy through the same canonical lifecycle while streaming Terraform."""
        if context is None:
            raise ValueError("DeploymentContext is required for SDK operations")

        yield "Terraform deployment starting"
        if not skip_credential_check:
            yield "[1/7] Validating cloud credentials"
            self._validate_credentials()
        else:
            yield "[1/7] Credential validation explicitly skipped"

        yield "[2/7] Initializing provider SDK clients"
        self._initialize_providers(context)
        yield "[3/7] Validating project and building packages"
        self._validate_project()
        self._extension_operation_id = context.operation_id
        self._resolved_deployment_graph = getattr(
            context,
            "resolved_deployment_graph",
            None,
        )
        self._prepare_shared_identity_capabilities(context)
        self._build_packages()
        yield f"{STAGE_COMPLETED_MARKER}package"
        self._generate_tfvars()
        self._gcp_v2_image_foundation_required = (
            self._prepare_gcp_v2_image_foundation()
        )
        yield f"{STAGE_COMPLETED_MARKER}preplan"

        yield "[4/7] Terraform init"
        async for line in self.runner.init_async():
            yield line
        if getattr(self, "_gcp_v2_image_foundation_required", False):
            kubernetes_already_applied = await asyncio.to_thread(
                self._gcp_kubernetes_state_exists
            )
            yield "[5/9] Creating the GCP image foundation"
            async for line in self.runner.apply_targets_async(
                str(self.tfvars_path),
                self.GCP_V2_IMAGE_FOUNDATION_TARGETS,
            ):
                yield line
            yield "[6/9] Publishing content-addressed GCP images"
            await asyncio.to_thread(self._publish_gcp_v2_images)
            if not kubernetes_already_applied:
                yield "[7/9] Applying cloud-provider resources"
                async for line in self.runner.apply_async(str(self.tfvars_path)):
                    yield line
            self._merge_tfvars({"gcp_v2_kubernetes_stage_enabled": True})
            yield "[8/9] Applying post-cluster Kubernetes resources"
            async for line in self.runner.apply_async(str(self.tfvars_path)):
                yield line
        else:
            yield "[5/7] Terraform apply"
            async for line in self.runner.apply_async(str(self.tfvars_path)):
                yield line

        self._terraform_outputs = self.runner.output()
        yield f"{STAGE_COMPLETED_MARKER}terraform"
        deployed_packages = self._record_applied_packages()
        yield f"Recorded {deployed_packages} applied user function packages"
        yield "Running SDK-owned post-deployment operations"
        await asyncio.to_thread(self._run_post_deployment, context)
        yield f"{STAGE_COMPLETED_MARKER}postapply"
        yield "Terraform deployment complete"
