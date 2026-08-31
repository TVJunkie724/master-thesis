"""Fail-closed tests for the directed federation evaluation runner."""

from __future__ import annotations

import base64
import json

import pytest

from scripts import run_live_evaluation_federation_probe as runner


class _AwsError(Exception):
    response = {"Error": {"Code": "AccessDenied"}}


class _ServiceAccounts:
    def __init__(self, pages: list[dict]) -> None:
        self.pages = pages

    def list(self, *, name: str, pageSize: int):
        assert name == "projects/project"
        assert pageSize == 100
        return self.pages[0]

    def list_next(self, request, page):
        index = self.pages.index(page) + 1
        return self.pages[index] if index < len(self.pages) else None


class _Projects:
    def __init__(self, pages: list[dict]) -> None:
        self._accounts = _ServiceAccounts(pages)

    def serviceAccounts(self):
        return self._accounts


class _Iam:
    def __init__(self, pages: list[dict]) -> None:
        self._projects = _Projects(pages)

    def projects(self):
        return self._projects


def test_only_implemented_approved_slices_are_enabled() -> None:
    assert runner.ENABLED_PROBES == {
        "federation-gcp-to-aws",
        "federation-gcp-to-azure",
        "federation-aws-to-azure",
        "federation-aws-to-gcp",
        "federation-azure-to-aws",
        "federation-azure-to-gcp",
    }
    assert runner.APPROVED_RUN_ID == "26083001"
    assert runner.APPROVED_PLAN_DIGEST.startswith("sha256:")


def test_materialized_names_remain_provider_safe_and_exact() -> None:
    assert runner.GCP_TO_AWS_NAMES == {
        "gcp_service_account": "t2mc-p8-gcp-aws-26083001-sa",
        "aws_role": "t2mc-p8-gcp-aws-26083001-role",
    }
    assert len(runner.GCP_TO_AWS_NAMES["gcp_service_account"]) <= 30
    assert runner.GCP_TO_AZURE_NAMES == {
        "gcp_service_account": "t2mc-p8-gcp-azure-26083001-sa",
        "azure_resource_group": "t2mc-p8-gcp-azure-26083001-rg",
        "azure_managed_identity": "t2mc-p8-gcp-azure-26083001-mi",
        "azure_federated_credential": "gcp-exchange-26083001",
    }
    assert runner.AWS_TO_AZURE_NAMES == {
        "aws_role": "t2mc-p8-aws-azure-26083001-role",
        "aws_inline_policy": "t2mc-p8-aws-azure-26083001-token",
        "azure_resource_group": "t2mc-p8-aws-azure-26083001-rg",
        "azure_managed_identity": "t2mc-p8-aws-azure-26083001-mi",
        "azure_federated_credential": "aws-exchange-26083001",
    }
    assert runner.AWS_TO_GCP_NAMES == {
        "aws_role": "t2mc-p8-aws-gcp-26083001-role",
        "gcp_service_account": "t2mc-p8-aws-gcp-26083001-sa",
        "gcp_workload_identity_pool": "t2mc-p8-aws-gcp-26083001",
        "gcp_workload_identity_provider": "t2mc-p8-aws-gcp-26083001",
    }
    assert runner.AZURE_TO_AWS_NAMES == {
        "azure_resource_group": "t2mc-p8-azure-aws-26083001-rg",
        "azure_managed_identity": "t2mc-p8-azure-aws-26083001-mi",
        "azure_application": "t2mc-p8-azure-aws-26083001-app",
        "azure_container_group": "t2mc-p8-azure-aws-26083001-aci",
        "azure_container": "federation-probe",
        "aws_role": "t2mc-p8-azure-aws-26083001-role",
    }
    assert runner.AZURE_TO_GCP_NAMES == {
        "azure_resource_group": "t2mc-p8-azure-gcp-26083001-rg",
        "azure_managed_identity": "t2mc-p8-azure-gcp-26083001-mi",
        "azure_application": "t2mc-p8-azure-gcp-26083001-app",
        "azure_container_group": "t2mc-p8-azure-gcp-26083001-aci",
        "azure_container": "federation-probe",
        "gcp_service_account": "t2mc-p8-azure-gcp-26083001-sa",
        "gcp_workload_identity_pool": "t2mc-p8-azure-gcp-26083001",
        "gcp_workload_identity_provider": "t2mc-p8-azure-gcp-26083001",
    }


def test_unimplemented_probe_fails_before_credentials_are_loaded(tmp_path) -> None:
    with pytest.raises(runner.ProbeBlocked, match="PROBE_NOT_IMPLEMENTED"):
        runner.execute(
            "federation-aws-to-aws",
            tmp_path / "missing.json",
            tmp_path / "missing-gcp.json",
        )


def test_safe_error_code_never_includes_raw_message() -> None:
    assert runner._safe_error_code(_AwsError("credential-value")) == "AWSERROR"


