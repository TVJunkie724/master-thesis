"""
Calculation API endpoints.

This module provides the core cost optimization endpoint for Digital Twin deployments.
It calculates the optimal complete cloud-provider path across all 5 architectural
layers based on exact pricing catalogs, route costs, and user-defined scenario
parameters.
"""

from datetime import datetime
import re
from time import perf_counter
from typing import Annotated, Literal, Union
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator
from backend.architecture_profiles import (
    ArchitectureProfileRegistry,
    build_resolution_context,
)
from backend.architecture_profiles.six_layer_optimizer import (
    SixLayerEventingV1OptimizationResult,
    optimize_six_layer_eventing_v1,
)
from backend.architecture_profiles.six_layer_workload import (
    resolve_six_layer_workload,
)
from backend.architecture_profiles.activation import (
    architecture_profile_resolution_enabled,
)
from backend.architecture_profiles.diagnostics import (
    ArchitectureResolutionError,
)
from backend.logger import logger
from backend.calculation_v2.transfer_pricing import TransferPricingContractError
from backend.utils import print_stack_trace
from backend.pricing_catalog_models import PricingCatalogContext
from backend.pricing_catalog_repository import (
    PricingCatalogNotFoundError,
    PricingCatalogRegionMismatchError,
    PricingCatalogStaleError,
    PricingCatalogStorageError,
    PricingCatalogTamperedError,
    PricingCatalogUnreviewedError,
    get_pricing_catalog_repository,
)
from backend.pricing_catalog_resolver import PricingCatalogResolver
from api.error_models import ERROR_RESPONSES

router = APIRouter(tags=["Calculation"])
_SAFE_CORRELATION_ID = re.compile(r"^[A-Za-z0-9._-]{1,64}$")


AwsTwinMakerBundleName = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=128),
]


