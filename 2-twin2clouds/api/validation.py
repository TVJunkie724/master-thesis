"""
Validation API endpoints for Optimizer.

Provides configuration validation for the optimizer config (params + result).
"""
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional, Any


router = APIRouter(tags=["Validation"])


# --------------------------------------------------
# Models
# --------------------------------------------------

class OptimizerConfigValidation(BaseModel):
    """Input model for optimizer config validation."""
    params: Optional[dict[str, Any]] = None
    result: Optional[dict[str, Any]] = None


class ValidationError(BaseModel):
    """Structured validation error."""
    code: str
    field: str
    message: str


class ValidationResponse(BaseModel):
    """Validation response with all errors."""
    valid: bool
    errors: list[ValidationError] = []


# --------------------------------------------------
# Endpoints
# --------------------------------------------------

@router.post(
    "/validate/optimizer-config",
    response_model=ValidationResponse,
    summary="Validate optimizer configuration completeness",
    description="""
Validates that the optimizer configuration is complete and ready for state transition.

**Checks performed:**
- `params`: Optimizer parameters must be present
- `result`: Optimization result must be present
- `result.cheapest_path`: The cheapest path must be calculated

**Example request:**
```json
{
    "params": {"numberOfDevices": 10, "useEventChecking": true, ...},
    "result": {"cheapest_path": {"L1": "aws", "L2": "azure", ...}, ...}
}
```
"""
)
async def validate_optimizer_config(
    config: OptimizerConfigValidation
) -> ValidationResponse:
    """
    Validates optimizer configuration for completeness.
    
    Returns all validation errors, not just the first one.
    """
    errors: list[ValidationError] = []
    
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
        # Check cheapest_path in result
        if not config.result.get("cheapest_path"):
            errors.append(ValidationError(
                code="MISSING_CHEAPEST_PATH",
                field="cheapest_path",
                message="cheapest_path missing in result - calculation may have failed"
            ))
    
    return ValidationResponse(
        valid=len(errors) == 0,
        errors=errors
    )
