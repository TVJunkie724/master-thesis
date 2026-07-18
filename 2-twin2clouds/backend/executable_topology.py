"""Executable topology policy for the five-layer baseline."""

from __future__ import annotations


ERROR_HANDLING_FIELD = "integrateErrorHandling"
UNSUPPORTED_ERROR_HANDLING_TOPOLOGY = "UNSUPPORTED_ERROR_HANDLING_TOPOLOGY"
UNSUPPORTED_ERROR_HANDLING_MESSAGE = (
    "The executable five-layer baseline does not deploy the requested "
    "error-handling topology"
)


class UnsupportedErrorHandlingTopologyError(ValueError):
    """Raised when a calculation requests a topology the Deployer cannot create."""

    code = UNSUPPORTED_ERROR_HANDLING_TOPOLOGY
    field = ERROR_HANDLING_FIELD

    def __init__(self) -> None:
        super().__init__(UNSUPPORTED_ERROR_HANDLING_MESSAGE)


def ensure_executable_error_handling_topology(value: object) -> None:
    """Reject the legacy flag when it requests undeployable resources."""
    if value is True:
        raise UnsupportedErrorHandlingTopologyError()
