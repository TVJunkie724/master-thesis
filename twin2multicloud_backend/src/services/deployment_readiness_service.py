"""Twin-scoped cached deployment readiness and explicit provider preflight."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
import json
import logging
from typing import Any, cast

from sqlalchemy.orm import Session

from src.models.cloud_connection import CloudConnection
from src.repositories.deployment_preflight_repository import DeploymentPreflightRepository
from src.repositories.twin_repository import TwinRepository
from src.schemas.deployment_readiness import (
    CloudProvider,
    DeploymentPreflightResponse,
    DeploymentReadinessCheck,
    DeploymentReadinessResponse,
    ProviderDeploymentReadiness,
    ProviderReadinessStatus,
)
from src.services.cloud_connection_service import CloudConnectionService
from src.services.cloud_credential_validation_service import (
    build_preflight_result,
    perform_dual_validation,
    redact_validation_result,
)
from src.services.credential_resolution_service import CredentialResolutionService
from src.services.permission_sets import compare_permission_set_version
from src.services.secret_redaction import redact_secret_like_text
from src.services.service_errors import EntityNotFoundError, ValidationError


logger = logging.getLogger(__name__)


PreflightValidator = Callable[
    [str, dict[str, Any], dict[str, Any]],
    Awaitable[dict[str, Any]],
]


@dataclass(frozen=True, repr=False)
class _ProviderCandidate:
    provider: CloudProvider
    connection_id: str
    connection_display_name: str
    payload_fingerprint: str
    supplied_permission_set_version: str | None
    expected_permission_set_version: str
    optimizer_credentials: dict[str, Any]
    deployer_credentials: dict[str, Any]


class DeploymentReadinessService:
    """Owns provider requirements, cache validity, and explicit preflight runs."""

    def __init__(
        self,
        db: Session,
        *,
        validator: PreflightValidator | None = None,
        clock: Callable[[], datetime] = datetime.utcnow,
        max_age: timedelta = timedelta(hours=24),
    ) -> None:
        self._db = db
        self._twin_repository = TwinRepository(db)
        self._connection_service = CloudConnectionService(db)
        self._cache_repository = DeploymentPreflightRepository(db)
        self._validator = validator or perform_dual_validation
        self._clock = clock
        if max_age <= timedelta(0):
            raise ValueError("max_age must be greater than zero")
        self._max_age = max_age

    def get_cached(self, twin_id: str, user_id: str) -> DeploymentReadinessResponse:
        """Build readiness exclusively from persisted metadata; never call a provider."""
        twin = self._require_twin(twin_id, user_id)
        required, issues = self._requirements(twin)
        providers = [
            self._cached_provider(twin, user_id, provider)
            for provider in required
        ]
        return DeploymentReadinessResponse(
            twin_id=twin.id,
            ready=self._aggregate_ready(required, providers, issues),
            summary=self._aggregate_summary(required, providers, issues),
            required_providers=required,
            providers=providers,
            checked_at=self._aggregate_checked_at(providers),
            issues=issues,
        )

    def require_ready(self, twin_id: str, user_id: str) -> DeploymentReadinessResponse:
        """Reject deployment unless the current provider bindings passed preflight."""
        readiness = self.get_cached(twin_id, user_id)
        if readiness.ready:
            return readiness

        failure_codes = [check.code for check in readiness.issues]
        failure_codes.extend(
            check.code
            for provider in readiness.providers
            for check in provider.checks
            if check.status == "failed"
        )
        raise ValidationError(
            "Deployment preflight is required before infrastructure deployment.",
            detail={
                "code": "DEPLOYMENT_PREFLIGHT_REQUIRED",
                "failure_codes": sorted(set(failure_codes)),
            },
        )

    async def run_preflight(
        self,
        twin_id: str,
        user_id: str,
    ) -> DeploymentPreflightResponse:
        """Validate every required provider and atomically replace safe cache entries."""
        twin = self._require_twin(twin_id, user_id)
        required, issues = self._requirements(twin)
        blocked: dict[str, ProviderDeploymentReadiness] = {}
        candidates: list[_ProviderCandidate] = []

        for provider in required:
            connection, failure = self._resolve_bound_connection(
                twin,
                user_id,
                provider,
            )
            if failure is not None:
                blocked[provider] = failure
                self._cache_repository.delete(twin.id, provider)
                continue
            if connection is None:
                blocked[provider] = self._provider_failure(
                    provider,
                    code="CLOUD_CONNECTION_UNAVAILABLE",
                    message="The bound deployment Cloud Connection is unavailable.",
                    action="Review the provider binding and run preflight again.",
                )
                self._cache_repository.delete(twin.id, provider)
                continue
            try:
                comparison = compare_permission_set_version(
                    provider,
                    connection.permission_set_version,
                )
                candidates.append(
                    _ProviderCandidate(
                        provider=provider,
                        connection_id=connection.id,
                        connection_display_name=connection.display_name,
                        payload_fingerprint=connection.payload_fingerprint,
                        supplied_permission_set_version=connection.permission_set_version,
                        expected_permission_set_version=comparison.expected_version,
                        optimizer_credentials=self._connection_service.build_optimizer_credentials(
                            connection,
                            user_id,
                        ),
                        deployer_credentials=self._connection_service.build_deployer_credentials(
                            connection,
                            user_id,
                        ),
                    )
                )
            except (TypeError, ValueError):
                blocked[provider] = self._provider_failure(
                    provider,
                    code="CREDENTIAL_PAYLOAD_INVALID",
                    message="The bound deployment credential cannot be resolved.",
                    action="Rotate or re-import the Cloud Connection, then run preflight again.",
                    connection=connection,
                )
                self._cache_repository.delete(twin.id, provider)

        raw_results = await asyncio.gather(
            *(self._validate_candidate(candidate) for candidate in candidates),
        )

        self._db.expire_all()
        current_twin = self._require_twin(twin_id, user_id)
        checked_at = self._clock()
        refreshed: dict[str, ProviderDeploymentReadiness] = {}
        for candidate, raw_result in zip(candidates, raw_results, strict=True):
            current_connection, failure = self._resolve_bound_connection(
                current_twin,
                user_id,
                candidate.provider,
            )
            if failure is not None or not self._candidate_is_current(
                candidate,
                current_connection,
            ):
                refreshed[candidate.provider] = self._provider_failure(
                    candidate.provider,
                    code="CONNECTION_CHANGED_DURING_PREFLIGHT",
                    message="The provider binding changed while preflight was running.",
                    action="Review the current Cloud Connection and run preflight again.",
                    connection=current_connection,
                    status="stale",
                )
                self._cache_repository.delete(twin_id, candidate.provider)
                continue

            provider_result = self._provider_from_validation(
                candidate,
                raw_result,
                checked_at,
            )
            refreshed[candidate.provider] = provider_result
            self._cache_repository.upsert(
                twin_id=twin_id,
                provider=candidate.provider,
                cloud_connection_id=candidate.connection_id,
                connection_payload_fingerprint=candidate.payload_fingerprint,
                supplied_permission_set_version=candidate.supplied_permission_set_version,
                expected_permission_set_version=candidate.expected_permission_set_version,
                ready=provider_result.ready,
                summary=provider_result.summary,
                checks_json=json.dumps(
                    [check.model_dump(mode="json") for check in provider_result.checks],
                    sort_keys=True,
                    separators=(",", ":"),
                ),
                checked_at=checked_at,
            )

        self._cache_repository.delete_unrequired(twin_id, set(required))
        self._db.commit()
        providers = [
            blocked.get(provider)
            or refreshed.get(provider)
            or self._provider_failure(
                provider,
                code="PREFLIGHT_RESULT_MISSING",
                message="Provider preflight did not produce a result.",
                action="Run deployment preflight again.",
            )
            for provider in required
        ]
        return DeploymentPreflightResponse(
            twin_id=twin_id,
            ready=self._aggregate_ready(required, providers, issues),
            summary=self._aggregate_summary(required, providers, issues),
            required_providers=required,
            providers=providers,
            checked_at=self._aggregate_checked_at(providers),
            issues=issues,
        )

    async def _validate_candidate(
        self,
        candidate: _ProviderCandidate,
    ) -> dict[str, Any]:
        try:
            result = await self._validator(
                candidate.provider,
                candidate.optimizer_credentials,
                candidate.deployer_credentials,
            )
        except Exception as exc:
            logger.warning(
                "Deployment preflight validator failed for provider %s: %s",
                candidate.provider,
                type(exc).__name__,
            )
            result = {
                "provider": candidate.provider,
                "valid": False,
                "optimizer": {
                    "valid": False,
                    "message": "Provider validation failed unexpectedly.",
                },
                "deployer": {
                    "valid": False,
                    "message": "Provider validation failed unexpectedly.",
                },
            }
        return redact_validation_result(
            result,
            candidate.optimizer_credentials,
            candidate.deployer_credentials,
        )

    def _cached_provider(
        self,
        twin,
        user_id: str,
        provider: CloudProvider,
    ) -> ProviderDeploymentReadiness:
        connection, failure = self._resolve_bound_connection(twin, user_id, provider)
        if failure is not None:
            return failure
        if connection is None:
            return self._provider_failure(
                provider,
                code="CLOUD_CONNECTION_UNAVAILABLE",
                message="The bound deployment Cloud Connection is unavailable.",
                action="Review the provider binding and run preflight again.",
            )
        comparison = compare_permission_set_version(
            provider,
            connection.permission_set_version,
        )
        cache = self._cache_repository.get(twin.id, provider)
        if cache is None:
            return self._provider_failure(
                provider,
                code="PREFLIGHT_NOT_RUN",
                message="Deployment preflight has not been run for this provider binding.",
                action="Run deployment preflight before deploying this twin.",
                connection=connection,
                status="not_checked",
            )
        if not self._cache_is_current(cache, connection, comparison.expected_version):
            return self._provider_failure(
                provider,
                code="PREFLIGHT_CACHE_STALE",
                message="Cached preflight no longer matches the current provider binding.",
                action="Run deployment preflight again.",
                connection=connection,
                status="stale",
                checked_at=cache.checked_at,
            )
        checks = self._parse_cached_checks(cache.checks_json)
        if checks is None:
            return self._provider_failure(
                provider,
                code="PREFLIGHT_CACHE_INVALID",
                message="Cached preflight evidence is invalid.",
                action="Run deployment preflight again.",
                connection=connection,
                status="stale",
                checked_at=cache.checked_at,
            )
        ready = bool(cache.ready) and comparison.matches
        return ProviderDeploymentReadiness(
            provider=provider,
            connection_id=connection.id,
            connection_display_name=connection.display_name,
            ready=ready,
            status="ready" if ready else "review_required",
            summary=self._safe_text(
                cache.summary,
                fallback="Cached provider preflight is unavailable.",
                max_length=2_000,
            ),
            expected_permission_set_version=comparison.expected_version,
            supplied_permission_set_version=comparison.supplied_version,
            permission_set_status=comparison.status,
            checked_at=cache.checked_at,
            checks=checks,
        )

    def _provider_from_validation(
        self,
        candidate: _ProviderCandidate,
        validation_result: dict[str, Any],
        checked_at: datetime,
    ) -> ProviderDeploymentReadiness:
        comparison = compare_permission_set_version(
            candidate.provider,
            candidate.supplied_permission_set_version,
        )
        raw = build_preflight_result(
            candidate.provider,
            validation_result,
            version_comparison=comparison,
        )
        checks = [self._safe_check(check) for check in raw.get("checks", [])[:32]]
        ready = bool(raw.get("ready")) and comparison.matches
        summary = redact_secret_like_text(
            str(raw.get("summary") or "Provider preflight failed"),
        )[:2_000]
        return ProviderDeploymentReadiness(
            provider=candidate.provider,
            connection_id=candidate.connection_id,
            connection_display_name=candidate.connection_display_name,
            ready=ready,
            status="ready" if ready else "review_required",
            summary=summary,
            expected_permission_set_version=comparison.expected_version,
            supplied_permission_set_version=comparison.supplied_version,
            permission_set_status=comparison.status,
            checked_at=checked_at,
            checks=checks,
        )

    def _resolve_bound_connection(
        self,
        twin,
        user_id: str,
        provider: CloudProvider,
    ) -> tuple[CloudConnection | None, ProviderDeploymentReadiness | None]:
        config = getattr(twin, "configuration", None)
        connection_id = (
            getattr(config, f"{provider}_cloud_connection_id", None)
            if config is not None
            else None
        )
        if not connection_id:
            return None, self._provider_failure(
                provider,
                code="CLOUD_CONNECTION_MISSING",
                message="No deployment Cloud Connection is bound for this provider.",
                action="Open Cloud Accounts, add deployment access, and bind it to the twin.",
            )
        connection = self._connection_service.get_connection(connection_id, user_id)
        if connection is None:
            return None, self._provider_failure(
                provider,
                code="CLOUD_CONNECTION_UNAVAILABLE",
                message="The bound deployment Cloud Connection is unavailable.",
                action="Select a user-owned deployment Cloud Connection and retry.",
            )
        if connection.provider != provider:
            return connection, self._provider_failure(
                provider,
                code="CLOUD_CONNECTION_PROVIDER_MISMATCH",
                message="The bound Cloud Connection belongs to a different provider.",
                action="Bind a matching deployment Cloud Connection.",
                connection=connection,
            )
        if connection.purpose != "deployment":
            return connection, self._provider_failure(
                provider,
                code="CLOUD_CONNECTION_PURPOSE_INVALID",
                message="Pricing access cannot be used for infrastructure deployment.",
                action="Bind a deployment-purpose Cloud Connection.",
                connection=connection,
            )
        return connection, None

    @staticmethod
    def _candidate_is_current(
        candidate: _ProviderCandidate,
        connection: CloudConnection | None,
    ) -> bool:
        return bool(
            connection
            and connection.id == candidate.connection_id
            and connection.payload_fingerprint == candidate.payload_fingerprint
            and connection.permission_set_version
            == candidate.supplied_permission_set_version
        )

    def _cache_is_current(self, cache, connection, expected_version: str) -> bool:
        cache_age = self._clock() - cache.checked_at
        return bool(
            cache.cloud_connection_id == connection.id
            and cache.connection_payload_fingerprint
            == connection.payload_fingerprint
            and cache.supplied_permission_set_version
            == connection.permission_set_version
            and cache.expected_permission_set_version == expected_version
            and timedelta(0) <= cache_age <= self._max_age
        )

    @staticmethod
    def _parse_cached_checks(raw: str) -> list[DeploymentReadinessCheck] | None:
        try:
            values = json.loads(raw)
            if not isinstance(values, list) or len(values) > 32:
                return None
            return [DeploymentReadinessCheck.model_validate(value) for value in values]
        except (TypeError, ValueError, json.JSONDecodeError):
            return None

    @staticmethod
    def _safe_check(raw: Any) -> DeploymentReadinessCheck:
        value = raw if isinstance(raw, dict) else {}
        permissions = value.get("permissions")
        safe_permissions = []
        if isinstance(permissions, list):
            safe_permissions = [
                DeploymentReadinessService._safe_text(
                    permission,
                    fallback="[invalid permission]",
                    max_length=300,
                )
                for permission in permissions[:250]
                if str(permission).strip()
            ]
        return DeploymentReadinessCheck(
            component=DeploymentReadinessService._safe_text(
                value.get("component"),
                fallback="provider",
                max_length=80,
            ),
            status="passed" if value.get("status") == "passed" else "failed",
            code=DeploymentReadinessService._safe_text(
                value.get("code"),
                fallback="VALIDATION_FAILED",
                max_length=120,
            ),
            message=DeploymentReadinessService._safe_text(
                value.get("message"),
                fallback="Provider validation failed.",
                max_length=2_000,
            ),
            action=DeploymentReadinessService._safe_text(
                value.get("action"),
                fallback="Review provider access and retry.",
                max_length=2_000,
            ),
            permissions=safe_permissions,
        )

    @staticmethod
    def _safe_text(value: Any, *, fallback: str, max_length: int) -> str:
        normalized = redact_secret_like_text(str(value or "")).strip()
        return (normalized or fallback)[:max_length]

    @staticmethod
    def _provider_failure(
        provider: CloudProvider,
        *,
        code: str,
        message: str,
        action: str,
        connection: CloudConnection | None = None,
        status: ProviderReadinessStatus = "review_required",
        checked_at: datetime | None = None,
    ) -> ProviderDeploymentReadiness:
        comparison = compare_permission_set_version(
            provider,
            getattr(connection, "permission_set_version", None),
        )
        check = DeploymentReadinessCheck(
            component="configuration",
            status="failed",
            code=code,
            message=redact_secret_like_text(message),
            action=redact_secret_like_text(action),
        )
        return ProviderDeploymentReadiness(
            provider=provider,
            connection_id=getattr(connection, "id", None),
            connection_display_name=getattr(connection, "display_name", None),
            ready=False,
            status=status,
            summary=check.message,
            expected_permission_set_version=comparison.expected_version,
            supplied_permission_set_version=comparison.supplied_version,
            permission_set_status=comparison.status,
            checked_at=checked_at,
            checks=[check],
        )

    def _requirements(self, twin) -> tuple[list[CloudProvider], list[DeploymentReadinessCheck]]:
        raw = CredentialResolutionService.required_providers_from_optimizer(
            getattr(twin, "optimizer_config", None),
        )
        required = [
            cast(CloudProvider, provider)
            for provider in sorted(raw)
            if provider in {"aws", "azure", "gcp"}
        ]
        if required:
            return required, []
        return [], [
            DeploymentReadinessCheck(
                component="architecture",
                status="failed",
                code="DEPLOYMENT_ARCHITECTURE_MISSING",
                message="No optimized provider architecture is stored for this twin.",
                action="Complete cost optimization and save the selected provider path.",
            )
        ]

    def _require_twin(self, twin_id: str, user_id: str):
        twin = self._twin_repository.get_with_configs_for_user(twin_id, user_id)
        if twin is None:
            raise EntityNotFoundError("Twin not found")
        return twin

    @staticmethod
    def _aggregate_ready(
        required: list[CloudProvider],
        providers: list[ProviderDeploymentReadiness],
        issues: list[DeploymentReadinessCheck],
    ) -> bool:
        return bool(required) and not issues and len(providers) == len(required) and all(
            provider.ready for provider in providers
        )

    @staticmethod
    def _aggregate_summary(
        required: list[CloudProvider],
        providers: list[ProviderDeploymentReadiness],
        issues: list[DeploymentReadinessCheck],
    ) -> str:
        if issues or not required:
            return "Deployment architecture must be completed before preflight."
        blocked = sum(not provider.ready for provider in providers)
        if blocked == 0:
            return "All required providers are ready for deployment."
        return f"{blocked} of {len(required)} required providers need review."

    @staticmethod
    def _aggregate_checked_at(
        providers: list[ProviderDeploymentReadiness],
    ) -> datetime | None:
        timestamps = [provider.checked_at for provider in providers if provider.checked_at]
        return min(timestamps) if timestamps else None
