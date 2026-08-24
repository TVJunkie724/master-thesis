"""Offline tests for provider-native deployment permission materialization."""

from __future__ import annotations

import json
from pathlib import Path
import unittest

from scripts.materialize_deployment_policy import (
    AWS_MANAGED_POLICY_CHARACTER_LIMIT,
    PolicyMaterializationError,
    aws_policy_character_count,
    materialize_aws_deployment_bundle,
    materialize_azure_custom_role,
    materialize_gcp_custom_role,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
PACK_ROOT = REPO_ROOT / "3-cloud-deployer" / "docs" / "references" / "permission_sets"
RUN_ID = "twin2mc-e2e-a1b2c3d4"
SUBSCRIPTION_ID = "22222222-2222-4222-8222-222222222222"


def pack(provider: str) -> dict:
    return json.loads(
        (PACK_ROOT / f"{provider}_thesis_demo_v2.json").read_text(encoding="utf-8")
    )


class PolicyMaterializationTests(unittest.TestCase):
    def test_aws_user_bundle_preserves_actions_and_mandatory_conditions(self) -> None:
        first = materialize_aws_deployment_bundle(
            account_id="123456789012", run_id=RUN_ID
        )
        second = materialize_aws_deployment_bundle(
            account_id="123456789012", run_id=RUN_ID
        )
        policy = first["managed_policy"]["document"]
        expected = {
            action
            for group in pack("aws")["policy_inputs"]
            for action in group["actions"]
        }
        actual = {
            action
            for statement in policy["Statement"]
            for action in (
                [statement["Action"]]
                if isinstance(statement["Action"], str)
                else statement["Action"]
            )
        }

        self.assertEqual(first, second)
        expected.update(
            {
                "ec2:DescribeRegions",
                "iam:ListUserPolicies",
                "iam:GetUserPolicy",
                "iam:ListAttachedUserPolicies",
                "iam:GetPolicy",
                "iam:GetPolicyVersion",
                "iam:ListGroupsForUser",
                "iam:ListGroupPolicies",
                "iam:GetGroupPolicy",
                "iam:ListAttachedGroupPolicies",
            }
        )
        self.assertEqual(actual, expected)
        self.assertLessEqual(
            aws_policy_character_count(policy), AWS_MANAGED_POLICY_CHARACTER_LIMIT
        )
        self.assertEqual(first["identity_binding_id"], "aws.thesis-demo-v2.iam-user-v1")
        self.assertEqual(first["region"], "eu-central-1")
        self.assertEqual(first["identity"]["kind"], "iam_user")
        self.assertEqual(first["identity"]["auth_type"], "access_key")
        self.assertEqual(first["attachment"]["kind"], "customer_managed_policy")
        self.assertEqual(
            first["attachment"]["user_name"], first["identity"]["user_name"]
        )
        self.assertEqual(
            first["managed_policy"]["character_count"],
            aws_policy_character_count(policy),
        )
        self.assertTrue(
            any(
                statement.get("Condition", {})
                .get("StringEquals", {})
                .get("iam:PassedToService")
                for statement in policy["Statement"]
            )
        )
        regional = [
            statement
            for statement in policy["Statement"]
            if statement["Sid"].endswith("Regional")
        ]
        self.assertTrue(regional)
        self.assertTrue(
            all(
                statement["Condition"]["StringEquals"]["aws:RequestedRegion"]
                == ["eu-central-1"]
                for statement in regional
            )
        )

    def test_azure_role_is_subscription_scoped_with_explicit_self_checks(self) -> None:
        first = materialize_azure_custom_role(
            subscription_id=SUBSCRIPTION_ID, run_id=RUN_ID
        )
        second = materialize_azure_custom_role(
            subscription_id=SUBSCRIPTION_ID, run_id=RUN_ID
        )
        permission = first["properties"]["permissions"][0]

        self.assertEqual(first, second)
        self.assertEqual(first["scope"], f"/subscriptions/{SUBSCRIPTION_ID}")
        self.assertEqual(first["properties"]["assignableScopes"], [first["scope"]])
        expected_actions = [
            *pack("azure")["role_inputs"]["actions"],
            "Microsoft.Resources/subscriptions/read",
            "Microsoft.Resources/subscriptions/locations/read",
            "Microsoft.Authorization/roleDefinitions/read",
        ]
        self.assertEqual(permission["actions"], expected_actions)
        self.assertEqual(
            permission["dataActions"], pack("azure")["role_inputs"]["data_actions"]
        )
        self.assertEqual(
            first["identity_binding_id"],
            "azure.thesis-demo-v2.service-principal-v1",
        )

    def test_gcp_role_is_project_scoped_and_inventory_exact(self) -> None:
        first = materialize_gcp_custom_role(
            project_id="twin2mc-test-project", run_id=RUN_ID
        )
        second = materialize_gcp_custom_role(
            project_id="twin2mc-test-project", run_id=RUN_ID
        )

        self.assertEqual(first, second)
        self.assertEqual(first["parent"], "projects/twin2mc-test-project")
        self.assertEqual(first["roleId"], "twin2mc_e2e_a1b2c3d4")
        self.assertEqual(
            first["role"]["includedPermissions"], pack("gcp")["custom_role_inputs"]
        )
        self.assertTrue(
            all("*" not in item for item in first["role"]["includedPermissions"])
        )

    def test_scope_and_ownership_inputs_fail_closed(self) -> None:
        with self.assertRaises(PolicyMaterializationError):
            materialize_aws_deployment_bundle(account_id="root", run_id=RUN_ID)
        with self.assertRaises(PolicyMaterializationError):
            materialize_azure_custom_role(subscription_id="not-a-uuid", run_id=RUN_ID)
        with self.assertRaises(PolicyMaterializationError):
            materialize_gcp_custom_role(project_id="INVALID", run_id=RUN_ID)
        with self.assertRaises(PolicyMaterializationError):
            materialize_gcp_custom_role(
                project_id="twin2mc-test-project", run_id="production"
            )

    def test_materialized_documents_contain_no_secret_shaped_fields(self) -> None:
        documents = [
            materialize_aws_deployment_bundle(account_id="123456789012", run_id=RUN_ID),
            materialize_azure_custom_role(
                subscription_id=SUBSCRIPTION_ID, run_id=RUN_ID
            ),
            materialize_gcp_custom_role(
                project_id="twin2mc-test-project", run_id=RUN_ID
            ),
        ]
        serialized = json.dumps(documents, sort_keys=True).lower()

        for forbidden in (
            "secret_access_key",
            "client_secret",
            "private_key",
            "session_token",
        ):
            self.assertNotIn(forbidden, serialized)


if __name__ == "__main__":
    unittest.main()
