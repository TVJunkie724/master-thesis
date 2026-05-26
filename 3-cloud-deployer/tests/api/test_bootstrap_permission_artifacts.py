"""Static guardrails for provider bootstrap permission artifacts."""

import json
from pathlib import Path

from api.azure_credentials_checker import REQUIRED_AZURE_PERMISSIONS, _action_matches
from api.credentials_checker import SELF_CHECK_PERMISSIONS, _get_all_required_permissions


ROOT = Path(__file__).resolve().parents[2]


def test_aws_bootstrap_policy_covers_required_deployer_and_self_check_permissions():
    policy = json.loads((ROOT / "docs/references/aws_deployer_policy.json").read_text())
    allowed_actions = _aws_allowed_actions(policy)

    required_actions = {
        action
        for service in _get_all_required_permissions().values()
        for action in service["actions"]
    }
    self_check_actions = {
        action
        for actions in SELF_CHECK_PERMISSIONS.values()
        for action in actions
    }

    missing = sorted(
        action
        for action in required_actions | self_check_actions
        if not _aws_action_allowed(action, allowed_actions)
    )

    assert missing == []


def test_azure_custom_role_covers_required_actions_and_data_actions():
    role = json.loads((ROOT / "docs/references/azure_custom_role.json").read_text())
    permissions = role["properties"]["permissions"][0]
    role_actions = set(permissions["actions"])
    role_data_actions = set(permissions["dataActions"])

    required_actions = {
        action
        for layer in REQUIRED_AZURE_PERMISSIONS.values()
        for action in layer.get("required_actions", [])
    }
    required_data_actions = {
        action
        for layer in REQUIRED_AZURE_PERMISSIONS.values()
        for action in layer.get("required_data_actions", [])
    }

    missing_actions = sorted(
        action
        for action in required_actions
        if _action_matches(role_actions, action) == "none"
    )
    missing_data_actions = sorted(
        action
        for action in required_data_actions
        if _action_matches(role_data_actions, action) == "none"
    )

    assert missing_actions == []
    assert missing_data_actions == []


def test_gcp_custom_role_covers_supported_deployer_permission_families():
    role_text = (ROOT / "docs/references/gcp_custom_role.yaml").read_text()
    included_permissions = _parse_gcp_included_permissions(role_text)
    required_permissions = {
        "resourcemanager.projects.get",
        "resourcemanager.projects.getIamPolicy",
        "iam.serviceAccounts.actAs",
        "storage.buckets.create",
        "pubsub.topics.create",
        "cloudfunctions.functions.create",
        "run.services.create",
        "eventarc.triggers.create",
        "cloudbuild.builds.create",
        "datastore.databases.create",
        "cloudscheduler.jobs.create",
        "serviceusage.services.enable",
        "serviceusage.services.get",
        "serviceusage.services.list",
    }

    assert included_permissions
    assert not [permission for permission in included_permissions if "*" in permission]
    assert sorted(required_permissions - included_permissions) == []


def _aws_allowed_actions(policy: dict) -> set[str]:
    actions = set()
    for statement in policy.get("Statement", []):
        if statement.get("Effect") != "Allow":
            continue
        statement_actions = statement.get("Action", [])
        if isinstance(statement_actions, str):
            actions.add(statement_actions)
        else:
            actions.update(statement_actions)
    return actions


def _aws_action_allowed(action: str, allowed_actions: set[str]) -> bool:
    if "*" in allowed_actions or action in allowed_actions:
        return True
    service = action.split(":", 1)[0]
    return f"{service}:*" in allowed_actions


def _parse_gcp_included_permissions(role_text: str) -> set[str]:
    permissions = set()
    in_permissions = False
    for line in role_text.splitlines():
        stripped = line.strip()
        if stripped == "includedPermissions:":
            in_permissions = True
            continue
        if in_permissions and stripped.startswith("- "):
            permissions.add(stripped[2:].strip())
    return permissions
