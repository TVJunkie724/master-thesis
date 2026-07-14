"""Canonical Terraform destruction and provider fallback lifecycle."""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor, as_completed
import copy
from dataclasses import asdict, dataclass, field
import logging
from pathlib import Path
import time
from typing import TYPE_CHECKING, AsyncIterator

from src.api.deployment_trace import sanitize_deployment_message
from src.providers.cleanup_registry import CleanupRequest
from src.providers.terraform.cleanup_execution import run_cleanup_attempt
from src.providers.terraform.pre_destroy import run_pre_destroy_cleanup
from src.terraform_runner import TerraformError

if TYPE_CHECKING:
    from src.core.context import DeploymentContext

logger = logging.getLogger(__name__)

_SDK_FALLBACK_POLICIES = frozenset({"never", "on_failure", "always"})


@dataclass
class DestroyResult:
    """Complete, JSON-serializable outcome of a destroy operation."""

    terraform_success: bool = False
    terraform_error: str | None = None
    sdk_fallback_ran: bool = False
    sdk_fallback_results: dict[str, bool] = field(default_factory=dict)
    dry_run: bool = False

    @property
    def sdk_fallback_success(self) -> bool:
        return all(self.sdk_fallback_results.values())

    @property
    def success(self) -> bool:
        return self.terraform_success and self.sdk_fallback_success

    def to_dict(self) -> dict:
        return {
            **asdict(self),
            "sdk_fallback_success": self.sdk_fallback_success,
            "success": self.success,
        }


