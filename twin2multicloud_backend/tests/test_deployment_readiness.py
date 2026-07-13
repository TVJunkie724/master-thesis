"""Deployment readiness contract, cache, and preflight behavior."""

from __future__ import annotations

from datetime import datetime, timedelta
import json

import pytest
from pydantic import ValidationError as PydanticValidationError

from src.models.cloud_connection import CloudConnection
from src.models.deployment_preflight import DeploymentPreflightCache
from src.models.optimizer_config import OptimizerConfiguration
from src.models.twin import DigitalTwin, TwinState
from src.models.twin_config import TwinConfiguration
from src.models.user import User
from src.schemas.cloud_connection import CloudConnectionCreate
from src.schemas.deployment_readiness import DeploymentReadinessResponse
from src.services.cloud_connection_service import CloudConnectionService
from src.services.deployment_readiness_service import DeploymentReadinessService
from src.services.service_errors import EntityNotFoundError, ValidationError


_AWS_SECRET = "aws-secret-value-for-redaction"
_AZURE_SECRET = "azure-secret-value-for-redaction"
_GCP_SECRET = "gcp-private-key-value-for-redaction"


def _create_user(db, email: str = "readiness@example.test") -> User:
    user = User(email=email, name="Readiness", auth_provider="google")
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _connection_request(
    provider: str,
    *,
    permission_set_version: str | None = "thesis-demo-v1",
    purpose: str = "deployment",
) -> CloudConnectionCreate:
    common = {
        "provider": provider,
        "purpose": purpose,
        "display_name": f"{provider.upper()} deployment",
        "permission_set_version": permission_set_version,
    }
    if purpose == "pricing":
        common.pop("permission_set_version")
    if provider == "aws":
        common["aws"] = {
            "access_key_id": "AKIAREADINESSFIXTURE",
            "secret_access_key": _AWS_SECRET,
            "region": "eu-central-1",
        }
    elif provider == "azure":
        common["azure"] = {
            "subscription_id": "subscription-readiness",
            "client_id": "client-readiness",
            "client_secret": _AZURE_SECRET,
            "tenant_id": "tenant-readiness",
            "region": "westeurope",
        }
    elif provider == "gcp":
        common["gcp"] = {
            "project_id": "readiness-project",
            "billing_account": "012345-6789AB-CDEF01",
            "region": "europe-west1",
            "service_account_json": json.dumps(
                {
                    "type": "service_account",
                    "project_id": "readiness-project",
                    "client_email": "deployer@readiness-project.iam.gserviceaccount.com",
                    "private_key": _GCP_SECRET,
                }
            ),
        }
    else:  # pragma: no cover - test helper guard
        raise AssertionError(f"Unsupported test provider: {provider}")
    return CloudConnectionCreate.model_validate(common)


def _create_twin(
    db,
    user: User,
    providers: tuple[str, ...],
    *,
    permission_versions: dict[str, str | None] | None = None,
    purposes: dict[str, str] | None = None,
) -> tuple[DigitalTwin, dict[str, CloudConnection]]:
    twin = DigitalTwin(
        name=f"Readiness Twin {len(db.query(DigitalTwin).all())}",
        user_id=user.id,
        state=TwinState.CONFIGURED,
    )
    db.add(twin)
    db.flush()

    path = {
        "cheapest_l1": providers[0] if providers else None,
        "cheapest_l2": providers[1] if len(providers) > 1 else None,
        "cheapest_l3_hot": providers[2] if len(providers) > 2 else None,
        "cheapest_l3_cool": providers[0] if providers else None,
    }
    db.add(OptimizerConfiguration(twin_id=twin.id, **path))
    config = TwinConfiguration(twin_id=twin.id)
    db.add(config)
    db.commit()

    connections: dict[str, CloudConnection] = {}
    service = CloudConnectionService(db)
    for provider in sorted(set(providers)):
        response = service.create_connection(
            user.id,
            _connection_request(
                provider,
                permission_set_version=(permission_versions or {}).get(
                    provider,
                    "thesis-demo-v1",
                ),
                purpose=(purposes or {}).get(provider, "deployment"),
            ),
        )
        connection = db.query(CloudConnection).filter_by(id=response.id).one()
        connections[provider] = connection
        setattr(config, f"{provider}_cloud_connection_id", connection.id)
    db.commit()
    db.refresh(twin)
    return twin, connections


