#!/usr/bin/env python3
"""Materialize frozen deployment permission inputs into provider-native JSON.

This utility is intentionally offline. It accepts only safe provider scope
identifiers, reads repository contracts, and never imports a cloud SDK or
contacts a provider endpoint.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
from typing import Any
from uuid import UUID, uuid5


REPO_ROOT = Path(__file__).resolve().parents[1]
PACK_ROOT = REPO_ROOT / "3-cloud-deployer" / "docs" / "references" / "permission_sets"
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
    path = PACK_ROOT / f"{provider}_thesis_demo_v2.json"
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


def materialize_aws_role_policy(*, account_id: str, run_id: str) -> dict[str, Any]:
    """Render the role policy described by the frozen AWS v2 pack.

    The pack explicitly assigns v2 to a deployment role. This function does
    not reinterpret it as an IAM-user policy; the supervised adapter remains
    blocked until the separate role-vs-user contract decision is resolved.
    """

    if not AWS_ACCOUNT_PATTERN.fullmatch(account_id):
        raise PolicyMaterializationError("AWS account ID must contain 12 digits.")
    _require_run_id(run_id)
    pack = _load_pack("aws")
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

    policy = {"Version": "2012-10-17", "Statement": statements}
    size = aws_policy_character_count(policy)
    if size > AWS_MANAGED_POLICY_CHARACTER_LIMIT:
        raise PolicyMaterializationError(
            "AWS v2 policy exceeds the 6,144-character managed-policy limit."
        )
    return policy


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
    inputs = pack.get("role_inputs")
    if not isinstance(inputs, dict) or set(inputs) != {"actions", "data_actions"}:
        raise PolicyMaterializationError("Azure role_inputs are invalid.")
    actions = _unique_strings(inputs["actions"], "Azure actions")
    data_actions = _unique_strings(inputs["data_actions"], "Azure data actions")
    scope = f"/subscriptions/{subscription}"
    role_id = str(uuid5(AZURE_ROLE_NAMESPACE, f"{subscription}:{run_id}"))
    return {
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
                    "actions": actions,
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
    permissions = _unique_strings(
        pack.get("custom_role_inputs"), "GCP custom_role_inputs"
    )
    if any("*" in permission for permission in permissions):
        raise PolicyMaterializationError(
            "GCP custom-role permissions must not contain wildcards."
        )
    role_id = run_id.replace("-", "_")
    if not GCP_ROLE_ID_PATTERN.fullmatch(role_id):
        raise PolicyMaterializationError("Derived GCP role ID has an invalid shape.")
    return {
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
        document = materialize_aws_role_policy(
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