class DestructionLifecycleMixin:
    """Destruction behavior shared by the stable strategy facade."""

    @staticmethod
    def _validate_destroy_policy(
        sdk_fallback: str,
        sdk_timeout_seconds: int,
        sdk_max_retries: int,
    ) -> None:
        if sdk_fallback not in _SDK_FALLBACK_POLICIES:
            allowed = ", ".join(sorted(_SDK_FALLBACK_POLICIES))
            raise ValueError(f"sdk_fallback must be one of: {allowed}")
        if sdk_timeout_seconds <= 0:
            raise ValueError("sdk_timeout_seconds must be greater than zero")
        if sdk_max_retries < 0:
            raise ValueError("sdk_max_retries must not be negative")

    def _ensure_context_credentials(self, context: "DeploymentContext | None") -> None:
        if context is None or context.credentials:
            return
        try:
            context.credentials = self._load_credentials()
        except Exception as exc:
            logger.warning(
                "Could not load credentials for destroy cleanup: %s",
                sanitize_deployment_message(str(exc)),
            )

    def _pre_destroy_cleanup(
        self,
        context: "DeploymentContext",
        *,
        dry_run: bool,
    ) -> None:
        run_pre_destroy_cleanup(
            context,
            self._load_providers_config(),
            dry_run=dry_run,
        )

    def destroy_all(
        self,
        context: "DeploymentContext | None" = None,
        sdk_fallback: str = "always",
        dry_run: bool = False,
        sdk_timeout_seconds: int = 300,
        sdk_max_retries: int = 2,
    ) -> DestroyResult:
        """Destroy Terraform resources and run one bounded fallback cleanup."""
        self._validate_destroy_policy(
            sdk_fallback,
            sdk_timeout_seconds,
            sdk_max_retries,
        )
        result = DestroyResult(dry_run=dry_run)
        self._ensure_context_credentials(context)
        if self._terraform_outputs is None:
            self._terraform_outputs = self._get_terraform_outputs_safe()

        if context is not None and context.credentials:
            self._pre_destroy_cleanup(context, dry_run=dry_run)

        if dry_run:
            logger.info("Dry run: Terraform destroy was not executed")
            result.terraform_success = True
        else:
            try:
                if not self.tfvars_path.exists():
                    self._generate_tfvars()
                self.runner.init()
                self.runner.destroy(var_file=str(self.tfvars_path))
                result.terraform_success = True
            except TerraformError as exc:
                result.terraform_error = sanitize_deployment_message(str(exc))
                logger.error("Terraform destroy failed: %s", result.terraform_error)

        should_run_sdk = sdk_fallback == "always" or (
            sdk_fallback == "on_failure" and not result.terraform_success
        )
        if should_run_sdk and context is not None:
            result.sdk_fallback_ran = True
            result.sdk_fallback_results = self._run_sdk_fallback_cleanup(
                context,
                dry_run,
                sdk_timeout_seconds,
                sdk_max_retries,
            )
        elif should_run_sdk:
            logger.warning("SDK fallback skipped because no context was provided")

        return result

    async def destroy_all_async(
        self,
        context: "DeploymentContext | None" = None,
    ) -> AsyncIterator[str]:
        """Destroy through the same lifecycle while streaming Terraform output."""
        self._ensure_context_credentials(context)
        if self._terraform_outputs is None:
            self._terraform_outputs = self._get_terraform_outputs_safe()
        if not self.tfvars_path.exists():
            self._generate_tfvars()

        yield "Terraform destroy starting"
        yield "[1/4] Terraform init"
        async for line in self.runner.init_async():
            yield line

        yield "[2/4] Pre-destroy cleanup"
        if context is not None and context.credentials:
            await asyncio.to_thread(
                self._pre_destroy_cleanup,
                context,
                dry_run=False,
            )
        else:
            yield "No credentials available; pre-destroy cleanup skipped"

        yield "[3/4] Terraform destroy"
        async for line in self.runner.destroy_async(str(self.tfvars_path)):
            yield line

        yield "[4/4] Provider fallback cleanup"
        if context is not None:
            results = await asyncio.to_thread(
                self._run_sdk_fallback_cleanup,
                context,
                False,
                300,
                2,
            )
            failed = sorted(name for name, success in results.items() if not success)
            if failed:
                raise RuntimeError(
                    "Provider fallback cleanup failed: " + ", ".join(failed)
                )
        else:
            yield "No context available; provider fallback cleanup skipped"
        yield "Terraform destroy complete"

    def _cleanup_requests(self, context: "DeploymentContext", dry_run: bool) -> list[CleanupRequest]:
        providers_config = context.config.providers
        credentials = copy.deepcopy(context.credentials)
        prefix = context.config.digital_twin_name
        if not prefix or len(prefix) < 2:
            raise ValueError("A valid digital twin name is required for SDK cleanup")

        outputs = self._get_terraform_outputs_safe()
        email = context.config.user.get("admin_email", "")
        requests: list[CleanupRequest] = []
        if self._uses_provider(providers_config, "aws"):
            if not credentials.get("aws"):
                raise ValueError("AWS cleanup credentials are required")
            requests.append(
                CleanupRequest(
                    provider="aws",
                    credentials=credentials,
                    prefix=prefix,
                    cleanup_identity_user=bool(
                        outputs.get("aws_platform_user_created", False)
                    ),
                    platform_user_email=email,
                    dry_run=dry_run,
                )
            )
        if self._uses_provider(providers_config, "azure"):
            if not credentials.get("azure"):
                raise ValueError("Azure cleanup credentials are required")
            requests.append(
                CleanupRequest(
                    provider="azure",
                    credentials=credentials,
                    prefix=prefix,
                    cleanup_identity_user=bool(
                        outputs.get("azure_platform_user_created", False)
                    ),
                    platform_user_email=email,
                    dry_run=dry_run,
                )
            )
        if self._uses_provider(providers_config, "gcp"):
            if not credentials.get("gcp"):
                raise ValueError("GCP cleanup credentials are required")
            gcp_credentials = credentials.get("gcp", {})
            if not gcp_credentials.get("gcp_project_id") and outputs.get(
                "gcp_project_id"
            ):
                gcp_credentials["gcp_project_id"] = outputs["gcp_project_id"]
            credentials_path = gcp_credentials.get("gcp_credentials_file")
            if (
                isinstance(credentials_path, str)
                and credentials_path
                and not credentials_path.lstrip().startswith("{")
            ):
                path = Path(credentials_path)
                if not path.is_absolute():
                    gcp_credentials["gcp_credentials_file"] = str(
                        self.project_path / path
                    )
            requests.append(
                CleanupRequest(
                    provider="gcp",
                    credentials=credentials,
                    prefix=prefix,
                    dry_run=dry_run,
                )
            )
        return requests

    def _run_sdk_fallback_cleanup(
        self,
        context: "DeploymentContext",
        dry_run: bool,
        timeout_seconds: int,
        max_retries: int,
    ) -> dict[str, bool]:
        requests = self._cleanup_requests(context, dry_run)
        if not requests:
            return {}

        results: dict[str, bool] = {}
        with ThreadPoolExecutor(max_workers=len(requests)) as executor:
            futures = {
                executor.submit(
                    self._run_with_retry_and_timeout,
                    request,
                    max_retries,
                    timeout_seconds,
                ): request.provider
                for request in requests
            }
            for future in as_completed(futures):
                provider = futures[future]
                try:
                    results[provider] = future.result()
                except Exception as exc:
                    logger.error(
                        "%s cleanup supervision failed: %s",
                        provider.upper(),
                        sanitize_deployment_message(str(exc)),
                    )
                    results[provider] = False
        return results

    def _run_with_retry_and_timeout(
        self,
        request: CleanupRequest,
        max_retries: int,
        timeout_seconds: int,
    ) -> bool:
        for attempt in range(max_retries + 1):
            try:
                run_cleanup_attempt(request, timeout_seconds)
                return True
            except Exception as exc:
                logger.warning(
                    "%s cleanup attempt %d/%d failed: %s",
                    request.provider.upper(),
                    attempt + 1,
                    max_retries + 1,
                    sanitize_deployment_message(str(exc)),
                )
                if attempt < max_retries:
                    time.sleep(5 * (attempt + 1))
        return False

    def has_deployed_resources(self) -> bool:
        """Return whether the Terraform state contains root resources."""
        try:
            state = self.runner.show_state()
        except Exception as exc:
            logger.warning(
                "Could not inspect Terraform state: %s",
                sanitize_deployment_message(str(exc)),
            )
            return False
        resources = state.get("values", {}).get("root_module", {}).get("resources", [])
        return bool(resources)

    def _get_terraform_outputs_safe(self) -> dict:
        if self._terraform_outputs is not None:
            return self._terraform_outputs
        try:
            return self.runner.output()
        except Exception as exc:
            logger.warning(
                "Could not read Terraform outputs: %s",
                sanitize_deployment_message(str(exc)),
            )
            return {}
