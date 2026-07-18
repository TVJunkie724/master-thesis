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

    def __init__(
        self,
        message: str,
        *,
        upstream_status_code: int | None = None,
        public_detail: str | None = None,
    ):
        super().__init__(message)
        self.upstream_status_code = upstream_status_code
        self.public_detail = public_detail or message


class OptimizerContractError(DomainError):
    status_code = 502

    def __init__(self, message: str, errors: list[dict] | None = None):
        super().__init__(message)
        self.errors = errors or []


class PricingCatalogUnavailable(DomainError):
    status_code = 409

    def __init__(
        self,
        message: str,
        *,
        error_code: str = "PRICING_CATALOG_UNAVAILABLE",
    ):
        super().__init__(message)
        self.error_code = error_code


class ProviderCapabilityContractInvalid(DomainError):
    status_code = 502


class CostCalculationRunSelectionError(DomainError):
    status_code = 409

    def __init__(
        self,
        message: str,
        *,
        error_code: str = "COST_CALCULATION_RUN_SELECTION_CONFLICT",
    ):
        super().__init__(message)
        self.error_code = error_code


class PricingRefreshRequestError(DomainError):
    status_code = 400


class PricingRefreshRunNotFound(DomainError):
    status_code = 404


class PricingRefreshConnectionNotFound(DomainError):
    status_code = 404


class CloudConnectionConflict(DomainError):
    status_code = 409


class PricingReviewReportNotFound(DomainError):
    status_code = 404


class PricingReviewRequestError(DomainError):
    status_code = 400