async def _successful_validator(provider, optimizer_credentials, deployer_credentials):
    assert optimizer_credentials
    assert deployer_credentials
    return {
        "provider": provider,
        "valid": True,
        "optimizer": {"valid": True, "message": "Optimizer access passed"},
        "deployer": {
            "valid": True,
            "message": "Deployer access passed",
            "permissions": [],
        },
    }


def test_cached_readiness_is_fail_closed_without_provider_calls(db_session):
    user = _create_user(db_session)
    twin, _ = _create_twin(db_session, user, ("aws",))

    async def forbidden_validator(*_args):  # pragma: no cover - must not be called
        raise AssertionError("cached readiness contacted a provider")

    response = DeploymentReadinessService(
        db_session,
        validator=forbidden_validator,
    ).get_cached(twin.id, user.id)

    assert response.schema_version == "deployment-readiness.v1"
    assert response.ready is False
    assert response.required_providers == ["aws"]
    assert response.providers[0].status == "not_checked"
    assert response.providers[0].checks[0].code == "PREFLIGHT_NOT_RUN"


def test_readiness_contract_rejects_inconsistent_or_empty_provider_evidence():
    base = {
        "twin_id": "twin-contract",
        "ready": True,
        "summary": "Ready",
        "required_providers": ["aws"],
        "providers": [
            {
                "provider": "aws",
                "connection_id": "connection-1",
                "connection_display_name": "AWS deployment",
                "ready": True,
                "status": "ready",
                "summary": "Ready",
                "expected_permission_set_version": "thesis-demo-v1",
                "supplied_permission_set_version": "thesis-demo-v1",
                "permission_set_status": "matched",
                "checked_at": "2026-07-14T09:00:00Z",
                "checks": [
                    {
                        "component": "deployer",
                        "status": "passed",
                        "code": "OK",
                        "message": "Access passed.",
                        "action": "No action required.",
                        "permissions": [],
                    }
                ],
            }
        ],
        "checked_at": "2026-07-14T09:00:00Z",
        "issues": [],
    }
    assert DeploymentReadinessResponse.model_validate(base).ready is True

    inconsistent = json.loads(json.dumps(base))
    inconsistent["providers"][0]["status"] = "review_required"
    with pytest.raises(PydanticValidationError):
        DeploymentReadinessResponse.model_validate(inconsistent)

    empty_checks = json.loads(json.dumps(base))
    empty_checks["providers"][0]["checks"] = []
    with pytest.raises(PydanticValidationError):
        DeploymentReadinessResponse.model_validate(empty_checks)

    wrong_order = json.loads(json.dumps(base))
    wrong_order["providers"][0]["provider"] = "gcp"
    with pytest.raises(PydanticValidationError):
        DeploymentReadinessResponse.model_validate(wrong_order)


@pytest.mark.asyncio
async def test_three_provider_preflight_is_deterministic_cached_and_secret_free(db_session):
    user = _create_user(db_session)
    twin, _ = _create_twin(db_session, user, ("gcp", "aws", "azure"))
    calls = []

    async def validator(provider, optimizer_credentials, deployer_credentials):
        calls.append(provider)
        return await _successful_validator(
            provider,
            optimizer_credentials,
            deployer_credentials,
        )

    service = DeploymentReadinessService(db_session, validator=validator)
    preflight = await service.run_preflight(twin.id, user.id)
    cached = service.get_cached(twin.id, user.id)

    assert preflight.schema_version == "deployment-preflight.v1"
    assert preflight.ready is True
    assert preflight.required_providers == ["aws", "azure", "gcp"]
    assert [provider.provider for provider in preflight.providers] == ["aws", "azure", "gcp"]
    assert sorted(calls) == ["aws", "azure", "gcp"]
    assert cached.ready is True
    assert db_session.query(DeploymentPreflightCache).filter_by(twin_id=twin.id).count() == 3

    serialized = preflight.model_dump_json()
    persisted = " ".join(
        entry.checks_json
        for entry in db_session.query(DeploymentPreflightCache).filter_by(twin_id=twin.id)
    )
    for secret in (_AWS_SECRET, _AZURE_SECRET, _GCP_SECRET):
        assert secret not in serialized
        assert secret not in persisted


