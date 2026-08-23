from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.schemas.cloud_bootstrap import (
    CloudBootstrapExecuteRequest,
    CloudBootstrapGuideRequest,
    CloudBootstrapSessionResponse,
)


def test_target_union_accepts_both_gcp_modes_and_rejects_paths():
    existing = CloudBootstrapGuideRequest.model_validate(
        {
            "target": {
                "provider": "gcp",
                "mode": "existing_project",
                "project_id": "thesis-project",
                "region": "europe-west1",
            }
        }
    )
    organization = CloudBootstrapGuideRequest.model_validate(
        {
            "target": {
                "provider": "gcp",
                "mode": "organization",
                "bootstrap_project_id": "thesis-admin-project",
                "organization_id": "123456789",
                "billing_account_id": "ABCDEF-123456-ABCDEF",
                "region": "europe-west1",
            }
        }
    )

    assert existing.target.mode == "existing_project"
    assert organization.target.mode == "organization"
    with pytest.raises(ValidationError):
        CloudBootstrapExecuteRequest.model_validate(
            {
                "expected_revision": 1,
                "idempotency_key": "bootstrap-command-0001",
                "credential_origin": "dedicated_disposable",
                "credential": "/tmp/service-account.json",
            }
        )


def test_execute_secret_values_are_redacted_from_model_strings():
    secret = "never-print-this-bootstrap-secret"
    request = CloudBootstrapExecuteRequest.model_validate(
        {
            "expected_revision": 1,
            "idempotency_key": "bootstrap-command-0002",
            "credential_origin": "dedicated_disposable",
            "credential": {
                "provider": "aws",
                "access_key_id": "AKIAIOSFODNN7EXAMPLE",
                "secret_access_key": secret,
            },
        }
    )

    assert secret not in str(request)
    assert secret not in repr(request)
    assert "**********" in str(request)


def test_safe_session_response_rejects_secret_fields():
    payload = {
        "schema_version": "cloud-bootstrap-session.v1",
        "id": "session-id",
        "provider": "aws",
        "target": {
            "provider": "aws",
            "account_id": "123456789012",
            "region": "eu-central-1",
        },
        "entry_point": "settings",
        "twin_id": None,
        "display_name": "AWS deployment access",
        "revision": 1,
        "state": "draft",
        "guide_digest": "sha256:" + ("a" * 64),
        "bootstrap_authority_pack": {
            "id": "bootstrap.aws.admin-v1",
            "version": "1",
            "digest": "sha256:" + ("b" * 64),
        },
        "generated_deployment_pack": {
            "id": "aws.thesis-demo-v2.iam-user-v1",
            "version": "thesis-demo-v2",
            "digest": "sha256:" + ("c" * 64),
        },
        "command_permissions": ["execute", "cancel"],
        "created_at": "2026-08-04T18:00:00Z",
        "updated_at": "2026-08-04T18:00:00Z",
    }
    assert CloudBootstrapSessionResponse.model_validate(payload).state == "draft"

    payload["client_secret"] = "must-not-be-returned"
    with pytest.raises(ValidationError):
        CloudBootstrapSessionResponse.model_validate(payload)
