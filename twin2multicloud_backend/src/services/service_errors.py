"""Typed service-layer exceptions for Management API use cases."""


class ServiceError(Exception):
    """Base class for service-layer failures."""


class EntityNotFoundError(ServiceError):
    """Raised when a user-owned entity cannot be found."""


class ValidationError(ServiceError):
    """Raised when an application-level validation rule fails."""


class ConflictError(ServiceError):
    """Raised when a request conflicts with existing application state."""


class DownstreamServiceError(ServiceError):
    """Raised when a downstream service call fails safely."""

    def __init__(self, status_code: int, public_detail: str):
        super().__init__(public_detail)
        self.status_code = status_code
        self.public_detail = public_detail
