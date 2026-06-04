"""Static guardrails for provider bootstrap permission artifacts."""

import json
from pathlib import Path
import re

from api.azure_credentials_checker import REQUIRED_AZURE_PERMISSIONS, _action_matches
from api.credentials_checker import SELF_CHECK_PERMISSIONS, _get_all_required_permissions
from api.gcp_credentials_checker import REQUIRED_GCP_APIS, REQUIRED_GCP_PERMISSIONS
from api.permission_sets import ACTIVE_PERMISSION_SET_VERSION


ROOT = Path(__file__).resolve().parents[2]
PERMISSION_SET_DIR = ROOT / "docs/references/permission_sets"


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


def test_aws_scope_review_covers_every_policy_statement_and_required_action():
    policy = json.loads((ROOT / "docs/references/aws_deployer_policy.json").read_text())
    review = json.loads(
        (PERMISSION_SET_DIR / "aws_thesis_demo_v1_scope_review.json").read_text()
    )

    assert review["provider"] == "aws"
    assert review["permission_set_version"] == ACTIVE_PERMISSION_SET_VERSION
    assert review["validation_level"] == "offline_pre_e2e"
    assert review["requires_e2e_before_final"] is True

    policy_statements = {
        statement["Sid"]: set(_aws_statement_actions(statement))
        for statement in policy["Statement"]
    }
    reviewed_statements = {
        statement["sid"]: statement
        for statement in review["statements"]
    }

    assert sorted(reviewed_statements) == sorted(policy_statements)

    allowed_scope_classes = set(review["scope_classes"])
    for statement in reviewed_statements.values():
        assert statement["scope_class"] in allowed_scope_classes
        assert statement["reason"]

    policy_actions = {
        action
        for actions in policy_statements.values()
        for action in actions
    }
    required_actions = {
        action
        for service in _get_all_required_permissions().values()
        for action in service["actions"]
    }
    checked_actions = required_actions | {
        action
        for actions in SELF_CHECK_PERMISSIONS.values()
        for action in actions
    }
    assert sorted(required_actions - policy_actions) == []
    assert sorted(policy_actions - checked_actions) == []


def test_aws_pass_role_remains_conditioned_to_lambda_only():
    policy = json.loads((ROOT / "docs/references/aws_deployer_policy.json").read_text())
    pass_role_statements = [
        statement
        for statement in policy["Statement"]
        if "iam:PassRole" in _aws_statement_actions(statement)
    ]

    assert len(pass_role_statements) == 1
    assert pass_role_statements[0]["Condition"] == {
        "StringEquals": {"iam:PassedToService": "lambda.amazonaws.com"}
    }


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


def test_azure_custom_role_and_checker_do_not_drift():
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

    assert sorted(role_actions - required_actions) == []
    assert sorted(required_actions - role_actions) == []
    assert sorted(role_data_actions - required_data_actions) == []
    assert sorted(required_data_actions - role_data_actions) == []


def test_azure_scope_review_covers_every_role_action_and_data_action():
    role = json.loads((ROOT / "docs/references/azure_custom_role.json").read_text())
    permissions = role["properties"]["permissions"][0]
    review = json.loads(
        (PERMISSION_SET_DIR / "azure_thesis_demo_v1_scope_review.json").read_text()
    )

    assert review["provider"] == "azure"
    assert review["permission_set_version"] == ACTIVE_PERMISSION_SET_VERSION
    assert review["validation_level"] == "offline_pre_e2e"
    assert review["requires_e2e_before_final"] is True

    allowed_scope_classes = set(review["scope_classes"])
    reviewed_actions = set()
    for group in review["action_groups"]:
        assert group["scope_class"] in allowed_scope_classes
        assert group["reason"]
        reviewed_actions.update(group["actions"])

    reviewed_data_actions = set()
    for group in review["data_action_groups"]:
        assert group["scope_class"] in allowed_scope_classes
        assert group["reason"]
        reviewed_data_actions.update(group["data_actions"])

    assert sorted(reviewed_actions) == sorted(permissions["actions"])
    assert sorted(reviewed_data_actions) == sorted(permissions["dataActions"])


