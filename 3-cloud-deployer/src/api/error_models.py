"""OpenAPI models for the FastAPI error envelope used by the Deployer."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class HttpErrorEnvelope(BaseModel):
    """Actual FastAPI error shape returned by HTTPException handlers."""

    detail: str | dict[str, Any] | list[Any] = Field(
        ...,
        description=(
            "Human-readable error text or a structured operation-specific error. "
            "Clients must preserve structured detail objects when present."
        ),
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "detail": "The requested operation could not be completed.",
            }
        }
    )


def _response(description: str, detail: str | dict[str, Any]) -> dict[str, Any]:
    return {
        "description": description,
        "model": HttpErrorEnvelope,
        "content": {
            "application/json": {
                "example": {"detail": detail},
            }
        },
    }


ERROR_RESPONSES = {
    400: _response(
        "Bad Request - The request is invalid for this operation",
        "Invalid request. Correct the supplied parameters or artifact and retry.",
    ),
    401: _response(
        "Unauthorized - Authentication credentials are missing or invalid",
        "Cloud provider credentials are invalid or expired.",
    ),
    403: _response(
        "Forbidden - The requested operation or resource is protected",
        "The requested operation is not permitted in this runtime.",
    ),
    404: _response(
        "Not Found - The requested resource does not exist",
        "The requested project or resource was not found.",
    ),
    413: _response(
        "Payload Too Large - The uploaded artifact exceeds the endpoint limit",
        "The uploaded artifact exceeds the configured size limit.",
    ),
    422: _response(
        "Validation Error - The request body failed schema validation",
        "The request body failed validation.",
    ),
    500: _response(
        "Internal Server Error - An unexpected error occurred",
        "Internal server error. Check logs.",
    ),
    502: _response(
        "Bad Gateway - A cloud provider rejected or failed the operation",
        "The cloud provider operation failed.",
    ),
}
