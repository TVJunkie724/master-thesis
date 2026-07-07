"""Safe provider bootstrap planning without executing cloud CLIs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.schemas.cloud_bootstrap import CloudBootstrapPlanRequest, CloudBootstrapPlanResponse
from src.services.permission_sets import active_permission_set_version
from src.services.provider_contract import normalize_provider_id


@dataclass(frozen=True)
class ProviderBootstrapSpec:
    provider: str
    script_path: str
    required_tool: str
    output_auth_type: str
    rotation_flag: str
    default_region: str
    creates: tuple[str, ...]


BOOTSTRAP_SPECS = {
    "aws": ProviderBootstrapSpec(
        provider="aws",
        script_path="bootstrap/aws/bootstrap_deployment_identity.sh",
        required_tool="aws",
        output_auth_type="access_key",
        rotation_flag="--rotate-access-keys",
        default_region="eu-central-1",
        creates=("IAM user", "inline deployment policy", "access key"),
    ),
    "azure": ProviderBootstrapSpec(
        provider="azure",
        script_path="bootstrap/azure/bootstrap_deployment_identity.sh",
        required_tool="az",
        output_auth_type="service_principal",
        rotation_flag="--rotate-client-secret",
        default_region="westeurope",
        creates=("app registration", "service principal", "client secret", "role assignments"),
    ),
    "gcp": ProviderBootstrapSpec(
        provider="gcp",
        script_path="bootstrap/gcp/bootstrap_deployment_identity.sh",
        required_tool="gcloud",
        output_auth_type="service_account_key",
        rotation_flag="--rotate-service-account-keys",
        default_region="europe-west1",
        creates=("custom role", "service account", "IAM binding", "service account key"),
    ),
}


class CloudBootstrapService:
    """Builds explicit, reviewable bootstrap plans for the UI/API contract."""

    def build_plan(self, provider: str, request: CloudBootstrapPlanRequest) -> CloudBootstrapPlanResponse:
        normalized_provider = normalize_provider_id(provider)
        if normalized_provider not in BOOTSTRAP_SPECS:
            raise ValueError("Unsupported bootstrap provider")

        spec = BOOTSTRAP_SPECS[normalized_provider]
        region = request.region or spec.default_region
        provider_args = self._provider_args(normalized_provider, request, region)
        base_command = [spec.script_path, *provider_args, "--name", request.display_name, "--region", region]

        return CloudBootstrapPlanResponse(
            provider=normalized_provider,
            script_path=spec.script_path,
            required_tool=spec.required_tool,
            output_auth_type=spec.output_auth_type,
            permission_set_version=active_permission_set_version(normalized_provider),
            dry_run_command=base_command,
            apply_command=[*base_command, "--apply"],
            rotation_flag=spec.rotation_flag,
            cloud_scope=self._cloud_scope(normalized_provider, request, region),
            creates=list(spec.creates),
            security_notes=[
                "The script is dry-run by default and requires --apply before cloud mutation.",
                "Bootstrap/admin credentials must be configured in the provider CLI session, not sent to this API.",
                "Generated CloudConnection output is local secret material and must not be committed.",
                f"Existing deployment secrets require explicit rotation with {spec.rotation_flag}.",
            ],
        )

    def _provider_args(self, provider: str, request: CloudBootstrapPlanRequest, region: str) -> list[str]:
        if provider == "aws":
            self._require(request.account_id, "account_id")
            return ["--account-id", request.account_id]

        if provider == "azure":
            self._require(request.subscription_id, "subscription_id")
            self._require(request.tenant_id, "tenant_id")
            return ["--subscription-id", request.subscription_id, "--tenant-id", request.tenant_id]

        if provider == "gcp":
            self._require(request.project_id, "project_id")
            args = ["--project-id", request.project_id]
            if request.billing_account:
                args.extend(["--billing-account", request.billing_account])
            return args

        raise ValueError("Unsupported bootstrap provider")

    @staticmethod
    def _cloud_scope(provider: str, request: CloudBootstrapPlanRequest, region: str) -> dict[str, Any]:
        if provider == "aws":
            return {
                "account_id": request.account_id,
                "region": region,
                "identity_name": request.display_name,
            }
        if provider == "azure":
            return {
                "subscription_id": request.subscription_id,
                "tenant_id": request.tenant_id,
                "region": region,
                "identity_name": request.display_name,
            }
        if provider == "gcp":
            return {
                "project_id": request.project_id,
                "billing_account": request.billing_account,
                "region": region,
                "identity_name": request.display_name,
            }
        return {}

    @staticmethod
    def _require(value: str | None, field: str) -> None:
        if not value:
            raise ValueError(f"{field} is required")
