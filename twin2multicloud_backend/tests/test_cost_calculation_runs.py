"""Management boundary tests for Six-layer optimizer runs."""

from __future__ import annotations

import copy
import json

import pytest

from src.models.architecture_profile import ResolvedTwinArchitectureRecord
from src.models.cost_calculation import CostCalculationResultItem, CostCalculationRun
from src.models.twin import DigitalTwin, TwinState
from src.models.user import User
from src.models.user_function_extension import (
    TwinExtensionBinding,
    UserFunctionArtifact,
)
from src.schemas.optimizer_calculation import (
    SIX_LAYER_WORKLOAD_ROOT,
    OptimizerCalculationParams,
)
from src.services.architecture_contract_service import (
    calculate_digest as calculate_architecture_digest,
    calculate_resolution_id,
)
from src.services.architecture_errors import ArchitectureDomainError
from src.services.architecture_profile_service import ArchitectureProfileService
from src.services.aws_twinmaker_pricing_context_service import (
    ResolvedAwsTwinMakerPricingContext,
)
from src.services.cost_calculation_run_service import (
    CostCalculationRunService,
    _validate_profile_workload_pair,
)
from src.services.errors import (
    CostCalculationRunSelectionError,
    OptimizerContractError,
)
from src.services.resolved_deployment_specification_service import calculate_digest
from src.services.user_function_extension_service import (
    runtime as extension_contract,
)
from tests.pricing_catalog_test_data import catalog_reference
from tests.test_six_layer_cost_ledger_service import _fixture


class FakeSixLayerOptimizerClient:
    def __init__(self, architecture_mutator=None):
        self.architecture_mutator = architecture_mutator
        self.calls: list[dict] = []

    async def calculate(self, params):
        self.calls.append(params)
        specification, architecture, _workload, context, ledger = _fixture()
        run_id = params["calculationRunId"]
        evidence = {
            provider: reference.content_digest
            for provider, reference in context.catalogs.items()
        }
        providers = sorted(
            {item["provider"] for item in specification["component_selections"]}
        )
        specification["calculation_run_id"] = run_id
        specification["optimization_context"]["pricing_evidence_refs"] = [
            {"provider": provider, "digest": evidence[provider]}
            for provider in providers
        ]

        aws_context = copy.deepcopy(params["providerPricingContexts"]["awsTwinMaker"])
        if aws_context.get("status") == "available":
            aws_context["status"] = "compatible"
        else:
            specification["readiness"]["blocking_gate_ids"].append(
                "gate.live-pricing.aws.twinmaker-account-plan"
            )
            specification["readiness"]["blocking_gate_ids"] = sorted(
                set(specification["readiness"]["blocking_gate_ids"])
            )
        specification["digest"] = calculate_digest(specification)

        architecture["calculation_run_id"] = run_id
        architecture["deployment_specification_ref"] = {
            "schema_version": specification["schema_version"],
            "calculation_run_id": run_id,
            "digest": specification["digest"],
        }
        architecture["pricing_evidence_refs"] = [
            {
                "id": context.catalogs[provider].snapshot_id,
                "version": "1",
                "digest": evidence[provider],
                "provider": provider,
                "currency": "USD",
            }
            for provider in providers
        ]
        trusted_extension = params["extensionBindings"][0]
        architecture["extension_bindings"][0].update(
            {
                "slot_id": trusted_extension["slotId"],
                "slot_version": trusted_extension["slotVersion"],
                "artifact_id": trusted_extension["artifactId"],
                "artifact_digest": trusted_extension["artifactDigest"],
                "configuration_digest": trusted_extension["configurationDigest"],
            }
        )
        architecture["resolution_id"] = calculate_resolution_id(architecture)
        architecture["content_digest"] = calculate_architecture_digest(architecture)
        if self.architecture_mutator is not None:
            self.architecture_mutator(architecture)

        assignment = {
            item["logical_component_id"]: item["provider"].upper()
            for item in architecture["component_assignments"]
        }
        result = {
            "calculationResult": {
                "L1": assignment["component.ingestion"],
                "L2": assignment["component.processing"],
                "L3": {
                    "Hot": assignment["component.hot-storage"],
                    "Cool": assignment["component.cool-storage"],
                    "Archive": assignment["component.archive-storage"],
                },
                "L4": assignment["component.twin-state"],
                "L5": assignment["component.visualization"],
                "Eventing": assignment["component.eventing"],
            },
            "cheapestPath": [
                f"{logical_id}:{provider}"
                for logical_id, provider in sorted(assignment.items())
            ],
            "totalCost": 0.0,
            "totalCostExact": "0",
            "currency": "USD",
            "optimization_profile_id": "cost-minimization-v2",
            "result_schema_version": "cost-result.v2",
            "optimizationProfile": {
                "enabled": True,
                "profile_version": "2",
                "scoring_strategy_id": "profile-local-min-total-cost-v2",
                "calculation_model_ids": ["profile-resolution-v2@2"],
                "pricing_registry_version": "phase-08-complete-service-pricing@1",
            },
            "evidenceReferences": {
                "pricing_registry": "phase-08-complete-service-pricing@1"
            },
            "providerPricingContexts": {"awsTwinMaker": aws_context},
            "pricingCatalogs": params["providerPricingCatalogs"],
            "costLedger": ledger,
            "resolvedTwinArchitecture": architecture,
            "resolvedDeploymentSpecification": specification,
        }
        return {"result": result}

    async def get_pricing_catalog_baseline(self, provider):
        return catalog_reference(provider).to_http_dict()

    async def get_exact_pricing_catalog_reference(
        self,
        provider,
        pricing_region,
        snapshot_id,
    ):
        reference = catalog_reference(provider)
        return {"reference": reference.to_http_dict(), "isFresh": True}


