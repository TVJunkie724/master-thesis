"""Classification policy for Terraform outputs.

The policy is intentionally conservative. Known UI-facing endpoints and names are
safe, known secret-bearing outputs are redacted, and unknown outputs are treated
as internal-only until explicitly classified.
"""

from dataclasses import dataclass
from enum import Enum


class TerraformOutputVisibility(str, Enum):
    """Visibility class for Terraform output values."""

    SAFE = "safe"
    REDACTED = "redacted"
    INTERNAL_ONLY = "internal_only"


@dataclass(frozen=True)
class TerraformOutputPolicy:
    """Classification result for one Terraform output."""

    name: str
    visibility: TerraformOutputVisibility
    reason: str


_REDACTED_MARKERS = (
    "api_key",
    "connection_string",
    "password",
    "secret",
    "token",
)

_SAFE_SUFFIXES = (
    "_endpoint",
    "_hostname",
    "_name",
    "_url",
)

_SAFE_EXACT_NAMES = {
    "digital_twin_name",
    "aws_region",
    "gcp_region",
}

_SAFE_MARKERS = (
    "access_instructions",
    "login_instructions",
    "sso_warning",
)

_INTERNAL_ONLY_MARKERS = (
    "_arn",
    "_id",
    "account_id",
    "client_id",
    "service_account_email",
    "workspace_id",
)


def classify_terraform_output(name: str) -> TerraformOutputPolicy:
    """Classify a Terraform output by name."""
    normalized = name.lower()

    for marker in _REDACTED_MARKERS:
        if marker in normalized:
            return TerraformOutputPolicy(
                name=name,
                visibility=TerraformOutputVisibility.REDACTED,
                reason=f"Output name contains secret marker '{marker}'.",
            )

    if normalized in _SAFE_EXACT_NAMES:
        return TerraformOutputPolicy(
            name=name,
            visibility=TerraformOutputVisibility.SAFE,
            reason="Output is an explicitly safe public metadata field.",
        )

    if normalized.endswith(_SAFE_SUFFIXES) or any(marker in normalized for marker in _SAFE_MARKERS):
        return TerraformOutputPolicy(
            name=name,
            visibility=TerraformOutputVisibility.SAFE,
            reason="Output is UI-facing endpoint, name, URL, or instruction metadata.",
        )

    for marker in _INTERNAL_ONLY_MARKERS:
        if marker in normalized:
            return TerraformOutputPolicy(
                name=name,
                visibility=TerraformOutputVisibility.INTERNAL_ONLY,
                reason=f"Output name contains infrastructure identifier marker '{marker}'.",
            )

    return TerraformOutputPolicy(
        name=name,
        visibility=TerraformOutputVisibility.INTERNAL_ONLY,
        reason="Output is not explicitly classified as safe.",
    )


def classify_terraform_outputs(outputs: dict) -> dict[str, TerraformOutputPolicy]:
    """Classify all Terraform outputs in a mapping."""
    return {
        name: classify_terraform_output(name)
        for name in outputs
    }