class AwsTwinMakerBundle(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tier: Literal["TIER_1", "TIER_2", "TIER_3", "TIER_4"]
    names: list[AwsTwinMakerBundleName] = Field(
        default_factory=list,
        max_length=20,
    )


class AwsTwinMakerPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: Literal["BASIC", "STANDARD", "TIERED_BUNDLE"]
    billableEntityCount: int = Field(ge=0)
    effectiveAt: datetime | None = None
    updatedAt: datetime | None = None
    updateReason: str | None = Field(default=None, max_length=500)
    bundle: AwsTwinMakerBundle | None = None

    @model_validator(mode="after")
    def validate_bundle_contract(self):
        if self.mode == "TIERED_BUNDLE" and self.bundle is None:
            raise ValueError("Tiered Bundle plans require bundle metadata")
        if self.mode != "TIERED_BUNDLE" and self.bundle is not None:
            raise ValueError("Only Tiered Bundle plans may contain bundle metadata")
        for field_name in ("effectiveAt", "updatedAt"):
            value = getattr(self, field_name)
            if value is not None and value.tzinfo is None:
                raise ValueError(f"{field_name} must be timezone-aware")
        return self


class AwsTwinMakerPricingContextAvailable(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schemaVersion: Literal["aws-twinmaker-account-pricing-context.v1"]
    status: Literal["available"]
    sourceRefreshRunId: str = Field(min_length=1, max_length=128)
    connectionFingerprint: str = Field(
        pattern=r"^sha256:[0-9a-f]{64}$",
    )
    providerAccountId: str = Field(pattern=r"^\d{12}$")
    pricingRegion: str = Field(
        pattern=r"^[a-z]{2}(?:-gov)?-[a-z0-9-]+-\d+$",
    )
    catalogSnapshotDigest: str = Field(
        pattern=r"^sha256:[0-9a-f]{64}$",
    )
    observedAt: datetime
    currentPlan: AwsTwinMakerPlan
    pendingPlan: AwsTwinMakerPlan | None = None

    @model_validator(mode="after")
    def validate_observation_timestamp(self):
        if self.observedAt.tzinfo is None:
            raise ValueError("observedAt must be timezone-aware")
        return self


class AwsTwinMakerPricingContextUnavailable(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["unavailable"] = "unavailable"
    reasonCode: str = Field(
        default="AWS_TWINMAKER_PLAN_UNOBSERVED",
        min_length=1,
        max_length=120,
        pattern=r"^[A-Z][A-Z0-9_]*$",
    )


AwsTwinMakerPricingContext = Annotated[
    Union[
        AwsTwinMakerPricingContextAvailable,
        AwsTwinMakerPricingContextUnavailable,
    ],
    Field(discriminator="status"),
]


class ProviderPricingContexts(BaseModel):
    model_config = ConfigDict(extra="forbid")

    awsTwinMaker: AwsTwinMakerPricingContext = Field(
        default_factory=AwsTwinMakerPricingContextUnavailable
    )


class ArchitectureProfileRequestRef(BaseModel):
    """Management-owned exact architecture profile reference."""

    model_config = ConfigDict(extra="forbid")

    profileId: str = Field(min_length=1, max_length=160)
    profileVersion: str = Field(min_length=1, max_length=32)
    contentDigest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class ExtensionBindingRequestRef(BaseModel):
    """Management-owned immutable extension binding reference."""

    model_config = ConfigDict(extra="forbid")

    slotId: str = Field(min_length=1, max_length=160)
    slotVersion: str = Field(min_length=1, max_length=32)
    artifactId: str = Field(min_length=1, max_length=160)
    artifactDigest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    configurationDigest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


# --------------------------------------------------
# Input model for calculation
# --------------------------------------------------
class SixLayerCalcParams(BaseModel):
    """Closed-world workload request for the sole deployable architecture."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    calculationRunId: UUID
    schemaVersion: Literal["six-layer-workload.v1"]
    numberOfDevices: int = Field(gt=0, strict=True)
    deviceSendingIntervalInMinutes: float = Field(gt=0, strict=True)
    averageSizeOfMessageInKb: float = Field(gt=0, strict=True)
    numberOfDeviceTypes: int = Field(ge=1, strict=True)
    hotStorageDurationInMonths: int = Field(ge=1, strict=True)
    coolStorageDurationInMonths: int = Field(ge=1, strict=True)
    archiveStorageDurationInMonths: int = Field(ge=6, strict=True)
    twinEntityCount: int = Field(ge=1, strict=True)
    aggregateDashboardRefreshesPerHour: int = Field(ge=0, strict=True)
    apiCallsPerAggregateDashboardRefresh: int = Field(ge=1, strict=True)
    dashboardActiveHoursPerDay: int = Field(ge=0, le=24, strict=True)
    monthlyEditorSeats: int = Field(ge=0, strict=True)
    monthlyViewerSeats: int = Field(ge=0, strict=True)
    twinStateMaterializationsPerSecond: float = Field(ge=0, strict=True)
    twinGraphUpdatesPerSecond: float = Field(ge=0, strict=True)
    eventingScenarioId: Literal[
        "eventing-small-v1",
        "eventing-medium-v1",
        "eventing-large-v1",
    ]
    currency: Literal["USD", "EUR"] = "USD"
    providerPricingCatalogs: PricingCatalogContext
    providerPricingContexts: ProviderPricingContexts = Field(
        default_factory=ProviderPricingContexts
    )
    architectureProfile: ArchitectureProfileRequestRef
    extensionBindings: list[ExtensionBindingRequestRef] = Field(max_length=64)

    def workload_payload(self) -> dict[str, object]:
        return self.model_dump(
            exclude={
                "calculationRunId",
                "providerPricingCatalogs",
                "providerPricingContexts",
                "architectureProfile",
                "extensionBindings",
            }
        )

    @model_validator(mode="after")
    def validate_frozen_scenario(self) -> "SixLayerCalcParams":
        resolve_six_layer_workload(self.workload_payload())
        return self


CalculationParams = SixLayerCalcParams


# --------------------------------------------------
# Calculation endpoint
# --------------------------------------------------
@router.put(
    "/calculate",
    operation_id="calculateOptimalCloudDistribution",
    summary="Calculate optimal multi-cloud cost distribution for Digital Twin deployment",
    description=(
        "**Purpose:** Computes the most cost-effective distribution of Digital Twin services "
        "across AWS, Azure, and GCP based on your scenario parameters and current cloud pricing.\n\n"
        "**When to use this endpoint:**\n"
        "- Before deploying a new Digital Twin to determine the cheapest provider configuration\n"
        "- When comparing costs across different scenario configurations\n"
        "- To understand cost breakdown by architectural layer\n\n"
        "**How it works:**\n"
        "1. Takes your Digital Twin parameters (device count, message frequency, storage needs, etc.)\n"
        "2. Resolves the exact reviewed provider-region catalogs supplied in `providerPricingCatalogs`\n"
        "3. Enumerates every executable assignment inside the Six-layer v1 profile\n"
        "4. Prices its reviewed direct, tiering, Twin-projection, and Cross-Cloud routes\n"
        "5. Scores complete layer and route totals and returns the deterministic winner\n"
        "6. Returns detailed cost, route, billing-pool, and immutable evidence context\n\n"
        "**The shared 5 architectural layers:**\n"
        "- **L1 (Ingestion):** IoT data acquisition - receives telemetry from devices\n"
        "- **L2 (Processing):** Data processing, event detection, notifications\n"
        "- **L3 (Storage):** Hot/Cool/Archive storage tiers - each can be on different providers\n"
        "- **L4 (Management):** Digital Twin state and bounded relationship management\n"
        "- **L5 (Visualization):** Dashboards and user interfaces\n\n"
        "Six-layer v1 keeps those responsibilities and adds one independently assigned "
        "Eventing responsibility.\n\n"
        "**Important:** This is a calculation-only endpoint. It does not deploy any resources. "
        "Use the Deployer API's `/infrastructure/deploy` to actually provision infrastructure."
    ),
    response_description=(
        "Complete-path cost analysis with selected providers, route pricing, "
        "immutable evidence, and bounded optimization diagnostics"
    ),
    responses={
        200: {
            "description": "Successful calculation - returns cost breakdown and optimal configuration",
            "content": {
                "application/json": {
                    "example": {
                        "result": {
                            "calculationResult": {
                                "L1": "GCP",
                                "L2": "AWS",
                                "L3": {
                                    "Hot": "AWS",
                                    "Cool": "GCP",
                                    "Archive": "AWS",
                                },
                                "L4": "Azure",
                                "L5": "Azure",
                            },
                            "cheapestPath": [
                                "L1_GCP",
                                "L2_AWS",
                                "L3_hot_AWS",
                                "L3_cool_GCP",
                                "L3_archive_AWS",
                                "L4_Azure",
                                "L5_Azure",
                            ],
                            "transferPricingContext": {
                                "schemaVersion": "complete-path-transfer-pricing.v1",
                                "currency": "USD",
                                "routes": [],
                                "pools": [],
                            },
                            "optimizationDiagnostics": {
                                "schemaVersion": "complete-path-optimization.v1",
                                "enumeratedPathCount": 972,
                                "evaluatedPathCount": 972,
                                "rejectedPathCount": 0,
                                "winningCandidateId": (
                                    "gcp|aws|aws|gcp|aws|azure|azure"
                                ),
                                "scoreUnit": "USD/month",
                            },
                            "totalCost": 85.50,
                            "optimization_profile_id": "cost_minimization_v1",
                            "result_schema_version": "cost-result.v1",
                            "currency": "USD",
                        }
                    }
                }
            },
        },
        400: ERROR_RESPONSES[400],
        409: ERROR_RESPONSES[409],
        422: ERROR_RESPONSES[422],
        500: ERROR_RESPONSES[500],
    },
)
def calc(params: CalculationParams, request: Request):
    """
    Perform a cloud cost optimization calculation based on Digital Twin configuration parameters.
    """
    resolution_started_at = perf_counter()
    architecture_context = None
    architecture_requested = (
        architecture_profile_resolution_enabled()
        or params.architectureProfile is not None
        or params.extensionBindings is not None
    )
    correlation_id = _correlation_id(
        request.headers.get("x-request-id"),
        fallback=str(params.calculationRunId),
    )
    architecture_log_emitted = False

    def log_architecture_failure(
        error_code: str,
        diagnostics: dict | None = None,
    ) -> None:
        nonlocal architecture_log_emitted
        if not architecture_requested or architecture_log_emitted:
            return
        _log_architecture_resolution_failure(
            params=params,
            context=architecture_context,
            correlation_id=correlation_id,
            error_code=error_code,
            started_at=resolution_started_at,
            diagnostics=diagnostics,
        )
        architecture_log_emitted = True

    try:
        architecture_context = _resolve_architecture_context(params)
        resolved_catalogs = PricingCatalogResolver(
            get_pricing_catalog_repository()
        ).resolve_context(
            params.providerPricingCatalogs,
            require_fresh=True,
        )
        result = _calculate_six_layer(
            params,
            resolved_catalogs=resolved_catalogs,
        )
        result["pricingCatalogs"] = resolved_catalogs.context.to_http_dict()
        if architecture_context is not None:
            _log_architecture_resolution_success(
                context=architecture_context,
                diagnostics=result.get("architectureResolutionDiagnostics"),
                correlation_id=correlation_id,
                started_at=resolution_started_at,
            )
            architecture_log_emitted = True

        return {"result": result}
    except PricingCatalogStaleError as e:
        log_architecture_failure(e.code)
        raise HTTPException(
            status_code=409,
            detail={
                "error_code": e.code,
                "message": str(e),
                "fix_suggestion": (
                    "Refresh the affected provider-region pricing catalog and "
                    "retry with its newly published exact reference."
                ),
                "http_status": 409,
            },
        ) from e
    except (
        PricingCatalogNotFoundError,
        PricingCatalogRegionMismatchError,
        PricingCatalogUnreviewedError,
    ) as e:
        log_architecture_failure(e.code)
        raise HTTPException(
            status_code=409,
            detail={
                "error_code": e.code,
                "message": str(e),
                "fix_suggestion": (
                    "Select exactly one published, reviewed catalog for AWS, "
                    "Azure, and GCP before calculating."
                ),
                "http_status": 409,
            },
        ) from e
    except (PricingCatalogTamperedError, PricingCatalogStorageError) as e:
        log_architecture_failure(e.code)
        logger.error("Pricing catalog resolution failed: %s", e.code)
        raise HTTPException(
            status_code=500,
            detail={
                "error_code": e.code,
                "message": "Pricing catalog storage failed integrity validation.",
                "fix_suggestion": (
                    "Restore the durable pricing catalog volume from reviewed "
                    "baselines or a verified backup before retrying."
                ),
                "http_status": 500,
            },
        ) from e
    except ArchitectureResolutionError as e:
        log_architecture_failure(e.code, e.safe_diagnostics())
        raise HTTPException(
            status_code=409,
            detail={
                "error_code": e.code,
                "message": e.message,
                "fix_suggestion": (
                    "Use the exact active Management-owned architecture "
                    "profile and extension references, then retry."
                ),
                "http_status": 409,
                "diagnostics": e.safe_diagnostics(),
            },
        ) from e
    except TransferPricingContractError as e:
        log_architecture_failure(e.code)
        raise HTTPException(
            status_code=409,
            detail={
                "error_code": e.code,
                "message": e.message,
                "fix_suggestion": (
                    "Review the selected provider regions, transfer-route "
                    "contract, and published transfer pricing evidence."
                ),
                "http_status": 409,
            },
        ) from e
    except ValueError as e:
        log_architecture_failure("ARCH_WORKLOAD_INCOMPATIBLE")
        logger.error(f"Validation error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        log_architecture_failure("ARCH_RESOLUTION_BUILD_FAILED")
        logger.error(f"Error during calculation: {e}")
        print_stack_trace()
        raise HTTPException(
            status_code=500, detail="Calculation failed. Check server logs."
        )


def _calculate_six_layer(
    params: SixLayerCalcParams,
    *,
    resolved_catalogs,
) -> dict[str, object]:
    references = {
        provider: {
            "id": reference.snapshot_id,
            # The RTA field versions the pricing-evidence reference contract,
            # while the immutable catalog identity stays in ``id`` and
            # ``digest``. Provider schema versions are intentionally not
            # substituted for this numeric contract version.
            "version": "1",
            "digest": reference.content_digest,
            "provider": provider,
            "currency": params.currency,
        }
        for provider, reference in resolved_catalogs.context.catalogs.items()
    }
    if (
        params.architectureProfile.profileId != "six-layer-eventing"
        or params.architectureProfile.profileVersion != "1"
    ):
        raise ArchitectureResolutionError(
            "ARCH_PROFILE_NOT_FOUND",
            "architectureProfile",
            "Only the Six-layer Eventing v1 profile is executable",
        )
    optimized = optimize_six_layer_eventing_v1(
        calculation_run_id=str(params.calculationRunId),
        architecture_profile=params.architectureProfile.model_dump(),
        extension_bindings=[item.model_dump() for item in params.extensionBindings],
        workload=params.workload_payload(),
        pricing_evidence_refs=references,
        pricing_by_provider=resolved_catalogs.detached_pricing(),
        resolution_status="offline_contract_fixture",
    )
    return _six_layer_http_result(params, optimized)


def _six_layer_http_result(
    params: SixLayerCalcParams,
    optimized: SixLayerEventingV1OptimizationResult,
) -> dict[str, object]:
    assignments = {
        item["logical_component_id"]: item["provider"]
        for item in optimized.resolved_architecture["component_assignments"]
    }
    provider_label = {"aws": "AWS", "azure": "Azure", "gcp": "GCP"}
    calculation_result = {
        "L1": provider_label[assignments["component.ingestion"]],
        "L2": provider_label[assignments["component.processing"]],
        "L3": {
            "Hot": provider_label[assignments["component.hot-storage"]],
            "Cool": provider_label[assignments["component.cool-storage"]],
            "Archive": provider_label[assignments["component.archive-storage"]],
        },
        "L4": provider_label[assignments["component.twin-state"]],
        "L5": provider_label[assignments["component.visualization"]],
    }
    if "component.eventing" in assignments:
        calculation_result["Eventing"] = provider_label[
            assignments["component.eventing"]
        ]
    cheapest_path = [
        f"L1_{calculation_result['L1']}",
        f"L2_{calculation_result['L2']}",
        f"L3_hot_{calculation_result['L3']['Hot']}",
        f"L3_cool_{calculation_result['L3']['Cool']}",
        f"L3_archive_{calculation_result['L3']['Archive']}",
        f"L4_{calculation_result['L4']}",
        f"L5_{calculation_result['L5']}",
    ]
    if "Eventing" in calculation_result:
        cheapest_path.append(f"Eventing_{calculation_result['Eventing']}")
    provider_pricing_contexts = params.providerPricingContexts.model_dump(mode="json")
    aws_twinmaker = provider_pricing_contexts["awsTwinMaker"]
    if calculation_result["L4"] == "AWS" and aws_twinmaker["status"] == "available":
        aws_twinmaker["status"] = "compatible"
    return {
        "calculationResult": calculation_result,
        "cheapestPath": cheapest_path,
        "totalCost": float(optimized.cost_evaluation.monthly_total),
        "totalCostExact": str(optimized.cost_evaluation.monthly_total),
        "currency": optimized.cost_evaluation.currency,
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
        "architectureResolutionDiagnostics": {
            "schemaVersion": "architecture-resolution-diagnostics.v2",
            "enumeratedCandidateCount": optimized.enumerated_candidate_count,
            "admissibleCandidateCount": optimized.costed_candidate_count,
            "rejectedCandidateCount": (
                optimized.enumerated_candidate_count - optimized.costed_candidate_count
            ),
            "rejectedByErrorCode": dict(optimized.rejected_by_error_code),
            "winningCandidateId": optimized.winning_candidate_id,
        },
        "providerPricingContexts": provider_pricing_contexts,
        "costLedger": dict(optimized.cost_ledger),
        "resolvedTwinArchitecture": dict(optimized.resolved_architecture),
        "resolvedDeploymentSpecification": dict(optimized.deployment_specification),
    }


def _resolve_architecture_context(params: CalculationParams):
    requested = (
        params.architectureProfile is not None or params.extensionBindings is not None
    )
    if not architecture_profile_resolution_enabled():
        if requested:
            raise ArchitectureResolutionError(
                "ARCH_PROFILE_BUNDLE_INCOMPATIBLE",
                "architectureProfile",
                "Architecture profile resolution is not enabled",
            )
        return None
    if params.architectureProfile is None or params.extensionBindings is None:
        raise ArchitectureResolutionError(
            "ARCH_PROFILE_BUNDLE_INCOMPATIBLE",
            "architectureProfile",
            "Enabled architecture resolution requires all trusted references",
        )
    return build_resolution_context(
        registry=ArchitectureProfileRegistry(
            profile_id=params.architectureProfile.profileId,
            profile_version=params.architectureProfile.profileVersion,
        ),
        calculation_run_id=str(params.calculationRunId),
        architecture_profile=params.architectureProfile.model_dump(),
        extension_bindings=[item.model_dump() for item in params.extensionBindings],
    )


def _correlation_id(value: str | None, *, fallback: str) -> str:
    if value is not None and _SAFE_CORRELATION_ID.fullmatch(value):
        return value
    return fallback


def _log_architecture_resolution_success(
    *,
    context,
    diagnostics: object,
    correlation_id: str,
    started_at: float,
) -> None:
    safe_diagnostics = diagnostics if isinstance(diagnostics, dict) else {}
    logger.info(
        "architecture_resolution outcome=success run_id=%s "
        "correlation_id=%s profile_id=%s profile_version=%s "
        "profile_digest=%s bundle_id=%s bundle_version=%s "
        "bundle_digest=%s enumerated_candidate_count=%s "
        "admissible_candidate_count=%s rejected_candidate_count=%s "
        "winner_candidate_id=%s duration_ms=%.3f",
        context.calculation_run_id,
        correlation_id,
        context.profile_ref.profile_id,
        context.profile_ref.profile_version,
        context.profile_ref.content_digest,
        context.bundle_ref.optimization_strategy_id,
        context.bundle_ref.optimization_strategy_version,
        context.bundle_ref.compatibility_digest,
        safe_diagnostics.get("enumeratedCandidateCount", 0),
        safe_diagnostics.get("admissibleCandidateCount", 0),
        safe_diagnostics.get("rejectedCandidateCount", 0),
        safe_diagnostics.get("winningCandidateId", "unavailable"),
        (perf_counter() - started_at) * 1000,
    )


def _log_architecture_resolution_failure(
    *,
    params: CalculationParams,
    context,
    correlation_id: str,
    error_code: str,
    started_at: float,
    diagnostics: dict | None,
) -> None:
    profile = params.architectureProfile
    safe_diagnostics = diagnostics or {}
    logger.warning(
        "architecture_resolution outcome=failure run_id=%s "
        "correlation_id=%s profile_id=%s profile_version=%s "
        "profile_digest=%s bundle_id=%s bundle_version=%s "
        "bundle_digest=%s enumerated_candidate_count=%s "
        "admissible_candidate_count=%s rejected_candidate_count=%s "
        "winner_candidate_id=none error_code=%s duration_ms=%.3f",
        str(params.calculationRunId),
        correlation_id,
        (
            context.profile_ref.profile_id
            if context is not None
            else profile.profileId
            if profile is not None
            else "unresolved"
        ),
        (
            context.profile_ref.profile_version
            if context is not None
            else profile.profileVersion
            if profile is not None
            else "unresolved"
        ),
        (
            context.profile_ref.content_digest
            if context is not None
            else profile.contentDigest
            if profile is not None
            else "unresolved"
        ),
        (
            context.bundle_ref.optimization_strategy_id
            if context is not None
            else "unresolved"
        ),
        (
            context.bundle_ref.optimization_strategy_version
            if context is not None
            else "unresolved"
        ),
        (
            context.bundle_ref.compatibility_digest
            if context is not None
            else "unresolved"
        ),
        safe_diagnostics.get("enumeratedCandidateCount", 0),
        safe_diagnostics.get("admissibleCandidateCount", 0),
        safe_diagnostics.get("rejectedCandidateCount", 0),
        error_code,
        (perf_counter() - started_at) * 1000,
    )
