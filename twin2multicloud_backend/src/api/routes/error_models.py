"""
API Error Models - Standardized response schemas for comprehensive error handling.

These models provide structured, machine-readable error responses with detailed
descriptions, strict typing, and actionable fix suggestions.
"""
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict


class FieldError(BaseModel):
    """
    Describes a validation error for a specific request field.
    
    Use this to understand exactly which field failed validation
    and what values would be acceptable.
    """
    field: str = Field(
        ...,
        description="The name of the field that failed validation (dot notation for nested fields)",
        json_schema_extra={"example": "numberOfDevices"}
    )
    message: str = Field(
        ...,
        description="Human-readable explanation of why this field failed validation",
        json_schema_extra={"example": "Value must be a positive integer"}
    )
    received_value: Optional[str] = Field(
        None,
        description="The actual value that was received (stringified for display)",
        json_schema_extra={"example": "-5"}
    )
    allowed_values: Optional[List[str]] = Field(
        None,
        description="If applicable, the list of valid values for this field",
        json_schema_extra={"example": ["aws", "azure", "gcp"]}
    )

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "field": "provider",
            "message": "Invalid cloud provider specified",
            "received_value": "alibaba",
            "allowed_values": ["aws", "azure", "gcp"]
        }
    })


class ErrorResponse(BaseModel):
    """
    Standardized error response with detailed information for troubleshooting.
    
    This schema provides structured error information that enables:
    1. Understanding what went wrong (error_code, message)
    2. Knowing exactly how to fix it (fix_suggestion)
    3. Identifying specific field issues (field_errors)
    4. Finding additional help (documentation_url)
    
    All error responses from this API follow this schema for consistency.
    """
    error_code: str = Field(
        ...,
        description=(
            "Machine-readable error code in SCREAMING_SNAKE_CASE format. "
            "Use this to programmatically identify error types. "
            "Common codes: VALIDATION_ERROR, INVALID_CREDENTIALS, RESOURCE_NOT_FOUND, "
            "RATE_LIMITED, INTERNAL_ERROR, CONFIGURATION_MISSING"
        ),
        json_schema_extra={"example": "VALIDATION_ERROR"}
    )
    message: str = Field(
        ...,
        description="Human-readable description of what went wrong",
        json_schema_extra={"example": "Request validation failed: numberOfDevices must be positive"}
    )
    fix_suggestion: str = Field(
        ...,
        description=(
            "Actionable instruction that explains exactly how to fix this error "
            "and retry the request successfully. Be specific about what to change."
        ),
        json_schema_extra={
            "example": "Set 'numberOfDevices' to a positive integer (e.g., 100). This field represents the number of IoT devices in your deployment."
        }
    )
    http_status: int = Field(
        ...,
        description="The HTTP status code associated with this error (400, 401, 403, 404, 422, 500, etc.)",
        json_schema_extra={"example": 400}
    )
    field_errors: Optional[List[FieldError]] = Field(
        None,
        description="For validation errors (422), detailed list of which fields failed and why"
    )
    documentation_url: Optional[str] = Field(
        None,
        description="URL to relevant documentation for this error or endpoint",
        json_schema_extra={"example": "/documentation/docs-overview.html"}
    )

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "error_code": "VALIDATION_ERROR",
            "message": "Request validation failed",
            "fix_suggestion": "Ensure all required fields are present and have valid values. See field_errors for details.",
            "http_status": 422,
            "field_errors": [
                {
                    "field": "numberOfDevices",
                    "message": "Value must be a positive integer",
                    "received_value": "-5",
                    "allowed_values": None
                }
            ],
            "documentation_url": "/documentation/docs-formulas.html"
        }
    })


# Common error response definitions for OpenAPI documentation
ERROR_RESPONSES = {
    400: {
        "description": "Bad Request - The request was malformed or missing required parameters",
        "model": ErrorResponse,
        "content": {
            "application/json": {
                "example": {
                    "error_code": "BAD_REQUEST",
                    "message": "Missing required parameter: provider",
                    "fix_suggestion": "Include 'provider' parameter with value 'aws', 'azure', or 'gcp'",
                    "http_status": 400
                }
            }
        }
    },
    401: {
        "description": "Unauthorized - Authentication credentials are missing or invalid",
        "model": ErrorResponse,
        "content": {
            "application/json": {
                "example": {
                    "error_code": "INVALID_CREDENTIALS",
                    "message": "Cloud provider credentials are invalid or expired",
                    "fix_suggestion": "Verify your credentials in config_credentials.json or provide valid credentials in the request body",
                    "http_status": 401
                }
            }
        }
    },
    404: {
        "description": "Not Found - The requested resource does not exist",
        "model": ErrorResponse,
        "content": {
            "application/json": {
                "example": {
                    "error_code": "RESOURCE_NOT_FOUND",
                    "message": "Project 'my-project' not found",
                    "fix_suggestion": "Use GET /projects to list available projects, then use an existing project name",
                    "http_status": 404
                }
            }
        }
    },
    422: {
        "description": "Validation Error - Request body failed schema validation",
        "model": ErrorResponse,
        "content": {
            "application/json": {
                "example": {
                    "error_code": "VALIDATION_ERROR",
                    "message": "Request validation failed",
                    "fix_suggestion": "Check field_errors for specific issues and correct the values",
                    "http_status": 422,
                    "field_errors": [
                        {"field": "numberOfDevices", "message": "Must be positive", "received_value": "0"}
                    ]
                }
            }
        }
    },
    500: {
        "description": "Internal Server Error - An unexpected error occurred",
        "model": ErrorResponse,
        "content": {
            "application/json": {
                "example": {
                    "error_code": "INTERNAL_ERROR",
                    "message": "An unexpected error occurred while processing your request",
                    "fix_suggestion": "Retry the request. If the error persists, check server logs or contact support.",
                    "http_status": 500
                }
            }
        }
    }
}
