"""Materialize frozen deployment permission inputs into provider-native JSON.

This provider-SDK-free module is shared by Management and the repository CLI.
It accepts only safe provider scope identifiers, reads synchronized generated
contracts, and never contacts a provider endpoint.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
from typing import Any
from uuid import UUID, uuid5


CONTRACT_ROOT = (
    Path(__file__).resolve().parents[1]
    / "contracts"
    / "generated"
    / "cloud-bootstrap"
    / "v1"
)
PACK_ROOT = CONTRACT_ROOT / "deployment-packs"
IDENTITY_BINDING_ROOT = CONTRACT_ROOT / "deployment-identity-bindings"
PERMISSION_SET_VERSION = "thesis-demo-v2"
AWS_MANAGED_POLICY_CHARACTER_LIMIT = 6_144
AWS_ACCOUNT_PATTERN = re.compile(r"^[0-9]{12}$")
GCP_PROJECT_PATTERN = re.compile(r"^[a-z][a-z0-9-]{4,28}[a-z0-9]$")
RUN_ID_PATTERN = re.compile(r"^twin2mc-e2e-[a-z0-9][a-z0-9-]{6,15}$")
GCP_ROLE_ID_PATTERN = re.compile(r"^[A-Za-z0-9_.]{3,64}$")
AZURE_ROLE_NAMESPACE = UUID("97e686e5-6ba4-4c60-a0cd-1c3df9148e89")


class PolicyMaterializationError(RuntimeError):
    """A frozen policy input cannot be rendered without ambiguity."""


def _load_pack(provider: str) -> dict[str, Any]:
    if provider not in {"aws", "azure", "gcp"}:
        raise PolicyMaterializationError(f"Unsupported provider: {provider}")
    path = PACK_ROOT / f"{provider}.json"
    document = json.loads(path.read_text(encoding="utf-8"))
    if (
        document.get("provider") != provider
        or document.get("permission_set_version") != PERMISSION_SET_VERSION
        or document.get("status") != "frozen_offline_contract"
    ):
        raise PolicyMaterializationError(
            f"{provider} deployment policy input is not the frozen v2 contract."
        )
    return document


def _document_digest(document: dict[str, Any]) -> str:
    payload = json.dumps(
        document,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(payload).hexdigest()}"


def _load_identity_binding(provider: str, pack: dict[str, Any]) -> dict[str, Any]:
    binding = json.loads(
        (IDENTITY_BINDING_ROOT / f"{provider}.json").read_text(encoding="utf-8")
    )
    expected = {
        "aws": (
            "aws.thesis-demo-v2.iam-user-v1",
            "iam_user",
            "access_key",
            "customer_managed_policy",
        ),
        "azure": (
            "azure.thesis-demo-v2.service-principal-v1",
            "service_principal",
            "client_secret",
            "custom_role_assignment",
        ),
        "gcp": (
            "gcp.thesis-demo-v2.service-account-v1",
            "service_account",
            "service_account_key",
            "project_custom_role_binding",
        ),
    }.get(provider)
    if (
        expected is None
        or binding.get("binding_id") != expected[0]
        or binding.get("provider") != provider
        or binding.get("permission_set_version") != PERMISSION_SET_VERSION
        or binding.get("base_pack_digest") != _document_digest(pack)
        or binding.get("identity_kind") != expected[1]
        or binding.get("connection_auth_type") != expected[2]
        or binding.get("policy_attachment_kind") != expected[3]
        or not isinstance(binding.get("self_check_permissions"), list)
        or not binding["self_check_permissions"]
        or len(binding["self_check_permissions"])
        != len(set(binding["self_check_permissions"]))
    ):
        raise PolicyMaterializationError(
            f"{provider.upper()} deployment identity binding does not match "
            "the frozen v2 pack."
        )
    return binding


def _require_run_id(run_id: str) -> None:
    if not RUN_ID_PATTERN.fullmatch(run_id):
        raise PolicyMaterializationError(
            "Run ID must match the setup-only twin2mc-e2e-* ownership boundary."
        )


def _unique_strings(values: Any, field: str) -> list[str]:
    if (
        not isinstance(values, list)
        or not values
        or any(not isinstance(value, str) or not value for value in values)
        or len(values) != len(set(values))
    ):
        raise PolicyMaterializationError(f"{field} must contain unique strings.")
    return values


def materialize_aws_deployment_bundle(
    *, account_id: str, run_id: str
) -> dict[str, Any]:
    """Render the explicit IAM-user binding for the frozen AWS v2 inventory."""

    if not AWS_ACCOUNT_PATTERN.fullmatch(account_id):
        raise PolicyMaterializationError("AWS account ID must contain 12 digits.")
    _require_run_id(run_id)
    pack = _load_pack("aws")
    binding = _load_identity_binding("aws", pack)
    inputs = pack.get("policy_inputs")
    if not isinstance(inputs, list) or not inputs:
        raise PolicyMaterializationError("AWS policy_inputs are missing.")

    passed_to_service: list[str] | None = None
    requested_regions: list[str] | None = None
    for condition in pack.get("conditions", []):
        if not isinstance(condition, dict):
            raise PolicyMaterializationError("AWS condition must be an object.")
        if condition.get("condition") == "iam:PassedToService":
            passed_to_service = _unique_strings(
                condition.get("values"), "iam:PassedToService values"
            )
        if condition.get("condition") == "aws:RequestedRegion":
            requested_regions = _unique_strings(
                condition.get("values"), "aws:RequestedRegion values"
            )
    if passed_to_service is None or requested_regions is None:
        raise PolicyMaterializationError("AWS mandatory conditions are incomplete.")
    region = pack.get("region")
    if not isinstance(region, str) or requested_regions != [region]:
        raise PolicyMaterializationError(
            "AWS deployment region does not match its requested-region condition."
        )

    statements: list[dict[str, Any]] = []
    seen_actions: set[str] = set()
    for item in inputs:
        if not isinstance(item, dict) or set(item) != {"group", "actions"}:
            raise PolicyMaterializationError("AWS policy input shape is invalid.")
        group = item["group"]
        if not isinstance(group, str) or not re.fullmatch(r"[a-z0-9_]+", group):
            raise PolicyMaterializationError("AWS policy input group is invalid.")
        actions = _unique_strings(item["actions"], f"AWS {group} actions")
        overlap = seen_actions.intersection(actions)
        if overlap:
            raise PolicyMaterializationError(
                f"AWS actions occur in more than one group: {sorted(overlap)}"
            )
        seen_actions.update(actions)

        global_actions = [
            action
            for action in actions
            if action.startswith(("iam:", "sts:")) and action != "iam:PassRole"
        ]
        regional_actions = [
            action
            for action in actions
            if action not in global_actions and action != "iam:PassRole"
        ]
        sid = "".join(part.title() for part in group.split("_"))
        if global_actions:
            statements.append(
                {
                    "Sid": f"{sid}Global",
                    "Effect": "Allow",
                    "Action": global_actions,
                    "Resource": "*",
                }
            )
        if regional_actions:
            statements.append(
                {
                    "Sid": f"{sid}Regional",
                    "Effect": "Allow",
                    "Action": regional_actions,
                    "Resource": "*",
                    "Condition": {
                        "StringEquals": {"aws:RequestedRegion": requested_regions}
                    },
                }
            )
        if "iam:PassRole" in actions:
            statements.append(
                {
                    "Sid": f"{sid}PassRole",
                    "Effect": "Allow",
                    "Action": "iam:PassRole",
                    "Resource": "*",
                    "Condition": {
                        "StringEquals": {"iam:PassedToService": passed_to_service}
                    },
                }
            )

    self_check_actions = _unique_strings(
        binding["self_check_permissions"], "AWS IAM-user self-check permissions"
    )
    overlap = seen_actions.intersection(self_check_actions)
    if overlap:
        raise PolicyMaterializationError(
            "AWS IAM-user self-check permissions duplicate base-pack actions: "
            f"{sorted(overlap)}"
        )
    statements.append(
        {
            "Sid": "IdentitySelfInspection",
            "Effect": "Allow",
            "Action": self_check_actions,
            "Resource": "*",
        }
    )

    policy = {"Version": "2012-10-17", "Statement": statements}
    size = aws_policy_character_count(policy)
    if size > AWS_MANAGED_POLICY_CHARACTER_LIMIT:
        raise PolicyMaterializationError(
            "AWS v2 policy exceeds the 6,144-character managed-policy limit."
        )
    user_name = f"{run_id}-deployer"
    policy_name = f"{run_id}-deployment"
    policy_arn = f"arn:aws:iam::{account_id}:policy/{policy_name}"
    return {
        "schema_version": "aws-deployment-identity-bundle.v1",
        "provider": "aws",
        "account_id": account_id,
        "region": region,
        "permission_set_version": PERMISSION_SET_VERSION,
        "identity_binding_id": binding["binding_id"],
        "identity": {
            "kind": binding["identity_kind"],
            "user_name": user_name,
            "auth_type": binding["connection_auth_type"],
        },
        "managed_policy": {
            "name": policy_name,
            "arn": policy_arn,
            "document": policy,
            "character_count": size,
        },
        "attachment": {
            "kind": binding["policy_attachment_kind"],
            "user_name": user_name,
            "policy_arn": policy_arn,
        },
    }


def aws_policy_character_count(policy: dict[str, Any]) -> int:
    """Count the compact policy characters used by the IAM quota."""

    return len(json.dumps(policy, sort_keys=True, separators=(",", ":")))


def materialize_azure_custom_role(
    *, subscription_id: str, run_id: str
) -> dict[str, Any]:
    try:
        subscription = str(UUID(subscription_id))
    except ValueError as exc:
        raise PolicyMaterializationError(
            "Azure subscription ID must be a UUID."
        ) from exc
    _require_run_id(run_id)
    pack = _load_pack("azure")
    binding = _load_identity_binding("azure", pack)
    inputs = pack.get("role_inputs")
    if not isinstance(inputs, dict) or set(inputs) != {"actions", "data_actions"}:
        raise PolicyMaterializationError("Azure role_inputs are invalid.")
    actions = _unique_strings(inputs["actions"], "Azure actions")
    data_actions = _unique_strings(inputs["data_actions"], "Azure data actions")
    self_check_actions = _unique_strings(
        binding["self_check_permissions"], "Azure self-check permissions"
    )
    overlap = set(actions).intersection(self_check_actions)
    if overlap:
        raise PolicyMaterializationError(
            "Azure self-check permissions duplicate base-pack actions: "
            f"{sorted(overlap)}"
        )
    region_conditions = [
        condition.get("value")
        for condition in pack.get("conditions", [])
        if isinstance(condition, dict) and condition.get("condition") == "region"
    ]
    if (
        not isinstance(pack.get("region"), str)
        or region_conditions != [pack["region"]]
    ):
        raise PolicyMaterializationError(
            "Azure deployment region does not match its resolver invariant."
        )
    scope = f"/subscriptions/{subscription}"
    role_id = str(uuid5(AZURE_ROLE_NAMESPACE, f"{subscription}:{run_id}"))
    return {
        "schema_version": "azure-deployment-identity-bundle.v1",
        "provider": "azure",
        "region": pack["region"],
        "permission_set_version": PERMISSION_SET_VERSION,
        "identity_binding_id": binding["binding_id"],
        "role_definition_id": role_id,
        "scope": scope,
        "properties": {
            "roleName": f"Twin2MultiCloud {run_id} deployment",
            "description": (
                "Gate-owned thesis-demo-v2 deployment role; offline-generated."
            ),
            "type": "CustomRole",
            "permissions": [
                {
                    "actions": [*actions, *self_check_actions],
                    "notActions": [],
                    "dataActions": data_actions,
                    "notDataActions": [],
                }
            ],
            "assignableScopes": [scope],
        },
    }


def materialize_gcp_custom_role(*, project_id: str, run_id: str) -> dict[str, Any]:
    if not GCP_PROJECT_PATTERN.fullmatch(project_id):
        raise PolicyMaterializationError("GCP project ID has an invalid shape.")
    _require_run_id(run_id)
    pack = _load_pack("gcp")
    binding = _load_identity_binding("gcp", pack)
    permissions = _unique_strings(
        pack.get("custom_role_inputs"), "GCP custom_role_inputs"
    )
    self_checks = _unique_strings(
        binding.get("self_check_permissions"),
        "GCP identity-binding self_check_permissions",
    )
    if not set(self_checks).issubset(permissions):
        raise PolicyMaterializationError(
            "GCP identity-binding self checks must be present in the custom role."
        )
    if any("*" in permission for permission in permissions):
        raise PolicyMaterializationError(
            "GCP custom-role permissions must not contain wildcards."
        )
    role_id = run_id.replace("-", "_")
    if not GCP_ROLE_ID_PATTERN.fullmatch(role_id):
        raise PolicyMaterializationError("Derived GCP role ID has an invalid shape.")
    return {
        "schema_version": "gcp-deployment-identity-bundle.v1",
        "provider": "gcp",
        "project_id": project_id,
        "region": pack["region"],
        "permission_set_version": PERMISSION_SET_VERSION,
        "identity_binding_id": binding["binding_id"],
        "identity": {
            "account_id": run_id,
            "email": f"{run_id}@{project_id}.iam.gserviceaccount.com",
        },
        "parent": f"projects/{project_id}",
        "roleId": role_id,
        "role": {
            "title": f"Twin2MultiCloud {run_id}",
            "description": (
                "Gate-owned thesis-demo-v2 deployment role; offline-generated."
            ),
            "includedPermissions": permissions,
            "stage": "GA",
        },
    }


def load_gcp_phase8_api_baseline() -> dict[str, Any]:
    """Return the exact existing-project API baseline admitted by bootstrap v3."""

    document = json.loads(
        (CONTRACT_ROOT / "gcp-phase8-api-baseline.json").read_text(encoding="utf-8")
    )
    services = document.get("services")
    prerequisites = document.get("bootstrap_prerequisite_services")
    if (
        document.get("schema_version") != "gcp-phase8-api-baseline.v1"
        or document.get("baseline_id") != "gcp.phase8-api-baseline.v1"
        or document.get("provider") != "gcp"
        or document.get("status") != "frozen_offline_contract"
        or document.get("target_mode") != "existing_project"
        or document.get("owner") != "bootstrap.gcp.admin-v3"
        or document.get("retain_enabled") is not True
        or not isinstance(services, list)
        or services != sorted(services)
        or len(services) != 19
        or len(services) != len(set(services))
        or not isinstance(prerequisites, list)
        or not set(prerequisites).issubset(services)
    ):
        raise PolicyMaterializationError(
            "GCP Phase 8 API baseline is not the frozen existing-project contract."
        )
    return document


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider", choices=("aws", "azure", "gcp"), required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--account-id")
    parser.add_argument("--subscription-id")
    parser.add_argument("--project-id")
    args = parser.parse_args()
    if args.provider == "aws":
        if args.subscription_id or args.project_id or not args.account_id:
            parser.error("AWS requires only --account-id.")
        document = materialize_aws_deployment_bundle(
            account_id=args.account_id, run_id=args.run_id
        )
    elif args.provider == "azure":
        if args.account_id or args.project_id or not args.subscription_id:
            parser.error("Azure requires only --subscription-id.")
        document = materialize_azure_custom_role(
            subscription_id=args.subscription_id, run_id=args.run_id
        )
    else:
        if args.account_id or args.subscription_id or not args.project_id:
            parser.error("GCP requires only --project-id.")
        document = materialize_gcp_custom_role(
            project_id=args.project_id, run_id=args.run_id
        )
    print(json.dumps(document, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