@pytest.mark.asyncio
async def test_secret_echo_from_validator_is_redacted_in_response_and_cache(db_session):
    user = _create_user(db_session)
    twin, _ = _create_twin(db_session, user, ("aws",))

    async def leaking_validator(provider, _optimizer_credentials, _deployer_credentials):
        return {
            "provider": provider,
            "valid": False,
            "optimizer": {"valid": False, "message": f"Rejected {_AWS_SECRET}"},
            "deployer": {"valid": False, "message": f"Rejected {_AWS_SECRET}"},
        }

    response = await DeploymentReadinessService(
        db_session,
        validator=leaking_validator,
    ).run_preflight(twin.id, user.id)
    entry = db_session.query(DeploymentPreflightCache).filter_by(twin_id=twin.id).one()

    assert response.ready is False
    assert _AWS_SECRET not in response.model_dump_json()
    assert _AWS_SECRET not in entry.checks_json
    assert "[REDACTED]" in response.model_dump_json()


@pytest.mark.asyncio
async def test_missing_wrong_purpose_and_outdated_connections_fail_closed(db_session):
    user = _create_user(db_session)

    missing_twin, _ = _create_twin(db_session, user, ("aws",))
    missing_twin.configuration.aws_cloud_connection_id = None
    wrong_twin, _ = _create_twin(
        db_session,
        user,
        ("aws",),
        purposes={"aws": "pricing"},
    )
    outdated_twin, _ = _create_twin(
        db_session,
        user,
        ("aws",),
        permission_versions={"aws": "legacy-v0"},
    )
    db_session.commit()
    calls = []

    async def validator(provider, optimizer_credentials, deployer_credentials):
        calls.append(provider)
        return await _successful_validator(provider, optimizer_credentials, deployer_credentials)

    service = DeploymentReadinessService(db_session, validator=validator)
    missing = await service.run_preflight(missing_twin.id, user.id)
    wrong = await service.run_preflight(wrong_twin.id, user.id)
    outdated = await service.run_preflight(outdated_twin.id, user.id)

    assert missing.providers[0].checks[0].code == "CLOUD_CONNECTION_MISSING"
    assert wrong.providers[0].checks[0].code == "CLOUD_CONNECTION_PURPOSE_INVALID"
    assert outdated.providers[0].permission_set_status == "outdated"
    assert outdated.providers[0].checks[0].code == "OUTDATED_PERMISSION_SET"
    assert missing.ready is wrong.ready is outdated.ready is False
    assert calls == ["aws"]


@pytest.mark.asyncio
async def test_cache_expires_after_ttl_or_connection_fingerprint_change(db_session):
    user = _create_user(db_session)
    twin, connections = _create_twin(db_session, user, ("aws",))
    checked_at = datetime(2026, 7, 14, 9, 0, 0)
    service = DeploymentReadinessService(
        db_session,
        validator=_successful_validator,
        clock=lambda: checked_at,
        max_age=timedelta(hours=24),
    )
    assert (await service.run_preflight(twin.id, user.id)).ready is True

    expired = DeploymentReadinessService(
        db_session,
        clock=lambda: checked_at + timedelta(hours=25),
        max_age=timedelta(hours=24),
    ).get_cached(twin.id, user.id)
    assert expired.providers[0].status == "stale"

    connections["aws"].payload_fingerprint = "rotated-fingerprint"
    db_session.commit()
    changed = DeploymentReadinessService(
        db_session,
        clock=lambda: checked_at + timedelta(hours=1),
    ).get_cached(twin.id, user.id)
    assert changed.providers[0].status == "stale"
    assert changed.providers[0].checks[0].code == "PREFLIGHT_CACHE_STALE"


