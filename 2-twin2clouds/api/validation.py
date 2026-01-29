"""
Validation API endpoints for Optimizer.

Provides configuration validation for the optimizer config (params + result).
Use this endpoint to verify optimizer configuration is complete before 
transitioning to the deployment phase.
"""
from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, Any, List

from api.error_models import ERROR_RESPONSES

router = APIRouter(tags=["Validation"])


# --------------------------------------------------
# Models
# --------------------------------------------------

class OptimizerConfigValidation(BaseModel):
    """
    Input model for optimizer config validation.
    
    Provide the optimizer parameters and calculation result to validate
    that the configuration is complete and ready for deployment.
    """
    params: Optional[dict[str, Any]] = Field(
        None,
        description="The optimizer parameters used for calculation (from Step 2 configuration)"
    )
    result: Optional[dict[str, Any]] = Field(
        None,
        description="The calculation result containing cheapestPath and cost breakdown"
    )

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "params": {
                "numberOfDevices": 100,
                "deviceSendingIntervalInMinutes": 2,
                "averageSizeOfMessageInKb": 0.25,
                "hotStorageDurationInMonths": 1,
                "coolStorageDurationInMonths": 3,
                "archiveStorageDurationInMonths": 12
            },
            "result": {
                "cheapestPath": ["L1_GCP", "L2_AWS", "L3_Azure"],
                "calculationResult": {"L1": "GCP", "L2": "AWS", "L3": "Azure"},
                "totalMonthlyCost": 125.50
            }
        }
    })


class ValidationError(BaseModel):
    """
    Structured validation error with actionable information.
    
    Each error includes a code, field, and message so agents can
    understand what needs to be fixed.
    """
    code: str = Field(
        ...,
        description="Machine-readable error code in SCREAMING_SNAKE_CASE",
        json_schema_extra={"example": "MISSING_PARAMS"}
    )
    field: str = Field(
        ...,
        description="The field path that has the error",
        json_schema_extra={"example": "params"}
    )
    message: str = Field(
        ...,
        description="Human-readable explanation and how to fix it",
        json_schema_extra={"example": "Optimizer parameters required - configure in Step 2"}
    )


class ValidationResponse(BaseModel):
    """
    Validation response with all errors found.
    
    When valid=true, the configuration is complete and ready for deployment.
    When valid=false, check the errors array for what needs to be fixed.
    """
    valid: bool = Field(
        ...,
        description="True if configuration is complete and valid, False if there are errors"
    )
    errors: List[ValidationError] = Field(
        default=[],
        description="List of all validation errors (empty if valid=true)"
    )

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "valid": False,
            "errors": [
                {
                    "code": "MISSING_RESULT",
                    "field": "result",
                    "message": "Optimizer result required - run cost calculation in Step 2"
                }
            ]
        }
    })


# --------------------------------------------------
# Endpoints
# --------------------------------------------------

@router.post(
    "/validate/optimizer-config",
    operation_id="validateOptimizerConfiguration",
    response_model=ValidationResponse,
    summary="Validate optimizer configuration before deployment",
    description=(
        "**Purpose:** Validates that the optimizer configuration is complete and ready "
        "for state transition to the deployment phase.\n\n"
        
        "**When to use:**\n"
        "- Before transitioning from 'optimized' to 'ready_to_deploy' state\n"
        "- To verify user has completed all Step 2 configuration\n\n"
        
        "**Validation checks:**\n"
        "- `params`: Optimizer parameters must be present (device count, intervals, etc.)\n"
        "- `result`: Calculation result must be present (run the calculation first)\n"
        "- `result.cheapestPath`: The optimal provider path must be calculated\n\n"
        
        "**Returns:** `valid=true` if ready, or list of errors detailing what's missing."
    ),
    responses={
        200: {
            "description": "Validation result with any errors",
            "content": {"application/json": {"examples": {
                "valid": {"value": {"valid": True, "errors": []}},
                "invalid": {"value": {
                    "valid": False,
                    "errors": [{"code": "MISSING_RESULT", "field": "result", "message": "Run calculation first"}]
                }}
            }}}
        },
        422: ERROR_RESPONSES[422],
    }
)
async def validate_optimizer_config(
    config: OptimizerConfigValidation
) -> ValidationResponse:
    """
    Validates optimizer configuration for completeness.
    
    Returns all validation errors, not just the first one.
    """
    errors: List[ValidationError] = []
    
    # Check params
    if not config.params:
        errors.append(ValidationError(
            code="MISSING_PARAMS",
            field="params",
            message="Optimizer parameters required - configure in Step 2"
        ))
    
    # Check result
    if not config.result:
        errors.append(ValidationError(
            code="MISSING_RESULT",
            field="result",
            message="Optimizer result required - run cost calculation in Step 2"
        ))
    else:
        # Check cheapestPath in result (camelCase as returned by optimizer)
        # Also accept calculationResult as it contains the same info in dict format
        has_path = config.result.get("cheapestPath") or config.result.get("calculationResult")
        if not has_path:
            errors.append(ValidationError(
                code="MISSING_CHEAPEST_PATH",
                field="cheapest_path",
                message="cheapestPath or calculationResult missing in result - calculation may have failed"
            ))
    
    return ValidationResponse(
        valid=len(errors) == 0,
        errors=errors
    )