def test_gcp_custom_role_covers_supported_deployer_permission_families():
    role_text = (ROOT / "docs/references/gcp_custom_role.yaml").read_text()
    included_permissions = _parse_gcp_included_permissions(role_text)
    required_permissions = {
        permission
        for group in REQUIRED_GCP_PERMISSIONS.values()
        for permission in group["permissions"]
    }

    assert included_permissions
    assert not [permission for permission in included_permissions if "*" in permission]
    assert sorted(required_permissions - included_permissions) == []
    assert sorted(included_permissions - required_permissions) == []


def test_gcp_scope_review_covers_every_custom_role_permission():
    role_text = (ROOT / "docs/references/gcp_custom_role.yaml").read_text()
    included_permissions = _parse_gcp_included_permissions(role_text)
    review = json.loads(
        (PERMISSION_SET_DIR / "gcp_thesis_demo_v1_scope_review.json").read_text()
    )

    assert review["provider"] == "gcp"
    assert review["permission_set_version"] == ACTIVE_PERMISSION_SET_VERSION
    assert review["validation_level"] == "offline_pre_e2e"
    assert review["requires_e2e_before_final"] is True

    allowed_scope_classes = set(review["scope_classes"])
    reviewed_permissions = set()
    for group in review["permission_groups"]:
        assert group["scope_class"] in allowed_scope_classes
        assert group["reason"]
        reviewed_permissions.update(group["permissions"])

    assert sorted(reviewed_permissions) == sorted(included_permissions)


def test_gcp_workflows_api_and_permissions_are_in_permission_contract():
    required_apis = {
        api
        for group in REQUIRED_GCP_APIS.values()
        for api in group["apis"]
    }
    required_permissions = {
        permission
        for group in REQUIRED_GCP_PERMISSIONS.values()
        for permission in group["permissions"]
    }

    assert "workflows.googleapis.com" in required_apis
    assert "workflows.workflows.create" in required_permissions
    assert "workflows.workflows.delete" in required_permissions
    assert "resourcemanager.projects.setIamPolicy" in required_permissions


def test_permission_set_artifacts_bind_current_version_to_reference_artifacts():
    expected = {
        "aws": "aws_deployer_policy.json",
        "azure": "azure_custom_role.json",
        "gcp": "gcp_custom_role.yaml",
    }

    for provider, reference_file in expected.items():
        artifact = json.loads(
            (PERMISSION_SET_DIR / f"{provider}_thesis_demo_v1.json").read_text()
        )
        assert artifact["provider"] == provider
        assert artifact["permission_set_version"] == ACTIVE_PERMISSION_SET_VERSION
        assert artifact["status"] == "validated"
        assert artifact["capabilities"]
        assert artifact["known_gaps"]
        assert artifact["verification"]["offline"]

        source_paths = [
            source["path"]
            for source in artifact["actions"]["source_artifacts"]
        ]
        assert f"3-cloud-deployer/docs/references/{reference_file}" in source_paths
        for source_path in source_paths:
            container_path = source_path.removeprefix("3-cloud-deployer/")
            assert (ROOT / container_path).exists()


def test_permission_inventory_matches_current_terraform_provider_types():
    inventory = json.loads(
        (PERMISSION_SET_DIR / "deployer_permission_inventory.json").read_text()
    )
    assert inventory["permission_set_version"] == ACTIVE_PERMISSION_SET_VERSION

    expected_prefixes = {
        "aws": ("aws_",),
        "azure": ("azurerm_", "azuread_"),
        "gcp": ("google_",),
    }
    terraform_dir = ROOT / "src/terraform"

    for provider, prefixes in expected_prefixes.items():
        actual_types = set()
        for path in terraform_dir.glob("*.tf"):
            for resource_type in re.findall(r'^(?:resource|data) "([^"]+)"', path.read_text(), flags=re.M):
                if resource_type.startswith(prefixes):
                    actual_types.add(resource_type)

        inventory_types = set(inventory["providers"][provider]["terraform_types"])
        assert inventory_types == actual_types


def _aws_allowed_actions(policy: dict) -> set[str]:
    actions = set()
    for statement in policy.get("Statement", []):
        if statement.get("Effect") != "Allow":
            continue
        actions.update(_aws_statement_actions(statement))
    return actions


def _aws_statement_actions(statement: dict) -> set[str]:
    statement_actions = statement.get("Action", [])
    if isinstance(statement_actions, str):
        return {statement_actions}
    return set(statement_actions)


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
