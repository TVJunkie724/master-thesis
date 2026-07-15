"""Canonical synchronous and streaming Terraform deployment lifecycle."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, AsyncIterator

from src.providers.terraform.deployment_metadata import mark_built_packages_deployed
if TYPE_CHECKING:
    from src.core.context import DeploymentContext

logger = logging.getLogger(__name__)


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
        self._build_packages()
        self._generate_tfvars()

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
        self.runner.apply(var_file=str(self.tfvars_path))
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
        self._build_packages()
        self._generate_tfvars()

        yield "[4/7] Terraform init"
        async for line in self.runner.init_async():
            yield line
        yield "[5/7] Terraform apply"
        async for line in self.runner.apply_async(str(self.tfvars_path)):
            yield line

        self._terraform_outputs = self.runner.output()
        deployed_packages = self._record_applied_packages()
        yield f"[6/7] Recorded {deployed_packages} applied user function packages"
        yield "[7/7] Running SDK-owned post-deployment operations"
        await asyncio.to_thread(self._run_post_deployment, context)
        yield "Terraform deployment complete"