class FakeAwsTwinMakerContextService:
    def __init__(self, payload, source_refresh_run_id):
        self.payload = payload
        self.source_refresh_run_id = source_refresh_run_id

    async def resolve(self, _user_id, _aws_catalog_reference):
        return ResolvedAwsTwinMakerPricingContext(
            payload=self.payload,
            source_refresh_run_id=self.source_refresh_run_id,
        )


def _available_aws_context():
    return {
        "schemaVersion": "aws-twinmaker-account-pricing-context.v1",
        "status": "available",
        "sourceRefreshRunId": "aws-refresh-1",
        "connectionFingerprint": "sha256:" + ("a" * 64),
        "providerAccountId": "123456789012",
        "pricingRegion": "eu-central-1",
        "catalogSnapshotDigest": catalog_reference("aws").content_digest,
        "observedAt": "2026-07-17T12:00:00Z",
        "currentPlan": {
            "mode": "STANDARD",
            "billableEntityCount": 10,
            "effectiveAt": None,
            "updatedAt": None,
            "updateReason": None,
            "bundle": None,
        },
        "pendingPlan": None,
    }


def _params() -> OptimizerCalculationParams:
    payload = json.loads(
        (SIX_LAYER_WORKLOAD_ROOT / "fixtures" / "valid" / "core-small.json").read_text(
            encoding="utf-8"
        )
    )
    return OptimizerCalculationParams.model_validate(payload)


def _twin_state(db_session):
    _specification, architecture, _workload, _context, _ledger = _fixture()
    extension = architecture["extension_bindings"][0]
    user = User(email="six-layer-run@example.test", name="Six-layer Run")
    db_session.add(user)
    db_session.flush()
    twin = DigitalTwin(
        name="Six-layer Run Twin",
        user_id=user.id,
        state=TwinState.DRAFT,
    )
    db_session.add(twin)
    db_session.flush()
    db_session.add(
        ArchitectureProfileService.build_default_selection(
            twin_id=twin.id,
            user_id=user.id,
        )
    )
    artifact = UserFunctionArtifact(
        id=extension["artifact_id"],
        user_id=user.id,
        schema_version="user-function-artifact.v1",
        artifact_state="valid",
        artifact_digest=extension["artifact_digest"],
        slot_id=extension["slot_id"],
        slot_version=extension["slot_version"],
        runtime_id="python311",
        configuration_json="{}",
        declared_capabilities_json="[]",
        validator_version="user-function-validator.v1",
        created_by=user.id,
    )
    db_session.add(artifact)
    db_session.flush()
    db_session.add(
        TwinExtensionBinding(
            id="six-layer-run-binding",
            user_id=user.id,
            twin_id=twin.id,
            slot_id=extension["slot_id"],
            slot_version=extension["slot_version"],
            artifact_id=artifact.id,
            binding_digest=extension_contract.binding_digest(
                twin_id=twin.id,
                slot_id=extension["slot_id"],
                slot_version=extension["slot_version"],
                artifact_id=artifact.id,
                artifact_digest=artifact.artifact_digest,
            ),
            active=True,
            revision=1,
        )
    )
    db_session.commit()
    return user, twin


def _service(db_session, optimizer, aws_context=None):
    return CostCalculationRunService(
        db_session,
        optimizer_client=optimizer,
        aws_twinmaker_contexts=FakeAwsTwinMakerContextService(
            aws_context or _available_aws_context(),
            "aws-refresh-1" if aws_context is None else None,
        ),
        architecture_resolution_enabled=True,
    )


def test_workload_is_bound_to_the_only_active_profile():
    params = _params()
    _validate_profile_workload_pair(
        params,
        {"profileId": "six-layer-eventing", "profileVersion": "1"},
    )
    with pytest.raises(ArchitectureDomainError):
        _validate_profile_workload_pair(
            params,
            {"profileId": "six-layer-eventing", "profileVersion": "2"},
        )


