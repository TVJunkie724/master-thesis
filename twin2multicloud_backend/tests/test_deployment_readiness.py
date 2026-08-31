"""Deployment readiness contract, cache, and preflight behavior."""

from __future__ import annotations

import json
from datetime import datetime, timedelta

import pytest
from pydantic import ValidationError as PydanticValidationError

from src.models.cloud_connection import CloudConnection
from src.models.deployment_preflight import DeploymentPreflightCache
from src.models.twin import DigitalTwin, TwinState
from src.models.twin_config import TwinConfiguration
from src.models.user import User
from src.schemas.cloud_connection import CloudConnectionCreate
from src.schemas.deployment_readiness import (
    DeploymentPreparationRequest,
    DeploymentReadinessCheck,
    DeploymentReadinessResponse,
)
from src.services.cloud_connection_service import CloudConnectionService
from src.services.credential_resolution_service import CredentialResolutionService
from src.services.deployment_readiness_service import DeploymentReadinessService
from src.services.service_errors import EntityNotFoundError, ValidationError

_AWS_SECRET = "aws-secret-value-for-redaction"
_AZURE_SECRET = "azure-secret-value-for-redaction"
_GCP_SECRET = "gcp-private-key-value-for-redaction"
_EXPECTED_PROVIDERS: dict[str, set[str]] = {}


@pytest.fixture(autouse=True)
def _selected_architecture_provider_projection(monkeypatch):
    _EXPECTED_PROVIDERS.clear()
    monkeypatch.setattr(
        CredentialResolutionService,
        "required_providers_from_architecture",
        staticmethod(lambda twin: set(_EXPECTED_PROVIDERS.get(twin.id, set()))),
    )

    async def resolve_requirements(_self, twin, _user_id):
        providers = sorted(_EXPECTED_PROVIDERS.get(twin.id, set()))
        requirements = [
            {
                "requirement_id": f"requirement.provider-scope.{provider}",
                "requirement_type": "provider_scope",
                "provider": provider,
            }
            for provider in providers
        ]
        return {
            "graph_evidence": {
                "architecture_digest": "sha256:" + "1" * 64,
                "graph_digest": "sha256:" + "2" * 64,
                "requirements_digest": "sha256:" + "3" * 64,
                "required_providers": providers,
            },
            "requirements": requirements,
            "preparation_plan": {
                "schema_version": "graph-account-preparation.v1",
                "graph_digest": "sha256:" + "2" * 64,
                "requirements_digest": "sha256:" + "3" * 64,
                "plan_digest": "sha256:" + "4" * 64,
                "actions": [],
                "manual_requirements": [],
            },
        }

    monkeypatch.setattr(
        DeploymentReadinessService,
        "_resolve_graph_requirements",
        resolve_requirements,
    )


def _create_user(db, email: str = "readiness@example.test") -> User:
    user = User(email=email, name="Readiness")
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _connection_request(
    provider: str,
    *,
    purpose: str = "deployment",
) -> CloudConnectionCreate:
    common = {
        "provider": provider,
        "purpose": purpose,
        "display_name": f"{provider.upper()} deployment",
    }
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
            "preparation_client_id": "preparation-client-readiness",
            "preparation_client_secret": "preparation-secret-for-redaction",
            "tenant_id": "tenant-readiness",
            "region": "westeurope",
        }
    elif provider == "gcp":
        common["gcp"] = {
            "project_id": "readiness-project",
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
    purposes: dict[str, str] | None = None,
) -> tuple[DigitalTwin, dict[str, CloudConnection]]:
    twin = DigitalTwin(
        name=f"Readiness Twin {len(db.query(DigitalTwin).all())}",
        user_id=user.id,
        state=TwinState.CONFIGURED,
    )
    db.add(twin)
    db.flush()
    _EXPECTED_PROVIDERS[twin.id] = set(providers)

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
                purpose=(purposes or {}).get(provider, "deployment"),
            ),
        )
        connection = db.query(CloudConnection).filter_by(id=response.id).one()
        connections[provider] = connection
        setattr(config, f"{provider}_cloud_connection_id", connection.id)
    db.commit()
    db.refresh(twin)
    return twin, connections


