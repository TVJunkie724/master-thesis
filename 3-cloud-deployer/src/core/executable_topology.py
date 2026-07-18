"""Executable topology policy for staged Deployer projects."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


ERROR_HANDLING_FIELD = "integrateErrorHandling"
UNSUPPORTED_ERROR_HANDLING_TOPOLOGY = "UNSUPPORTED_ERROR_HANDLING_TOPOLOGY"
UNSUPPORTED_ERROR_HANDLING_MESSAGE = (
    "The executable five-layer baseline does not deploy the requested "
    "error-handling topology"
)


class UnsupportedErrorHandlingTopologyError(ValueError):
    """Raised before a staged project can reach provider or Terraform code."""

    code = UNSUPPORTED_ERROR_HANDLING_TOPOLOGY
    field = ERROR_HANDLING_FIELD
    message = UNSUPPORTED_ERROR_HANDLING_MESSAGE

    def __init__(self) -> None:
        super().__init__(
            f"{UNSUPPORTED_ERROR_HANDLING_TOPOLOGY}: "
            f"{self.message}"
        )

    def as_detail(self) -> dict[str, str]:
        """Return the stable API-safe error detail."""
        return {
            "error_code": self.code,
            "field": self.field,
            "message": self.message,
        }


def optimization_input_params(data: Mapping[str, Any]) -> Mapping[str, Any]:
    """Resolve the canonical result envelope or the transitional flat format."""
    result = data.get("result")
    if isinstance(result, Mapping):
        nested = result.get("inputParamsUsed")
        if isinstance(nested, Mapping) and nested:
            return nested
    return data


def ensure_executable_optimization_topology(data: object) -> None:
    """Reject undeployable optimization flags without rewriting the request."""
    if not isinstance(data, Mapping):
        return
    if optimization_input_params(data).get(ERROR_HANDLING_FIELD) is True:
        raise UnsupportedErrorHandlingTopologyError()
