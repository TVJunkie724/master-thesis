"""Provider cleanup registry for SDK fallback cleanup.

The cleanup registry is the single dispatcher from orchestration code to
provider-specific cleanup implementations. Terraform retry, timeout, and
parallel execution policies stay with the caller; provider-specific function
signatures stay behind this boundary.
"""

from dataclasses import dataclass
import re
from typing import Callable

from src.providers.cleanup_observability import enforce_cleanup_outcome

@dataclass(frozen=True)
class CleanupRequest:
    """Inputs required to clean provider resources for one twin prefix."""

    provider: str
    credentials: dict
    prefix: str
    cleanup_identity_user: bool = False
    platform_user_email: str = ""
    dry_run: bool = False


def cleanup_aws_resources(*args, **kwargs) -> None:
    """Lazy wrapper kept monkeypatchable for tests and integration seams."""
    from src.providers.aws.cleanup import cleanup_aws_resources as provider_cleanup

    provider_cleanup(*args, **kwargs)


def cleanup_azure_resources(*args, **kwargs) -> None:
    """Lazy wrapper kept monkeypatchable for tests and integration seams."""
    from src.providers.azure.cleanup import cleanup_azure_resources as provider_cleanup

    provider_cleanup(*args, **kwargs)


def cleanup_gcp_resources(*args, **kwargs) -> None:
    """Run GCP cleanup through its transitional fail-closed adapter."""
    from src.providers.gcp import cleanup as cleanup_module
    from src.providers.gcp.cleanup import cleanup_gcp_resources as provider_cleanup

    with enforce_cleanup_outcome(cleanup_module.logger, "GCP"):
        provider_cleanup(*args, **kwargs)


def resource_name_owned_by_prefix(
    resource_name: str,
    prefix: str,
    *,
    allow_compact: bool = False,
    allow_embedded: bool = False,
) -> bool:
    """Match generated resource names without unsafe plain substrings."""
    if not resource_name or not prefix:
        return False

    basename = resource_name.rsplit("/", 1)[-1]
    account_local_name = basename.split("@", 1)[0]
    candidates = {resource_name, basename, account_local_name}
    variants = {prefix, prefix.replace("-", "_")}

    for candidate in candidates:
        for variant in variants:
            if candidate == variant or candidate.startswith((f"{variant}-", f"{variant}_")):
                return True
            if allow_embedded and re.search(
                rf"(?:^|[-_/]){re.escape(variant)}(?:$|[-_/])",
                candidate,
            ):
                return True

    if allow_compact:
        compact_prefix = prefix.replace("-", "").replace("_", "")
        return any(
            candidate.startswith(f"{compact_prefix}st")
            for candidate in candidates
        )
    return False


def normalize_cleanup_provider(provider: str) -> str:
    """Normalize public provider aliases to cleanup registry identifiers."""
    provider_name = provider.lower()
    if provider_name == "google":
        return "gcp"
    return provider_name


def _cleanup_aws(request: CleanupRequest) -> None:
    cleanup_aws_resources(
        request.credentials,
        request.prefix,
        cleanup_identity_user=request.cleanup_identity_user,
        platform_user_email=request.platform_user_email,
        dry_run=request.dry_run,
    )


def _cleanup_azure(request: CleanupRequest) -> None:
    cleanup_azure_resources(
        request.credentials,
        request.prefix,
        cleanup_entra_user=request.cleanup_identity_user,
        platform_user_email=request.platform_user_email,
        dry_run=request.dry_run,
    )


def _cleanup_gcp(request: CleanupRequest) -> None:
    cleanup_gcp_resources(
        request.credentials,
        request.prefix,
        dry_run=request.dry_run,
    )


_CLEANUP_DISPATCHERS: dict[str, Callable[[CleanupRequest], None]] = {
    "aws": _cleanup_aws,
    "azure": _cleanup_azure,
    "gcp": _cleanup_gcp,
}


def supported_cleanup_providers() -> tuple[str, ...]:
    """Return cleanup providers supported by the registry."""
    return tuple(sorted(_CLEANUP_DISPATCHERS.keys()))


def cleanup_provider_resources(request: CleanupRequest) -> None:
    """Run provider-specific cleanup through the central registry."""
    provider = normalize_cleanup_provider(request.provider)
    dispatcher = _CLEANUP_DISPATCHERS.get(provider)
    if dispatcher is None:
        supported = ", ".join(supported_cleanup_providers())
        raise ValueError(
            f"Unsupported cleanup provider '{request.provider}'. Supported providers: {supported}"
        )
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{1,127}", request.prefix):
        raise ValueError(
            "Cleanup prefix must contain 2 to 128 safe resource-name characters"
        )
    expected_credential_keys = {provider}
    if set(request.credentials) != expected_credential_keys:
        raise ValueError(
            f"{provider.upper()} cleanup request must contain only scoped {provider} credentials"
        )

    dispatcher(
        CleanupRequest(
            provider=provider,
            credentials=request.credentials,
            prefix=request.prefix,
            cleanup_identity_user=request.cleanup_identity_user,
            platform_user_email=request.platform_user_email,
            dry_run=request.dry_run,
        )
    )