@pytest.mark.asyncio
async def test_run_persists_complete_six_layer_evaluation_evidence(db_session):
    user, twin = _twin_state(db_session)
    optimizer = FakeSixLayerOptimizerClient()

    run = await _service(db_session, optimizer).create_run(twin.id, user.id, _params())

    assert run.status == "succeeded"
    assert run.optimization_profile_id == "cost-minimization-v2"
    assert (
        run.deployment_specification_version == "resolved-deployment-specification.v2"
    )
    assert run.resolved_architecture_version == "resolved-twin-architecture.v2"
    assert run.deployment_compatibility_status == "ready"
    assert run.architecture_compatibility_status == "ready"
    assert len(run.resolved_architecture.components) == 8
    assert len(run.resolved_architecture.edges) == 9
    assert len(run.result_items) > 0
    assert optimizer.calls[0]["architectureProfile"]["profileVersion"] == "1"

    with pytest.raises(CostCalculationRunSelectionError) as rejected:
        await _service(db_session, optimizer).select_for_deployment(
            twin.id,
            user.id,
            run.id,
        )
    assert rejected.value.error_code == "DEPLOYMENT_CAPACITY_EVIDENCE_PENDING"


@pytest.mark.asyncio
async def test_unobserved_aws_plan_is_an_explicit_offline_gate(db_session):
    user, twin = _twin_state(db_session)
    unavailable = {
        "status": "unavailable",
        "reasonCode": "AWS_TWINMAKER_PLAN_UNOBSERVED",
    }

    run = await _service(
        db_session,
        FakeSixLayerOptimizerClient(),
        unavailable,
    ).create_run(twin.id, user.id, _params())

    readiness = json.loads(run.deployment_specification_json)["readiness"]
    assert (
        "gate.live-pricing.aws.twinmaker-account-plan" in readiness["blocking_gate_ids"]
    )


@pytest.mark.asyncio
async def test_architecture_resolution_gate_cannot_be_disabled(db_session):
    user = User(email="six-layer-gate@example.test", name="Six-layer Gate")
    db_session.add(user)
    db_session.flush()
    twin = DigitalTwin(name="Gate Twin", user_id=user.id, state=TwinState.DRAFT)
    db_session.add(twin)
    db_session.commit()
    optimizer = FakeSixLayerOptimizerClient()
    service = CostCalculationRunService(
        db_session,
        optimizer_client=optimizer,
        architecture_resolution_enabled=False,
    )

    with pytest.raises(ArchitectureDomainError) as rejected:
        await service.create_run(twin.id, user.id, _params())

    assert rejected.value.code == "ARCH_PROFILE_NOT_ACTIVE"
    assert optimizer.calls == []


def test_result_total_requires_exact_reconciliation(db_session):
    result = {
        "calculationResult": {},
        "cheapestPath": [],
        "totalCost": 12.5,
        "totalCostExact": "12.5",
        "currency": "USD",
        "optimization_profile_id": "cost-minimization-v2",
        "result_schema_version": "cost-result.v2",
        "optimizationProfile": {
            "profile_version": "2",
            "scoring_strategy_id": "profile-local-min-total-cost-v2",
            "calculation_model_ids": ["profile-resolution-v2@2"],
            "pricing_registry_version": "phase-08-complete-service-pricing@1",
        },
        "evidenceReferences": {
            "pricing_registry": "phase-08-complete-service-pricing@1"
        },
    }
    service = CostCalculationRunService(db_session)
    assert service._validate_optimizer_result(result)["total_monthly_cost"] == 12.5

    result["totalCostExact"] = "12.6"
    with pytest.raises(OptimizerContractError) as rejected:
        service._validate_optimizer_result(result)
    assert rejected.value.errors[0]["field"] == "totalCostExact"


@pytest.mark.asyncio
async def test_invalid_architecture_persists_only_bounded_failure(db_session):
    user, twin = _twin_state(db_session)

    def tamper(architecture):
        architecture["content_digest"] = "sha256:" + ("0" * 64)

    with pytest.raises(OptimizerContractError):
        await _service(
            db_session,
            FakeSixLayerOptimizerClient(architecture_mutator=tamper),
        ).create_run(twin.id, user.id, _params())

    failed = db_session.query(CostCalculationRun).one()
    assert failed.status == "failed"
    assert failed.deployment_compatibility_status == "unavailable"
    assert failed.architecture_compatibility_status == "unavailable"
    assert failed.result_summary_json is None
    assert failed.resolved_architecture is None
    assert db_session.query(ResolvedTwinArchitectureRecord).count() == 0
    assert db_session.query(CostCalculationResultItem).count() == 0