def test_result_redaction_rejects_credential_escape() -> None:
    credentials = (
        {"aws_access_key_id": "example-access-key"},
        {"gcp_project_id": "example-project"},
        {"private_key": "example-private-key"},
    )
    runner._assert_no_sensitive_values(
        {"result_code": "PROBE_PASSED"}, credentials
    )
    with pytest.raises(ValueError, match="sensitive field escaped"):
        runner._assert_no_sensitive_values(
            {"unsafe": "example-private-key"}, credentials
        )


def test_load_credentials_requires_service_account_schema(tmp_path) -> None:
    config = tmp_path / "config.json"
    key = tmp_path / "gcp.json"
    config.write_text(
        json.dumps(
            {
                "aws": {
                    "aws_access_key_id": "x",
                    "aws_secret_access_key": "y",
                    "aws_region": "eu-central-1",
                },
                "gcp": {
                    "gcp_project_id": "project",
                    "gcp_region": "europe-west1",
                },
            }
        ),
        encoding="utf-8",
    )
    key.write_text(json.dumps({"type": "authorized_user"}), encoding="utf-8")
    with pytest.raises(runner.ProbeBlocked, match="CREDENTIAL_SCHEMA_INVALID"):
        runner._load_credentials(config, key)


def test_gcp_to_aws_rejects_region_outside_approved_scope() -> None:
    with pytest.raises(
        runner.ProbeBlocked, match="AWS_REGION_OUTSIDE_APPROVED_SCOPE"
    ):
        runner._run_gcp_to_aws(
            {"aws_region": "us-east-1"},
            {},
            {},
        )


def test_gcp_to_azure_uses_frozen_phase8_region() -> None:
    assert runner.AZURE_REGION == "westeurope"


def test_aws_to_azure_rejects_region_outside_approved_scope() -> None:
    with pytest.raises(
        runner.ProbeBlocked, match="AWS_REGION_OUTSIDE_APPROVED_SCOPE"
    ):
        runner._run_aws_to_azure(
            {"aws_region": "us-east-1"},
            {},
        )


def test_aws_to_gcp_rejects_region_outside_approved_scope() -> None:
    with pytest.raises(
        runner.ProbeBlocked, match="AWS_REGION_OUTSIDE_APPROVED_SCOPE"
    ):
        runner._run_aws_to_gcp(
            {"aws_region": "us-east-1"},
            {},
            {},
        )


def test_azure_to_aws_rejects_region_outside_approved_scope() -> None:
    with pytest.raises(
        runner.ProbeBlocked, match="AWS_REGION_OUTSIDE_APPROVED_SCOPE"
    ):
        runner._run_azure_to_aws(
            {"aws_region": "us-east-1"},
            {},
        )


def test_azure_source_container_is_pinned_bounded_and_has_no_ingress() -> None:
    body = runner._azure_container_group_body(
        "/subscriptions/example/resourceGroups/example/providers/"
        "Microsoft.ManagedIdentity/userAssignedIdentities/example",
        {"B": "2", "A": "1"},
        "print('PROBE_PASSED')",
    )
    assert body["identity"]["type"] == "UserAssigned"
    properties = body["properties"]
    assert properties["osType"] == "Linux"
    assert properties["restartPolicy"] == "Never"
    assert "ipAddress" not in properties
    container = properties["containers"][0]
    assert container["properties"]["image"] == runner.AZURE_SOURCE_RUNNER_IMAGE
    assert "@sha256:" in container["properties"]["image"]
    assert container["properties"]["resources"] == {
        "requests": {"cpu": 1, "memoryInGB": 1}
    }
    assert container["properties"]["environmentVariables"] == [
        {"name": "A", "value": "1"},
        {"name": "B", "value": "2"},
    ]
    assert runner.AZURE_SOURCE_RUNNER_MAXIMUM_SECONDS == 300
    assert runner.AZURE_SOURCE_DIRECT_COST_CAP_USD == "0.010000"


def test_azure_to_aws_runner_is_valid_and_emits_only_typed_result() -> None:
    script = runner._azure_to_aws_runner_script()
    compile(script, "<azure-to-aws-runner>", "exec")
    assert "print('PROBE_PASSED')" in script
    assert "print('PROBE_BLOCKED')" in script
    assert "traceback" not in script.lower()


def test_azure_to_gcp_provider_and_binding_are_exact_identity_bound() -> None:
    tenant_id = "11111111-1111-4111-8111-111111111111"
    application_id = "22222222-2222-4222-8222-222222222222"
    principal_id = "33333333-3333-4333-8333-333333333333"
    audience = f"api://{application_id}"
    body = runner._azure_to_gcp_provider_body(
        tenant_id,
        audience,
        principal_id,
    )
    assert body["oidc"] == {
        "issuerUri": f"https://sts.windows.net/{tenant_id}/",
        "allowedAudiences": [audience],
    }
    assert body["attributeMapping"] == {
        "google.subject": "assertion.sub",
        "attribute.azure_oid": "assertion.oid",
    }
    condition = body["attributeCondition"]
    assert tenant_id in condition
    assert audience in condition
    assert condition.count(principal_id) == 2
    assert "'EventBridge.Exchange' in assertion.roles" in condition

    pool_id = runner.AZURE_TO_GCP_NAMES["gcp_workload_identity_pool"]
    assert runner._azure_to_gcp_principal(
        "123456789012",
        pool_id,
        principal_id,
    ) == (
        "principal://iam.googleapis.com/projects/123456789012/"
        f"locations/global/workloadIdentityPools/{pool_id}/"
        f"subject/{principal_id}"
    )