@pytest.mark.asyncio
async def test_binding_change_during_preflight_discards_result(db_session):
    user = _create_user(db_session)
    twin, _ = _create_twin(db_session, user, ("aws",))

    async def changing_validator(provider, optimizer_credentials, deployer_credentials):
        twin.configuration.aws_cloud_connection_id = None
        db_session.commit()
        return await _successful_validator(provider, optimizer_credentials, deployer_credentials)

    response = await DeploymentReadinessService(
        db_session,
        validator=changing_validator,
    ).run_preflight(twin.id, user.id)

    assert response.ready is False
    assert response.providers[0].status == "stale"
    assert response.providers[0].checks[0].code == "CONNECTION_CHANGED_DURING_PREFLIGHT"
    assert db_session.query(DeploymentPreflightCache).filter_by(twin_id=twin.id).count() == 0


def test_missing_architecture_and_owner_mismatch_fail_closed(db_session):
    user = _create_user(db_session)
    other = _create_user(db_session, "other-readiness@example.test")
    twin, _ = _create_twin(db_session, user, ())
    service = DeploymentReadinessService(db_session)

    missing = service.get_cached(twin.id, user.id)

    assert missing.ready is False
    assert missing.required_providers == []
    assert missing.issues[0].code == "DEPLOYMENT_ARCHITECTURE_MISSING"
    with pytest.raises(EntityNotFoundError, match="Twin not found"):
        service.get_cached(twin.id, other.id)


@pytest.mark.asyncio
async def test_deploy_guard_requires_current_successful_preflight(db_session):
    user = _create_user(db_session)
    twin, _ = _create_twin(db_session, user, ("aws",))
    service = DeploymentReadinessService(db_session, validator=_successful_validator)

    with pytest.raises(ValidationError) as exc_info:
        service.require_ready(twin.id, user.id)
    assert exc_info.value.detail == {
        "code": "DEPLOYMENT_PREFLIGHT_REQUIRED",
        "failure_codes": ["PREFLIGHT_NOT_RUN"],
    }

    await service.run_preflight(twin.id, user.id)
    assert service.require_ready(twin.id, user.id).ready is True


def test_readiness_routes_are_owner_scoped_and_cached(authenticated_client, db_session):
    client, headers = authenticated_client
    user = db_session.query(User).one()
    twin, _ = _create_twin(db_session, user, ("aws",))

    response = client.get(f"/twins/{twin.id}/deployment-readiness", headers=headers)
    missing = client.get("/twins/not-owned/deployment-readiness", headers=headers)

    assert response.status_code == 200
    assert response.json()["schema_version"] == "deployment-readiness.v1"
    assert response.json()["providers"][0]["status"] == "not_checked"
    assert missing.status_code == 404


def test_preflight_route_delegates_to_owner_scoped_service(auth_client, test_twin, monkeypatch):
    calls = []

    class FakeReadinessService:
        async def run_preflight(self, twin_id, user_id):
            calls.append((twin_id, user_id))
            return {
                "schema_version": "deployment-preflight.v1",
                "twin_id": twin_id,
                "ready": False,
                "summary": "Deployment architecture must be completed before preflight.",
                "required_providers": [],
                "providers": [],
                "checked_at": None,
                "issues": [
                    {
                        "component": "architecture",
                        "status": "failed",
                        "code": "DEPLOYMENT_ARCHITECTURE_MISSING",
                        "message": "No provider architecture is stored.",
                        "action": "Complete optimization.",
                        "permissions": [],
                    }
                ],
            }

    monkeypatch.setattr(
        "src.api.routes.twin_operations._deployment_readiness_service",
        lambda _db: FakeReadinessService(),
    )

    response = auth_client.post(f"/twins/{test_twin.id}/deployment-preflight")

    assert response.status_code == 200
    assert response.json()["schema_version"] == "deployment-preflight.v1"
    assert calls == [(test_twin.id, test_twin.user_id)]
