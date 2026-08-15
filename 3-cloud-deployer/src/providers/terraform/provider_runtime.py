"""Provider SDK lifecycle operations around Terraform infrastructure changes."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from src.deployment_access.runtime_evidence import (
    DeploymentAccessRuntimeEvidence,
    collect_deployment_access_runtime_evidence,
)

from src.providers.terraform.aws_deployer import (
    configure_aws_grafana,
    create_twinmaker_entities,
    register_aws_iot_devices,
)
from src.providers.terraform.azure_deployer import (
    configure_azure_grafana,
    register_azure_iot_devices,
    upload_dtdl_models,
)
from src.providers.terraform.cross_cloud_identity import (
    aws_outbound_identity_destinations,
    ensure_aws_outbound_identity,
)
from src.providers.terraform.cross_cloud_routes import cross_cloud_route_tfvars

if TYPE_CHECKING:
    from src.core.context import DeploymentContext

logger = logging.getLogger(__name__)

_SDK_LAYER_KEYS = ("layer_1_provider", "layer_4_provider", "layer_5_provider")
_SDK_POST_DEPLOYMENT_PROVIDERS = frozenset({"aws", "azure"})


def normalize_provider_name(provider: str) -> str:
    """Return the canonical runtime provider identifier."""
    normalized = provider.strip().lower()
    return "gcp" if normalized == "google" else normalized


def configured_runtime_providers(
    providers_config: dict,
    graph=None,
) -> set[str]:
    """Return providers needing postapply or graph preplan SDK clients."""
    providers = {
        normalize_provider_name(provider)
        for key in _SDK_LAYER_KEYS
        if isinstance((provider := providers_config.get(key)), str) and provider.strip()
        if normalize_provider_name(provider) in _SDK_POST_DEPLOYMENT_PROVIDERS
    }
    if "azure" in aws_outbound_identity_destinations(graph):
        # An AWS SDK client is also required when a non-L1/L4/L5 AWS node is
        # the source of an AWS-to-Azure workload-identity edge.
        providers.add("aws")
    return providers


def initialize_providers(
    context: "DeploymentContext",
    providers_config: dict,
    credentials: dict,
) -> None:
    """Initialize each configured provider once and attach it to the context."""
    context.credentials = credentials
    used_clouds = configured_runtime_providers(
        providers_config,
        getattr(context, "resolved_deployment_graph", None),
    )
    logger.info(
        "Clouds requiring SDK initialization: %s",
        ", ".join(sorted(used_clouds)) or "none",
    )

    if "azure" in used_clouds and "azure" not in context.providers:
        from src.providers.azure.provider import AzureProvider

        provider = AzureProvider()
        provider.initialize_clients(
            credentials.get("azure", {}),
            context.config.digital_twin_name,
        )
        context.providers["azure"] = provider

    if "aws" in used_clouds and "aws" not in context.providers:
        from src.providers.aws.provider import AWSProvider

        provider = AWSProvider()
        provider.initialize_clients(
            credentials.get("aws", {}),
            context.config.digital_twin_name,
        )
        context.providers["aws"] = provider


def prepare_shared_identity_capabilities(
    context: "DeploymentContext",
) -> dict:
    """Prepare graph-required account capabilities after deploy confirmation."""

    readiness = ensure_aws_outbound_identity(
        context,
        getattr(context, "resolved_deployment_graph", None),
    )
    if readiness.required:
        logger.info(
            "AWS outbound workload identity ready for: %s",
            ", ".join(readiness.destination_providers),
        )
    return {
        **readiness.to_tfvars(),
        **cross_cloud_route_tfvars(getattr(context, "resolved_deployment_graph", None)),
    }


def run_post_deployment(
    context: "DeploymentContext",
    project_path: Path,
    providers_config: dict,
    terraform_outputs: dict,
) -> DeploymentAccessRuntimeEvidence | None:
    """Create resources that deliberately remain outside Terraform ownership."""
    required = ("layer_1_provider", "layer_4_provider", "layer_5_provider")
    missing = [key for key in required if key not in providers_config]
    if missing:
        raise ValueError(
            "Missing required provider config: " + ", ".join(sorted(missing))
        )

    if providers_config["layer_4_provider"] == "azure":
        upload_dtdl_models(context, project_path)
    if providers_config["layer_1_provider"] == "azure":
        register_azure_iot_devices(context, project_path)
    if providers_config["layer_5_provider"] == "azure":
        configure_azure_grafana(context, terraform_outputs)

    if providers_config["layer_4_provider"] == "aws":
        create_twinmaker_entities(context, project_path, terraform_outputs)
    if providers_config["layer_1_provider"] == "aws":
        register_aws_iot_devices(context, project_path)
    if providers_config["layer_5_provider"] == "aws":
        configure_aws_grafana(context, terraform_outputs)

    return collect_deployment_access_runtime_evidence(context, terraform_outputs)
