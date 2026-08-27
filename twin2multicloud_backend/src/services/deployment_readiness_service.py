"""Twin-scoped cached deployment readiness and explicit provider preflight."""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, cast

from sqlalchemy.orm import Session

from src.clients.deployer_client import DeployerClient
from src.models.cloud_connection import CloudConnection
from src.repositories.deployment_preflight_repository import (
    DeploymentPreflightRepository,
)
from src.repositories.twin_repository import TwinRepository
from src.schemas.deployment_readiness import (
    CloudProvider,
    DeploymentPreflightResponse,
    DeploymentReadinessCheck,
    DeploymentReadinessResponse,
    DeploymentRequirementReadiness,
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
from src.services.secret_redaction import redact_secret_like_text
from src.services.service_errors import EntityNotFoundError, ValidationError

logger = logging.getLogger(__name__)


PreflightValidator = Callable[
    [str, dict[str, Any], dict[str, Any]],
    Awaitable[dict[str, Any]],
]
GraphRequirementsResolver = Callable[[Any, str], Awaitable[dict[str, Any]]]


@dataclass(frozen=True, repr=False)
class _ProviderCandidate:
    provider: CloudProvider
    connection_id: str
    connection_display_name: str
    payload_fingerprint: str
    optimizer_credentials: dict[str, Any]
    deployer_credentials: dict[str, Any]


class DeploymentReadinessService:
    """Owns provider requirements, cache validity, and explicit preflight runs."""

    def __init__(
        self,
        db: Session,
        *,
        validator: PreflightValidator | None = None,
        requirements_resolver: GraphRequirementsResolver | None = None,
        clock: Callable[[], datetime] = datetime.utcnow,
        max_age: timedelta = timedelta(hours=24),
    ) -> None:
        self._db = db
        self._twin_repository = TwinRepository(db)
        self._connection_service = CloudConnectionService(db)
        self._cache_repository = DeploymentPreflightRepository(db)
        self._validator = validator or perform_dual_validation
        self._requirements_resolver = (
            requirements_resolver or self._resolve_graph_requirements
        )
        self._clock = clock
        if max_age <= timedelta(0):
            raise ValueError("max_age must be greater than zero")
        self._max_age = max_age

    def get_cached(self, twin_id: str, user_id: str) -> DeploymentReadinessResponse:
        """Build readiness exclusively from persisted metadata; never call a provider."""
        twin = self._require_twin(twin_id, user_id)
        required, issues = self._requirements(twin)
        providers = [
            self._cached_provider(twin, user_id, provider) for provider in required
        ]
        if not self._provider_evidence_is_coherent(providers):
            providers = [
                self._provider_failure(
                    provider,
                    code="PREFLIGHT_GRAPH_EVIDENCE_INCONSISTENT",
                    message="Cached provider checks do not share one deployment graph.",
                    action="Run deployment preflight again.",
                    status="stale",
                )
                for provider in required
            ]
        return DeploymentReadinessResponse(
            twin_id=twin.id,
            ready=self._aggregate_ready(required, providers, issues),
            summary=self._aggregate_summary(required, providers, issues),
            required_providers=required,
            providers=providers,
            checked_at=self._aggregate_checked_at(providers),
            graph_digest=self._aggregate_evidence_digest(
                providers, "graph_digest"
            ),
            requirements_digest=self._aggregate_evidence_digest(
                providers, "requirements_digest"
            ),
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
                candidates.append(
                    _ProviderCandidate(
                        provider=provider,
                        connection_id=connection.id,
                        connection_display_name=connection.display_name,
                        payload_fingerprint=connection.payload_fingerprint,
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

        inspection = None
        if not issues and not blocked and len(candidates) == len(required):
            try:
                inspection = await self._requirements_resolver(twin, user_id)
                self._validate_requirement_inspection(inspection, twin, required)
            except Exception as exc:  # noqa: BLE001 - fail-closed service boundary
                logger.warning(
                    "Deployment graph inspection failed for twin %s: %s",
                    twin_id,
                    type(exc).__name__,
                )
                inspection = None
                issues.append(
                    DeploymentReadinessCheck(
                        component="architecture",
                        status="failed",
                        code="DEPLOYMENT_GRAPH_INSPECTION_FAILED",
                        message=(
                            "The exact deployment prerequisites could not be resolved."
                        ),
                        action=(
                            "Review the selected optimization result and retry preflight."
                        ),
                    )
                )

        if inspection is None:
            for provider in required:
                self._cache_repository.delete(twin.id, provider)
            self._db.commit()
            providers = [
                blocked.get(provider)
                or self._provider_failure(
                    provider,
                    code="GRAPH_REQUIREMENTS_UNAVAILABLE",
                    message="Provider checks require an exact resolved deployment graph.",
                    action="Resolve the blocking configuration and run preflight again.",
                    status="not_checked",
                )
                for provider in required
            ]
            return DeploymentPreflightResponse(
                twin_id=twin_id,
                ready=False,
                summary=self._aggregate_summary(required, providers, issues),
                required_providers=required,
                providers=providers,
                checked_at=self._aggregate_checked_at(providers),
                issues=issues,
            )

        graph_evidence = inspection["graph_evidence"]
        requirements = inspection["requirements"]
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
            ) or not self._architecture_is_current(current_twin, graph_evidence):
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
                provider_requirements=[
                    item
                    for item in requirements
                    if item.get("provider") == candidate.provider
                ],
                graph_digest=graph_evidence["graph_digest"],
                requirements_digest=graph_evidence["requirements_digest"],
            )
            refreshed[candidate.provider] = provider_result
            self._cache_repository.upsert(
                twin_id=twin_id,
                provider=candidate.provider,
                cloud_connection_id=candidate.connection_id,
                connection_payload_fingerprint=candidate.payload_fingerprint,
                architecture_digest=graph_evidence["architecture_digest"],
                graph_digest=graph_evidence["graph_digest"],
                requirements_digest=graph_evidence["requirements_digest"],
                ready=provider_result.ready,
                summary=provider_result.summary,
                checks_json=json.dumps(
                    [check.model_dump(mode="json") for check in provider_result.checks],
                    sort_keys=True,
                    separators=(",", ":"),
                ),
                requirements_json=json.dumps(
                    [
                        item.model_dump(mode="json")
                        for item in provider_result.requirements
                    ],
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
            graph_digest=self._aggregate_evidence_digest(
                providers, "graph_digest"
            ),
            requirements_digest=self._aggregate_evidence_digest(
                providers, "requirements_digest"
            ),
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
        except Exception as exc:  # noqa: BLE001 - provider adapter boundary
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

    async def _resolve_graph_requirements(
        self,
        twin,
        user_id: str,
    ) -> dict[str, Any]:
        """Build the exact package and resolve its graph without staging it."""

        from src.services.deployment_service import build_project_zip, get_resource_name

        archive = build_project_zip(twin, user_id)
        archive.seek(0)
        return await DeployerClient().inspect_deployment_requirements(
            get_resource_name(twin),
            archive.read(),
        )

    def _validate_requirement_inspection(
        self,
        inspection: object,
        twin,
        required: list[CloudProvider],
    ) -> None:
        if not isinstance(inspection, dict):
            raise TypeError("Requirement inspection must be an object")
        evidence = inspection.get("graph_evidence")
        requirements = inspection.get("requirements")
        if not isinstance(evidence, dict) or not isinstance(requirements, list):
            raise TypeError("Requirement inspection is incomplete")
        for field in (
            "architecture_digest",
            "graph_digest",
            "requirements_digest",
        ):
            value = evidence.get(field)
            if (
                not isinstance(value, str)
                or not value.startswith("sha256:")
                or len(value) != 71
            ):
                raise ValueError(f"Invalid graph evidence field: {field}")
        if evidence.get("required_providers") != list(required):
            raise ValueError("Resolved graph provider set differs from the architecture")
        if not requirements or any(
            not isinstance(item, dict)
            or item.get("provider") not in required
            or not isinstance(item.get("requirement_id"), str)
            for item in requirements
        ):
            raise ValueError("Resolved graph requirements are invalid")
        current_architecture_digest = self._current_architecture_digest(twin)
        if (
            current_architecture_digest is not None
            and evidence["architecture_digest"] != current_architecture_digest
        ):
            raise ValueError("Resolved graph does not match the selected architecture")

    @staticmethod
    def _current_architecture_digest(twin) -> str | None:
        selected = [
            run
            for run in tuple(getattr(twin, "cost_calculation_runs", None) or ())
            if getattr(run, "selected_for_deployment_at", None) is not None
        ]
        if len(selected) != 1:
            return None
        value = getattr(selected[0], "resolved_architecture_digest", None)
        return value if isinstance(value, str) and value else None

    def _architecture_is_current(self, twin, evidence: dict[str, Any]) -> bool:
        current = self._current_architecture_digest(twin)
        return current is None or current == evidence.get("architecture_digest")

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
        if not self._cache_is_current(cache, connection, twin):
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
        requirements = self._parse_cached_requirements(
            cache.requirements_json,
            provider,
        )
        if checks is None or requirements is None:
            return self._provider_failure(
                provider,
                code="PREFLIGHT_CACHE_INVALID",
                message="Cached preflight evidence is invalid.",
                action="Run deployment preflight again.",
                connection=connection,
                status="stale",
                checked_at=cache.checked_at,
            )
        ready = bool(cache.ready)
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
            checked_at=cache.checked_at,
            graph_digest=cache.graph_digest,
            requirements_digest=cache.requirements_digest,
            checks=checks,
            requirements=requirements,
        )

    def _provider_from_validation(
        self,
        candidate: _ProviderCandidate,
        validation_result: dict[str, Any],
        checked_at: datetime,
        *,
        provider_requirements: list[dict[str, Any]],
        graph_digest: str,
        requirements_digest: str,
    ) -> ProviderDeploymentReadiness:
        raw = build_preflight_result(
            candidate.provider,
            validation_result,
        )
        checks = [self._safe_check(check) for check in raw.get("checks", [])[:32]]
        requirement_results = [
            self._project_requirement_readiness(requirement, checks)
            for requirement in provider_requirements
        ]
        ready = bool(raw.get("ready")) and bool(requirement_results) and all(
            item.status == "ready" for item in requirement_results
        )
        summary = redact_secret_like_text(
            (
                "All graph-derived provider requirements are ready."
                if ready
                else str(raw.get("summary") or "Provider preflight failed")
            ),
        )[:2_000]
        return ProviderDeploymentReadiness(
            provider=candidate.provider,
            connection_id=candidate.connection_id,
            connection_display_name=candidate.connection_display_name,
            ready=ready,
            status="ready" if ready else "review_required",
            summary=summary,
            checked_at=checked_at,
            graph_digest=graph_digest,
            requirements_digest=requirements_digest,
            checks=checks,
            requirements=requirement_results,
        )

    def _project_requirement_readiness(
        self,
        requirement: dict[str, Any],
        checks: list[DeploymentReadinessCheck],
    ) -> DeploymentRequirementReadiness:
        capability = self._safe_text(
            requirement.get("capability_id"),
            fallback="unknown-capability",
            max_length=300,
        )
        requirement_type = self._safe_text(
            requirement.get("requirement_type"),
            fallback="unknown",
            max_length=80,
        )
        preparation_mode = requirement.get("preparation_mode")
        if preparation_mode not in {
            "none",
            "confirmed_account",
            "manual_external",
            "terraform",
        }:
            preparation_mode = "none"
        failed = [check for check in checks if check.status == "failed"]
        relevant = self._relevant_requirement_failure(
            requirement_type,
            capability,
            failed,
        )

        if preparation_mode == "terraform" or requirement_type == "verification_probe":
            status = "ready"
            message = "The immutable deployment graph contains this Terraform-managed contract."
            action = "No account preparation is required before apply."
        elif preparation_mode == "manual_external":
            status = "manual_action"
            message = "This provider prerequisite cannot be changed safely by the PoC."
            action = self._manual_requirement_action(capability)
        elif capability == "aws.outbound-identity-federation":
            status = "manual_action"
            message = "AWS outbound identity federation needs an account-level review."
            action = (
                "Review the account identity settings and confirm completion before retrying."
            )
        elif relevant is None and not failed:
            status = "ready"
            message = "The non-mutating provider check passed for this requirement."
            action = "No action required."
        elif preparation_mode == "confirmed_account" and requirement_type in {
            "api",
            "resource_provider",
        }:
            status = "preparable"
            message = (
                relevant.message
                if relevant is not None
                else "The account prerequisite needs confirmed preparation."
            )
            action = "Review and confirm the bounded provider preparation action."
        else:
            failure = relevant or (failed[0] if failed else None)
            status = self._failure_requirement_status(failure)
            message = (
                failure.message
                if failure is not None
                else "The requirement could not be verified safely."
            )
            action = (
                failure.action
                if failure is not None
                else "Review the provider prerequisite and run preflight again."
            )

        return DeploymentRequirementReadiness(
            requirement_id=self._safe_text(
                requirement.get("requirement_id"),
                fallback=f"requirement.{requirement_type}.{capability}",
                max_length=300,
            ),
            requirement_type=requirement_type,
            provider=requirement.get("provider"),
            capability_id=capability,
            preparation_mode=preparation_mode,
            mandatory=bool(requirement.get("mandatory", True)),
            status=status,
            message=self._safe_text(message, fallback="Requirement needs review.", max_length=2_000),
            action=self._safe_text(action, fallback="Review and retry.", max_length=2_000),
            source_node_ids=self._safe_requirement_sources(
                requirement.get("source_node_ids")
            ),
            source_edge_ids=self._safe_requirement_sources(
                requirement.get("source_edge_ids")
            ),
        )

    @staticmethod
    def _relevant_requirement_failure(
        requirement_type: str,
        capability: str,
        failures: list[DeploymentReadinessCheck],
    ) -> DeploymentReadinessCheck | None:
        for failure in failures:
            if capability in failure.permissions:
                return failure
            if requirement_type == "region" and failure.code == "REGION_NOT_SUPPORTED":
                return failure
            if requirement_type == "permission" and failure.code in {
                "MISSING_PERMISSIONS",
                "SELF_CHECK_PERMISSION_MISSING",
                "ROLE_ASSIGNMENT_CHECK_UNAVAILABLE",
                "PERMISSION_CHECK_FAILED",
            }:
                return failure
            if requirement_type == "provider_scope" and failure.code in {
                "ACCOUNT_NOT_ACTIVE",
                "BILLING_NOT_ENABLED",
                "PROJECT_ACCESS_DENIED",
                "PROJECT_NOT_ACTIVE",
                "PROJECT_NOT_FOUND",
                "SUBSCRIPTION_NOT_ENABLED",
            }:
                return failure
        return None

    @staticmethod
    def _failure_requirement_status(
        failure: DeploymentReadinessCheck | None,
    ) -> str:
        if failure is None:
            return "unsupported"
        if failure.code in {"DOWNSTREAM_SERVICE_UNAVAILABLE", "DOWNSTREAM_API_ERROR"}:
            return "transient"
        if failure.code in {
            "MISSING_PERMISSIONS",
            "SELF_CHECK_PERMISSION_MISSING",
            "ROLE_ASSIGNMENT_CHECK_UNAVAILABLE",
            "PERMISSION_CHECK_FAILED",
            "PROJECT_ACCESS_DENIED",
            "PROJECT_NOT_FOUND",
            "CREDENTIAL_EXPIRED",
        }:
            return "replace_connection"
        if failure.code in {
            "ACCOUNT_NOT_ACTIVE",
            "BILLING_NOT_ENABLED",
            "PROJECT_NOT_ACTIVE",
            "SUBSCRIPTION_NOT_ENABLED",
            "REGION_NOT_SUPPORTED",
        }:
            return "manual_action"
        return "unsupported"

    @staticmethod
    def _manual_requirement_action(capability: str) -> str:
        if ".quota." in capability:
            return "Review the named regional quota and request capacity if required."
        if capability == "aws.iam-identity-center.primary-region":
            return "Open IAM Identity Center in its primary Region and verify access."
        if capability == "azure.microsoft-graph.authority":
            return "Grant the required Microsoft Graph application consent and retry."
        if capability.startswith("gcp.iap."):
            return "Complete the project IAP OAuth configuration and retry."
        return "Complete this provider-console prerequisite and retry."

    @staticmethod
    def _safe_requirement_sources(value: Any) -> list[str]:
        if not isinstance(value, list):
            return []
        return [str(item)[:300] for item in value[:512] if str(item).strip()]

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
        )

    def _cache_is_current(self, cache, connection, twin) -> bool:
        cache_age = self._clock() - cache.checked_at
        current_architecture_digest = self._current_architecture_digest(twin)
        return bool(
            cache.cloud_connection_id == connection.id
            and cache.connection_payload_fingerprint == connection.payload_fingerprint
            and isinstance(cache.graph_digest, str)
            and isinstance(cache.requirements_digest, str)
            and isinstance(cache.architecture_digest, str)
            and (
                current_architecture_digest is None
                or cache.architecture_digest == current_architecture_digest
            )
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
    def _parse_cached_requirements(
        raw: str,
        provider: str,
    ) -> list[DeploymentRequirementReadiness] | None:
        try:
            values = json.loads(raw)
            if (
                not isinstance(values, list)
                or not values
                or len(values) > 4096
                or any(
                    not isinstance(value, dict)
                    or value.get("provider") != provider
                    or not isinstance(value.get("requirement_id"), str)
                    for value in values
                )
            ):
                return None
            return [
                DeploymentRequirementReadiness.model_validate(value)
                for value in values
            ]
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
            checked_at=checked_at,
            checks=[check],
        )

    def _requirements(
        self, twin
    ) -> tuple[list[CloudProvider], list[DeploymentReadinessCheck]]:
        raw = CredentialResolutionService.required_providers_from_architecture(twin)
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
        return (
            bool(required)
            and not issues
            and len(providers) == len(required)
            and all(provider.ready for provider in providers)
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
        timestamps = [
            provider.checked_at for provider in providers if provider.checked_at
        ]
        return min(timestamps) if timestamps else None

    @staticmethod
    def _provider_evidence_is_coherent(
        providers: list[ProviderDeploymentReadiness],
    ) -> bool:
        return all(
            len(
                {
                    getattr(provider, field)
                    for provider in providers
                    if getattr(provider, field) is not None
                }
            )
            <= 1
            for field in ("graph_digest", "requirements_digest")
        )

    @staticmethod
    def _aggregate_evidence_digest(
        providers: list[ProviderDeploymentReadiness],
        field: str,
    ) -> str | None:
        values = {
            getattr(provider, field)
            for provider in providers
            if getattr(provider, field) is not None
        }
        return next(iter(values)) if len(values) == 1 else None
