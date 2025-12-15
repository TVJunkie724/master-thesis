"""
Calculation API endpoints.
"""
from fastapi import APIRouter, Body
from pydantic import BaseModel, ConfigDict, Field, model_validator

from backend.logger import logger
from backend.utils import print_stack_trace
from backend.config_loader import load_combined_pricing

router = APIRouter(tags=["Calculation"])


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
    currency: str = "USD"
    
    # Parameters for supporter services
    useEventChecking: bool = False
    triggerNotificationWorkflow: bool = False
    returnFeedbackToDevice: bool = False
    integrateErrorHandling: bool = False
    
    orchestrationActionsPerMessage: int = Field(default=3, ge=1)
    eventsPerMessage: int = Field(default=1, ge=1)
    apiCallsPerDashboardRefresh: int = Field(default=1, ge=1)
    average3DModelSizeInMB: float = Field(default=100.0, gt=0)
    
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
        return self

    model_config = ConfigDict(json_schema_extra={
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
            "allowGcpSelfHostedL4": False,
            "allowGcpSelfHostedL5": False
        }
    })


# --------------------------------------------------
# Calculation endpoint
# --------------------------------------------------
@router.put(
    "/api/calculate",
    summary="Calculate Cloud Costs and Determine Cheapest Provider Setup",
    description=(
        "This endpoint receives a complete set of **Digital Twin scenario parameters**, "
        "processes them through the Python calculation engine, and returns "
        "the calculated cost breakdown for AWS, Azure, and GCP, along with the optimal provider "
        "per architectural layer (L1–L5)."
        "\n"
        "**Layers overview:**\n"
        "- **L1:** IoT Data Acquisition & Processing\n"
        "- **L2:** Storage (Hot, Cool, Archive)\n"
        "- **L3:** Data Processing & Integration\n"
        "- **L4:** Twin Management (3D model)\n"
        "- **L5:** Data Visualization (Dashboards)"
    ),
    response_description="JSON object containing cost breakdowns and cheapest provider path.",
    responses={
        200: {
            "description": "Successful calculation of costs and cheapest cloud configuration.",
            "content": {
                "application/json": {
                    "example": {
                        "result": {
                            "calculationResult": {
                                "L1": "GCP",
                                "L2": {"Hot": "AWS", "Cool": "GCP", "Archive": "AWS"},
                                "L3": "AWS",
                                "L4": "GCP",
                                "L5": "GCP"
                            },
                            "awsCosts": "...",
                            "azureCosts": "...",
                            "gcpCosts": "...",
                            "cheapestPath": ["L1_GCP", "L2_AWS_Hot", "L2_GCP_Cool", "L2_AWS_Archive", "L3_AWS", "L4_GCP", "L5_GCP"]
                        }
                    }
                }
            },
        },
        400: {"description": "Invalid input parameters."},
        500: {"description": "Internal error during cost calculation."},
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
        "apiCallsPerDashboardRefresh": 1
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
        
        # Load combined pricing from separate files
        pricing_data = load_combined_pricing()
        result = calculate_cheapest_costs(params_dict, pricing=pricing_data)
        
        return {"result": result}
    except Exception as e:
        logger.error(f"Error during calculation: {e}")
        print_stack_trace()
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=500, content={"error": str(e)})
