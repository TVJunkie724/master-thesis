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


def test_unimplemented_probe_fails_before_credentials_are_loaded(tmp_path) -> None:
    with pytest.raises(runner.ProbeBlocked, match="PROBE_NOT_IMPLEMENTED"):
        runner.execute(
            "federation-azure-to-aws",
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