async def _successful_validator(provider, deployer_credentials):
    assert deployer_credentials
    return {
        "provider": provider,
        "valid": True,
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
                "checked_at": "2026-07-14T09:00:00Z",
                "graph_digest": "sha256:" + "2" * 64,
                "requirements_digest": "sha256:" + "3" * 64,
                "requirements": [
                    {
                        "requirement_id": "requirement.provider-scope.aws",
                        "requirement_type": "provider_scope",
                        "provider": "aws",
                        "capability_id": "aws.target-scope",
                        "preparation_mode": "none",
                        "mandatory": True,
                        "status": "ready",
                        "message": "Account scope is ready.",
                        "action": "No action required.",
                        "source_node_ids": ["node.aws"],
                        "source_edge_ids": [],
                    }
                ],
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
        "graph_digest": "sha256:" + "2" * 64,
        "requirements_digest": "sha256:" + "3" * 64,
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
async def test_three_provider_preflight_is_deterministic_cached_and_secret_free(
    db_session,
):
    user = _create_user(db_session)
    twin, _ = _create_twin(db_session, user, ("gcp", "aws", "azure"))
    calls = []

    async def validator(provider, deployer_credentials):
        calls.append(provider)
        return await _successful_validator(
            provider,
            deployer_credentials,
        )

    service = DeploymentReadinessService(db_session, validator=validator)
    preflight = await service.run_preflight(twin.id, user.id)
    cached = service.get_cached(twin.id, user.id)

    assert preflight.schema_version == "deployment-preflight.v1"
    assert preflight.ready is True
    assert preflight.required_providers == ["aws", "azure", "gcp"]
    assert [provider.provider for provider in preflight.providers] == [
        "aws",
        "azure",
        "gcp",
    ]
    assert sorted(calls) == ["aws", "azure", "gcp"]
    assert cached.ready is True
    assert (
        db_session.query(DeploymentPreflightCache).filter_by(twin_id=twin.id).count()
        == 3
    )

    serialized = preflight.model_dump_json()
    persisted = " ".join(
        entry.checks_json
        for entry in db_session.query(DeploymentPreflightCache).filter_by(
            twin_id=twin.id
        )
    )
    for secret in (_AWS_SECRET, _AZURE_SECRET, _GCP_SECRET):
        assert secret not in serialized
        assert secret not in persisted


@pytest.mark.asyncio
async def test_graph_api_requirement_is_preparable_when_provider_reports_it_missing(
    db_session,
):
    user = _create_user(db_session)
    twin, _ = _create_twin(db_session, user, ("gcp",))

    async def requirements_resolver(_twin, _user_id):
        return {
            "graph_evidence": {
                "architecture_digest": "sha256:" + "1" * 64,
                "graph_digest": "sha256:" + "2" * 64,
                "requirements_digest": "sha256:" + "3" * 64,
                "required_providers": ["gcp"],
            },
            "requirements": [
                {
                    "requirement_id": "requirement.api.gcp.run",
                    "requirement_type": "api",
                    "provider": "gcp",
                    "capability_id": "run.googleapis.com",
                    "preparation_mode": "confirmed_account",
                    "mandatory": True,
                    "source_node_ids": ["node.processing"],
                    "source_edge_ids": [],
                }
            ],
            "preparation_plan": {
                "schema_version": "graph-account-preparation.v1",
                "graph_digest": "sha256:" + "2" * 64,
                "requirements_digest": "sha256:" + "3" * 64,
                "plan_digest": "sha256:" + "4" * 64,
                "actions": [
                    {
                        "action_id": "prepare.gcp.enable_project_api.run.googleapis.com",
                        "provider": "gcp",
                        "action_type": "enable_project_api",
                        "capability_id": "run.googleapis.com",
                        "scope": "project",
                        "requirement_ids": ["requirement.api.gcp.run"],
                        "reason": "Required by the graph.",
                        "persistent_after_destroy": True,
                        "destructive": False,
                    }
                ],
                "manual_requirements": [],
            },
        }

    async def validator(_provider, _deployer):
        return {
            "deployer": {
                "valid": False,
                "message": "GCP deployment preflight failed",
                "checks": [
                    {
                        "name": "enabled_apis",
                        "status": "failed",
                        "code": "MISSING_APIS",
                        "message": "A required API is disabled.",
                        "action": "Enable the API.",
                        "apis": ["run.googleapis.com"],
                    }
                ],
            },
        }

    response = await DeploymentReadinessService(
        db_session,
        validator=validator,
        requirements_resolver=requirements_resolver,
    ).run_preflight(twin.id, user.id)

    requirement = response.providers[0].requirements[0]
    assert response.ready is False
    assert requirement.status == "preparable"
    assert requirement.capability_id == "run.googleapis.com"
    assert requirement.source_node_ids == ["node.processing"]


@pytest.mark.asyncio
async def test_confirmed_preparation_records_evidence_and_reruns_readiness(db_session):
    user = _create_user(db_session)
    twin, _ = _create_twin(db_session, user, ("gcp",))
    plan_digest = "sha256:" + "4" * 64
    requirements_digest = "sha256:" + "3" * 64
    calls = []

    async def requirements_resolver(_twin, _user_id):
        return {
            "graph_evidence": {
                "architecture_digest": "sha256:" + "1" * 64,
                "graph_digest": "sha256:" + "2" * 64,
                "requirements_digest": requirements_digest,
                "required_providers": ["gcp"],
            },
            "requirements": [
                {
                    "requirement_id": "requirement.api.gcp.run",
                    "requirement_type": "api",
                    "provider": "gcp",
                    "capability_id": "run.googleapis.com",
                    "scope": "project",
                    "preparation_mode": "confirmed_account",
                    "mandatory": True,
                    "source_node_ids": ["node.processing"],
                    "source_edge_ids": [],
                }
            ],
            "preparation_plan": {
                "schema_version": "graph-account-preparation.v1",
                "graph_digest": "sha256:" + "2" * 64,
                "requirements_digest": requirements_digest,
                "plan_digest": plan_digest,
                "actions": [
                    {
                        "action_id": "prepare.gcp.enable_project_api.run.googleapis.com",
                        "provider": "gcp",
                        "action_type": "enable_project_api",
                        "capability_id": "run.googleapis.com",
                        "scope": "project",
                        "requirement_ids": ["requirement.api.gcp.run"],
                        "reason": "Required by the graph.",
                        "persistent_after_destroy": True,
                        "destructive": False,
                    }
                ],
                "manual_requirements": [],
            },
        }

    async def prepare(_twin, _user_id, reviewed_digest):
        calls.append(reviewed_digest)
        return {
            "project_name": "factory",
            "plan_digest": plan_digest,
            "requirements_digest": requirements_digest,
            "status": "ready",
            "completed_actions": [
                {
                    "action_id": "prepare.gcp.enable_project_api.run.googleapis.com",
                    "provider": "gcp",
                    "capability_id": "run.googleapis.com",
                    "status": "ready",
                    "message": "API enabled.",
                }
            ],
            "failed_actions": [],
            "remaining_actions": [],
            "retry_safe": True,
        }

    service = DeploymentReadinessService(
        db_session,
        validator=_successful_validator,
        requirements_resolver=requirements_resolver,
        account_preparer=prepare,
    )
    initial = await service.run_preflight(twin.id, user.id)
    assert initial.providers[0].requirements[0].status == "preparable"

    result = await service.prepare_account(
        twin.id,
        user.id,
        DeploymentPreparationRequest(
            plan_digest=plan_digest,
            requirements_digest=requirements_digest,
            confirmed=True,
        ),
    )

    assert calls == [plan_digest]
    assert result.status == "ready"
    assert result.readiness.ready is True
    assert result.readiness.providers[0].requirements[0].status == "ready"


@pytest.mark.asyncio
async def test_unautomated_graph_prerequisite_remains_explicit_manual_action(
    db_session,
):
    user = _create_user(db_session)
    twin, _ = _create_twin(db_session, user, ("azure",))

    async def requirements_resolver(_twin, _user_id):
        return {
            "graph_evidence": {
                "architecture_digest": "sha256:" + "1" * 64,
                "graph_digest": "sha256:" + "2" * 64,
                "requirements_digest": "sha256:" + "3" * 64,
                "required_providers": ["azure"],
            },
            "requirements": [
                {
                    "requirement_id": "requirement.access.azure.graph",
                    "requirement_type": "access_prerequisite",
                    "provider": "azure",
                    "capability_id": "azure.microsoft-graph.authority",
                    "preparation_mode": "manual_external",
                    "mandatory": True,
                    "source_node_ids": ["node.twin-state"],
                    "source_edge_ids": [],
                }
            ],
            "preparation_plan": {
                "schema_version": "graph-account-preparation.v1",
                "graph_digest": "sha256:" + "2" * 64,
                "requirements_digest": "sha256:" + "3" * 64,
                "plan_digest": "sha256:" + "4" * 64,
                "actions": [],
                "manual_requirements": [
                    {
                        "requirement_id": "requirement.access.azure.graph",
                        "provider": "azure",
                        "capability_id": "azure.microsoft-graph.authority",
                        "reason": "Manual consent is required.",
                    }
                ],
            },
        }

    service = DeploymentReadinessService(
        db_session,
        validator=_successful_validator,
        requirements_resolver=requirements_resolver,
    )
    response = await service.run_preflight(twin.id, user.id)

    requirement = response.providers[0].requirements[0]
    assert response.ready is False
    assert requirement.status == "manual_action"
    assert "Microsoft Graph" in requirement.action

    prepared = await service.prepare_account(
        twin.id,
        user.id,
        DeploymentPreparationRequest(
            plan_digest="sha256:" + "4" * 64,
            requirements_digest="sha256:" + "3" * 64,
            confirmed=True,
            manual_requirement_ids=["requirement.access.azure.graph"],
        ),
    )
    assert prepared.status == "ready"
    assert prepared.readiness.ready is True
    assert prepared.acknowledged_manual_requirement_ids == [
        "requirement.access.azure.graph"
    ]


def test_identity_center_authority_check_resolves_manual_graph_requirement(db_session):
    requirement = {
        "requirement_id": "requirement.access.aws.identity-center",
        "requirement_type": "access_prerequisite",
        "provider": "aws",
        "capability_id": "aws.iam-identity-center.primary-region",
        "preparation_mode": "manual_external",
        "mandatory": True,
        "source_node_ids": ["node.twin-state"],
        "source_edge_ids": [],
    }
    check = DeploymentReadinessCheck(
        component="deployer.identity_center_primary_region",
        status="passed",
        code="IDENTITY_CENTER_PRIMARY_REGION_READY",
        message="Identity Center primary Region verified.",
        action="No action required.",
    )

    projected = DeploymentReadinessService(db_session)._project_requirement_readiness(
        requirement,
        [check],
    )

    assert projected.status == "ready"
    assert projected.action == "No action required."


def test_microsoft_graph_authority_check_resolves_manual_graph_requirement(db_session):
    requirement = {
        "requirement_id": "requirement.access.azure.graph",
        "requirement_type": "access_prerequisite",
        "provider": "azure",
        "capability_id": "azure.microsoft-graph.authority",
        "preparation_mode": "manual_external",
        "mandatory": True,
        "source_node_ids": ["node.twin-state"],
        "source_edge_ids": [],
    }
    check = DeploymentReadinessCheck(
        component="deployer.microsoft_graph_authority",
        status="passed",
        code="MICROSOFT_GRAPH_AUTHORITY_READY",
        message="Microsoft Graph authority verified.",
        action="No action required.",
    )

    projected = DeploymentReadinessService(db_session)._project_requirement_readiness(
        requirement,
        [check],
    )

    assert projected.status == "ready"


def test_optional_authority_checks_are_filtered_by_resolved_graph():
    checks = [
        DeploymentReadinessCheck(
            component="deployer.microsoft_graph_authority",
            status="failed",
            code="MICROSOFT_GRAPH_CONSENT_REQUIRED",
            message="Consent missing.",
            action="Grant consent.",
        ),
        DeploymentReadinessCheck(
            component="deployer.credentials",
            status="passed",
            code="AZURE_READY",
            message="Subscription ready.",
            action="No action required.",
        ),
    ]

    filtered = DeploymentReadinessService._checks_for_graph(
        checks,
        [
            {
                "capability_id": "credential.azure.owner",
                "provider": "azure",
            }
        ],
    )

    assert [check.code for check in filtered] == ["AZURE_READY"]


def test_split_azure_authority_failures_remain_independent():
    checks = [
        DeploymentReadinessCheck(
            component="deployer.credentials",
            status="failed",
            code="AZURE_DEPLOYMENT_RBAC_AUTHORITY_FORBIDDEN",
            message="Deployment authority is too broad.",
            action="Replace the deployment principal role.",
        ),
        DeploymentReadinessCheck(
            component="deployer.credentials",
            status="failed",
            code="AZURE_PREPARATION_RBAC_CONDITION_INVALID",
            message="Preparation condition is invalid.",
            action="Repair the bounded condition.",
        ),
        DeploymentReadinessCheck(
            component="deployer.microsoft_graph_authority",
            status="failed",
            code="MICROSOFT_GRAPH_AUTHORITY_OVERPRIVILEGED",
            message="Graph authority is too broad.",
            action="Replace the Graph permission set.",
        ),
    ]

    with_graph = DeploymentReadinessService._checks_for_graph(
        checks,
        [
            {
                "capability_id": "azure.microsoft-graph.authority",
                "provider": "azure",
            }
        ],
    )
    without_graph = DeploymentReadinessService._checks_for_graph(checks, [])

    assert [check.code for check in with_graph] == [
        "AZURE_DEPLOYMENT_RBAC_AUTHORITY_FORBIDDEN",
        "AZURE_PREPARATION_RBAC_CONDITION_INVALID",
        "MICROSOFT_GRAPH_AUTHORITY_OVERPRIVILEGED",
    ]
    assert [check.code for check in without_graph] == [
        "AZURE_DEPLOYMENT_RBAC_AUTHORITY_FORBIDDEN",
        "AZURE_PREPARATION_RBAC_CONDITION_INVALID",
    ]


@pytest.mark.asyncio
async def test_secret_echo_from_validator_is_redacted_in_response_and_cache(db_session):
    user = _create_user(db_session)
    twin, _ = _create_twin(db_session, user, ("aws",))

    async def leaking_validator(provider, _deployer_credentials):
        return {
            "provider": provider,
            "valid": False,
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
async def test_missing_connections_fail_closed(db_session):
    user = _create_user(db_session)

    missing_twin, _ = _create_twin(db_session, user, ("aws",))
    missing_twin.configuration.aws_cloud_connection_id = None
    db_session.commit()
    calls = []

    async def validator(provider, deployer_credentials):
        calls.append(provider)
        return await _successful_validator(provider, deployer_credentials)

    service = DeploymentReadinessService(db_session, validator=validator)
    missing = await service.run_preflight(missing_twin.id, user.id)

    assert missing.providers[0].checks[0].code == "CLOUD_CONNECTION_MISSING"
    assert missing.ready is False
    assert calls == []


@pytest.mark.asyncio
async def test_cache_expires_after_ttl_or_connection_fingerprint_change(db_session):
    user = _create_user(db_session)
    twin, connections = _create_twin(db_session, user, ("aws",))
    checked_at = datetime(2026, 7, 14, 9, 0, 0)  # noqa: DTZ001 - SQLite is naive
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

    async def changing_validator(provider, deployer_credentials):
        twin.configuration.aws_cloud_connection_id = None
        db_session.commit()
        return await _successful_validator(provider, deployer_credentials)

    response = await DeploymentReadinessService(
        db_session,
        validator=changing_validator,
    ).run_preflight(twin.id, user.id)

    assert response.ready is False
    assert response.providers[0].status == "stale"
    assert response.providers[0].checks[0].code == "CONNECTION_CHANGED_DURING_PREFLIGHT"
    assert (
        db_session.query(DeploymentPreflightCache).filter_by(twin_id=twin.id).count()
        == 0
    )


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


def test_preflight_route_delegates_to_owner_scoped_service(
    auth_client, test_twin, monkeypatch
):
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


def test_preparation_route_requires_typed_confirmation_and_delegates(
    auth_client,
    test_twin,
    monkeypatch,
):
    calls = []
    plan_digest = "sha256:" + "4" * 64
    requirements_digest = "sha256:" + "3" * 64

    class FakeReadinessService:
        async def prepare_account(self, twin_id, user_id, request):
            calls.append((twin_id, user_id, request))
            return {
                "schema_version": "deployment-preparation.v1",
                "twin_id": twin_id,
                "plan_digest": plan_digest,
                "requirements_digest": requirements_digest,
                "status": "manual_action",
                "completed_actions": [],
                "failed_actions": [],
                "remaining_action_ids": [],
                "acknowledged_manual_requirement_ids": [],
                "pending_manual_requirement_ids": ["requirement.manual.aws"],
                "retry_safe": True,
                "readiness": {
                    "schema_version": "deployment-preflight.v1",
                    "twin_id": twin_id,
                    "ready": False,
                    "summary": "One provider needs review.",
                    "required_providers": [],
                    "providers": [],
                    "checked_at": None,
                    "graph_digest": None,
                    "requirements_digest": None,
                    "preparation_plan": None,
                    "issues": [
                        {
                            "component": "architecture",
                            "status": "failed",
                            "code": "MANUAL_ACTION_REQUIRED",
                            "message": "Manual action remains.",
                            "action": "Confirm it.",
                            "permissions": [],
                        }
                    ],
                },
            }

    monkeypatch.setattr(
        "src.api.routes.twin_operations._deployment_readiness_service",
        lambda _db: FakeReadinessService(),
    )

    response = auth_client.post(
        f"/twins/{test_twin.id}/deployment-preparation",
        json={
            "plan_digest": plan_digest,
            "requirements_digest": requirements_digest,
            "confirmed": True,
            "manual_requirement_ids": [],
        },
    )

    assert response.status_code == 200
    assert response.json()["schema_version"] == "deployment-preparation.v1"
    assert calls[0][0:2] == (test_twin.id, test_twin.user_id)
    assert calls[0][2].confirmed is True
