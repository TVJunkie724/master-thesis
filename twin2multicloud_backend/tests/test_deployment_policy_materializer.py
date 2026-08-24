from __future__ import annotations

import json

import pytest

from src.services import deployment_policy_materializer as materializer
from src.services.deployment_policy_materializer import (
    AWS_MANAGED_POLICY_CHARACTER_LIMIT,
    PolicyMaterializationError,
    load_gcp_phase8_api_baseline,
    materialize_aws_deployment_bundle,
    materialize_azure_custom_role,
    materialize_gcp_custom_role,
)


RUN_ID = "twin2mc-e2e-a1b2c3d4"


def test_management_materializes_all_provider_documents_from_generated_contracts():
    aws = materialize_aws_deployment_bundle(
        account_id="123456789012",
        run_id=RUN_ID,
    )
    azure = materialize_azure_custom_role(
        subscription_id="22222222-2222-4222-8222-222222222222",
        run_id=RUN_ID,
    )
    gcp = materialize_gcp_custom_role(
        project_id="twin2mc-test-project",
        run_id=RUN_ID,
    )

    assert aws["permission_set_version"] == "thesis-demo-v2"
    assert aws["region"] == "eu-central-1"
    assert aws["managed_policy"]["character_count"] <= (
        AWS_MANAGED_POLICY_CHARACTER_LIMIT
    )
    assert azure["permission_set_version"] == "thesis-demo-v2"
    assert azure["region"] == "westeurope"
    assert azure["scope"] == ("/subscriptions/22222222-2222-4222-8222-222222222222")
    assert gcp["parent"] == "projects/twin2mc-test-project"
    assert gcp["roleId"] == "twin2mc_e2e_a1b2c3d4"
    assert gcp["permission_set_version"] == "thesis-demo-v2"
    assert gcp["region"] == "europe-west1"
    assert gcp["identity_binding_id"] == "gcp.thesis-demo-v2.service-account-v1"
    baseline = load_gcp_phase8_api_baseline()
    assert baseline["owner"] == "bootstrap.gcp.admin-v3"
    assert baseline["target_mode"] == "existing_project"
    assert baseline["retain_enabled"] is True
    assert len(baseline["services"]) == 19

    serialized = json.dumps([aws, azure, gcp], sort_keys=True).lower()
    for forbidden in (
        "secret_access_key",
        "client_secret",
        "private_key",
        "session_token",
    ):
        assert forbidden not in serialized


def test_gcp_identity_binding_self_checks_must_exist_in_custom_role(monkeypatch):
    original = materializer._load_identity_binding

    def binding_with_ungranted_self_check(provider, pack):
        binding = original(provider, pack)
        return {
            **binding,
            "self_check_permissions": [
                *binding["self_check_permissions"],
                "ungranted.example.permission",
            ],
        }

    monkeypatch.setattr(
        materializer,
        "_load_identity_binding",
        binding_with_ungranted_self_check,
    )

    with pytest.raises(PolicyMaterializationError, match="self checks"):
        materialize_gcp_custom_role(
            project_id="twin2mc-test-project",
            run_id=RUN_ID,
        )
