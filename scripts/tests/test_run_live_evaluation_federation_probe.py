"""Fail-closed tests for the directed federation evaluation runner."""

from __future__ import annotations

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


def test_unimplemented_probe_fails_before_credentials_are_loaded(tmp_path) -> None:
    with pytest.raises(runner.ProbeBlocked, match="PROBE_NOT_IMPLEMENTED"):
        runner.execute(
            "federation-aws-to-azure",
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
