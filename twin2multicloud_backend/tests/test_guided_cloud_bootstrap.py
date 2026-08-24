from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker
import pytest
from src.config import settings
from src.models.cloud_bootstrap_session import CloudBootstrapSession
from src.models.cloud_connection import CloudConnection
from src.models.user import User
from src.repositories.architecture_repository import ArchitectureRepository
from src.schemas.cloud_bootstrap import CloudBootstrapApiBaseline
from src.services.cloud_bootstrap_errors import CloudBootstrapDomainError
from src.services.guided_cloud_bootstrap_service import GuidedCloudBootstrapService


CONTRACT_ROOT = (
    Path(__file__).resolve().parents[1]
    / "src"
    / "contracts"
    / "generated"
    / "cloud-bootstrap"
    / "v1"
)


def _validator(name: str) -> Draft202012Validator:
    schema = json.loads((CONTRACT_ROOT / name).read_text(encoding="utf-8"))
    return Draft202012Validator(schema, format_checker=FormatChecker())


def _target(provider: str) -> dict:
    if provider == "aws":
        return {
            "provider": "aws",
            "account_id": "123456789012",
            "region": "eu-central-1",
        }
    if provider == "azure":
        return {
            "provider": "azure",
            "tenant_id": "tenant-123",
            "subscription_id": "subscription-123",
            "region": "westeurope",
            "bootstrap_credential_key_id": "key-123",
        }
    return {
        "provider": "gcp",
        "mode": "existing_project",
        "project_id": "thesis-project",
        "region": "europe-west1",
    }


def _credential(provider: str, *, identifier: str | None = None) -> dict:
    if provider == "aws":
        return {
            "provider": "aws",
            "access_key_id": identifier or "AKIAIOSFODNN7EXAMPLE",
            "secret_access_key": "submitted-aws-bootstrap-secret",
        }
    if provider == "azure":
        return {
            "provider": "azure",
            "tenant_id": "tenant-123",
            "subscription_id": "subscription-123",
            "client_id": identifier or "client-123",
            "client_secret": "submitted-azure-bootstrap-secret",
        }
    return {
        "provider": "gcp",
        "type": "service_account",
        "project_id": "thesis-project",
        "private_key_id": identifier or "bootstrap-key-123",
        "private_key": "submitted-gcp-bootstrap-private-key",
        "client_email": "bootstrap@thesis-project.iam.gserviceaccount.com",
        "client_id": "12345678901234567890",
        "token_uri": "https://oauth2.googleapis.com/token",
    }


def _guide(client, provider: str) -> dict:
    response = client.post(
        f"/cloud-bootstrap/{provider}/guide",
        json={"target": _target(provider)},
    )
    assert response.status_code == 200, response.text
    return response.json()


