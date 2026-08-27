"""Canonical Terraform destruction and provider fallback lifecycle."""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor, as_completed
import copy
from dataclasses import asdict, dataclass, field
import logging
from pathlib import Path
import time
from typing import Any, TYPE_CHECKING, AsyncIterator

from src.api.deployment_trace import sanitize_deployment_message
from src.cleanup_evidence import CleanupEvidence
from src.providers.cleanup_observability import ProviderCleanupReport
from src.providers.cleanup_registry import CleanupRequest
from src.providers.terraform.cleanup_execution import run_cleanup_attempt
from src.providers.terraform.pre_destroy import run_pre_destroy_cleanup
from src.terraform_runner import TerraformError

if TYPE_CHECKING:
    from src.core.context import DeploymentContext

logger = logging.getLogger(__name__)

_SDK_FALLBACK_POLICIES = frozenset({"never", "on_failure", "always"})
STAGE_COMPLETED_MARKER = "T2MC_STAGE_COMPLETED:"


@dataclass
class DestroyResult:
    """Complete, JSON-serializable outcome of a destroy operation."""

    terraform_success: bool = False
    terraform_error: str | None = None
    sdk_fallback_ran: bool = False
    sdk_fallback_results: dict[str, bool] = field(default_factory=dict)
    dry_run: bool = False
    cleanup_evidence: dict[str, Any] | None = None

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

    _cleanup_reports: dict[str, ProviderCleanupReport]
    _cleanup_evidence: dict[str, Any] | None

    @staticmethod
    def _uses_provider(providers_config: Any, provider: str) -> bool:
        """Return whether any resolved layer selects the provider."""
        if hasattr(providers_config, "model_dump"):
            providers_config = providers_config.model_dump()
        values = (
            providers_config.values()
            if isinstance(providers_config, dict)
            else vars(providers_config).values()
        )
        normalized = {
            "gcp" if str(value).casefold() == "google" else str(value).casefold()
            for value in values
            if value
        }
        return provider in normalized

    def _prepare_destroy_inputs(
        self,
        context: "DeploymentContext | None",
    ) -> bool:
        """Rebuild graph-selected local packages before Terraform destroy."""

        graph = (
            getattr(context, "resolved_deployment_graph", None)
            if context is not None
            else None
        )
        self._resolved_deployment_graph = graph
        self._extension_operation_id = (
            getattr(context, "operation_id", None) if context is not None else None
        )
        if graph is not None:
            self._build_packages()
        if not self.tfvars_path.exists():
            self._generate_tfvars()
        return graph is not None

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

    @staticmethod
    def _state_resource_count(state: dict[str, Any]) -> int:
        """Count resources in the root and every nested child module."""

        def count_module(module: dict[str, Any]) -> int:
            return len(module.get("resources", [])) + sum(
                count_module(child) for child in module.get("child_modules", [])
            )

        root = state.get("values", {}).get("root_module")
        return count_module(root) if isinstance(root, dict) else 0

    def _inspect_terraform_state(self) -> tuple[str, int | None]:
        try:
            count = self._state_resource_count(self.runner.show_state())
        except Exception as exc:
            logger.warning(
                "Could not inspect Terraform state: %s",
                sanitize_deployment_message(str(exc)),
            )
            return "inspection_failed", None
        return ("empty" if count == 0 else "residual"), count

    @staticmethod
    def _retained_shared_prerequisites(
        context: "DeploymentContext | None",
    ) -> list[dict[str, str]]:
        graph = (
            getattr(context, "resolved_deployment_graph", None)
            if context is not None
            else None
        )
        retained: set[tuple[str, str, str, str]] = set()
        for requirement in getattr(graph, "requirements", ()):
            provider = getattr(requirement, "provider", "")
            requirement_type = getattr(requirement, "requirement_type", "")
            if getattr(requirement, "preparation_mode", "") != "confirmed_account" or (
                provider,
                requirement_type,
            ) not in {("azure", "resource_provider"), ("gcp", "api")}:
                continue
            retained.add(
                (
                    provider,
                    requirement_type,
                    getattr(requirement, "capability_id", ""),
                    getattr(requirement, "scope", ""),
                )
            )
        return [
            {
                "provider": provider,
                "requirement_type": requirement_type,
                "capability_id": capability_id,
                "scope": scope,
                "reason": "persistent_account_prerequisite",
            }
            for provider, requirement_type, capability_id, scope in sorted(retained)
        ]

    def _build_cleanup_evidence(
        self,
        *,
        context: "DeploymentContext | None",
        terraform_success: bool,
        dry_run: bool,
        state_before_count: int | None,
        state_after: tuple[str, int | None],
        cleanup_results: dict[str, bool],
        inventory_results: dict[str, ProviderCleanupReport | None],
    ) -> dict[str, Any]:
        state_status, state_after_count = state_after
        residuals: list[dict[str, str | None]] = []
        if not dry_run:
            if not terraform_success:
                residuals.append(
                    {
                        "scope": "terraform_state",
                        "provider": None,
                        "reason": "cleanup_failed",
                    }
                )
            if state_status == "inspection_failed":
                residuals.append(
                    {
                        "scope": "terraform_state",
                        "provider": None,
                        "reason": "inspection_failed",
                    }
                )
            elif state_status == "residual":
                residuals.append(
                    {
                        "scope": "terraform_state",
                        "provider": None,
                        "reason": "resources_remain",
                    }
                )

        providers = []
        provider_ids = sorted(
            (set(cleanup_results) | set(inventory_results)) & {"aws", "azure", "gcp"}
        )
        if (
            context is None
            or cleanup_results.get("context") is False
            or not provider_ids
        ) and not dry_run:
            residuals.append(
                {
                    "scope": "provider_cleanup",
                    "provider": None,
                    "reason": "context_unavailable",
                }
            )
        for provider in provider_ids:
            cleanup_success = cleanup_results.get(provider)
            cleanup_report = self._cleanup_reports.get(provider)
            inventory_report = inventory_results.get(provider)
            if cleanup_success is False:
                residuals.append(
                    {
                        "scope": "provider_cleanup",
                        "provider": provider,
                        "reason": "cleanup_failed",
                    }
                )
            if inventory_report is None and not dry_run:
                residuals.append(
                    {
                        "scope": "provider_inventory",
                        "provider": provider,
                        "reason": "inspection_failed",
                    }
                )
                inventory_status = "inspection_failed"
                residual_count = None
            elif inventory_report is not None:
                residual_count = inventory_report.discovered_resource_count
                inventory_status = "empty" if residual_count == 0 else "residual"
                if residual_count:
                    residuals.append(
                        {
                            "scope": "provider_inventory",
                            "provider": provider,
                            "reason": "resources_remain",
                        }
                    )
            else:
                inventory_status = "not_run"
                residual_count = None

            providers.append(
                {
                    "provider": provider,
                    "cleanup_status": (
                        "completed"
                        if cleanup_success is True
                        else "failed"
                        if cleanup_success is False
                        else "not_run"
                    ),
                    "discovered_during_cleanup_count": (
                        cleanup_report.discovered_resource_count
                        if cleanup_report is not None
                        else None
                    ),
                    "discovered_resource_kinds": (
                        list(cleanup_report.discovered_resource_kinds)
                        if cleanup_report is not None
                        else []
                    ),
                    "post_destroy_inventory": inventory_status,
                    "residual_resource_count": residual_count,
                }
            )

        status = "dry_run" if dry_run else "incomplete" if residuals else "complete"
        evidence = CleanupEvidence.model_validate(
            {
                "status": status,
                "terraform": {
                    "destroy_status": (
                        "dry_run"
                        if dry_run
                        else "completed"
                        if terraform_success
                        else "failed"
                    ),
                    "observed_before_resource_count": state_before_count,
                    "post_destroy_inventory": ("not_run" if dry_run else state_status),
                    "residual_resource_count": (None if dry_run else state_after_count),
                },
                "providers": providers,
                "retained_shared_prerequisites": (
                    self._retained_shared_prerequisites(context)
                ),
                "residual_failures": residuals,
            }
        )
        return evidence.model_dump(mode="json")

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
        self._cleanup_reports = {}
        self._cleanup_evidence = None
        state_before_count: int | None = None
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
                self._prepare_destroy_inputs(context)
                self.runner.init()
                _, state_before_count = self._inspect_terraform_state()
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
            try:
                result.sdk_fallback_results = self._run_sdk_fallback_cleanup(
                    context,
                    dry_run,
                    sdk_timeout_seconds,
                    sdk_max_retries,
                )
            except Exception as exc:
                logger.error(
                    "Provider cleanup setup failed: %s",
                    sanitize_deployment_message(str(exc)),
                )
                result.sdk_fallback_results = {"context": False}
        elif should_run_sdk:
            logger.warning("SDK fallback skipped because no context was provided")
            result.sdk_fallback_results = {"context": False}

        inventory_results = (
            {}
            if dry_run or context is None
            else self._run_post_destroy_provider_inventory(
                context,
                sdk_timeout_seconds,
            )
        )
        state_after = ("not_run", None) if dry_run else self._inspect_terraform_state()
        result.cleanup_evidence = self._build_cleanup_evidence(
            context=context,
            terraform_success=result.terraform_success,
            dry_run=dry_run,
            state_before_count=state_before_count,
            state_after=state_after,
            cleanup_results=result.sdk_fallback_results,
            inventory_results=inventory_results,
        )
        self._cleanup_evidence = result.cleanup_evidence
        return result

    async def destroy_all_async(
        self,
        context: "DeploymentContext | None" = None,
    ) -> AsyncIterator[str]:
        """Destroy through the same lifecycle while streaming Terraform output."""
        self._cleanup_reports = {}
        self._cleanup_evidence = None
        self._ensure_context_credentials(context)
        if self._terraform_outputs is None:
            self._terraform_outputs = self._get_terraform_outputs_safe()
        graph_packages_built = self._prepare_destroy_inputs(context)

        yield "Terraform destroy starting"
        if graph_packages_built:
            yield f"{STAGE_COMPLETED_MARKER}package"
        yield f"{STAGE_COMPLETED_MARKER}preplan"
        yield "[1/4] Terraform init"
        async for line in self.runner.init_async():
            yield line
        _, state_before_count = await asyncio.to_thread(self._inspect_terraform_state)

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
        terraform_success = False
        try:
            async for line in self.runner.destroy_async(str(self.tfvars_path)):
                yield line
            terraform_success = True
            yield f"{STAGE_COMPLETED_MARKER}terraform"
        except Exception as exc:
            logger.error(
                "Terraform destroy failed: %s",
                sanitize_deployment_message(str(exc)),
            )
            yield "Terraform destroy failed; bounded provider cleanup continues"

        yield "[4/4] Provider fallback cleanup"
        cleanup_results: dict[str, bool] = {}
        if context is not None:
            try:
                cleanup_results = await asyncio.to_thread(
                    self._run_sdk_fallback_cleanup,
                    context,
                    False,
                    300,
                    2,
                )
            except Exception as exc:
                logger.error(
                    "Provider cleanup setup failed: %s",
                    sanitize_deployment_message(str(exc)),
                )
                cleanup_results = {"context": False}
        else:
            yield "No context available; provider fallback cleanup skipped"

        yield "Post-destroy inventory"
        inventory_results = (
            await asyncio.to_thread(
                self._run_post_destroy_provider_inventory,
                context,
                300,
            )
            if context is not None
            else {}
        )
        state_after = await asyncio.to_thread(self._inspect_terraform_state)
        self._cleanup_evidence = self._build_cleanup_evidence(
            context=context,
            terraform_success=terraform_success,
            dry_run=False,
            state_before_count=state_before_count,
            state_after=state_after,
            cleanup_results=cleanup_results,
            inventory_results=inventory_results,
        )
        yield f"{STAGE_COMPLETED_MARKER}postapply"
        if self._cleanup_evidence["status"] == "complete":
            yield "Terraform destroy and post-destroy inventory complete"
        else:
            yield "Destroy finished with incomplete cleanup evidence"

    def _cleanup_requests(
        self, context: "DeploymentContext", dry_run: bool
    ) -> list[CleanupRequest]:
        providers_config = context.config.providers
        all_credentials = copy.deepcopy(context.credentials)
        prefix = context.config.digital_twin_name
        if not prefix or len(prefix) < 2:
            raise ValueError("A valid digital twin name is required for SDK cleanup")

        outputs = self._get_terraform_outputs_safe()
        email = context.config.user.get("admin_email", "")
        requests: list[CleanupRequest] = []
        if self._uses_provider(providers_config, "aws"):
            if not all_credentials.get("aws"):
                raise ValueError("AWS cleanup credentials are required")
            requests.append(
                CleanupRequest(
                    provider="aws",
                    credentials={"aws": all_credentials["aws"]},
                    prefix=prefix,
                    cleanup_identity_user=bool(
                        outputs.get("aws_platform_user_created", False)
                    ),
                    platform_user_email=email,
                    dry_run=dry_run,
                )
            )
        if self._uses_provider(providers_config, "azure"):
            if not all_credentials.get("azure"):
                raise ValueError("Azure cleanup credentials are required")
            requests.append(
                CleanupRequest(
                    provider="azure",
                    credentials={"azure": all_credentials["azure"]},
                    prefix=prefix,
                    cleanup_identity_user=bool(
                        outputs.get("azure_platform_user_created", False)
                    ),
                    platform_user_email=email,
                    dry_run=dry_run,
                )
            )
        if self._uses_provider(providers_config, "gcp"):
            if not all_credentials.get("gcp"):
                raise ValueError("GCP cleanup credentials are required")
            gcp_credentials = all_credentials.get("gcp", {})
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
                    credentials={"gcp": gcp_credentials},
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
        self._cleanup_reports = {}
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
                    report = future.result()
                    results[provider] = isinstance(report, ProviderCleanupReport)
                    if isinstance(report, ProviderCleanupReport):
                        self._cleanup_reports[provider] = report
                except Exception as exc:
                    logger.error(
                        "%s cleanup supervision failed: %s",
                        provider.upper(),
                        sanitize_deployment_message(str(exc)),
                    )
                    results[provider] = False
        return results

    def _run_post_destroy_provider_inventory(
        self,
        context: "DeploymentContext",
        timeout_seconds: int,
    ) -> dict[str, ProviderCleanupReport | None]:
        """Run one read-only scan of every provider cleanup catalog."""
        try:
            requests = self._cleanup_requests(context, dry_run=True)
        except Exception as exc:
            logger.error(
                "Post-destroy inventory setup failed: %s",
                sanitize_deployment_message(str(exc)),
            )
            return {provider: None for provider in sorted(self._cleanup_reports)}
        if not requests:
            return {}

        results: dict[str, ProviderCleanupReport | None] = {}
        with ThreadPoolExecutor(max_workers=len(requests)) as executor:
            futures = {
                executor.submit(
                    self._run_with_retry_and_timeout,
                    request,
                    0,
                    timeout_seconds,
                ): request.provider
                for request in requests
            }
            for future in as_completed(futures):
                provider = futures[future]
                try:
                    report = future.result()
                    results[provider] = (
                        report if isinstance(report, ProviderCleanupReport) else None
                    )
                except Exception as exc:
                    logger.error(
                        "%s post-destroy inventory supervision failed: %s",
                        provider.upper(),
                        sanitize_deployment_message(str(exc)),
                    )
                    results[provider] = None
        return results

    def _run_with_retry_and_timeout(
        self,
        request: CleanupRequest,
        max_retries: int,
        timeout_seconds: int,
    ) -> ProviderCleanupReport | bool:
        for attempt in range(max_retries + 1):
            try:
                return run_cleanup_attempt(request, timeout_seconds)
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
        """Return whether Terraform state contains root or child resources."""
        status, _ = self._inspect_terraform_state()
        if status == "inspection_failed":
            raise RuntimeError("Terraform state inspection failed")
        return status == "residual"

    def get_cleanup_evidence(self) -> dict[str, Any] | None:
        """Return the validated terminal destroy evidence, when available."""
        return self._cleanup_evidence

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
