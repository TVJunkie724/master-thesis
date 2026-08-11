import copy
import json
from uuid import UUID

import pytest
from sqlalchemy.exc import IntegrityError

from src.api.routes.optimizer_runs import get_optimizer_client
from src.config import settings
from src.models.architecture_profile import ResolvedTwinArchitectureRecord
from src.models.cost_calculation import (
    CostCalculationResultItem,
    CostCalculationRun,
)
from src.models.optimizer_config import OptimizerConfiguration
from src.models.twin import DigitalTwin, TwinState
from src.models.user import User
from src.models.user_function_extension import (
    TwinExtensionBinding,
    UserFunctionArtifact,
)
from src.schemas.optimizer_calculation import (
    FIVE_LAYER_V2_WORKLOAD_ROOT,
    FiveLayerV2OptimizerCalculationParams,
    OptimizerCalculationParams,
)
from src.schemas.architecture_profile import PinnedArchitectureReference
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
    ExternalServiceError,
    ExternalServiceUnavailable,
    OptimizerContractError,
)
from src.services.resolved_deployment_specification_service import (
    calculate_digest,
)
from src.services.user_function_extension_service import (
    runtime as extension_contract,
)
from tests.architecture_test_data import (
    calculation_result_and_contracts,
    linked_architecture_fixture_documents,
)
from tests.conftest import create_test_twin
from tests.optimizer_transfer_pricing_test_data import (
    transfer_pricing_result_fields,
)
from tests.pricing_catalog_test_data import catalog_context, catalog_reference
from tests.resolved_deployment_specification_test_data import (
    build_resolved_deployment_specification,
)
from tests.test_five_layer_v2_cost_ledger_service import (
    _fixture as five_layer_v2_evidence_fixture,
)


@pytest.fixture(autouse=True)
def _legacy_optimizer_api_uses_explicit_rollback_mode(monkeypatch):
    """Keep historical v1 route tests isolated from the active v2 default."""

    monkeypatch.setattr(
        settings,
        "ARCHITECTURE_PROFILE_RESOLUTION_ENABLED",
        False,
    )


class FakeOptimizerClient:
    def __init__(self, payload=None, exc=None, specification_mutator=None):
        self.payload = payload if payload is not None else _optimizer_payload()
        self.exc = exc
        self.specification_mutator = specification_mutator
        self.calls = []
        self.catalog_calls = []

    async def calculate(self, params):
        self.calls.append(params)
        if self.exc:
            raise self.exc
        result = self.payload.get("result", self.payload)
        if isinstance(result, dict):
            result["pricingCatalogs"] = params["providerPricingCatalogs"]
            if not all(
                key in result
                for key in (
                    "calculationResult",
                    "optimizationProfile",
                    "calculationStrategy",
                )
            ):
                return self.payload
            generated_specification = build_resolved_deployment_specification(
                result,
                calculation_run_id=params["calculationRunId"],
                pricing_catalogs=params["providerPricingCatalogs"],
            )
            if "resolvedDeploymentSpecification" not in result:
                result["resolvedDeploymentSpecification"] = generated_specification
            elif isinstance(result["resolvedDeploymentSpecification"], dict):
                generated_specification.update(
                    result["resolvedDeploymentSpecification"]
                )
                result["resolvedDeploymentSpecification"] = generated_specification
            if self.specification_mutator is not None and isinstance(
                result.get("resolvedDeploymentSpecification"),
                dict,
            ):
                self.specification_mutator(result["resolvedDeploymentSpecification"])
        return self.payload

    async def get_pricing_catalog_baseline(self, provider):
        self.catalog_calls.append(("baseline", provider))
        return catalog_reference(provider).to_http_dict()

    async def get_exact_pricing_catalog_reference(
        self,
        provider,
        pricing_region,
        snapshot_id,
    ):
        self.catalog_calls.append(("exact", provider, pricing_region, snapshot_id))
        reference = catalog_reference(provider)
        assert pricing_region == reference.pricing_region
        assert snapshot_id == reference.snapshot_id
        return {"reference": reference.to_http_dict(), "isFresh": True}


class FakeArchitectureOptimizerClient(FakeOptimizerClient):
    def __init__(self, *, architecture_mutator=None):
        super().__init__()
        self.architecture_mutator = architecture_mutator

    async def calculate(self, params):
        self.calls.append(params)
        _fixture_result, specification, architecture = (
            calculation_result_and_contracts()
        )
        result = _optimizer_payload()["result"]
        result["calculationResult"] = {
            "L1": "AWS",
            "L2": "Azure",
            "L3": {
                "Hot": "Azure",
                "Cool": "Azure",
                "Archive": "Azure",
            },
            "L4": "Azure",
            "L5": "Azure",
        }
        result["cheapestPath"] = [
            "L1_AWS",
            "L2_Azure",
            "L3_hot_Azure",
            "L3_cool_Azure",
            "L3_archive_Azure",
            "L4_Azure",
            "L5_Azure",
        ]
        result["totalCost"] = 7.6
        result["totalCostExact"] = "7.6"
        result["optimizationProfile"]["profile_version"] = "1"
        result["optimizationProfile"]["pricing_registry_version"] = "2026.07.17"
        result["pricingCatalogs"] = params["providerPricingCatalogs"]
        _sync_transfer_pricing(result)

        specification["calculation_run_id"] = params["calculationRunId"]
        specification["digest"] = calculate_digest(specification)
        architecture["calculation_run_id"] = params["calculationRunId"]
        architecture["deployment_specification_ref"]["calculation_run_id"] = params[
            "calculationRunId"
        ]
        architecture["deployment_specification_ref"]["digest"] = specification["digest"]
        architecture["resolution_id"] = calculate_resolution_id(architecture)
        architecture["content_digest"] = calculate_architecture_digest(architecture)
        if self.architecture_mutator is not None:
            self.architecture_mutator(architecture)
        result["resolvedDeploymentSpecification"] = specification
        result["resolvedTwinArchitecture"] = architecture
        return {"result": result}


