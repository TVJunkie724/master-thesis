"""
Calculation API endpoints.

This module provides the core cost optimization endpoint for Digital Twin deployments.
It calculates the optimal cloud provider distribution across all 5 architectural layers
based on current pricing data and user-defined scenario parameters.
"""
from datetime import datetime
from typing import Annotated, Literal, Union

from fastapi import APIRouter, Body, HTTPException
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    model_validator,
)

from backend.logger import logger
from backend.utils import print_stack_trace
from backend.config_loader import load_combined_pricing
from api.error_models import ERROR_RESPONSES

router = APIRouter(tags=["Calculation"])


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


# --------------------------------------------------
# Input model for calculation
# --------------------------------------------------
class CalcParams(BaseModel):
    """
    Defines the parameters for calculating the cost-optimized Digital Twin deployment.
    
    Server-side validation ensures:
    - Positive values for device counts, intervals, and sizes
    - Storage duration ordering: Hot ≤ Cool ≤ Archive
    - Non-negative values for editor/viewer counts and dashboard settings
    """
    # Core IoT parameters - must be positive
    numberOfDevices: int = Field(..., gt=0, description="Number of IoT devices (must be > 0)")
    deviceSendingIntervalInMinutes: float = Field(..., gt=0, description="Sending interval in minutes (must be > 0)")
    averageSizeOfMessageInKb: float = Field(..., gt=0, description="Average message size in KB (must be > 0)")
    
    # Storage durations - must be positive (ordering validated by model_validator)
    hotStorageDurationInMonths: int = Field(..., ge=1, description="Hot storage duration (must be >= 1)")
    coolStorageDurationInMonths: int = Field(..., ge=1, description="Cool storage duration (must be >= 1)")
    archiveStorageDurationInMonths: int = Field(..., ge=6, description="Archive storage duration (must be >= 6)")
    
    # 3D model settings
    needs3DModel: bool
    entityCount: int = Field(..., ge=0, description="Number of entities (must be >= 0)")
    
    # Dashboard settings
    amountOfActiveEditors: int = Field(..., ge=0, description="Number of active editors (must be >= 0)")
    amountOfActiveViewers: int = Field(..., ge=0, description="Number of active viewers (must be >= 0)")
    dashboardRefreshesPerHour: int = Field(..., ge=0, description="Dashboard refresh rate (must be >= 0)")
    dashboardActiveHoursPerDay: int = Field(..., ge=0, le=24, description="Active hours per day (must be 0-24)")
    currency: Literal["USD", "EUR"] = "USD"
    
    # Parameters for supporter services
    useEventChecking: bool = False
    triggerNotificationWorkflow: bool = False
    returnFeedbackToDevice: bool = False
    integrateErrorHandling: bool = False
    
    orchestrationActionsPerMessage: int = Field(default=3, ge=1)
    eventsPerMessage: int = Field(default=1, ge=1)
    apiCallsPerDashboardRefresh: int = Field(default=1, ge=1)
    average3DModelSizeInMB: float = Field(default=100.0, gt=0)
    averageDigitalTwinQueryUnitsPerQuery: float = Field(
        default=1.0,
        gt=0,
        strict=True,
        allow_inf_nan=False,
        description="Estimated average Azure Digital Twins query units per logical query",
    )
    averageDigitalTwinQueryResponseSizeInKb: float = Field(
        default=1.0,
        gt=0,
        strict=True,
        allow_inf_nan=False,
        description="Estimated average Azure Digital Twins query response size in KB",
    )
    
    # New parameters for enhanced cost calculation
    numberOfDeviceTypes: int = Field(default=1, ge=1, description="Number of distinct device types (each requires a processor)")
    numberOfEventActions: int = Field(default=0, ge=0, description="Number of event action handlers from config_events.json")
    eventTriggerRate: float = Field(default=0.1, ge=0.0, le=1.0, description="Fraction of messages that trigger events (0.0-1.0)")
    
    # GCP Self-Hosted Options (L4/L5)
    # GCP lacks managed equivalents to AWS TwinMaker/Managed Grafana and Azure Digital Twins/Managed Grafana.
    # These toggles allow users to include or exclude GCP's self-hosted Compute Engine alternatives.
    # Default: False (GCP L4/L5 not implemented - future work)
    allowGcpSelfHostedL4: bool = Field(default=False, description="Include GCP self-hosted L4 (Twin Management on Compute Engine) in optimization - NOT IMPLEMENTED")
    allowGcpSelfHostedL5: bool = Field(default=False, description="Include GCP self-hosted L5 (Grafana on Compute Engine) in optimization - NOT IMPLEMENTED")

    optimizationProfileId: str = Field(
        default="cost_minimization_v1",
        description="Executable optimization profile. Only cost_minimization_v1 is enabled.",
    )
    providerPricingContexts: ProviderPricingContexts = Field(
        default_factory=ProviderPricingContexts,
        description=(
            "Management-injected provider account pricing observations. "
            "Clients cannot infer an AWS TwinMaker plan."
        ),
    )

    @model_validator(mode='after')
    def validate_storage_duration_ordering(self) -> 'CalcParams':
        """Ensure storage durations follow logical ordering: Hot ≤ Cool ≤ Archive."""
        if self.hotStorageDurationInMonths > self.coolStorageDurationInMonths:
            raise ValueError(
                f"Hot storage duration ({self.hotStorageDurationInMonths}) must be <= "
                f"Cool storage duration ({self.coolStorageDurationInMonths})"
            )
        if self.coolStorageDurationInMonths > self.archiveStorageDurationInMonths:
            raise ValueError(
                f"Cool storage duration ({self.coolStorageDurationInMonths}) must be <= "
                f"Archive storage duration ({self.archiveStorageDurationInMonths})"
            )
        if self.allowGcpSelfHostedL4 or self.allowGcpSelfHostedL5:
            raise ValueError(
                "GCP self-hosted L4/L5 cannot be enabled until the Deployer "
                "implements and verifies those deployment paths"
            )
        return self

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False, json_schema_extra={
        "example": {
            "numberOfDevices": 100,
            "deviceSendingIntervalInMinutes": 2,
            "averageSizeOfMessageInKb": 0.25,
            "hotStorageDurationInMonths": 1,
            "coolStorageDurationInMonths": 3,
            "archiveStorageDurationInMonths": 12,
            "needs3DModel": False,
            "entityCount": 1,
            "amountOfActiveEditors": 0,
            "amountOfActiveViewers": 0,
            "dashboardRefreshesPerHour": 2,
            "dashboardActiveHoursPerDay": 0,
            "currency": "USD",
            "useEventChecking": True,
            "triggerNotificationWorkflow": True,
            "returnFeedbackToDevice": False,
            "integrateErrorHandling": True,
            "orchestrationActionsPerMessage": 3,
            "eventsPerMessage": 1,
            "apiCallsPerDashboardRefresh": 1,
            "averageDigitalTwinQueryUnitsPerQuery": 1.0,
            "averageDigitalTwinQueryResponseSizeInKb": 1.0,
            "optimizationProfileId": "cost_minimization_v1",
            "allowGcpSelfHostedL4": False,
            "allowGcpSelfHostedL5": False
        }
    })


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
        "2. Loads current pricing data for all three cloud providers\n"
        "3. Calculates costs for each of the 5 architectural layers on each provider\n"
        "4. Returns the optimal provider per layer and detailed cost breakdowns\n\n"
        
        "**The 5 Architectural Layers:**\n"
        "- **L1 (Ingestion):** IoT data acquisition - receives telemetry from devices\n"
        "- **L2 (Processing):** Data processing, event detection, notifications\n"
        "- **L3 (Storage):** Hot/Cool/Archive storage tiers - each can be on different providers\n"
        "- **L4 (Management):** Digital Twin entity management and 3D modeling\n"
        "- **L5 (Visualization):** Dashboards and user interfaces\n\n"
        
        "**Important:** This is a calculation-only endpoint. It does not deploy any resources. "
        "Use the Deployer API's `/infrastructure/deploy` to actually provision infrastructure."
    ),
    response_description="Complete cost analysis with optimal provider per layer and detailed breakdowns",
    responses={
        200: {
            "description": "Successful calculation - returns cost breakdown and optimal configuration",
            "content": {
                "application/json": {
                    "example": {
                        "result": {
                            "calculationResult": {
                                "L1": "GCP",
                                "L2": {"Hot": "AWS", "Cool": "GCP", "Archive": "AWS"},
                                "L3": "AWS",
                                "L4": "Azure",
                                "L5": "GCP"
                            },
                            "awsCosts": {"L1": 12.50, "L2_Hot": 5.00, "L2_Cool": 8.00, "L2_Archive": 2.00},
                            "azureCosts": {"L1": 15.00, "L4": 20.00},
                            "gcpCosts": {"L1": 10.00, "L5": 18.00},
                            "cheapestPath": ["L1_GCP", "L2_AWS_Hot", "L2_GCP_Cool", "L2_AWS_Archive", "L3_AWS", "L4_Azure", "L5_GCP"],
                            "totalCost": 85.50,
                            "optimization_profile_id": "cost_minimization_v1",
                            "result_schema_version": "cost-result.v1",
                            "currency": "USD"
                        }
                    }
                }
            },
        },
        400: ERROR_RESPONSES[400],
        422: ERROR_RESPONSES[422],
        500: ERROR_RESPONSES[500],
    },
)
def calc(params: CalcParams = Body(
    ...,
    examples=[{
        "numberOfDevices": 100,
        "deviceSendingIntervalInMinutes": 2.0,
        "averageSizeOfMessageInKb": 0.25,
        "hotStorageDurationInMonths": 1,
        "coolStorageDurationInMonths": 3,
        "archiveStorageDurationInMonths": 12,
        "needs3DModel": False,
        "entityCount": 0,
        "amountOfActiveEditors": 2,
        "amountOfActiveViewers": 10,
        "dashboardRefreshesPerHour": 4,
        "dashboardActiveHoursPerDay": 8,
        "currency": "USD",
        "useEventChecking": True,
        "triggerNotificationWorkflow": True,
        "returnFeedbackToDevice": False,
        "integrateErrorHandling": True,
        "orchestrationActionsPerMessage": 3,
        "eventsPerMessage": 1,
        "apiCallsPerDashboardRefresh": 1,
        "averageDigitalTwinQueryUnitsPerQuery": 1.0,
        "averageDigitalTwinQueryResponseSizeInKb": 1.0,
        "optimizationProfileId": "cost_minimization_v1"
    }]
)):
    """
    Perform a cloud cost optimization calculation based on Digital Twin configuration parameters.
    """
    try:
        # Use new component-level calculation engine (v2)
        from backend.calculation_v2.engine import calculate_cheapest_costs
        
        # Convert Pydantic model to dict
        params_dict = params.model_dump()
        optimization_profile_id = params_dict.pop("optimizationProfileId")
        params_dict["_assumption_sources"] = {
            field: (
                "explicit_input"
                if field in params.model_fields_set
                else "compatibility_default"
            )
            for field in (
                "averageDigitalTwinQueryUnitsPerQuery",
                "averageDigitalTwinQueryResponseSizeInKb",
            )
        }
        
        # Load combined pricing from separate files
        pricing_data = load_combined_pricing()
        result = calculate_cheapest_costs(
            params_dict,
            pricing=pricing_data,
            optimization_profile_id=optimization_profile_id,
        )
        
        return {"result": result}
    except ValueError as e:
        logger.error(f"Validation error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error during calculation: {e}")
        print_stack_trace()
        raise HTTPException(status_code=500, detail="Calculation failed. Check server logs.")
