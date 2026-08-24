from __future__ import annotations

import json

from src.services.deployment_policy_materializer import (
    AWS_MANAGED_POLICY_CHARACTER_LIMIT,
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
    assert aws["managed_policy"]["character_count"] <= (
        AWS_MANAGED_POLICY_CHARACTER_LIMIT
    )
    assert azure["permission_set_version"] == "thesis-demo-v2"
    assert azure["scope"] == (
        "/subscriptions/22222222-2222-4222-8222-222222222222"
    )
    assert gcp["parent"] == "projects/twin2mc-test-project"
    assert gcp["roleId"] == "twin2mc_e2e_a1b2c3d4"

    serialized = json.dumps([aws, azure, gcp], sort_keys=True).lower()
    for forbidden in (
        "secret_access_key",
        "client_secret",
        "private_key",
        "session_token",
    ):
        assert forbidden not in serialized