class FakeFiveLayerV2OptimizerClient(FakeOptimizerClient):
    async def calculate(self, params):
        self.calls.append(params)
        specification, architecture, _workload, context, ledger = (
            five_layer_v2_evidence_fixture("small")
        )
        run_id = params["calculationRunId"]
        evidence = {
            provider: reference.content_digest
            for provider, reference in context.catalogs.items()
        }
        specification["calculation_run_id"] = run_id
        specification["optimization_context"]["pricing_evidence_refs"] = [
            {"provider": "aws", "digest": evidence["aws"]}
        ]
        specification["digest"] = calculate_digest(specification)

        architecture["calculation_run_id"] = run_id
        architecture["deployment_specification_ref"] = {
            "schema_version": "resolved-deployment-specification.v2",
            "calculation_run_id": run_id,
            "digest": specification["digest"],
        }
        architecture["pricing_evidence_refs"] = [
            {
                "id": "pricing-evidence.aws.test",
                "version": "1",
                "digest": evidence["aws"],
                "provider": "aws",
                "currency": "USD",
            }
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
        aws_context = copy.deepcopy(params["providerPricingContexts"]["awsTwinMaker"])
        if aws_context.get("status") == "available":
            aws_context["status"] = "compatible"
        result = {
            "calculationResult": {
                "L1": "AWS",
                "L2": "AWS",
                "L3": {"Hot": "AWS", "Cool": "AWS", "Archive": "AWS"},
                "L4": "AWS",
                "L5": "AWS",
            },
            "cheapestPath": [
                "L1_AWS",
                "L2_AWS",
                "L3_hot_AWS",
                "L3_cool_AWS",
                "L3_archive_AWS",
                "L4_AWS",
                "L5_AWS",
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
                "pricing_registry_version": ("phase-08-complete-service-pricing@1"),
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


class FakeAwsTwinMakerContextService:
    def __init__(self, payload, source_refresh_run_id):
        self.payload = payload
        self.source_refresh_run_id = source_refresh_run_id
        self.calls = []

    async def resolve(self, user_id, aws_catalog_reference):
        self.calls.append((user_id, aws_catalog_reference))
        return ResolvedAwsTwinMakerPricingContext(
            payload=self.payload,
            source_refresh_run_id=self.source_refresh_run_id,
        )


def _available_aws_context(source_refresh_run_id="aws-refresh-1"):
    return {
        "schemaVersion": "aws-twinmaker-account-pricing-context.v1",
        "status": "available",
        "sourceRefreshRunId": source_refresh_run_id,
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


def _architecture_twin_state(db_session):
    user = User(
        email="architecture-run@example.test",
        name="Architecture Run",
    )
    db_session.add(user)
    db_session.flush()
    twin = DigitalTwin(
        name="Architecture Run Twin",
        user_id=user.id,
        state=TwinState.DRAFT,
    )
    db_session.add(twin)
    db_session.flush()
    db_session.add(
        ArchitectureProfileService.build_default_selection(
            twin_id=twin.id,
            user_id=user.id,
            reference=PinnedArchitectureReference(
                id="five-layer-baseline",
                version="1",
                digest=ArchitectureProfileService.get_definition(
                    "five-layer-baseline",
                    "1",
                )["content_digest"],
            ),
        )
    )
    artifact = UserFunctionArtifact(
        id="artifact.user.processor.example",
        user_id=user.id,
        schema_version="user-function-artifact.v1",
        artifact_state="valid",
        artifact_digest=(
            "sha256:cd6107c2e04d7004ff8ade6c6c82f2e0272264dc556e05b46a00fd47269e8fef"
        ),
        slot_id="processor.telemetry",
        slot_version="1",
        runtime_id="python311",
        configuration_json="{}",
        declared_capabilities_json="[]",
        validator_version="user-function-validator.v1",
        created_by=user.id,
    )
    binding = TwinExtensionBinding(
        id="architecture-run-binding",
        user_id=user.id,
        twin_id=twin.id,
        slot_id="processor.telemetry",
        slot_version="1",
        artifact_id=artifact.id,
        binding_digest=extension_contract.binding_digest(
            twin_id=twin.id,
            slot_id="processor.telemetry",
            slot_version="1",
            artifact_id=artifact.id,
            artifact_digest=artifact.artifact_digest,
        ),
        active=True,
        revision=1,
    )
    db_session.add_all([artifact, binding])
    db_session.commit()
    return user, twin, artifact


def _five_layer_v2_params() -> FiveLayerV2OptimizerCalculationParams:
    payload = json.loads(
        (
            FIVE_LAYER_V2_WORKLOAD_ROOT / "fixtures" / "valid" / "core-small.json"
        ).read_text(encoding="utf-8")
    )
    return FiveLayerV2OptimizerCalculationParams.model_validate(payload)


def test_shared_v2_workload_accepts_six_layer_profile_and_keeps_eventing_path(
    db_session,
):
    params = _five_layer_v2_params()

    _validate_profile_workload_pair(
        params,
        {"profileId": "six-layer-eventing", "profileVersion": "1"},
    )
    path = CostCalculationRunService(db_session)._extract_cheapest_path(
        {
            "calculationResult": {
                "L1": "AWS",
                "L2": "GCP",
                "L3": {"Hot": "Azure", "Cool": "AWS", "Archive": "GCP"},
                "L4": "AWS",
                "L5": "Azure",
                "Eventing": "Azure",
            }
        }
    )

    assert path["eventing"] == "Azure"


def _five_layer_v2_twin_state(db_session):
    _specification, architecture, _params, _context, _ledger = (
        five_layer_v2_evidence_fixture("small")
    )
    extension = architecture["extension_bindings"][0]
    user = User(email="v2-active@example.test", name="V2 Active")
    db_session.add(user)
    db_session.flush()
    twin = DigitalTwin(
        name="V2 Active Twin",
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
    binding = TwinExtensionBinding(
        id="v2-active-binding",
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
    db_session.add_all([artifact, binding])
    db_session.commit()
    return user, twin


@pytest.mark.asyncio
async def test_active_five_layer_v2_run_persists_evaluation_evidence(
    db_session,
):
    user, twin = _five_layer_v2_twin_state(db_session)
    optimizer = FakeFiveLayerV2OptimizerClient()
    service = CostCalculationRunService(
        db_session,
        optimizer_client=optimizer,
        aws_twinmaker_contexts=FakeAwsTwinMakerContextService(
            _available_aws_context(),
            "aws-refresh-1",
        ),
        architecture_resolution_enabled=True,
    )

    run = await service.create_run(
        twin.id,
        user.id,
        _five_layer_v2_params(),
    )

    assert run.status == "succeeded"
    assert run.optimization_profile_id == "cost-minimization-v2"
    assert run.deployment_specification_version == (
        "resolved-deployment-specification.v2"
    )
    assert run.resolved_architecture_version == "resolved-twin-architecture.v2"
    assert run.architecture_compatibility_status == "ready"
    assert (
        json.loads(run.deployment_specification_json)["readiness"]["status"]
        == "offline_contract_fixture"
    )
    assert optimizer.calls[0]["architectureProfile"]["profileVersion"] == "2"

    with pytest.raises(CostCalculationRunSelectionError) as rejected:
        await service.select_for_deployment(twin.id, user.id, run.id)

    assert rejected.value.error_code == "DEPLOYMENT_CAPACITY_EVIDENCE_PENDING"
    assert run.selected_for_deployment_at is None


@pytest.mark.asyncio
async def test_five_layer_v2_aws_l4_persists_without_live_account_plan(
    db_session,
):
    user, twin = _five_layer_v2_twin_state(db_session)
    optimizer = FakeFiveLayerV2OptimizerClient()
    unavailable = {
        "status": "unavailable",
        "reasonCode": "AWS_TWINMAKER_PLAN_UNOBSERVED",
    }
    service = CostCalculationRunService(
        db_session,
        optimizer_client=optimizer,
        aws_twinmaker_contexts=FakeAwsTwinMakerContextService(
            unavailable,
            None,
        ),
        architecture_resolution_enabled=True,
    )

    run = await service.create_run(
        twin.id,
        user.id,
        _five_layer_v2_params(),
    )

    result = json.loads(run.result_summary_json)
    readiness = json.loads(run.deployment_specification_json)["readiness"]
    assert run.status == "succeeded"
    assert result["providerPricingContexts"]["awsTwinMaker"] == unavailable
    assert (
        "gate.live-pricing.aws.twinmaker-account-plan" in readiness["blocking_gate_ids"]
    )
    with pytest.raises(CostCalculationRunSelectionError) as rejected:
        await service.select_for_deployment(twin.id, user.id, run.id)
    assert rejected.value.error_code == "DEPLOYMENT_CAPACITY_EVIDENCE_PENDING"


@pytest.mark.asyncio
async def test_five_layer_v2_run_requires_architecture_resolution_gate(db_session):
    user = User(email="v2-gate@example.test", name="V2 Gate")
    db_session.add(user)
    db_session.flush()
    twin = DigitalTwin(
        name="V2 Gate Twin",
        user_id=user.id,
        state=TwinState.DRAFT,
    )
    db_session.add(twin)
    db_session.commit()
    optimizer = FakeOptimizerClient()
    service = CostCalculationRunService(
        db_session,
        optimizer_client=optimizer,
        architecture_resolution_enabled=False,
    )

    with pytest.raises(ArchitectureDomainError) as raised:
        await service.create_run(twin.id, user.id, _five_layer_v2_params())

    assert raised.value.code == "ARCH_PROFILE_NOT_ACTIVE"
    assert optimizer.calls == []


@pytest.mark.asyncio
async def test_five_layer_v2_workload_rejects_historical_profile_selection(
    db_session,
):
    user, twin, _artifact = _architecture_twin_state(db_session)
    optimizer = FakeOptimizerClient()
    service = CostCalculationRunService(
        db_session,
        optimizer_client=optimizer,
        architecture_resolution_enabled=True,
    )

    with pytest.raises(ArchitectureDomainError) as raised:
        await service.create_run(twin.id, user.id, _five_layer_v2_params())

    assert raised.value.code == "ARCH_WORKLOAD_INCOMPATIBLE"
    assert optimizer.calls == []


def test_five_layer_v2_result_requires_exact_reconciled_total(db_session):
    result = _optimizer_payload()["result"]
    result.update(
        {
            "optimization_profile_id": "cost-minimization-v2",
            "result_schema_version": "cost-result.v2",
            "totalCost": 12.5,
            "totalCostExact": "12.5",
        }
    )
    result["optimizationProfile"].update(
        {
            "profile_version": "2",
            "scoring_strategy_id": "profile-local-min-total-cost-v2",
            "calculation_model_ids": ["profile-resolution-v2@2"],
        }
    )
    service = CostCalculationRunService(db_session)

    validated = service._validate_optimizer_result(result)

    assert validated["optimization_profile_id"] == "cost-minimization-v2"
    assert validated["total_monthly_cost"] == 12.5

    result["totalCostExact"] = "12.6"
    with pytest.raises(OptimizerContractError) as raised:
        service._validate_optimizer_result(result)
    assert raised.value.errors[0]["field"] == "totalCostExact"


def _optimizer_payload_with_compatible_aws_context(context):
    payload = _optimizer_payload()
    payload["result"]["calculationResult"]["L4"] = "AWS"
    payload["result"]["cheapestPath"] = [
        "L4_AWS" if item == "L4_Azure" else item
        for item in payload["result"]["cheapestPath"]
    ]
    payload["result"]["providerPricingContexts"] = {
        "awsTwinMaker": {
            **context,
            "status": "compatible",
        }
    }
    _sync_transfer_pricing(payload["result"])
    return payload


def _optimizer_payload(overrides=None):
    result = {
        "optimization_profile_id": "cost_minimization_v1",
        "calculation_strategy_id": "cost_calculation_v2",
        "result_schema_version": "cost-result.v1",
        "optimizationProfile": {
            "profile_id": "cost_minimization_v1",
            "profile_version": "2026.06.08",
            "enabled": True,
            "metric_provider_ids": ["cost"],
            "calculation_model_ids": ["cost_model_v1"],
            "scoring_strategy_id": "min_total_cost_v1",
            "intent_group_ids": ["cost"],
            "pricing_registry_version": "2026.06.08",
        },
        "calculationStrategy": {
            "optimization_profile_id": "cost_minimization_v1",
            "calculation_strategy_id": "cost_calculation_v2",
            "formula_set_id": "cost_formula_set_v1",
            "workload_contract_id": "digital_twin_workload_v1",
            "pricing_contract_group_id": "cost_provider_pricing_contracts_v1",
            "pricing_model_classification_group_id": "cost_pricing_models_v1",
            "price_source_classification_group_id": "cost_price_sources_v1",
            "scoring_strategy_id": "min_total_cost_v1",
            "result_schema_version": "cost-result.v1",
            "publishable_mode": True,
            "formula_refs": [],
            "provider_pricing_contract_ids": [],
        },
        "evidenceReferences": {
            "pricing_registry": "pricing_registry:2026.06.08",
            "pricing_evidence_contract": "pricing-evidence.v1",
            "intent_group_ids": ["cost"],
        },
        "calculationResult": {
            "L1": "AWS",
            "L2": "Azure",
            "L3": {"Hot": "GCP", "Cool": "AWS", "Archive": "Azure"},
            "L4": "Azure",
            "L5": "Azure",
        },
        "awsCosts": {
            "L1": {"cost": 1.0},
            "L2": {"cost": 9.0},
            "L3_hot": {"cost": 9.0},
            "L3_cool": {"cost": 2.0},
            "L3_archive": {"cost": 9.0},
            "L4": {"cost": 3.0},
            "L5": {"cost": 9.0},
        },
        "azureCosts": {
            "L1": {"cost": 9.0},
            "L2": {"cost": 1.5},
            "L3_hot": {"cost": 9.0},
            "L3_cool": {"cost": 9.0},
            "L3_archive": {"cost": 2.5},
            "L4": {"cost": 9.0},
            "L5": {"cost": 4.0},
        },
        "gcpCosts": {
            "L1": {"cost": 9.0},
            "L2": {"cost": 9.0},
            "L3_hot": {"cost": 1.25},
            "L3_cool": {"cost": 9.0},
            "L3_archive": {"cost": 9.0},
            "L4": {"cost": 9.0},
            "L5": {"cost": 9.0},
        },
        "cheapestPath": [
            "L1_AWS",
            "L2_Azure",
            "L3_hot_GCP",
            "L3_cool_AWS",
            "L3_archive_Azure",
            "L4_Azure",
            "L5_Azure",
        ],
        "totalCost": 14.75,
        "currency": "USD",
        "trace_schema_version": "intent-result-trace.v1",
        "intentTrace": _intent_trace(),
        "resultTraceSchemaVersion": "intent-to-result-trace.v1",
        "resultTrace": _field_trace(),
    }
    if overrides:
        result.update(overrides)
    _sync_transfer_pricing(result)
    return {"result": result}


def _sync_transfer_pricing(result):
    result.update(
        transfer_pricing_result_fields(
            result["calculationResult"],
            total_cost=result["totalCost"],
            currency=result["currency"],
        )
    )


def _intent_trace(overrides=None):
    trace = {
        "schema_version": "intent-result-trace.v1",
        "profile": {
            "profile_id": "cost_minimization_v1",
            "profile_version": "2026.06.08",
        },
        "workload": {
            "inputs": {"numberOfDevices": 100},
            "derived": {"total_messages_per_month": 2160000},
        },
        "selected_path": [
            {"layer_cost_key": "L1", "provider": "AWS"},
            {"layer_cost_key": "L2", "provider": "Azure"},
        ],
        "records": [
            {
                "trace_id": "trace:aws.l1.iot_core.message_tiers",
                "record_id": "aws.l1.iot_core.message_tiers",
                "intent_id": "aws.l1.iot_core",
                "provider": "aws",
                "layer": "L1_INGESTION",
                "service_key": "iotCore",
                "field_id": "message_tiers",
                "source": {"primary_source_type": "dynamic_provider_api"},
                "pricing": {"canonical_unit": "usd/message"},
                "formula": {"binding_id": "cost.aws.l1.iot_core"},
                "contribution": {
                    "selected": True,
                    "path_key": "L1_AWS",
                    "cost": 1.0,
                },
                "verification": {
                    "status": "ready",
                    "review_required": False,
                    "publishable": True,
                    "evidence_reference_id": (
                        "pricing_registry:2026.06.08/aws.l1.iot_core.message_tiers"
                    ),
                },
            }
        ],
        "transfer_trace": [
            {
                "source_intent_id": "aws.transfer.egress",
                "evidence_reference_ids": ["pricing_registry:aws.transfer.egress"],
            }
        ],
        "transition_runtime_trace": [
            {
                "edge_id": "l3_hot_to_l3_cool",
                "source_provider": "gcp",
                "cost": 0.0,
            },
            {
                "edge_id": "l3_cool_to_l3_archive",
                "source_provider": "aws",
                "cost": 0.0,
            },
        ],
        "summary": {
            "record_count": 1,
            "selected_path_count": 2,
            "transfer_segment_count": 1,
            "transition_runtime_count": 2,
        },
    }
    if overrides:
        trace.update(overrides)
    return trace


def _field_trace():
    return [
        {
            "trace_id": "aws.iot.message_ingest.L1.v1",
            "provider": "aws",
            "layer": "iot",
            "service": "AWSIoT",
            "intent_id": "iot.message_ingest",
            "provider_pricing_contract_id": (
                "aws.iot_message_ingest.pricing_contract.v1"
            ),
            "pricing_model_classification_id": "aws.iot_message_ingest.model.v1",
            "price_source_classification_ids": ["aws.iot_message_ingest.source.v1"],
            "selected_evidence_id": "aws.iot.message_ingest.mapping:2026.06.08",
            "alternative_record_ids": [
                "azure.iot_message_ingest.pricing_contract.v1",
                "gcp.iot_message_ingest.pricing_contract.v1",
            ],
            "rejected_evidence_ids": [],
            "formula_ref": "tiered_unit_cost",
            "result_field": "L1",
            "cost_contribution": 1.0,
            "cost_contribution_scope": "component_total",
            "cost_contribution_is_additive": False,
            "selection_status": "selected",
            "selected_for_path": True,
            "verification_status": "passed",
            "source_type": "provider_api",
        }
    ]


def _override_optimizer(client, fake):
    client.app.dependency_overrides[get_optimizer_client] = lambda: fake


def test_create_run_persists_history_items_and_compatibility_state(
    authenticated_client,
    db_session,
    sample_calc_params,
):
    client, headers = authenticated_client
    twin_id = create_test_twin(client, headers)
    fake = FakeOptimizerClient()
    _override_optimizer(client, fake)

    response = client.post(
        f"/twins/{twin_id}/optimizer-runs/",
        json={
            "params": sample_calc_params,
            "pricing_evidence_version": "evidence.v1",
        },
        headers=headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "succeeded"
    assert data["optimization_profile_id"] == "cost_minimization_v1"
    assert data["optimization_profile_version"] == "2026.06.08"
    assert data["scoring_strategy_id"] == "min_total_cost_v1"
    assert data["calculation_model_version"] == "cost_model_v1"
    assert data["pricing_registry_version"] == "2026.06.08"
    assert data["pricing_evidence_version"] == "evidence.v1"
    assert data["pricing_run_reference"] is None
    assert data["total_monthly_cost"] == 14.75
    assert data["cheapest_path"]["l1"] == "AWS"
    assert data["deployment_compatibility_status"] == "ready"
    assert data["deployment_specification_version"] == (
        "resolved-deployment-specification.v1"
    )
    specification = data["resolved_deployment_specification"]
    assert data["deployment_specification_digest"] == specification["digest"]
    assert specification["calculation_run_id"] == data["id"]
    assert len(data["result_items"]) == 13

    run = db_session.query(CostCalculationRun).filter_by(id=data["id"]).one()
    config = db_session.query(OptimizerConfiguration).filter_by(twin_id=twin_id).one()
    assert run.optimizer_config_id == config.id
    assert config.cheapest_l1 == "AWS"
    assert config.cheapest_l2 == "Azure"
    assert config.cheapest_l3_hot == "GCP"
    assert config.cheapest_l4 == "Azure"
    assert (
        json.loads(config.params)["numberOfDevices"]
        == sample_calc_params["numberOfDevices"]
    )
    assert json.loads(config.result_json)["totalCost"] == 14.75
    assert json.loads(run.deployment_specification_json) == specification
    assert run.deployment_specification_digest == specification["digest"]
    assert run.deployment_compatibility_status == "ready"
    assert data["pricing_catalog_context"] == catalog_context().to_http_dict()
    assert json.loads(run.pricing_catalog_context_json) == (
        catalog_context().to_http_dict()
    )
    assert len(fake.calls) == 1
    optimizer_call = dict(fake.calls[0])
    assert str(UUID(optimizer_call.pop("calculationRunId"))) == data["id"]
    assert optimizer_call == {
        **sample_calc_params,
        "providerPricingCatalogs": catalog_context().to_http_dict(),
        "providerPricingContexts": {
            "awsTwinMaker": {
                "status": "unavailable",
                "reasonCode": "AWS_TWINMAKER_PLAN_UNOBSERVED",
            }
        },
    }


@pytest.mark.asyncio
async def test_architecture_gate_enriches_and_atomically_persists_resolution(
    db_session,
    sample_calc_params,
):
    user, twin, artifact = _architecture_twin_state(db_session)
    optimizer = FakeArchitectureOptimizerClient()
    service = CostCalculationRunService(
        db_session,
        optimizer_client=optimizer,
        aws_twinmaker_contexts=FakeAwsTwinMakerContextService(
            _available_aws_context(),
            "aws-refresh-1",
        ),
        architecture_resolution_enabled=True,
        linked_architecture_documents=(linked_architecture_fixture_documents()),
    )

    run = await service.create_run(
        twin.id,
        user.id,
        OptimizerCalculationParams.model_validate(sample_calc_params),
    )

    assert run.status == "succeeded"
    assert run.deployment_compatibility_status == "ready"
    assert run.architecture_compatibility_status == "ready"
    assert run.resolved_architecture is not None
    assert run.total_monthly_cost == 7.6
    assert db_session.query(ResolvedTwinArchitectureRecord).count() == 1
    optimizer_call = optimizer.calls[0]
    assert optimizer_call["architectureProfile"] == {
        "profileId": "five-layer-baseline",
        "profileVersion": "1",
        "contentDigest": (
            ArchitectureProfileService.get_definition(
                "five-layer-baseline",
                "1",
            )["content_digest"]
        ),
    }
    assert optimizer_call["extensionBindings"] == [
        {
            "slotId": "processor.telemetry",
            "slotVersion": "1",
            "artifactId": artifact.id,
            "artifactDigest": artifact.artifact_digest,
            "configurationDigest": (
                "sha256:"
                "44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310"
                "c060f61caaff8a"
            ),
        }
    ]
    config = db_session.get(
        OptimizerConfiguration,
        run.optimizer_config_id,
    )
    assignments = {
        item.logical_component_id: item.provider
        for item in run.resolved_architecture.components
    }
    assert config.cheapest_l1.lower() == assignments["component.ingestion"]
    assert config.cheapest_l2.lower() == assignments["component.processing"]
    assert config.cheapest_l5.lower() == assignments["component.visualization"]


@pytest.mark.asyncio
async def test_architecture_gate_rejects_incomplete_trusted_enrichment(
    db_session,
    sample_calc_params,
):
    user, twin, _artifact = _architecture_twin_state(db_session)
    binding = db_session.query(TwinExtensionBinding).one()
    binding.active = False
    db_session.commit()
    optimizer = FakeArchitectureOptimizerClient()
    service = CostCalculationRunService(
        db_session,
        optimizer_client=optimizer,
        architecture_resolution_enabled=True,
    )

    with pytest.raises(ArchitectureDomainError) as raised:
        await service.create_run(
            twin.id,
            user.id,
            OptimizerCalculationParams.model_validate(sample_calc_params),
        )

    assert raised.value.code == "ARCH_EXTENSION_BINDING_INVALID"
    assert optimizer.calls == []
    assert db_session.query(CostCalculationRun).count() == 0


@pytest.mark.asyncio
async def test_architecture_gate_rejects_tampered_binding_digest(
    db_session,
    sample_calc_params,
):
    user, twin, _artifact = _architecture_twin_state(db_session)
    binding = db_session.query(TwinExtensionBinding).one()
    binding.binding_digest = "sha256:" + ("0" * 64)
    db_session.commit()
    optimizer = FakeArchitectureOptimizerClient()
    service = CostCalculationRunService(
        db_session,
        optimizer_client=optimizer,
        architecture_resolution_enabled=True,
    )

    with pytest.raises(ArchitectureDomainError) as raised:
        await service.create_run(
            twin.id,
            user.id,
            OptimizerCalculationParams.model_validate(sample_calc_params),
        )

    assert raised.value.code == "ARCH_EXTENSION_BINDING_INVALID"
    assert optimizer.calls == []


@pytest.mark.asyncio
async def test_architecture_gate_invalid_response_persists_failed_run_only(
    db_session,
    sample_calc_params,
):
    user, twin, _artifact = _architecture_twin_state(db_session)

    def tamper_digest(architecture):
        architecture["content_digest"] = "sha256:" + ("0" * 64)

    optimizer = FakeArchitectureOptimizerClient(
        architecture_mutator=tamper_digest,
    )
    service = CostCalculationRunService(
        db_session,
        optimizer_client=optimizer,
        aws_twinmaker_contexts=FakeAwsTwinMakerContextService(
            _available_aws_context(),
            "aws-refresh-1",
        ),
        architecture_resolution_enabled=True,
        linked_architecture_documents=(linked_architecture_fixture_documents()),
    )

    with pytest.raises(OptimizerContractError):
        await service.create_run(
            twin.id,
            user.id,
            OptimizerCalculationParams.model_validate(sample_calc_params),
        )

    failed = db_session.query(CostCalculationRun).one()
    assert failed.status == "failed"
    assert failed.error_code == "ARCH_RESOLUTION_DIGEST_MISMATCH"
    assert failed.result_summary_json is None
    assert failed.deployment_specification_json is None
    assert failed.resolved_architecture is None
    assert db_session.query(ResolvedTwinArchitectureRecord).count() == 0
    assert db_session.query(CostCalculationResultItem).count() == 0


@pytest.mark.asyncio
async def test_architecture_gate_persists_bounded_upstream_rejection(
    db_session,
    sample_calc_params,
):
    user, twin, _artifact = _architecture_twin_state(db_session)
    optimizer = FakeOptimizerClient(
        exc=ExternalServiceError(
            "private upstream architecture detail",
            upstream_status_code=409,
            public_detail=("Optimizer rejected architecture profile resolution."),
            error_code="ARCH_PROVIDER_IMPLEMENTATION_MISSING",
        )
    )
    service = CostCalculationRunService(
        db_session,
        optimizer_client=optimizer,
        aws_twinmaker_contexts=FakeAwsTwinMakerContextService(
            _available_aws_context(),
            "aws-refresh-1",
        ),
        architecture_resolution_enabled=True,
    )

    with pytest.raises(ExternalServiceError):
        await service.create_run(
            twin.id,
            user.id,
            OptimizerCalculationParams.model_validate(sample_calc_params),
        )

    failed = db_session.query(CostCalculationRun).one()
    assert failed.status == "failed"
    assert failed.error_code == "ARCH_PROVIDER_IMPLEMENTATION_MISSING"
    assert "private upstream" not in failed.error_message


@pytest.mark.asyncio
async def test_architecture_gate_maps_unexpected_upstream_failure(
    db_session,
    sample_calc_params,
):
    user, twin, _artifact = _architecture_twin_state(db_session)
    service = CostCalculationRunService(
        db_session,
        optimizer_client=FakeOptimizerClient(
            exc=RuntimeError("private unexpected failure")
        ),
        aws_twinmaker_contexts=FakeAwsTwinMakerContextService(
            _available_aws_context(),
            "aws-refresh-1",
        ),
        architecture_resolution_enabled=True,
    )

    with pytest.raises(ExternalServiceError) as raised:
        await service.create_run(
            twin.id,
            user.id,
            OptimizerCalculationParams.model_validate(sample_calc_params),
        )

    assert raised.value.public_detail == "Optimizer service returned an error."
    assert "private unexpected" not in raised.value.public_detail
    failed = db_session.query(CostCalculationRun).one()
    assert failed.status == "failed"
    assert failed.error_code == "OPTIMIZER_ERROR"
    assert "private unexpected" not in failed.error_message


def test_create_run_rejects_unsupported_error_handling_without_side_effects(
    authenticated_client,
    db_session,
    sample_calc_params,
):
    client, headers = authenticated_client
    twin_id = create_test_twin(client, headers)
    fake = FakeOptimizerClient()
    _override_optimizer(client, fake)
    invalid_params = dict(sample_calc_params)
    invalid_params["integrateErrorHandling"] = True

    response = client.post(
        f"/twins/{twin_id}/optimizer-runs/",
        json={"params": invalid_params},
        headers=headers,
    )

    assert response.status_code == 422
    assert fake.calls == []
    assert db_session.query(CostCalculationRun).count() == 0
    assert db_session.query(OptimizerConfiguration).count() == 0


def test_create_run_rejects_client_owned_pricing_run_reference(
    authenticated_client,
    sample_calc_params,
):
    client, headers = authenticated_client
    twin_id = create_test_twin(client, headers)

    response = client.post(
        f"/twins/{twin_id}/optimizer-runs/",
        json={
            "params": sample_calc_params,
            "pricing_run_reference": "client-controlled-run",
        },
        headers=headers,
    )

    assert response.status_code == 422
    assert "pricing_run_reference" in response.text


def test_create_run_rejects_aws_l4_selected_without_trusted_context(
    authenticated_client,
    db_session,
    sample_calc_params,
):
    client, headers = authenticated_client
    twin_id = create_test_twin(client, headers)
    payload = _optimizer_payload()
    payload["result"]["calculationResult"]["L4"] = "AWS"
    payload["result"]["cheapestPath"] = [
        "L4_AWS" if item == "L4_Azure" else item
        for item in payload["result"]["cheapestPath"]
    ]
    _sync_transfer_pricing(payload["result"])
    _override_optimizer(client, FakeOptimizerClient(payload=payload))

    response = client.post(
        f"/twins/{twin_id}/optimizer-runs/",
        json={"params": sample_calc_params},
        headers=headers,
    )

    assert response.status_code == 502
    assert response.json()["detail"]["error_code"] == "OPTIMIZER_CONTRACT_INVALID"
    assert db_session.query(CostCalculationRun).count() == 0


def test_list_and_detail_are_scoped_to_current_user(
    authenticated_client,
    db_session,
    sample_calc_params,
):
    client, headers = authenticated_client
    own_twin_id = create_test_twin(client, headers, name="Own Twin")
    fake = FakeOptimizerClient()
    _override_optimizer(client, fake)

    create_response = client.post(
        f"/twins/{own_twin_id}/optimizer-runs/",
        json={"params": sample_calc_params},
        headers=headers,
    )
    assert create_response.status_code == 200
    created_run = create_response.json()
    run_id = created_run["id"]
    assert created_run["created_at"].endswith(("Z", "+00:00"))
    assert created_run["completed_at"].endswith(("Z", "+00:00"))
    assert all(
        item["created_at"].endswith(("Z", "+00:00"))
        for item in created_run["result_items"]
    )

    other_user = User(email="other@example.com", name="Other")
    db_session.add(other_user)
    db_session.commit()
    db_session.refresh(other_user)
    other_twin = DigitalTwin(
        name="Other Twin",
        user_id=other_user.id,
        state=TwinState.DRAFT,
    )
    db_session.add(other_twin)
    db_session.commit()
    db_session.refresh(other_twin)

    list_response = client.get(f"/twins/{own_twin_id}/optimizer-runs/", headers=headers)
    assert list_response.status_code == 200
    assert [run["id"] for run in list_response.json()] == [run_id]

    detail_response = client.get(
        f"/twins/{own_twin_id}/optimizer-runs/{run_id}",
        headers=headers,
    )
    assert detail_response.status_code == 200
    assert detail_response.json()["id"] == run_id
    assert detail_response.json()["created_at"].endswith(("Z", "+00:00"))

    foreign_response = client.get(
        f"/twins/{other_twin.id}/optimizer-runs/",
        headers=headers,
    )
    assert foreign_response.status_code == 404


def test_detail_returns_explicit_evidence_references(
    authenticated_client,
    sample_calc_params,
):
    client, headers = authenticated_client
    twin_id = create_test_twin(client, headers)
    payload = _optimizer_payload(
        {
            "resultItems": [
                {
                    "layer": "L1",
                    "component": "ingestion",
                    "provider": "AWS",
                    "service_intent_id": "iot.message_ingest",
                    "cost_amount": 1.23,
                    "currency": "USD",
                    "unit": "message",
                    "quantity": 1000,
                    "unit_price": 0.00123,
                    "evidence_id": "aws-iot-evidence-1",
                    "service_model_id": "iot_ingestion_v1",
                    "calculation_notes": {"selected_row": "sku-1"},
                    "review_status": "reviewed",
                },
                {
                    "layer": "L1_to_L2",
                    "component": "TRANSFER",
                    "provider": "gcp",
                    "cost_amount": 999999,
                    "currency": "USD",
                    "evidence_id": "client-authored-transfer",
                    "review_status": "reviewed",
                },
            ]
        }
    )
    _override_optimizer(client, FakeOptimizerClient(payload=payload))

    response = client.post(
        f"/twins/{twin_id}/optimizer-runs/",
        json={"params": sample_calc_params},
        headers=headers,
    )

    assert response.status_code == 200
    item = response.json()["result_items"][0]
    assert item["evidence_id"] == "aws-iot-evidence-1"
    assert item["service_intent_id"] == "iot.message_ingest"
    assert item["calculation_notes"] == {"selected_row": "sku-1"}
    transfer_items = [
        result_item
        for result_item in response.json()["result_items"]
        if result_item["component"] == "transfer"
    ]
    assert len(transfer_items) == 6
    assert all(
        result_item["evidence_id"] != "client-authored-transfer"
        for result_item in transfer_items
    )


def test_create_run_persists_optimizer_evidence_reference_metadata(
    authenticated_client,
    db_session,
    sample_calc_params,
):
    client, headers = authenticated_client
    twin_id = create_test_twin(client, headers)
    payload = _optimizer_payload()
    payload["result"]["calculationResult"]["L4"] = "Azure"
    payload["result"]["cheapestPath"] = [
        "L4_Azure" if item == "L4_AWS" else item
        for item in payload["result"]["cheapestPath"]
    ]
    _override_optimizer(client, FakeOptimizerClient(payload=payload))

    response = client.post(
        f"/twins/{twin_id}/optimizer-runs/",
        json={"params": sample_calc_params},
        headers=headers,
    )

    assert response.status_code == 200
    run = db_session.query(CostCalculationRun).filter_by(id=response.json()["id"]).one()
    result_summary = json.loads(run.result_summary_json)
    assert result_summary["evidenceReferences"]["pricing_registry"] == (
        "pricing_registry:2026.06.08"
    )
    assert result_summary["evidenceReferences"]["pricing_evidence_contract"] == (
        "pricing-evidence.v1"
    )
    assert result_summary["intentTrace"]["schema_version"] == "intent-result-trace.v1"


def test_create_run_persists_exact_transfer_result_items(
    authenticated_client,
    sample_calc_params,
):
    client, headers = authenticated_client
    twin_id = create_test_twin(client, headers)
    _override_optimizer(client, FakeOptimizerClient())

    response = client.post(
        f"/twins/{twin_id}/optimizer-runs/",
        json={"params": sample_calc_params},
        headers=headers,
    )

    assert response.status_code == 200
    transfer_items = [
        item
        for item in response.json()["result_items"]
        if item["component"] == "transfer"
    ]
    assert len(transfer_items) == 6
    assert {item["review_status"] for item in transfer_items} == {"ready"}
    assert {item["unit"] for item in transfer_items} == {"bytes/month"}
    charged = next(item for item in transfer_items if item["layer"] == "L1_to_L2")
    assert charged["provider"] == "aws"
    assert charged["service_intent_id"] == "aws.transfer.egress"
    assert charged["evidence_id"] == "transfer.aws.test.v1"
    assert charged["quantity"] == 1_000_000_000
    assert charged["calculation_notes"]["source"] == (
        "optimizer_transfer_pricing_context"
    )
    assert charged["calculation_notes"]["route"]["catalogSnapshotId"] == (
        catalog_reference("aws").snapshot_id
    )


def test_create_run_rejects_tampered_transfer_evidence_without_persistence(
    authenticated_client,
    db_session,
    sample_calc_params,
):
    client, headers = authenticated_client
    twin_id = create_test_twin(client, headers)
    payload = _optimizer_payload()
    payload["result"]["transferPricingContext"]["routes"][0]["source"]["region"] = (
        "eu-west-1"
    )
    _override_optimizer(client, FakeOptimizerClient(payload=payload))

    response = client.post(
        f"/twins/{twin_id}/optimizer-runs/",
        json={"params": sample_calc_params},
        headers=headers,
    )

    assert response.status_code == 502
    assert response.json()["detail"]["error_code"] == ("OPTIMIZER_CONTRACT_INVALID")
    assert any(
        error["field"].endswith("source.region")
        for error in response.json()["detail"]["field_errors"]
    )
    assert db_session.query(CostCalculationRun).count() == 0


def test_pricing_evidence_detail_returns_trace_and_result_items(
    authenticated_client,
    sample_calc_params,
):
    client, headers = authenticated_client
    twin_id = create_test_twin(client, headers)
    payload = _optimizer_payload(
        {
            "resultItems": [
                {
                    "layer": "L1",
                    "component": "ingestion",
                    "provider": "AWS",
                    "service_intent_id": "aws.l1.iot_core",
                    "cost_amount": 1.0,
                    "currency": "USD",
                    "unit": "message",
                    "quantity": 2160000,
                    "unit_price": 0.000001,
                    "evidence_id": "pricing_registry:aws.l1.iot_core.message_tiers",
                    "service_model_id": "iot_core_message_tiers",
                    "calculation_notes": {
                        "trace_id": "trace:aws.l1.iot_core.message_tiers"
                    },
                    "review_status": "ready",
                }
            ]
        }
    )
    _override_optimizer(client, FakeOptimizerClient(payload=payload))
    create_response = client.post(
        f"/twins/{twin_id}/optimizer-runs/",
        json={"params": sample_calc_params},
        headers=headers,
    )
    run_id = create_response.json()["id"]

    response = client.get(
        f"/twins/{twin_id}/optimizer-runs/{run_id}/pricing-evidence",
        headers=headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["run_id"] == run_id
    assert data["twin_id"] == twin_id
    assert data["trace_available"] is True
    assert data["trace_schema_version"] == "intent-result-trace.v1"
    assert data["profile"]["profile_id"] == "cost_minimization_v1"
    assert data["workload"]["derived"]["total_messages_per_month"] == 2160000
    assert data["selected_path"][0]["provider"] == "AWS"
    assert data["records"][0]["trace_id"] == "trace:aws.l1.iot_core.message_tiers"
    assert data["transfer_trace"][0]["source_intent_id"] == "aws.transfer.egress"
    assert len(data["transition_runtime_trace"]) == 2
    assert data["field_trace_available"] is True
    assert data["field_trace_schema_version"] == "intent-to-result-trace.v1"
    assert data["field_trace_records"][0]["selection_status"] == "selected"
    assert data["field_trace_records"][0]["cost_contribution_is_additive"] is False
    assert data["transfer_pricing_context_available"] is True
    assert data["transfer_pricing_context"]["schemaVersion"] == (
        "complete-path-transfer-pricing.v1"
    )
    assert len(data["transfer_pricing_context"]["routes"]) == 6
    assert data["transition_runtime_context_available"] is True
    assert data["transition_runtime_context"]["schemaVersion"] == (
        "baseline-transition-runtime.v1"
    )
    assert len(data["transition_runtime_context"]["transitions"]) == 2
    assert set(data["transition_runtime_costs"]) == {
        "l3_hot_to_l3_cool",
        "l3_cool_to_l3_archive",
    }
    assert data["optimization_diagnostics"]["winningCandidateId"] == (
        "aws|azure|gcp|aws|azure|azure|azure"
    )
    assert data["result_metadata"]["evidenceReferences"]["pricing_registry"] == (
        "pricing_registry:2026.06.08"
    )
    assert data["result_items"][0]["evidence_id"] == (
        "pricing_registry:aws.l1.iot_core.message_tiers"
    )


def test_pricing_evidence_detail_handles_missing_trace_gracefully(
    authenticated_client,
    sample_calc_params,
):
    client, headers = authenticated_client
    twin_id = create_test_twin(client, headers)
    payload = _optimizer_payload({"intentTrace": None, "trace_schema_version": None})
    _override_optimizer(client, FakeOptimizerClient(payload=payload))
    create_response = client.post(
        f"/twins/{twin_id}/optimizer-runs/",
        json={"params": sample_calc_params},
        headers=headers,
    )
    run_id = create_response.json()["id"]

    response = client.get(
        f"/twins/{twin_id}/optimizer-runs/{run_id}/pricing-evidence",
        headers=headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["trace_available"] is False
    assert data["records"] == []
    assert data["transfer_trace"] == []
    assert data["warnings"] == ["Optimizer intent trace is not available for this run."]


def test_pricing_evidence_detail_handles_historical_run_without_field_trace(
    authenticated_client,
    sample_calc_params,
):
    client, headers = authenticated_client
    twin_id = create_test_twin(client, headers)
    payload = _optimizer_payload(
        {"resultTrace": None, "resultTraceSchemaVersion": None}
    )
    _override_optimizer(client, FakeOptimizerClient(payload=payload))
    create_response = client.post(
        f"/twins/{twin_id}/optimizer-runs/",
        json={"params": sample_calc_params},
        headers=headers,
    )
    run_id = create_response.json()["id"]

    response = client.get(
        f"/twins/{twin_id}/optimizer-runs/{run_id}/pricing-evidence",
        headers=headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["trace_available"] is True
    assert data["field_trace_available"] is False
    assert data["field_trace_records"] == []
    assert data["warnings"] == ["Optimizer field trace is not available for this run."]


def test_pricing_evidence_detail_preserves_historical_run_without_transfer_contract(
    db_session,
):
    run = CostCalculationRun(
        id="historical-run",
        twin_id="historical-twin",
        user_id="historical-user",
        status="succeeded",
        params_json="{}",
        result_summary_json=json.dumps(
            {
                "result_schema_version": "cost-result.v1",
                "currency": "USD",
                "totalCost": 1.0,
            }
        ),
        optimization_profile_id="cost_minimization_v1",
        scoring_strategy_id="min_total_cost_v1",
        currency="USD",
    )

    detail = CostCalculationRunService(db_session).build_pricing_evidence_detail(run)

    assert detail["transfer_pricing_context_available"] is False
    assert detail["transfer_pricing_context"] == {}
    assert detail["optimization_diagnostics"] == {}
    assert not any("transfer pricing" in warning for warning in detail["warnings"])


def test_pricing_evidence_detail_warns_for_present_non_object_transfer_contract(
    db_session,
):
    run = CostCalculationRun(
        id="malformed-transfer-run",
        twin_id="malformed-transfer-twin",
        user_id="malformed-transfer-user",
        status="succeeded",
        params_json="{}",
        result_summary_json=json.dumps(
            {
                "result_schema_version": "cost-result.v1",
                "currency": "USD",
                "totalCost": 1.0,
                "transferPricingContext": [],
            }
        ),
        optimization_profile_id="cost_minimization_v1",
        scoring_strategy_id="min_total_cost_v1",
        currency="USD",
    )

    detail = CostCalculationRunService(db_session).build_pricing_evidence_detail(run)

    assert detail["transfer_pricing_context_available"] is False
    assert detail["transfer_pricing_context"] == {}
    assert detail["optimization_diagnostics"] == {}
    assert (
        "Malformed optimizer transfer pricing evidence was omitted."
        in (detail["warnings"])
    )


def test_pricing_evidence_detail_omits_tampered_persisted_transfer_contract(
    authenticated_client,
    db_session,
    sample_calc_params,
):
    client, headers = authenticated_client
    twin_id = create_test_twin(client, headers)
    _override_optimizer(client, FakeOptimizerClient())
    create_response = client.post(
        f"/twins/{twin_id}/optimizer-runs/",
        json={"params": sample_calc_params},
        headers=headers,
    )
    run = (
        db_session.query(CostCalculationRun)
        .filter_by(id=create_response.json()["id"])
        .one()
    )
    result = json.loads(run.result_summary_json)
    result["transferPricingContext"]["pools"][0]["catalogSnapshotId"] = (
        catalog_reference("aws", identity_hex="d").snapshot_id
    )
    run.result_summary_json = json.dumps(result)
    db_session.commit()

    response = client.get(
        f"/twins/{twin_id}/optimizer-runs/{run.id}/pricing-evidence",
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json()["transfer_pricing_context_available"] is False
    assert response.json()["transfer_pricing_context"] == {}
    assert response.json()["optimization_diagnostics"] == {}
    assert (
        "Malformed optimizer transfer pricing evidence was omitted."
        in (response.json()["warnings"])
    )


def test_pricing_evidence_detail_omits_malformed_field_trace_records(
    authenticated_client,
    sample_calc_params,
):
    client, headers = authenticated_client
    twin_id = create_test_twin(client, headers)
    payload = _optimizer_payload({"resultTrace": ["invalid", *_field_trace()]})
    _override_optimizer(client, FakeOptimizerClient(payload=payload))
    create_response = client.post(
        f"/twins/{twin_id}/optimizer-runs/",
        json={"params": sample_calc_params},
        headers=headers,
    )
    run_id = create_response.json()["id"]

    response = client.get(
        f"/twins/{twin_id}/optimizer-runs/{run_id}/pricing-evidence",
        headers=headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["field_trace_available"] is True
    assert len(data["field_trace_records"]) == 1
    assert data["warnings"] == ["Malformed optimizer field trace records were omitted."]


def test_pricing_evidence_detail_redacts_secret_like_values(
    authenticated_client,
    sample_calc_params,
):
    client, headers = authenticated_client
    twin_id = create_test_twin(client, headers)
    trace = _intent_trace(
        {
            "records": [
                {
                    "trace_id": "trace:secret",
                    "provider": "aws",
                    "private_key": "SHOULD_NOT_LEAK",
                    "message": "authorization: Bearer abcdefghijklmnopqrstuvwxyz",
                }
            ]
        }
    )
    payload = _optimizer_payload(
        {
            "intentTrace": trace,
            "resultTrace": [
                {
                    "trace_id": "field:secret",
                    "client_secret": "SHOULD_NOT_LEAK",
                    "source_url": "/Users/caroline/private_key.json",
                }
            ],
            "evidenceReferences": {
                "pricing_registry": "pricing_registry:2026.06.08",
                "api_key": "SHOULD_NOT_LEAK",
            },
        }
    )
    _override_optimizer(client, FakeOptimizerClient(payload=payload))
    create_response = client.post(
        f"/twins/{twin_id}/optimizer-runs/",
        json={"params": sample_calc_params},
        headers=headers,
    )
    run_id = create_response.json()["id"]

    response = client.get(
        f"/twins/{twin_id}/optimizer-runs/{run_id}/pricing-evidence",
        headers=headers,
    )

    assert response.status_code == 200
    serialized = json.dumps(response.json())
    assert "SHOULD_NOT_LEAK" not in serialized
    assert "Bearer abcdefghijklmnopqrstuvwxyz" not in serialized
    assert response.json()["records"][0]["private_key"] == "[REDACTED]"
    assert response.json()["field_trace_records"][0]["client_secret"] == ("[REDACTED]")
    assert "/Users/" not in serialized


def test_pricing_evidence_detail_is_scoped_to_current_user(
    authenticated_client,
    db_session,
    sample_calc_params,
):
    client, headers = authenticated_client
    own_twin_id = create_test_twin(client, headers, name="Evidence Twin")
    _override_optimizer(client, FakeOptimizerClient())
    create_response = client.post(
        f"/twins/{own_twin_id}/optimizer-runs/",
        json={"params": sample_calc_params},
        headers=headers,
    )
    run_id = create_response.json()["id"]

    other_user = User(email="evidence-other@example.com", name="Other")
    db_session.add(other_user)
    db_session.commit()
    db_session.refresh(other_user)
    other_twin = DigitalTwin(
        name="Other Evidence Twin",
        user_id=other_user.id,
        state=TwinState.DRAFT,
    )
    db_session.add(other_twin)
    db_session.commit()
    db_session.refresh(other_twin)

    response = client.get(
        f"/twins/{other_twin.id}/optimizer-runs/{run_id}/pricing-evidence",
        headers=headers,
    )

    assert response.status_code == 404


def test_missing_evidence_references_are_rejected(
    authenticated_client,
    db_session,
    sample_calc_params,
):
    client, headers = authenticated_client
    twin_id = create_test_twin(client, headers)
    payload = _optimizer_payload()
    payload["result"].pop("evidenceReferences")
    _override_optimizer(client, FakeOptimizerClient(payload=payload))

    response = client.post(
        f"/twins/{twin_id}/optimizer-runs/",
        json={"params": sample_calc_params},
        headers=headers,
    )

    assert response.status_code == 502
    assert "evidenceReferences" in str(response.json()["detail"]["field_errors"])
    assert db_session.query(CostCalculationRun).count() == 0


def test_invalid_optimizer_contract_returns_structured_502_without_successful_run(
    authenticated_client,
    db_session,
    sample_calc_params,
):
    client, headers = authenticated_client
    twin_id = create_test_twin(client, headers)
    _override_optimizer(
        client, FakeOptimizerClient(payload={"result": {"totalCost": 1.0}})
    )

    response = client.post(
        f"/twins/{twin_id}/optimizer-runs/",
        json={"params": sample_calc_params},
        headers=headers,
    )

    assert response.status_code == 502
    assert response.json()["detail"]["error_code"] == "OPTIMIZER_CONTRACT_INVALID"
    assert db_session.query(CostCalculationRun).count() == 0


def test_optimizer_calculation_identity_mismatch_is_rejected_without_persistence(
    authenticated_client,
    db_session,
    sample_calc_params,
):
    client, headers = authenticated_client
    twin_id = create_test_twin(client, headers)
    payload = _optimizer_payload(
        {
            "resolvedDeploymentSpecification": {
                "calculation_run_id": "018f0f5e-7b5e-7b2d-9f0b-7f66c2a88aff",
            }
        }
    )
    _override_optimizer(client, FakeOptimizerClient(payload=payload))

    response = client.post(
        f"/twins/{twin_id}/optimizer-runs/",
        json={"params": sample_calc_params},
        headers=headers,
    )

    assert response.status_code == 502
    assert response.json()["detail"]["error_code"] == "OPTIMIZER_CONTRACT_INVALID"
    assert "calculation_run_id" in str(response.json()["detail"]["field_errors"])
    assert db_session.query(CostCalculationRun).count() == 0


@pytest.mark.parametrize(
    "specification_override",
    [
        {"digest": "sha256:" + ("0" * 64)},
        {"client_secret": "must-not-leak"},
    ],
)
def test_invalid_deployment_specification_is_rejected_without_persistence(
    authenticated_client,
    db_session,
    sample_calc_params,
    specification_override,
):
    client, headers = authenticated_client
    twin_id = create_test_twin(client, headers)
    payload = _optimizer_payload(
        {"resolvedDeploymentSpecification": specification_override}
    )
    _override_optimizer(client, FakeOptimizerClient(payload=payload))

    response = client.post(
        f"/twins/{twin_id}/optimizer-runs/",
        json={"params": sample_calc_params},
        headers=headers,
    )

    assert response.status_code == 502
    response_text = str(response.json())
    assert "must-not-leak" not in response_text
    assert db_session.query(CostCalculationRun).count() == 0


def test_unknown_deployment_component_is_rejected_without_persistence(
    authenticated_client,
    db_session,
    sample_calc_params,
):
    client, headers = authenticated_client
    twin_id = create_test_twin(client, headers)

    def mutate(specification):
        specification["components"][0]["component_id"] = "l1.aws.unknown"
        specification["digest"] = calculate_digest(specification)

    _override_optimizer(
        client,
        FakeOptimizerClient(specification_mutator=mutate),
    )

    response = client.post(
        f"/twins/{twin_id}/optimizer-runs/",
        json={"params": sample_calc_params},
        headers=headers,
    )

    assert response.status_code == 502
    assert db_session.query(CostCalculationRun).count() == 0


def test_disabled_optimizer_profile_is_rejected(
    authenticated_client,
    db_session,
    sample_calc_params,
):
    client, headers = authenticated_client
    twin_id = create_test_twin(client, headers)
    payload = _optimizer_payload({"optimization_profile_id": "latency_minimization_v1"})
    _override_optimizer(client, FakeOptimizerClient(payload=payload))

    response = client.post(
        f"/twins/{twin_id}/optimizer-runs/",
        json={"params": sample_calc_params},
        headers=headers,
    )

    assert response.status_code == 502
    assert "disabled profile" in str(response.json()["detail"]["field_errors"])
    assert db_session.query(CostCalculationRun).count() == 0


def test_optimizer_unavailable_returns_503_without_successful_run(
    authenticated_client,
    db_session,
    sample_calc_params,
):
    client, headers = authenticated_client
    twin_id = create_test_twin(client, headers)
    _override_optimizer(
        client,
        FakeOptimizerClient(
            exc=ExternalServiceUnavailable("Optimizer API unavailable")
        ),
    )

    response = client.post(
        f"/twins/{twin_id}/optimizer-runs/",
        json={"params": sample_calc_params},
        headers=headers,
    )

    assert response.status_code == 503
    assert response.json()["detail"]["error_code"] == "OPTIMIZER_UNAVAILABLE"
    assert db_session.query(CostCalculationRun).count() == 0


def test_optimizer_error_response_does_not_echo_raw_downstream_body(
    authenticated_client,
    db_session,
    sample_calc_params,
):
    client, headers = authenticated_client
    twin_id = create_test_twin(client, headers)
    _override_optimizer(
        client,
        FakeOptimizerClient(
            exc=ExternalServiceError(
                "Optimizer API returned 500: private_key=SHOULD_NOT_LEAK"
            )
        ),
    )

    response = client.post(
        f"/twins/{twin_id}/optimizer-runs/",
        json={"params": sample_calc_params},
        headers=headers,
    )

    assert response.status_code == 502
    payload = response.json()
    assert payload["detail"]["error_code"] == "OPTIMIZER_ERROR"
    assert "SHOULD_NOT_LEAK" not in str(payload)
    assert db_session.query(CostCalculationRun).count() == 0


def test_optimizer_architecture_rejection_maps_known_code_only(
    authenticated_client,
    db_session,
    sample_calc_params,
):
    client, headers = authenticated_client
    twin_id = create_test_twin(client, headers)
    _override_optimizer(
        client,
        FakeOptimizerClient(
            exc=ExternalServiceError(
                "private upstream architecture detail",
                upstream_status_code=409,
                public_detail=("Optimizer rejected architecture profile resolution."),
                error_code="ARCH_NO_ADMISSIBLE_CANDIDATE",
            )
        ),
    )

    response = client.post(
        f"/twins/{twin_id}/optimizer-runs/",
        json={"params": sample_calc_params},
        headers=headers,
    )

    assert response.status_code == 409
    assert response.json()["detail"]["error_code"] == ("ARCH_NO_ADMISSIBLE_CANDIDATE")
    assert "private upstream" not in str(response.json())
    assert db_session.query(CostCalculationRun).count() == 0


def test_select_for_deployment_marks_run_and_preserves_compatibility(
    authenticated_client,
    db_session,
    sample_calc_params,
):
    client, headers = authenticated_client
    twin_id = create_test_twin(client, headers)
    payload = _optimizer_payload()
    payload["result"]["calculationResult"]["L4"] = "Azure"
    payload["result"]["cheapestPath"] = [
        "L4_Azure" if item == "L4_AWS" else item
        for item in payload["result"]["cheapestPath"]
    ]
    _sync_transfer_pricing(payload["result"])
    _override_optimizer(client, FakeOptimizerClient(payload=payload))
    create_response = client.post(
        f"/twins/{twin_id}/optimizer-runs/",
        json={"params": sample_calc_params},
        headers=headers,
    )
    run_id = create_response.json()["id"]

    response = client.post(
        f"/twins/{twin_id}/optimizer-runs/{run_id}/select-for-deployment",
        headers=headers,
    )

    assert response.status_code == 200
    selection = response.json()
    assert selection["run"]["selected_for_deployment_at"] is not None
    assert selection["selected_for_deployment_at"].endswith(("Z", "+00:00"))
    assert (
        selection["resolved_deployment_specification"]["digest"]
        == selection["run"]["deployment_specification_digest"]
    )
    config = db_session.query(OptimizerConfiguration).filter_by(twin_id=twin_id).one()
    assert config.cheapest_l1 == "AWS"
    assert config.cheapest_l3_archive == "Azure"


@pytest.mark.asyncio
async def test_select_for_deployment_maps_concurrent_selection_conflict(
    db_session,
    sample_calc_params,
    monkeypatch,
):
    user = User(email="selection-conflict@example.test", name="Selection Conflict")
    db_session.add(user)
    db_session.flush()
    twin = DigitalTwin(
        name="Selection Conflict Twin",
        user_id=user.id,
        state=TwinState.DRAFT,
    )
    db_session.add(twin)
    db_session.commit()
    payload = _optimizer_payload()
    payload["result"]["calculationResult"]["L4"] = "Azure"
    payload["result"]["cheapestPath"] = [
        "L4_Azure" if item == "L4_AWS" else item
        for item in payload["result"]["cheapestPath"]
    ]
    _sync_transfer_pricing(payload["result"])
    service = CostCalculationRunService(
        db_session,
        optimizer_client=FakeOptimizerClient(payload=payload),
        aws_twinmaker_contexts=FakeAwsTwinMakerContextService(
            _available_aws_context(),
            "aws-refresh-1",
        ),
    )
    run = await service.create_run(
        twin.id,
        user.id,
        OptimizerCalculationParams.model_validate(sample_calc_params),
    )

    def raise_selection_conflict():
        raise IntegrityError(
            "unique selection",
            {},
            RuntimeError("concurrent selection"),
        )

    monkeypatch.setattr(db_session, "commit", raise_selection_conflict)

    with pytest.raises(CostCalculationRunSelectionError) as exc_info:
        await service.select_for_deployment(twin.id, user.id, run.id)

    assert exc_info.value.error_code == ("COST_CALCULATION_RUN_SELECTION_CONFLICT")


@pytest.mark.asyncio
async def test_aws_l4_run_persists_server_context_and_revalidates_on_selection(
    db_session,
    sample_calc_params,
):
    user = User(email="aws-run-context@example.test", name="AWS Context")
    db_session.add(user)
    db_session.flush()
    twin = DigitalTwin(
        name="AWS Context Twin",
        user_id=user.id,
        state=TwinState.DRAFT,
    )
    db_session.add(twin)
    db_session.commit()
    context = _available_aws_context()
    context_service = FakeAwsTwinMakerContextService(context, "aws-refresh-1")
    optimizer = FakeOptimizerClient(
        payload=_optimizer_payload_with_compatible_aws_context(context)
    )
    service = CostCalculationRunService(
        db_session,
        optimizer_client=optimizer,
        aws_twinmaker_contexts=context_service,
    )

    run = await service.create_run(
        twin.id,
        user.id,
        OptimizerCalculationParams(**sample_calc_params),
    )
    selected = await service.select_for_deployment(twin.id, user.id, run.id)

    assert run.pricing_run_reference == "aws-refresh-1"
    assert optimizer.calls[0]["providerPricingContexts"]["awsTwinMaker"] == context
    assert selected.selected_for_deployment_at is not None
    assert context_service.calls == [
        (user.id, catalog_reference("aws")),
        (user.id, catalog_reference("aws")),
    ]


@pytest.mark.asyncio
async def test_aws_l4_selection_rejects_context_changed_after_calculation(
    db_session,
    sample_calc_params,
):
    user = User(email="aws-run-changed@example.test", name="AWS Changed")
    db_session.add(user)
    db_session.flush()
    twin = DigitalTwin(
        name="AWS Changed Twin",
        user_id=user.id,
        state=TwinState.DRAFT,
    )
    db_session.add(twin)
    db_session.commit()
    original = _available_aws_context()
    context_service = FakeAwsTwinMakerContextService(original, "aws-refresh-1")
    service = CostCalculationRunService(
        db_session,
        optimizer_client=FakeOptimizerClient(
            payload=_optimizer_payload_with_compatible_aws_context(original)
        ),
        aws_twinmaker_contexts=context_service,
    )
    run = await service.create_run(
        twin.id,
        user.id,
        OptimizerCalculationParams(**sample_calc_params),
    )
    changed = _available_aws_context("aws-refresh-2")
    context_service.payload = changed
    context_service.source_refresh_run_id = "aws-refresh-2"

    with pytest.raises(CostCalculationRunSelectionError) as exc_info:
        await service.select_for_deployment(twin.id, user.id, run.id)

    assert exc_info.value.error_code == "AWS_TWINMAKER_PLAN_CONNECTION_CHANGED"
    db_session.refresh(run)
    assert run.selected_for_deployment_at is None


@pytest.mark.asyncio
async def test_selection_rejects_result_with_tampered_catalog_context(
    db_session,
    sample_calc_params,
):
    user = User(email="catalog-tamper@example.test", name="Catalog Tamper")
    db_session.add(user)
    db_session.flush()
    twin = DigitalTwin(
        name="Catalog Tamper Twin",
        user_id=user.id,
        state=TwinState.DRAFT,
    )
    db_session.add(twin)
    db_session.commit()
    optimizer = FakeOptimizerClient()
    service = CostCalculationRunService(
        db_session,
        optimizer_client=optimizer,
        aws_twinmaker_contexts=FakeAwsTwinMakerContextService(
            _available_aws_context(),
            "aws-refresh-1",
        ),
    )
    run = await service.create_run(
        twin.id,
        user.id,
        OptimizerCalculationParams(**sample_calc_params),
    )
    result = json.loads(run.result_summary_json)
    tampered_context = catalog_context().to_http_dict()
    tampered_context["catalogs"]["aws"] = catalog_reference(
        "aws",
        identity_hex="d",
    ).to_http_dict()
    result["pricingCatalogs"] = tampered_context
    run.result_summary_json = json.dumps(result)
    db_session.commit()
    catalog_calls_before_selection = list(optimizer.catalog_calls)

    with pytest.raises(CostCalculationRunSelectionError) as exc_info:
        await service.select_for_deployment(twin.id, user.id, run.id)

    assert exc_info.value.error_code == "PRICING_CATALOG_CONTEXT_MISMATCH"
    assert optimizer.catalog_calls == catalog_calls_before_selection
    db_session.refresh(run)
    assert run.selected_for_deployment_at is None


def test_select_for_deployment_rejects_failed_run(authenticated_client, db_session):
    client, headers = authenticated_client
    twin_id = create_test_twin(client, headers)
    dev_user = db_session.query(User).filter_by(email="dev@example.com").one()
    failed = CostCalculationRun(
        twin_id=twin_id,
        user_id=dev_user.id,
        status="failed",
        params_json="{}",
        optimization_profile_id="cost_minimization_v1",
        scoring_strategy_id="min_total_cost_v1",
        currency="USD",
    )
    db_session.add(failed)
    db_session.commit()
    db_session.refresh(failed)

    response = client.post(
        f"/twins/{twin_id}/optimizer-runs/{failed.id}/select-for-deployment",
        headers=headers,
    )

    assert response.status_code == 409


def test_select_for_deployment_rejects_legacy_run(
    authenticated_client,
    db_session,
):
    client, headers = authenticated_client
    twin_id = create_test_twin(client, headers)
    dev_user = db_session.query(User).filter_by(email="dev@example.com").one()
    legacy = CostCalculationRun(
        twin_id=twin_id,
        user_id=dev_user.id,
        status="succeeded",
        params_json="{}",
        optimization_profile_id="cost_minimization_v1",
        scoring_strategy_id="min_total_cost_v1",
        currency="USD",
        deployment_compatibility_status="legacy_not_deployable",
    )
    db_session.add(legacy)
    db_session.commit()

    response = client.post(
        f"/twins/{twin_id}/optimizer-runs/{legacy.id}/select-for-deployment",
        headers=headers,
    )

    assert response.status_code == 409
    assert response.json()["detail"]["error_code"] == ("LEGACY_RUN_NOT_DEPLOYABLE")


def test_legacy_run_remains_readable_with_explicit_compatibility_status(
    authenticated_client,
    db_session,
):
    client, headers = authenticated_client
    twin_id = create_test_twin(client, headers)
    dev_user = db_session.query(User).filter_by(email="dev@example.com").one()
    legacy = CostCalculationRun(
        twin_id=twin_id,
        user_id=dev_user.id,
        status="succeeded",
        params_json="{}",
        result_summary_json='{"totalMonthlyCost":12.5}',
        optimization_profile_id="cost_minimization_v1",
        scoring_strategy_id="min_total_cost_v1",
        currency="USD",
        deployment_compatibility_status="legacy_not_deployable",
    )
    db_session.add(legacy)
    db_session.commit()

    response = client.get(
        f"/twins/{twin_id}/optimizer-runs/{legacy.id}",
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json()["deployment_compatibility_status"] == (
        "legacy_not_deployable"
    )
    assert response.json()["resolved_deployment_specification"] is None


def test_persisted_deployment_specification_is_immutable(
    authenticated_client,
    db_session,
    sample_calc_params,
):
    client, headers = authenticated_client
    twin_id = create_test_twin(client, headers)
    _override_optimizer(client, FakeOptimizerClient())
    response = client.post(
        f"/twins/{twin_id}/optimizer-runs/",
        json={"params": sample_calc_params},
        headers=headers,
    )
    run = db_session.get(CostCalculationRun, response.json()["id"])

    run.deployment_specification_digest = "sha256:" + ("f" * 64)
    with pytest.raises(
        ValueError,
        match="specification fields are immutable",
    ):
        db_session.commit()
    db_session.rollback()


@pytest.mark.asyncio
async def test_create_run_rolls_back_run_items_and_compatibility_on_db_failure(
    db_session,
    sample_calc_params,
):
    user = User(email="rollback@example.com", name="Rollback")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    twin = DigitalTwin(name="Rollback Twin", user_id=user.id, state=TwinState.DRAFT)
    db_session.add(twin)
    db_session.commit()
    db_session.refresh(twin)

    class FailingService(CostCalculationRunService):
        def _before_commit(self):
            raise RuntimeError("forced persistence failure")

    service = FailingService(db_session, optimizer_client=FakeOptimizerClient())

    with pytest.raises(RuntimeError):
        await service.create_run(
            twin.id,
            user.id,
            OptimizerCalculationParams.model_validate(sample_calc_params),
        )

    assert db_session.query(CostCalculationRun).count() == 0
    assert (
        db_session.query(OptimizerConfiguration).filter_by(twin_id=twin.id).count() == 0
    )