def test_azure_to_gcp_runner_is_valid_and_emits_only_typed_result() -> None:
    script = runner._azure_to_gcp_runner_script()
    compile(script, "<azure-to-gcp-runner>", "exec")
    assert "print('PROBE_PASSED')" in script
    assert "print('PROBE_BLOCKED')" in script
    assert "traceback" not in script.lower()


def test_aws_to_gcp_provider_and_binding_are_exact_role_bound() -> None:
    role_name = runner.AWS_TO_GCP_NAMES["aws_role"]
    pool_id = runner.AWS_TO_GCP_NAMES["gcp_workload_identity_pool"]
    body = runner._aws_to_gcp_provider_body("123456789012", role_name)
    assert body["aws"] == {"accountId": "123456789012"}
    assert body["attributeMapping"] == {
        "google.subject": "assertion.arn",
        "attribute.aws_role": (
            "assertion.arn.extract('assumed-role/{role_name}/')"
        ),
    }
    assert body["attributeCondition"] == (
        f"attribute.aws_role == '{role_name}'"
    )
    assert runner._aws_to_gcp_principal_set(
        "123456789012",
        pool_id,
        role_name,
    ) == (
        "principalSet://iam.googleapis.com/projects/123456789012/"
        f"locations/global/workloadIdentityPools/{pool_id}/"
        f"attribute.aws_role/{role_name}"
    )


@pytest.mark.parametrize(
    ("response", "expected"),
    [
        (
            {
                "JwtVendingEnabled": True,
                "IssuerIdentifier": "https://issuer.example.invalid/path/",
            },
            "https://issuer.example.invalid/path",
        ),
    ],
)
def test_aws_outbound_issuer_accepts_only_enabled_https_issuer(
    response,
    expected,
) -> None:
    class _OutboundIam:
        def get_outbound_web_identity_federation_info(self):
            return response

    assert runner._aws_outbound_issuer(_OutboundIam()) == expected


@pytest.mark.parametrize(
    "response",
    [
        {"JwtVendingEnabled": False, "IssuerIdentifier": "https://issuer.invalid"},
        {"JwtVendingEnabled": True, "IssuerIdentifier": "http://issuer.invalid"},
        {"JwtVendingEnabled": True, "IssuerIdentifier": "https://user@issuer.invalid"},
        {"JwtVendingEnabled": True, "IssuerIdentifier": "https://issuer.invalid?q=1"},
    ],
)
def test_aws_outbound_issuer_fails_closed(response) -> None:
    class _OutboundIam:
        def get_outbound_web_identity_federation_info(self):
            return response

    with pytest.raises(runner.ProbeBlocked):
        runner._aws_outbound_issuer(_OutboundIam())


def test_aws_role_subject_uses_stable_iam_role_arn() -> None:
    role_name = runner.AWS_TO_AZURE_NAMES["aws_role"]
    role_arn = f"arn:aws:iam::123456789012:role/{role_name}"
    assert runner._aws_role_subject(role_arn, role_name) == role_arn

    with pytest.raises(
        runner.ProbeBlocked, match="AWS_SOURCE_ROLE_ARN_INVALID"
    ):
        runner._aws_role_subject(
            f"arn:aws:sts::123456789012:assumed-role/{role_name}/session",
            role_name,
        )


def test_jwt_claims_decodes_payload_without_retaining_token() -> None:
    claims = {
        "iss": "https://issuer.example.invalid",
        "sub": "subject",
        "aud": [runner.AZURE_FEDERATION_AUDIENCE],
    }

    def encode(value: dict) -> str:
        raw = json.dumps(value).encode("utf-8")
        return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")

    token = f"{encode({'alg': 'RS256'})}.{encode(claims)}.signature"
    assert runner._jwt_claims(token) == claims

    with pytest.raises(runner.ProbeBlocked, match="IDENTITY_TOKEN_INVALID"):
        runner._jwt_claims("not-a-jwt")


def test_gcp_absence_uses_active_inventory_not_deleted_account_get(
    monkeypatch,
) -> None:
    monkeypatch.setattr(runner, "_gcp_execute", lambda request: request)
    runner._expect_gcp_service_account_absent(
        _Iam([{"accounts": [{"email": "other@example.invalid"}]}]),
        "project",
        "target@example.invalid",
    )
    with pytest.raises(runner.ProbeBlocked, match="PREEXISTING_RESOURCE"):
        runner._expect_gcp_service_account_absent(
            _Iam([{"accounts": [{"email": "target@example.invalid"}]}]),
            "project",
            "target@example.invalid",
        )