def _session(client, provider: str, *, key: str) -> dict:
    guide = _guide(client, provider)
    response = client.post(
        "/cloud-bootstrap/sessions",
        json={
            "provider": provider,
            "target": guide["target"],
            "entry_point": "settings",
            "twin_id": None,
            "display_name": f"{provider.upper()} deployment access",
            "guide_digest": guide["guide_digest"],
            "bootstrap_authority_pack_digest": guide["bootstrap_authority_pack"][
                "digest"
            ],
            "generated_deployment_pack_digest": guide["generated_deployment_pack"][
                "digest"
            ],
            "idempotency_key": key,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def _execute(
    client,
    session: dict,
    provider: str,
    *,
    origin: str = "dedicated_disposable",
    identifier: str | None = None,
    key: str,
) -> dict:
    response = client.post(
        f"/cloud-bootstrap/sessions/{session['id']}/execute",
        json={
            "expected_revision": session["revision"],
            "idempotency_key": key,
            "credential_origin": origin,
            "credential": _credential(provider, identifier=identifier),
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_guides_are_strict_safe_and_reference_v2_for_every_provider(auth_client):
    validator = _validator("cloud-bootstrap-guide.schema.json")
    for provider in ("aws", "azure", "gcp"):
        guide = _guide(auth_client, provider)
        validator.validate(guide)
        serialized = json.dumps(guide, sort_keys=True).lower()
        assert guide["schema_version"] == "cloud-bootstrap-guide.v1"
        assert guide["execution_mode"] == "deterministic_fake"
        assert guide["generated_deployment_pack"]["version"] == "thesis-demo-v2"
        expected_deployment_pack = {
            "aws": "aws.thesis-demo-v2.iam-user-v1",
            "azure": "azure.thesis-demo-v2.service-principal-v1",
            "gcp": "gcp.thesis-demo-v2",
        }[provider]
        assert guide["generated_deployment_pack"]["id"] == expected_deployment_pack
        if provider == "aws":
            assert (
                "IAM deployment user"
                in guide["generated_deployment_pack"]["scope_summary"]
            )
        if provider == "azure":
            assert (
                "service principal"
                in guide["generated_deployment_pack"]["scope_summary"]
            )
        expected_authority = {
            "aws": ("bootstrap.aws.admin-v2", "2"),
            "azure": ("bootstrap.azure.admin-v2", "2"),
            "gcp": ("bootstrap.gcp.admin-v3", "3"),
        }[provider]
        assert guide["bootstrap_authority_pack"]["id"] == expected_authority[0]
        assert guide["bootstrap_authority_pack"]["version"] == expected_authority[1]
        if provider == "gcp":
            baseline = guide["api_baseline"]
            assert baseline["id"] == "gcp.phase8-api-baseline.v1"
            assert len(baseline["services"]) == 19
            assert baseline["services"] == sorted(baseline["services"])
            assert baseline["retain_enabled"] is True
        else:
            assert guide["api_baseline"] is None
        assert guide["legacy_fallback_available"] is True
        assert "submitted-" not in serialized
        assert '"private_key":' not in serialized
        assert all(
            step["official_url"].startswith("https://")
            for step in guide["preparation_steps"]
        )


def test_gcp_api_baseline_model_rejects_schema_drift():
    baseline = {
        "id": "gcp.phase8-api-baseline.v1",
        "digest": "sha256:" + ("a" * 64),
        "services": ["not-a-google-api.example.com"],
        "retain_enabled": True,
        "mutation_summary": "Enable the fixed baseline.",
        "limitations": ["Existing project only."],
        "artifact_url": "https://example.com/gcp/api-baseline",
    }

    with pytest.raises(ValueError, match="services must be sorted"):
        CloudBootstrapApiBaseline.model_validate(baseline)

    baseline["services"] = ["serviceusage.googleapis.com"]
    baseline["limitations"] = []
    with pytest.raises(ValueError):
        CloudBootstrapApiBaseline.model_validate(baseline)


def test_twin_prepare_admits_only_a_provider_in_the_selected_resolution(
    auth_client,
    test_twin,
    monkeypatch,
):
    class Assignment:
        def __init__(self, provider: str):
            self.provider = provider

    class Resolution:
        components = [Assignment("aws")]

    monkeypatch.setattr(
        ArchitectureRepository,
        "get_resolution_for_selected_run",
        lambda _repository, twin_id, _user_id: (
            Resolution() if twin_id == test_twin.id else None
        ),
    )

    aws_guide = _guide(auth_client, "aws")
    admitted = auth_client.post(
        "/cloud-bootstrap/sessions",
        json={
            "provider": "aws",
            "target": aws_guide["target"],
            "entry_point": "twin_prepare",
            "twin_id": test_twin.id,
            "display_name": "Twin-scoped AWS deployment access",
            "guide_digest": aws_guide["guide_digest"],
            "bootstrap_authority_pack_digest": aws_guide["bootstrap_authority_pack"][
                "digest"
            ],
            "generated_deployment_pack_digest": aws_guide["generated_deployment_pack"][
                "digest"
            ],
            "idempotency_key": "create-twin-prepare-aws-0001",
        },
    )

    assert admitted.status_code == 200
    assert admitted.json()["entry_point"] == "twin_prepare"
    assert admitted.json()["twin_id"] == test_twin.id

    gcp_guide = _guide(auth_client, "gcp")
    rejected = auth_client.post(
        "/cloud-bootstrap/sessions",
        json={
            "provider": "gcp",
            "target": gcp_guide["target"],
            "entry_point": "twin_prepare",
            "twin_id": test_twin.id,
            "display_name": "Out-of-resolution GCP deployment access",
            "guide_digest": gcp_guide["guide_digest"],
            "bootstrap_authority_pack_digest": gcp_guide["bootstrap_authority_pack"][
                "digest"
            ],
            "generated_deployment_pack_digest": gcp_guide["generated_deployment_pack"][
                "digest"
            ],
            "idempotency_key": "create-twin-prepare-gcp-0001",
        },
    )

    assert rejected.status_code == 409
    assert rejected.json()["error_code"] == "BOOTSTRAP_SESSION_CONFLICT"


def test_all_provider_execute_paths_create_one_valid_bounded_connection(
    auth_client,
    db,
):
    validator = _validator("cloud-bootstrap-session.schema.json")
    submitted_secrets = {
        "aws": "submitted-aws-bootstrap-secret",
        "azure": "submitted-azure-bootstrap-secret",
        "gcp": "submitted-gcp-bootstrap-private-key",
    }
    for index, provider in enumerate(("aws", "azure", "gcp"), start=1):
        session = _session(
            auth_client,
            provider,
            key=f"create-{provider}-session-000{index}",
        )
        ready = _execute(
            auth_client,
            session,
            provider,
            key=f"execute-{provider}-session-000{index}",
        )
        validator.validate(ready)
        assert ready["state"] == "ready"
        assert ready["disposal_status"] == "revoked"
        assert ready["connection"]["provider"] == provider
        assert ready["connection"]["purpose"] == "deployment"
        assert ready["connection"]["permission_set_version"] == "thesis-demo-v2"
        assert ready["connection"]["validation_status"] == "valid"

        stored_session = db.query(CloudBootstrapSession).filter_by(id=ready["id"]).one()
        stored_connection = (
            db.query(CloudConnection).filter_by(id=ready["connection"]["id"]).one()
        )
        persisted = " ".join(
            str(value)
            for value in stored_session.__dict__.values()
            if not str(value).startswith("<")
        )
        assert submitted_secrets[provider] not in persisted
        assert submitted_secrets[provider] not in stored_connection.encrypted_payload


def test_generated_v2_connection_alone_passes_normal_deployment_preflight(
    auth_client,
    monkeypatch,
):
    session = _session(auth_client, "aws", key="create-aws-preflight-0001")
    ready = _execute(
        auth_client,
        session,
        "aws",
        key="execute-aws-preflight-0001",
    )
    submitted_secret = _credential("aws")["secret_access_key"]
    seen: dict[str, dict] = {}

    async def fake_validate(provider, optimizer_credentials, deployer_credentials):
        seen["optimizer"] = optimizer_credentials
        seen["deployer"] = deployer_credentials
        return {
            "provider": provider,
            "valid": True,
            "optimizer": {"valid": True, "message": "optimizer access passed"},
            "deployer": {
                "valid": True,
                "message": "deployer access passed",
                "permissions": [],
            },
        }

    monkeypatch.setattr(
        "src.api.routes.cloud_connections.perform_dual_validation",
        fake_validate,
    )
    response = auth_client.post(
        f"/cloud-connections/{ready['connection']['id']}/preflight"
    )

    assert response.status_code == 200
    result = response.json()
    assert result["ready"] is True
    assert result["permission_set_status"] == "matched"
    assert result["expected_permission_set_version"] == "thesis-demo-v2"
    assert result["supplied_permission_set_version"] == "thesis-demo-v2"
    assert seen["deployer"]["permission_set_version"] == "thesis-demo-v2"
    assert seen["deployer"]["aws_secret_access_key"] != submitted_secret
    assert submitted_secret not in json.dumps(seen, sort_keys=True)


def test_execute_is_idempotent_and_does_not_create_a_second_connection(auth_client, db):
    session = _session(auth_client, "aws", key="create-aws-idempotency-01")
    ready = _execute(
        auth_client,
        session,
        "aws",
        key="execute-aws-idempotency-01",
    )
    duplicate = auth_client.post(
        f"/cloud-bootstrap/sessions/{session['id']}/execute",
        json={
            "expected_revision": session["revision"],
            "idempotency_key": "execute-aws-idempotency-01",
            "credential_origin": "dedicated_disposable",
            "credential": _credential("aws", identifier="AKIAOTHER00000000000"),
        },
    )

    assert duplicate.status_code == 200
    assert duplicate.json()["revision"] == ready["revision"]
    assert duplicate.json()["connection"]["id"] == ready["connection"]["id"]
    assert db.query(CloudConnection).count() == 1


def test_gcp_organization_path_fails_closed_before_v3_guide(auth_client):
    target = {
        "provider": "gcp",
        "mode": "organization",
        "bootstrap_project_id": "thesis-admin-project",
        "organization_id": "123456789",
        "folder_id": "987654321",
        "billing_account_id": "ABCDEF-123456-ABCDEF",
        "region": "europe-west1",
    }
    response = auth_client.post(
        "/cloud-bootstrap/gcp/guide",
        json={"target": target},
    )

    assert response.status_code == 409
    assert response.json()["error_code"] == "BOOTSTRAP_SCOPE_UNSUPPORTED"


def test_existing_user_owned_credential_is_released_but_not_claimed_revoked(
    auth_client,
):
    session = _session(auth_client, "azure", key="create-azure-existing-01")
    ready = _execute(
        auth_client,
        session,
        "azure",
        origin="existing_user_owned",
        key="execute-azure-existing-01",
    )

    assert ready["state"] == "ready"
    assert ready["disposal_status"] == "not_retained_user_managed"


def test_manual_revocation_requires_exact_revision_and_acknowledgement(auth_client):
    target = _target("azure")
    target["bootstrap_credential_key_id"] = "manual-key-123"
    guide_response = auth_client.post(
        "/cloud-bootstrap/azure/guide",
        json={"target": target},
    )
    guide = guide_response.json()
    created = auth_client.post(
        "/cloud-bootstrap/sessions",
        json={
            "provider": "azure",
            "target": target,
            "entry_point": "settings",
            "display_name": "Azure manual cleanup",
            "guide_digest": guide["guide_digest"],
            "bootstrap_authority_pack_digest": guide["bootstrap_authority_pack"][
                "digest"
            ],
            "generated_deployment_pack_digest": guide["generated_deployment_pack"][
                "digest"
            ],
            "idempotency_key": "create-azure-manual-001",
        },
    ).json()
    pending = _execute(
        auth_client,
        created,
        "azure",
        key="execute-azure-manual-001",
    )

    assert pending["state"] == "manual_revocation_required"
    assert pending["safe_credential_identifier"] == "manual-key-123"
    assert pending["command_permissions"] == ["acknowledge_manual_revocation"]
    assert pending["finding"]["code"] == "BOOTSTRAP_MANUAL_REVOCATION_REQUIRED"
    assert pending["finding"]["remediation_url"].startswith(
        "https://learn.microsoft.com/"
    )
    stale = auth_client.post(
        f"/cloud-bootstrap/sessions/{pending['id']}/acknowledge-manual-revocation",
        json={"expected_revision": pending["revision"] - 1},
    )
    assert stale.status_code == 409
    ready = auth_client.post(
        f"/cloud-bootstrap/sessions/{pending['id']}/acknowledge-manual-revocation",
        json={"expected_revision": pending["revision"]},
    )
    assert ready.status_code == 200
    assert ready.json()["state"] == "ready"
    assert ready.json()["disposal_status"] == "revoked"


def test_aws_sts_records_provider_expiry_without_revocation_claim(auth_client):
    expiry = datetime.now(timezone.utc) + timedelta(hours=1)
    target = _target("aws")
    target["session_expires_at"] = expiry.isoformat()
    guide = auth_client.post(
        "/cloud-bootstrap/aws/guide",
        json={"target": target},
    ).json()
    created = auth_client.post(
        "/cloud-bootstrap/sessions",
        json={
            "provider": "aws",
            "target": target,
            "entry_point": "settings",
            "display_name": "AWS STS access",
            "guide_digest": guide["guide_digest"],
            "bootstrap_authority_pack_digest": guide["bootstrap_authority_pack"][
                "digest"
            ],
            "generated_deployment_pack_digest": guide["generated_deployment_pack"][
                "digest"
            ],
            "idempotency_key": "create-aws-sts-session-01",
        },
    ).json()
    credential = _credential("aws")
    credential["access_key_id"] = "ASIAIOSFODNN7EXAMPLE"
    credential["session_token"] = "submitted-temporary-session-token"
    response = auth_client.post(
        f"/cloud-bootstrap/sessions/{created['id']}/execute",
        json={
            "expected_revision": created["revision"],
            "idempotency_key": "execute-aws-sts-session-01",
            "credential_origin": "dedicated_disposable",
            "credential": credential,
        },
    )

    assert response.status_code == 200
    assert response.json()["disposal_status"] == "expires_at_provider"
    assert response.json()["credential_expires_at"] is not None


def test_invalid_execute_response_never_echoes_secret(auth_client):
    session = _session(auth_client, "aws", key="create-aws-invalid-0001")
    secret = "this-value-must-never-return"
    response = auth_client.post(
        f"/cloud-bootstrap/sessions/{session['id']}/execute",
        json={
            "expected_revision": session["revision"],
            "idempotency_key": "execute-aws-invalid-0001",
            "credential_origin": "dedicated_disposable",
            "credential": {
                "provider": "aws",
                "access_key_id": "short",
                "secret_access_key": secret,
                "unexpected_secret": secret,
            },
        },
    )

    assert response.status_code == 422
    assert response.json()["error_code"] == "BOOTSTRAP_CREDENTIAL_INVALID"
    assert secret not in response.text
    assert "unexpected_secret" not in response.text


def test_duplicate_scope_resumes_and_cancel_is_terminal(auth_client):
    first = _session(auth_client, "gcp", key="create-gcp-resume-0001")
    second = _session(auth_client, "gcp", key="create-gcp-resume-0002")
    assert second["id"] == first["id"]

    cancelled = auth_client.post(
        f"/cloud-bootstrap/sessions/{first['id']}/cancel",
        json={"expected_revision": first["revision"]},
    )
    assert cancelled.status_code == 200
    assert cancelled.json()["state"] == "cancelled"
    assert cancelled.json()["command_permissions"] == ["start_new"]


def test_same_scope_with_different_cleanup_context_conflicts(auth_client):
    first = _session(auth_client, "azure", key="create-azure-scope-context-01")
    target = _target("azure")
    target["bootstrap_credential_key_id"] = "another-key-id"
    guide = auth_client.post(
        "/cloud-bootstrap/azure/guide",
        json={"target": target},
    ).json()
    response = auth_client.post(
        "/cloud-bootstrap/sessions",
        json={
            "provider": "azure",
            "target": target,
            "entry_point": "settings",
            "display_name": "Conflicting Azure context",
            "guide_digest": guide["guide_digest"],
            "bootstrap_authority_pack_digest": guide["bootstrap_authority_pack"][
                "digest"
            ],
            "generated_deployment_pack_digest": guide["generated_deployment_pack"][
                "digest"
            ],
            "idempotency_key": "create-azure-scope-context-02",
        },
    )

    assert first["state"] == "draft"
    assert response.status_code == 409
    assert response.json()["error_code"] == "BOOTSTRAP_SESSION_CONFLICT"


def test_disabled_adapter_fails_closed_without_persisting_connection(auth_client, db):
    original = settings.CLOUD_BOOTSTRAP_ADAPTER_MODE
    settings.CLOUD_BOOTSTRAP_ADAPTER_MODE = "disabled"
    try:
        session = _session(auth_client, "aws", key="create-aws-disabled-001")
        failed = _execute(
            auth_client,
            session,
            "aws",
            key="execute-aws-disabled-001",
        )
    finally:
        settings.CLOUD_BOOTSTRAP_ADAPTER_MODE = original

    assert failed["state"] == "credential_reentry_required"
    assert failed["disposal_status"] == "released_after_failure"
    assert failed["finding"]["code"] == "BOOTSTRAP_IDENTITY_CREATION_FAILED"
    assert "connection" not in failed
    assert db.query(CloudConnection).count() == 0


def test_stale_running_lease_requires_explicit_credential_reentry(auth_client, db):
    created = _session(auth_client, "aws", key="create-aws-stale-lease-01")
    stored = db.query(CloudBootstrapSession).filter_by(id=created["id"]).one()
    stored.state = "bootstrap_running"
    stored.revision = 2
    stored.execute_idempotency_key = "execute-aws-stale-lease-01"
    stored.credential_origin = "dedicated_disposable"
    stored.safe_credential_identifier = "AKIA…MPLE"
    stored.lease_started_at = datetime.now(timezone.utc) - timedelta(hours=1)
    db.commit()

    response = auth_client.get(f"/cloud-bootstrap/sessions/{created['id']}")

    assert response.status_code == 200
    body = response.json()
    assert body["state"] == "credential_reentry_required"
    assert body["disposal_status"] == "released_after_failure"
    assert body["finding"]["code"] == "BOOTSTRAP_CREDENTIAL_REENTRY_REQUIRED"
    assert body["command_permissions"] == ["execute", "cancel"]


def test_session_reads_are_owner_scoped(auth_client, db):
    created = _session(auth_client, "gcp", key="create-gcp-owner-scope-01")
    outsider = User(email="outsider@example.test", auth_provider="development")
    db.add(outsider)
    db.commit()
    db.refresh(outsider)

    try:
        GuidedCloudBootstrapService(db).get_session(outsider.id, created["id"])
    except CloudBootstrapDomainError as exc:
        assert exc.http_status == 404
        assert exc.code == "BOOTSTRAP_SESSION_CONFLICT"
    else:
        raise AssertionError("Another owner unexpectedly read the bootstrap session")


def test_execute_openapi_marks_every_secret_value_write_only(auth_client):
    schemas = auth_client.get("/openapi.json").json()["components"]["schemas"]
    expected = {
        "AWSBootstrapCredential": ("access_key_id", "secret_access_key"),
        "AzureBootstrapCredential": (
            "tenant_id",
            "subscription_id",
            "client_id",
            "client_secret",
        ),
        "GCPBootstrapCredential": (
            "private_key_id",
            "private_key",
            "client_id",
        ),
    }
    for schema_name, fields in expected.items():
        properties = schemas[schema_name]["properties"]
        for field in fields:
            assert properties[field]["writeOnly"] is True
