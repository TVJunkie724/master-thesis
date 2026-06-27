"""Mapping helpers from typed client errors to route-facing service errors."""

from src.services.errors import ExternalServiceError, ExternalServiceUnavailable
from src.services.service_errors import DownstreamServiceError


def map_optimizer_client_error(exc: ExternalServiceError | ExternalServiceUnavailable) -> DownstreamServiceError:
    """Convert Optimizer client exceptions to the existing Management API contract."""
    if isinstance(exc, ExternalServiceUnavailable):
        if "timed out" in exc.message.lower():
            return DownstreamServiceError(504, "Optimizer service timed out")
        return DownstreamServiceError(503, "Cannot connect to Optimizer service")
    return DownstreamServiceError(
        exc.upstream_status_code or 502,
        exc.public_detail,
    )
