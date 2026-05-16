"""Domain exceptions for Management API services."""


class DomainError(Exception):
    """Base class for service-layer domain errors."""

    status_code = 500

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class TwinNotFound(DomainError):
    status_code = 404


class TwinNameConflict(DomainError):
    status_code = 409


class InvalidTwinStateTransition(DomainError):
    status_code = 400


class OperationAlreadyInProgress(DomainError):
    status_code = 409


class ConfigurationValidationFailed(DomainError):
    status_code = 400

    def __init__(self, message: str, errors: list[dict]):
        super().__init__(message)
        self.errors = errors


class CredentialResolutionFailed(DomainError):
    status_code = 400

    def __init__(self, message: str, errors: list[dict]):
        super().__init__(message)
        self.errors = errors


class DeploymentPackageBuildFailed(DomainError):
    status_code = 400

    def __init__(self, message: str, errors: list[dict]):
        super().__init__(message)
        self.errors = errors


class ExternalServiceUnavailable(DomainError):
    status_code = 503


class ExternalServiceError(DomainError):
    status_code = 502
