from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import hmac
import json
from math import isfinite
import re
from typing import Any
import uuid

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.clients.optimizer_client import OptimizerClient
from src.config import settings
from src.models.architecture_profile import ArchitectureAuditEvent
from src.models.cost_calculation import CostCalculationResultItem, CostCalculationRun
from src.models.optimizer_config import OptimizerConfiguration
from src.models.user_function_extension import TwinExtensionBinding
from src.repositories.twin_repository import TwinRepository
from src.schemas.optimizer_calculation import OptimizerCalculationParams
from src.schemas.pricing_catalog import PricingCatalogContext
from src.services.aws_twinmaker_pricing_context_service import (
    OPTIMIZER_CONTEXT_COMPARABLE_FIELDS,
    AwsTwinMakerPricingContextService,
    ResolvedAwsTwinMakerPricingContext,
    optimizer_aws_l4_selection_matches_context,
)
from src.services.errors import (
    CostCalculationRunSelectionError,
    ExternalServiceError,
    ExternalServiceUnavailable,
    OptimizerContractError,
    PricingCatalogUnavailable,
    TwinNotFound,
)
from src.services.six_layer_cost_ledger_service import (
    validate_six_layer_cost_ledger,
)
from src.services.pricing_catalog_context_service import (
    PricingCatalogContextService,
    parse_pricing_catalog_context,
    pricing_catalog_contexts_match,
)
from src.services.optimizer_transfer_pricing_contract import (
    EXPECTED_EDGES,
    ValidatedOptimizerTransferPricing,
    validate_optimizer_transfer_pricing_result,
)
from src.services.resolved_deployment_specification_service import (
    READY,
    ResolvedDeploymentSpecificationError,
    ValidatedResolvedDeploymentSpecification,
    canonical_json,
    validate_resolved_deployment_specification,
)
from src.services.secret_redaction import SECRET_FIELD_NAMES, redact_secret_like_text
from src.services.resolved_architecture_service import ResolvedArchitectureService
from src.services.architecture_errors import ArchitectureDomainError, architecture_error
from src.services.architecture_profile_service import ArchitectureProfileService
from src.services.user_function_extension_service import (
    runtime as extension_contract,
)
from src.security.request_context import current_request_id


SUCCESS = "succeeded"
FAILED = "failed"
SELECTABLE_STATUSES = {SUCCESS}
ENABLED_OPTIMIZATION_PROFILES = {
    "cost-minimization-v2",
}
SECRET_FIELD_PATTERN = re.compile(rf"(?i)^({SECRET_FIELD_NAMES})$")


def _validate_profile_workload_pair(
    params: OptimizerCalculationParams,
    profile: Mapping[str, Any],
) -> None:
    expected_profiles = {("six-layer-eventing", "1")}
    selected_profile = (
        str(profile.get("profileId") or ""),
        str(profile.get("profileVersion") or ""),
    )
    if selected_profile not in expected_profiles:
        raise architecture_error(
            "ARCH_WORKLOAD_INCOMPATIBLE",
            "The calculation workload does not match the selected architecture profile.",
            field="params.schemaVersion",
        )


class CostCalculationRunService:
    """Owns Management API persistence for optimizer calculation runs."""

    def __init__(
        self,
        db: Session,
        optimizer_client: OptimizerClient | None = None,
        aws_twinmaker_contexts: AwsTwinMakerPricingContextService | None = None,
        pricing_catalog_contexts: PricingCatalogContextService | None = None,
        architecture_resolution_enabled: bool | None = None,
        linked_architecture_documents: tuple[Mapping[str, Any], ...] | None = None,
    ):
        self.db = db
        self.optimizer_client = optimizer_client or OptimizerClient()
        self.twin_repository = TwinRepository(db)
        self.aws_twinmaker_contexts = (
            aws_twinmaker_contexts or AwsTwinMakerPricingContextService(db)
        )
        self.pricing_catalog_contexts = (
            pricing_catalog_contexts
            or PricingCatalogContextService(
                db,
                optimizer_client=self.optimizer_client,
            )
        )
        self.architecture_resolution_enabled = (
            settings.ARCHITECTURE_PROFILE_RESOLUTION_ENABLED
            if architecture_resolution_enabled is None
            else architecture_resolution_enabled
        )
        self.linked_architecture_documents = linked_architecture_documents

    async def create_run(
        self,
        twin_id: str,
        user_id: str,
        params: OptimizerCalculationParams,
        *,
        pricing_evidence_version: str | None = None,
    ) -> CostCalculationRun:
        twin = self.twin_repository.get_with_configs_for_user(twin_id, user_id)
        if not twin:
            raise TwinNotFound("Twin not found")

        if not self.architecture_resolution_enabled:
            raise architecture_error(
                "ARCH_PROFILE_NOT_ACTIVE",
                "Phase 8 workload-v2 calculations require architecture profile resolution.",
                field="params.schemaVersion",
            )

        trusted_architecture_request = None
        if self.architecture_resolution_enabled:
            trusted_architecture_request = self._trusted_architecture_request(
                twin_id=twin_id,
                user_id=user_id,
            )
            _validate_profile_workload_pair(
                params,
                trusted_architecture_request["architectureProfile"],
            )

        optimizer_params = params.to_optimizer_payload()
        persisted_params = params.to_persisted_payload()
        run_id = str(uuid.uuid4())
        optimizer_params["calculationRunId"] = run_id
        catalog_context = await self.pricing_catalog_contexts.resolve_for_user(user_id)
        optimizer_params["providerPricingCatalogs"] = catalog_context.to_http_dict()
        aws_context = await self.aws_twinmaker_contexts.resolve(
            user_id,
            catalog_context.catalogs["aws"],
        )
        optimizer_params["providerPricingContexts"] = {
            "awsTwinMaker": aws_context.payload
        }
        failed_run = None
        if trusted_architecture_request is not None:
            optimizer_params.update(trusted_architecture_request)
            failed_run = self._build_failed_run_source(
                twin=twin,
                run_id=run_id,
                user_id=user_id,
                persisted_params=persisted_params,
                catalog_context=catalog_context,
                aws_context=aws_context,
                pricing_evidence_version=pricing_evidence_version,
            )

        try:
            optimizer_payload = await self.optimizer_client.calculate(optimizer_params)
        except (ExternalServiceUnavailable, ExternalServiceError) as exc:
            if failed_run is not None:
                self._persist_failed_run(
                    failed_run,
                    (
                        "OPTIMIZER_UNAVAILABLE"
                        if isinstance(exc, ExternalServiceUnavailable)
                        else exc.error_code or "OPTIMIZER_ERROR"
                    ),
                )
            raise
        except Exception as exc:
            if failed_run is None:
                raise
            self._persist_failed_run(failed_run, "OPTIMIZER_ERROR")
            raise ExternalServiceError(
                "Optimizer calculation failed",
                public_detail="Optimizer service returned an error.",
            ) from exc

        try:
            result = self._extract_optimizer_result(optimizer_payload)
            contract = self._validate_optimizer_result(result)
            _validate_optimizer_pricing_catalog_context(result, catalog_context)
            _validate_optimizer_aws_selection_context(result, aws_context)
            cheapest_path = self._extract_cheapest_path(result)
            deployment_specification = _validate_optimizer_deployment_specification(
                result,
                run_id=run_id,
                cheapest_path=cheapest_path,
                catalog_context=catalog_context,
            )
            resolved_architecture = (
                self._require_optimizer_resolved_architecture(result)
                if self.architecture_resolution_enabled
                else None
            )
            if resolved_architecture is None:
                raise OptimizerContractError(
                    "Optimizer response did not contain a resolved architecture",
                    [
                        {
                            "field": "resolvedTwinArchitecture",
                            "message": "Expected v2 object",
                        }
                    ],
                )
            validated_ledger = validate_six_layer_cost_ledger(
                result.get("costLedger"),
                specification=deployment_specification.specification,
                architecture=resolved_architecture,
                persisted_params=persisted_params,
                catalog_context=catalog_context,
                expected_total_exact=result.get("totalCostExact"),
            )
            result_items = list(validated_ledger.result_items)
        except Exception as exc:
            if failed_run is not None:
                self._persist_failed_run(
                    failed_run,
                    getattr(exc, "code", "OPTIMIZER_CONTRACT_INVALID"),
                )
                if not isinstance(exc, OptimizerContractError):
                    raise OptimizerContractError(
                        "Optimizer response contract is invalid",
                        [
                            {
                                "field": "result",
                                "message": "Response validation failed",
                            }
                        ],
                    ) from exc
            raise

        now = datetime.now(timezone.utc)
        if self.architecture_resolution_enabled:
            config = twin.optimizer_config or OptimizerConfiguration(
                id=str(uuid.uuid4()),
                twin_id=twin_id,
            )
            self.db.add(config)
            run = CostCalculationRun(
                id=run_id,
                twin_id=twin_id,
                user_id=user_id,
                optimizer_config_id=config.id,
                optimizer_config=config,
                status=SUCCESS,
                params_json=_json_dumps(persisted_params),
                total_monthly_cost=contract["total_monthly_cost"],
                currency=contract["currency"],
                optimization_profile_id=contract["optimization_profile_id"],
                optimization_profile_version=(contract["optimization_profile_version"]),
                scoring_strategy_id=contract["scoring_strategy_id"],
                calculation_model_version=contract["calculation_model_version"],
                pricing_registry_version=contract["pricing_registry_version"],
                pricing_evidence_version=pricing_evidence_version,
                pricing_run_reference=aws_context.source_refresh_run_id,
                pricing_catalog_context_json=catalog_context.canonical_json(),
                created_at=now,
            )
            self._update_optimizer_config_projection(
                config,
                params=persisted_params,
                result=result,
                pricing_catalog_context=catalog_context,
                calculated_at=now,
            )
            try:
                return self.persist_successful_run(
                    result,
                    deployment_specification.specification,
                    resolved_architecture,
                    run=run,
                    catalog_context=catalog_context,
                    result_items=result_items,
                    linked_architecture_documents=(self.linked_architecture_documents),
                )
            except (
                ArchitectureDomainError,
                ResolvedDeploymentSpecificationError,
            ) as exc:
                raise OptimizerContractError(
                    "Optimizer architecture resolution is invalid",
                    [
                        {
                            "field": getattr(
                                exc,
                                "field",
                                "resolvedTwinArchitecture",
                            ),
                            "message": str(exc),
                        }
                    ],
                ) from exc

        try:
            config = twin.optimizer_config or OptimizerConfiguration(twin_id=twin_id)
            self.db.add(config)
            self.db.flush()

            run = CostCalculationRun(
                id=run_id,
                twin_id=twin_id,
                user_id=user_id,
                optimizer_config_id=config.id,
                status=SUCCESS,
                params_json=_json_dumps(persisted_params),
                result_summary_json=_json_dumps(result),
                cheapest_path_json=_json_dumps(cheapest_path),
                total_monthly_cost=contract["total_monthly_cost"],
                currency=contract["currency"],
                optimization_profile_id=contract["optimization_profile_id"],
                optimization_profile_version=contract["optimization_profile_version"],
                scoring_strategy_id=contract["scoring_strategy_id"],
                calculation_model_version=contract["calculation_model_version"],
                pricing_registry_version=contract["pricing_registry_version"],
                pricing_evidence_version=pricing_evidence_version,
                pricing_run_reference=aws_context.source_refresh_run_id,
                pricing_catalog_context_json=catalog_context.canonical_json(),
                deployment_specification_json=(deployment_specification.canonical_json),
                deployment_specification_digest=deployment_specification.digest,
                deployment_specification_version=(
                    deployment_specification.schema_version
                ),
                deployment_compatibility_status=READY,
                created_at=now,
                completed_at=now,
            )
            self.db.add(run)
            self.db.flush()

            for item in result_items:
                self.db.add(CostCalculationResultItem(run_id=run.id, **item))

            self._update_optimizer_config_projection(
                config,
                params=persisted_params,
                result=result,
                pricing_catalog_context=catalog_context,
                calculated_at=now,
            )
            self._before_commit()
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        self.db.refresh(run)
        return run

    def persist_successful_run(
        self,
        calculation_result: Mapping[str, Any],
        resolved_deployment_specification: Mapping[str, Any],
        resolved_twin_architecture: Mapping[str, Any],
        *,
        run: CostCalculationRun,
        catalog_context: PricingCatalogContext,
        result_items: list[dict[str, Any]] | None = None,
        linked_architecture_documents: tuple[Mapping[str, Any], ...] | None = None,
    ) -> CostCalculationRun:
        """Fixture-gated Phase 8.4 atomic ingestion boundary.

        Phase 8.5 calls this boundary from the live Optimizer response path.
        Phase 8.4 deliberately exercises it only with canonical fixtures.
        """

        result = dict(calculation_result)
        cheapest_path = self._extract_cheapest_path(result)
        try:
            deployment = validate_resolved_deployment_specification(
                resolved_deployment_specification,
                expected_run_id=run.id,
                expected_cheapest_path=cheapest_path,
                expected_catalog_context=catalog_context,
                expected_result=result,
            )
            persisted_items = list(result_items or [])
            params = _json_loads(run.params_json) or {}
            validated_ledger = validate_six_layer_cost_ledger(
                result.get("costLedger"),
                specification=deployment.specification,
                architecture=resolved_twin_architecture,
                persisted_params=params,
                catalog_context=catalog_context,
                expected_total_exact=result.get("totalCostExact"),
            )
            persisted_items = list(validated_ledger.result_items)
            result["resolvedDeploymentSpecification"] = deployment.specification
            run.result_summary_json = _json_dumps(result)
            run.cheapest_path_json = _json_dumps(cheapest_path)
            run.deployment_specification_json = deployment.canonical_json
            run.deployment_specification_digest = deployment.digest
            run.deployment_specification_version = deployment.schema_version
            run.deployment_compatibility_status = READY
            run.status = SUCCESS
            run.completed_at = datetime.now(timezone.utc)
            self.db.add(run)
            for item in persisted_items:
                self.db.add(CostCalculationResultItem(run_id=run.id, **item))
            ResolvedArchitectureService(self.db).persist(
                run=run,
                raw_architecture=resolved_twin_architecture,
                origin="native_v2",
                linked_documents=linked_architecture_documents,
            )
            self._before_commit()
            self.db.commit()
        except Exception as exc:
            self.db.rollback()
            error_code = getattr(
                exc,
                "code",
                (
                    "DEPLOYMENT_SPECIFICATION_INVALID"
                    if isinstance(exc, ResolvedDeploymentSpecificationError)
                    else "ARCH_RESOLUTION_INVALID"
                ),
            )
            self._persist_failed_run(run, str(error_code))
            if isinstance(
                exc,
                (
                    ArchitectureDomainError,
                    ResolvedDeploymentSpecificationError,
                ),
            ):
                raise
            raise
        self.db.refresh(run)
        return run

    def _persist_failed_run(
        self,
        source: CostCalculationRun,
        error_code: str,
    ) -> None:
        """Persist only bounded failed-run metadata after atomic rollback."""

        if re.fullmatch(r"[A-Z][A-Z0-9_]{0,63}", error_code) is None:
            error_code = "OPTIMIZER_CONTRACT_INVALID"
        optimizer_config_id = None
        if source.optimizer_config_id:
            with self.db.no_autoflush:
                optimizer_config_id = (
                    self.db.query(OptimizerConfiguration.id)
                    .filter(OptimizerConfiguration.id == source.optimizer_config_id)
                    .scalar()
                )
        failed = CostCalculationRun(
            id=source.id,
            twin_id=source.twin_id,
            user_id=source.user_id,
            optimizer_config_id=optimizer_config_id,
            status=FAILED,
            params_json=source.params_json or "{}",
            result_summary_json=None,
            cheapest_path_json=None,
            total_monthly_cost=None,
            currency=source.currency or "USD",
            optimization_profile_id=source.optimization_profile_id,
            optimization_profile_version=source.optimization_profile_version,
            scoring_strategy_id=source.scoring_strategy_id,
            calculation_model_version=source.calculation_model_version,
            pricing_registry_version=source.pricing_registry_version,
            pricing_evidence_version=source.pricing_evidence_version,
            pricing_run_reference=source.pricing_run_reference,
            pricing_catalog_context_json=source.pricing_catalog_context_json,
            deployment_compatibility_status="unavailable",
            architecture_compatibility_status="unavailable",
            created_at=source.created_at or datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
            error_code=error_code,
            error_message="Optimizer contract validation failed.",
        )
        self.db.add(failed)
        self.db.add(
            ArchitectureAuditEvent(
                user_id=failed.user_id,
                action="resolution.persistence",
                outcome="rejected",
                twin_id=failed.twin_id,
                calculation_run_id=failed.id,
                result_code=error_code,
                correlation_id=current_request_id(),
            )
        )
        self.db.commit()

    def _trusted_architecture_request(
        self,
        *,
        twin_id: str,
        user_id: str,
    ) -> dict[str, Any]:
        architecture_service = ResolvedArchitectureService(self.db)
        selection = architecture_service.repository.get_selection(
            twin_id,
            user_id,
        )
        if selection is None:
            raise ArchitectureDomainError(
                "ARCH_PROFILE_NOT_FOUND",
                "The Twin architecture selection is missing.",
                http_status=409,
            )
        profile = ArchitectureProfileService.get_definition(
            selection.profile_id,
            selection.profile_version,
        )
        if not hmac.compare_digest(
            selection.profile_digest,
            profile["content_digest"],
        ):
            raise ArchitectureDomainError(
                "ARCH_PROFILE_DIGEST_MISMATCH",
                "The selected architecture profile digest is stale.",
                http_status=409,
            )
        slots = {
            (item["slot_id"], item["slot_version"]): item
            for item in profile["extension_slots"]
        }
        bindings = (
            self.db.query(TwinExtensionBinding)
            .filter(
                TwinExtensionBinding.twin_id == twin_id,
                TwinExtensionBinding.user_id == user_id,
                TwinExtensionBinding.active.is_(True),
            )
            .all()
        )
        active = {
            (item.slot_id, item.slot_version): item for item in bindings if item.active
        }
        if set(active) != set(slots):
            raise ArchitectureDomainError(
                "ARCH_EXTENSION_BINDING_INVALID",
                "Every selected architecture extension slot requires one "
                "current binding.",
                http_status=422,
            )
        projected_bindings = []
        for identity in sorted(active):
            binding = active[identity]
            artifact = binding.artifact
            expected_binding_digest = extension_contract.binding_digest(
                twin_id=binding.twin_id,
                slot_id=binding.slot_id,
                slot_version=binding.slot_version,
                artifact_id=binding.artifact_id,
                artifact_digest=(
                    artifact.artifact_digest if artifact is not None else ""
                ),
            )
            if (
                artifact is None
                or artifact.user_id != user_id
                or artifact.artifact_state != "valid"
                or (artifact.slot_id, artifact.slot_version) != identity
                or not hmac.compare_digest(
                    binding.binding_digest,
                    expected_binding_digest,
                )
            ):
                raise ArchitectureDomainError(
                    "ARCH_EXTENSION_BINDING_INVALID",
                    "An architecture extension binding is not valid.",
                    http_status=422,
                )
            try:
                configuration = json.loads(artifact.configuration_json)
            except json.JSONDecodeError as exc:
                raise ArchitectureDomainError(
                    "ARCH_EXTENSION_BINDING_INVALID",
                    "An architecture extension configuration is invalid.",
                    http_status=422,
                ) from exc
            configuration_digest = (
                "sha256:"
                + hashlib.sha256(
                    canonical_json(configuration).encode("utf-8")
                ).hexdigest()
            )
            projected_bindings.append(
                {
                    "slotId": binding.slot_id,
                    "slotVersion": binding.slot_version,
                    "artifactId": binding.artifact_id,
                    "artifactDigest": artifact.artifact_digest,
                    "configurationDigest": configuration_digest,
                }
            )
        return {
            "architectureProfile": {
                "profileId": selection.profile_id,
                "profileVersion": selection.profile_version,
                "contentDigest": selection.profile_digest,
            },
            "extensionBindings": projected_bindings,
        }

    def _build_failed_run_source(
        self,
        *,
        twin,
        run_id: str,
        user_id: str,
        persisted_params: dict[str, Any],
        catalog_context: PricingCatalogContext,
        aws_context: ResolvedAwsTwinMakerPricingContext,
        pricing_evidence_version: str | None,
    ) -> CostCalculationRun:
        selection = ResolvedArchitectureService(self.db).repository.get_selection(
            twin.id, user_id
        )
        profile = ArchitectureProfileService.get_definition(
            selection.profile_id,
            selection.profile_version,
        )
        bundle = profile["optimization_bundle"]
        return CostCalculationRun(
            id=run_id,
            twin_id=twin.id,
            user_id=user_id,
            optimizer_config_id=(
                twin.optimizer_config.id if twin.optimizer_config is not None else None
            ),
            status=FAILED,
            params_json=_json_dumps(persisted_params),
            currency=persisted_params.get("currency", "USD"),
            optimization_profile_id=bundle["optimization_strategy_id"],
            optimization_profile_version=bundle["optimization_strategy_version"],
            scoring_strategy_id=bundle["scoring_strategy_id"],
            calculation_model_version=bundle["calculation_strategy_version"],
            pricing_evidence_version=pricing_evidence_version,
            pricing_run_reference=aws_context.source_refresh_run_id,
            pricing_catalog_context_json=catalog_context.canonical_json(),
            created_at=datetime.now(timezone.utc),
        )

    @staticmethod
    def _require_optimizer_resolved_architecture(
        result: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        architecture = result.get("resolvedTwinArchitecture")
        if not isinstance(architecture, Mapping):
            raise OptimizerContractError(
                "Optimizer response did not contain a resolved architecture",
                [
                    {
                        "field": "resolvedTwinArchitecture",
                        "message": "Expected object",
                    }
                ],
            )
        return architecture

    def list_runs(self, twin_id: str, user_id: str) -> list[CostCalculationRun]:
        twin = self.twin_repository.get_for_user(twin_id, user_id)
        if not twin:
            raise TwinNotFound("Twin not found")
        return (
            self.db.query(CostCalculationRun)
            .filter(
                CostCalculationRun.twin_id == twin_id,
                CostCalculationRun.user_id == user_id,
            )
            .order_by(CostCalculationRun.created_at.desc())
            .all()
        )

    def get_run(self, twin_id: str, user_id: str, run_id: str) -> CostCalculationRun:
        run = (
            self.db.query(CostCalculationRun)
            .filter(
                CostCalculationRun.id == run_id,
                CostCalculationRun.twin_id == twin_id,
                CostCalculationRun.user_id == user_id,
            )
            .first()
        )
        if not run:
            raise TwinNotFound("Cost calculation run not found")
        return run

    def get_pricing_evidence_detail(
        self,
        twin_id: str,
        user_id: str,
        run_id: str,
    ) -> dict[str, Any]:
        """Return bounded, secret-free trace evidence for a stored run."""
        run = self.get_run(twin_id, user_id, run_id)
        return self.build_pricing_evidence_detail(run)

    def build_pricing_evidence_detail(self, run: CostCalculationRun) -> dict[str, Any]:
        """Build the public pricing evidence payload for an already scoped run."""
        result = _json_loads(run.result_summary_json) or {}
        trace = result.get("intentTrace") if isinstance(result, dict) else None
        trace_available = isinstance(trace, dict)
        trace_payload = trace if trace_available else {}
        field_trace = result.get("resultTrace") if isinstance(result, dict) else None
        field_trace_records = _list_of_dicts(field_trace)
        field_trace_available = bool(field_trace_records)
        warnings = []
        if not trace_available:
            warnings.append("Optimizer intent trace is not available for this run.")
        if not field_trace_available:
            warnings.append("Optimizer field trace is not available for this run.")
        if isinstance(field_trace, list) and len(field_trace_records) != len(
            field_trace
        ):
            warnings.append("Malformed optimizer field trace records were omitted.")
        transfer_pricing = None
        raw_transfer_pricing = (
            result.get("transferPricingContext") if isinstance(result, dict) else None
        )
        transfer_pricing_field_present = (
            isinstance(result, dict) and "transferPricingContext" in result
        )
        if isinstance(raw_transfer_pricing, dict):
            try:
                transfer_pricing = validate_optimizer_transfer_pricing_result(
                    result,
                    _run_pricing_catalog_context(run),
                )
            except (OptimizerContractError, CostCalculationRunSelectionError):
                warnings.append(
                    "Malformed optimizer transfer pricing evidence was omitted."
                )
        elif transfer_pricing_field_present:
            warnings.append(
                "Malformed optimizer transfer pricing evidence was omitted."
            )

        return _redact_payload(
            {
                "run_id": run.id,
                "twin_id": run.twin_id,
                "trace_schema_version": _string_or_none(
                    trace_payload.get("schema_version")
                    or result.get("trace_schema_version")
                ),
                "trace_available": trace_available,
                "profile": _dict_or_empty(trace_payload.get("profile")),
                "workload": _dict_or_empty(trace_payload.get("workload")),
                "selected_path": _list_of_dicts(trace_payload.get("selected_path")),
                "records": _list_of_dicts(trace_payload.get("records")),
                "transfer_trace": _list_of_dicts(trace_payload.get("transfer_trace")),
                "transition_runtime_trace": _list_of_dicts(
                    trace_payload.get("transition_runtime_trace")
                ),
                "summary": _dict_or_empty(trace_payload.get("summary")),
                "field_trace_schema_version": _string_or_none(
                    result.get("resultTraceSchemaVersion")
                ),
                "field_trace_available": field_trace_available,
                "field_trace_records": field_trace_records,
                "transfer_pricing_context_available": (transfer_pricing is not None),
                "transfer_pricing_context": (
                    raw_transfer_pricing if transfer_pricing is not None else {}
                ),
                "transition_runtime_context_available": (transfer_pricing is not None),
                "transition_runtime_context": (
                    _dict_or_empty(result.get("transitionRuntimeContext"))
                    if transfer_pricing is not None
                    else {}
                ),
                "transition_runtime_costs": (
                    _numeric_dict_or_empty(result.get("transitionRuntimeCosts"))
                    if transfer_pricing is not None
                    else {}
                ),
                "optimization_diagnostics": (
                    _dict_or_empty(result.get("optimizationDiagnostics"))
                    if transfer_pricing is not None
                    else {}
                ),
                "pricing_catalog_context": (
                    safe_pricing_catalog_context(run.pricing_catalog_context_json)
                ),
                "result_metadata": _result_metadata(result),
                "warnings": warnings,
            }
        )

    async def select_for_deployment(
        self,
        twin_id: str,
        user_id: str,
        run_id: str,
    ) -> CostCalculationRun:
        run = self.get_run(twin_id, user_id, run_id)
        if run.status not in SELECTABLE_STATUSES:
            raise CostCalculationRunSelectionError(
                f"Cost calculation run {run_id} is not selectable",
                error_code="COST_CALCULATION_RUN_NOT_SELECTABLE",
            )
        result = _json_loads(run.result_summary_json) or {}
        validate_persisted_run_deployment_specification(
            run,
            result=result,
        )
        persisted_catalog_context = _run_pricing_catalog_context(run)
        if not pricing_catalog_contexts_match(
            persisted_catalog_context,
            result.get("pricingCatalogs"),
        ):
            raise CostCalculationRunSelectionError(
                "The persisted calculation result no longer matches its pricing "
                "catalog evidence; run the optimizer again before deployment.",
                error_code="PRICING_CATALOG_CONTEXT_MISMATCH",
            )
        try:
            verified_catalog_context = (
                await self.pricing_catalog_contexts.verify_context(
                    persisted_catalog_context
                )
            )
        except PricingCatalogUnavailable as exc:
            raise CostCalculationRunSelectionError(
                "Pricing evidence is no longer fresh; refresh pricing and run "
                "the optimizer again before deployment.",
                error_code=exc.error_code,
            ) from exc
        if _selected_l4_provider(result) == "aws":
            current_context = await self.aws_twinmaker_contexts.resolve(
                user_id,
                verified_catalog_context.catalogs["aws"],
            )
            _validate_selected_aws_context(run, result, current_context)
        architecture_service = ResolvedArchitectureService(self.db)
        architecture_service.require_selectable(run)
        now = datetime.now(timezone.utc)
        (
            self.db.query(CostCalculationRun)
            .filter(
                CostCalculationRun.twin_id == twin_id,
                CostCalculationRun.user_id == user_id,
            )
            .update({CostCalculationRun.selected_for_deployment_at: None})
        )
        run.selected_for_deployment_at = now

        selection = architecture_service.repository.get_selection(
            twin_id,
            user_id,
        )
        self.db.add(
            ArchitectureAuditEvent(
                user_id=user_id,
                action="run.selection",
                outcome="succeeded",
                profile_id=(selection.profile_id if selection is not None else None),
                profile_version=(
                    selection.profile_version if selection is not None else None
                ),
                profile_digest=(
                    selection.profile_digest if selection is not None else None
                ),
                twin_id=twin_id,
                calculation_run_id=run.id,
                resolution_digest=run.resolved_architecture_digest,
                result_code=None,
                correlation_id=current_request_id(),
            )
        )

        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise CostCalculationRunSelectionError(
                "Another optimizer run was selected concurrently; reload the "
                "calculation history before retrying.",
                error_code="COST_CALCULATION_RUN_SELECTION_CONFLICT",
            ) from exc
        except Exception:
            self.db.rollback()
            raise
        self.db.refresh(run)
        return run

    def _extract_optimizer_result(self, payload: dict[str, Any]) -> dict[str, Any]:
        result = payload.get("result", payload)
        if not isinstance(result, dict):
            raise OptimizerContractError(
                "Optimizer response did not contain an object result",
                [{"field": "result", "message": "Expected object"}],
            )
        return result

    def _validate_optimizer_result(self, result: dict[str, Any]) -> dict[str, Any]:
        errors: list[dict[str, str]] = []
        profile = result.get("optimizationProfile")
        profile_id = result.get("optimization_profile_id")
        if not profile_id:
            errors.append({"field": "optimization_profile_id", "message": "Missing"})
        elif profile_id not in ENABLED_OPTIMIZATION_PROFILES:
            errors.append(
                {
                    "field": "optimization_profile_id",
                    "message": f"Unsupported or disabled profile {profile_id}",
                }
            )
        if not isinstance(profile, dict):
            errors.append({"field": "optimizationProfile", "message": "Missing object"})
            profile = {}
        elif profile.get("enabled") is False:
            errors.append(
                {
                    "field": "optimizationProfile.enabled",
                    "message": "Profile is disabled",
                }
            )

        total_cost = result.get("totalCost")
        if not isinstance(total_cost, (int, float)):
            errors.append(
                {"field": "totalCost", "message": "Missing numeric total cost"}
            )
        if profile_id == "cost-minimization-v2":
            raw_exact = result.get("totalCostExact")
            try:
                exact = Decimal(str(raw_exact))
            except (InvalidOperation, ValueError):
                exact = Decimal("NaN")
            if (
                result.get("result_schema_version") != "cost-result.v2"
                or not isinstance(raw_exact, str)
                or not exact.is_finite()
                or exact < 0
                or not isinstance(total_cost, (int, float))
                or float(exact) != float(total_cost)
            ):
                errors.append(
                    {
                        "field": "totalCostExact",
                        "message": "Missing or inconsistent exact v2 total",
                    }
                )

        if not isinstance(result.get("calculationResult"), dict):
            errors.append({"field": "calculationResult", "message": "Missing object"})
        if not isinstance(result.get("cheapestPath"), list):
            errors.append({"field": "cheapestPath", "message": "Missing list"})
        if not profile.get("scoring_strategy_id"):
            errors.append(
                {
                    "field": "optimizationProfile.scoring_strategy_id",
                    "message": "Missing",
                }
            )
        if not profile.get("calculation_model_ids"):
            errors.append(
                {
                    "field": "optimizationProfile.calculation_model_ids",
                    "message": "Missing",
                }
            )
        evidence_references = result.get("evidenceReferences")
        if not isinstance(evidence_references, dict):
            errors.append({"field": "evidenceReferences", "message": "Missing object"})
        elif not evidence_references.get("pricing_registry"):
            errors.append(
                {
                    "field": "evidenceReferences.pricing_registry",
                    "message": "Missing",
                }
            )

        if errors:
            raise OptimizerContractError(
                "Optimizer response contract is invalid", errors
            )

        calculation_model_ids = profile.get("calculation_model_ids") or []
        calculation_model_version = (
            calculation_model_ids[0] if calculation_model_ids else None
        )
        return {
            "total_monthly_cost": float(total_cost),
            "currency": str(result.get("currency") or "USD"),
            "optimization_profile_id": str(profile_id),
            "optimization_profile_version": profile.get("profile_version"),
            "scoring_strategy_id": str(profile.get("scoring_strategy_id") or ""),
            "calculation_model_version": calculation_model_version,
            "pricing_registry_version": profile.get("pricing_registry_version"),
        }

    def _extract_cheapest_path(self, result: dict[str, Any]) -> dict[str, Any]:
        calculation = result.get("calculationResult") or {}
        l3 = calculation.get("L3") or {}
        path = {
            "l1": calculation.get("L1"),
            "l2": calculation.get("L2"),
            "l3_hot": l3.get("Hot"),
            "l3_cool": l3.get("Cool"),
            "l3_archive": l3.get("Archive"),
            "l4": calculation.get("L4"),
            "l5": calculation.get("L5"),
        }
        if "Eventing" in calculation:
            path["eventing"] = calculation.get("Eventing")
        return path

    def _build_result_items(
        self,
        result: dict[str, Any],
        cheapest_path: dict[str, Any],
        currency: str,
        transfer_pricing: ValidatedOptimizerTransferPricing,
    ) -> list[dict[str, Any]]:
        provider_costs = {
            "AWS": result.get("awsCosts") or {},
            "Azure": result.get("azureCosts") or {},
            "GCP": result.get("gcpCosts") or {},
        }
        explicit_items = result.get("resultItems") or result.get("costItems")
        if isinstance(explicit_items, list) and explicit_items:
            items = [
                self._normalize_result_item(item, currency)
                for item in explicit_items
                if (
                    isinstance(item, dict)
                    and str(item.get("component") or "").lower() != "transfer"
                    and item.get("layer") not in EXPECTED_EDGES
                )
            ]
        else:
            layer_mapping = {
                "l1": "L1",
                "l2": "L2",
                "l3_hot": "L3_hot",
                "l3_cool": "L3_cool",
                "l3_archive": "L3_archive",
                "l4": "L4",
                "l5": "L5",
            }
            items = []
            for path_key, layer_key in layer_mapping.items():
                provider = cheapest_path.get(path_key)
                cost_payload = provider_costs.get(provider, {}).get(layer_key) or {}
                items.append(
                    {
                        "layer": layer_key,
                        "component": "layer_total",
                        "provider": provider,
                        "cost_amount": _float_or_none(cost_payload.get("cost")),
                        "currency": currency,
                        "unit": "month",
                        "calculation_notes_json": _json_dumps(
                            {
                                "source": "optimizer_layer_total",
                                "path_key": path_key,
                            }
                        ),
                        "review_status": "pending_evidence",
                    }
                )

        for route in transfer_pricing.context.routes:
            items.append(
                {
                    "layer": route.segment_id,
                    "component": "transfer",
                    "provider": route.source.provider,
                    "service_intent_id": (
                        f"{route.source.provider}.transfer.egress"
                        if route.route_class == "cross_provider_public_internet"
                        else None
                    ),
                    "cost_amount": float(route.total_cost),
                    "currency": currency,
                    "unit": "bytes/month",
                    "quantity": float(route.volume_bytes),
                    "unit_price": None,
                    "evidence_id": route.evidence_id,
                    "calculation_notes_json": _json_dumps(
                        {
                            "source": "optimizer_transfer_pricing_context",
                            "schemaVersion": (transfer_pricing.context.schema_version),
                            "route": route.model_dump(
                                mode="json",
                                by_alias=True,
                            ),
                        }
                    ),
                    "review_status": "ready",
                }
            )
        return items

    def _normalize_result_item(
        self,
        item: dict[str, Any],
        default_currency: str,
    ) -> dict[str, Any]:
        notes = (
            item.get("calculation_notes") or item.get("calculation_notes_json") or {}
        )
        return {
            "layer": str(item.get("layer") or "unknown"),
            "component": item.get("component"),
            "provider": item.get("provider"),
            "service_intent_id": item.get("service_intent_id"),
            "cost_amount": _float_or_none(item.get("cost_amount")),
            "currency": str(item.get("currency") or default_currency),
            "unit": item.get("unit"),
            "quantity": _float_or_none(item.get("quantity")),
            "unit_price": _float_or_none(item.get("unit_price")),
            "evidence_id": item.get("evidence_id"),
            "service_model_id": item.get("service_model_id"),
            "calculation_notes_json": _json_dumps(
                notes if isinstance(notes, dict) else {}
            ),
            "review_status": item.get("review_status"),
        }

    def _update_optimizer_config_projection(
        self,
        config: OptimizerConfiguration,
        *,
        params: dict[str, Any],
        result: dict[str, Any],
        pricing_catalog_context: PricingCatalogContext,
        calculated_at: datetime,
    ) -> None:
        config.params = _json_dumps(params)
        config.result_json = _json_dumps(result)
        config.pricing_catalog_context_json = pricing_catalog_context.canonical_json()
        config.calculated_at = calculated_at
        self.db.add(config)

    def _before_commit(self) -> None:
        """Test hook for rollback verification."""


def _selected_l4_provider(result: dict[str, Any]) -> str | None:
    calculation_result = result.get("calculationResult")
    if not isinstance(calculation_result, dict):
        return None
    provider = calculation_result.get("L4")
    if not isinstance(provider, str):
        return None
    return provider.strip().lower() or None


def _validate_selected_aws_context(
    run: CostCalculationRun,
    result: dict[str, Any],
    current: ResolvedAwsTwinMakerPricingContext,
) -> None:
    if not current.available:
        reason = str(
            current.payload.get("reasonCode") or "AWS_TWINMAKER_PLAN_UNOBSERVED"
        )
        raise CostCalculationRunSelectionError(
            "AWS TwinMaker pricing context is no longer deployable; "
            "refresh pricing and run the optimizer again.",
            error_code=reason,
        )

    provider_contexts = result.get("providerPricingContexts")
    stored = (
        provider_contexts.get("awsTwinMaker")
        if isinstance(provider_contexts, dict)
        else None
    )
    expected = current.payload
    if (
        not isinstance(stored, dict)
        or stored.get("status") != "compatible"
        or run.pricing_run_reference != current.source_refresh_run_id
        or any(
            stored.get(field) != expected.get(field)
            for field in OPTIMIZER_CONTEXT_COMPARABLE_FIELDS
        )
    ):
        raise CostCalculationRunSelectionError(
            "AWS TwinMaker pricing context changed after this calculation; "
            "run the optimizer again before deployment.",
            error_code="AWS_TWINMAKER_PLAN_CONNECTION_CHANGED",
        )


def _validate_optimizer_aws_selection_context(
    result: dict[str, Any],
    expected: ResolvedAwsTwinMakerPricingContext,
) -> None:
    if _selected_l4_provider(result) != "aws":
        return
    if not optimizer_aws_l4_selection_matches_context(result, expected):
        specification = result.get("resolvedDeploymentSpecification")
        readiness = (
            specification.get("readiness")
            if isinstance(specification, Mapping)
            else None
        )
        provider_contexts = result.get("providerPricingContexts")
        stored = (
            provider_contexts.get("awsTwinMaker")
            if isinstance(provider_contexts, Mapping)
            else None
        )
        explicitly_blocked_offline_v2 = (
            result.get("optimization_profile_id") == "cost-minimization-v2"
            and not expected.available
            and stored == expected.payload
            and isinstance(readiness, Mapping)
            and readiness.get("status") == "offline_contract_fixture"
            and "gate.live-pricing.aws.twinmaker-account-plan"
            in readiness.get("blocking_gate_ids", [])
        )
        if explicitly_blocked_offline_v2:
            return
        raise OptimizerContractError(
            "Optimizer selected AWS TwinMaker without the trusted account "
            "pricing context supplied by Management.",
            [
                {
                    "field": "providerPricingContexts.awsTwinMaker",
                    "message": "AWS L4 selection is not bound to trusted context",
                }
            ],
        )


def _validate_optimizer_pricing_catalog_context(
    result: dict[str, Any],
    expected: PricingCatalogContext,
) -> None:
    if pricing_catalog_contexts_match(expected, result.get("pricingCatalogs")):
        return
    raise OptimizerContractError(
        "Optimizer result is not bound to the exact pricing catalog context "
        "supplied by Management.",
        [
            {
                "field": "pricingCatalogs",
                "message": "Exact catalog references do not match",
            }
        ],
    )


def _validate_optimizer_deployment_specification(
    result: dict[str, Any],
    *,
    run_id: str,
    cheapest_path: Mapping[str, Any],
    catalog_context: PricingCatalogContext,
) -> ValidatedResolvedDeploymentSpecification:
    try:
        return validate_resolved_deployment_specification(
            result.get("resolvedDeploymentSpecification"),
            expected_run_id=run_id,
            expected_cheapest_path=cheapest_path,
            expected_catalog_context=catalog_context,
            expected_result=result,
        )
    except ResolvedDeploymentSpecificationError as exc:
        raise OptimizerContractError(
            "Optimizer resolved deployment specification is invalid",
            [{"field": exc.field, "message": str(exc)}],
        ) from exc


def validate_persisted_run_deployment_specification(
    run: CostCalculationRun,
    *,
    result: Mapping[str, Any] | None = None,
    catalog_context: PricingCatalogContext | None = None,
) -> ValidatedResolvedDeploymentSpecification:
    """Return a validated immutable run specification or a typed conflict."""

    if run.deployment_compatibility_status != READY:
        raise CostCalculationRunSelectionError(
            "This optimizer run has no deployment-compatible specification; "
            "run the optimizer again before deployment.",
            error_code="DEPLOYMENT_SPECIFICATION_NOT_READY",
        )
    stored_result = result or _json_loads(run.result_summary_json) or {}
    stored_context = catalog_context or _run_pricing_catalog_context(run)
    cheapest_path = _json_loads(run.cheapest_path_json) or {}
    raw_specification = _json_loads(run.deployment_specification_json)
    try:
        validated = validate_resolved_deployment_specification(
            raw_specification,
            expected_run_id=run.id,
            expected_cheapest_path=cheapest_path,
            expected_catalog_context=stored_context,
            expected_result=stored_result,
        )
    except ResolvedDeploymentSpecificationError as exc:
        raise CostCalculationRunSelectionError(
            "The stored deployment specification is invalid; run the "
            "optimizer again before deployment.",
            error_code=exc.code,
        ) from exc
    if (
        run.deployment_specification_digest != validated.digest
        or run.deployment_specification_version != validated.schema_version
    ):
        raise CostCalculationRunSelectionError(
            "The stored deployment specification metadata is inconsistent; "
            "run the optimizer again before deployment.",
            error_code="DEPLOYMENT_SPECIFICATION_METADATA_MISMATCH",
        )
    if (
        validated.schema_version == "resolved-deployment-specification.v2"
        and validated.specification.get("readiness")
        != {"status": "deployment_ready", "blocking_gate_ids": []}
    ):
        raise CostCalculationRunSelectionError(
            "This optimizer result is evaluation-only until its live capacity "
            "evidence gates are satisfied.",
            error_code="DEPLOYMENT_CAPACITY_EVIDENCE_PENDING",
        )
    summary_specification = stored_result.get("resolvedDeploymentSpecification")
    if (
        not isinstance(summary_specification, Mapping)
        or canonical_json(summary_specification) != validated.canonical_json
    ):
        raise CostCalculationRunSelectionError(
            "The stored optimizer result and deployment specification differ; "
            "run the optimizer again before deployment.",
            error_code="DEPLOYMENT_SPECIFICATION_RESULT_MISMATCH",
        )
    return validated


def _run_pricing_catalog_context(
    run: CostCalculationRun,
) -> PricingCatalogContext:
    raw_context = _json_loads(run.pricing_catalog_context_json)
    try:
        return parse_pricing_catalog_context(raw_context)
    except OptimizerContractError as exc:
        raise CostCalculationRunSelectionError(
            "This calculation predates verifiable pricing catalog evidence; "
            "run the optimizer again before deployment.",
            error_code="PRICING_CATALOG_CONTEXT_MISSING",
        ) from exc


def safe_pricing_catalog_context(value: str | None) -> dict[str, Any] | None:
    """Return a validated public context or None for historical invalid rows."""

    raw_context = _json_loads(value)
    try:
        return parse_pricing_catalog_context(raw_context).to_http_dict()
    except OptimizerContractError:
        return None


def _json_dumps(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _json_loads(value: str | None) -> dict[str, Any] | None:
    if not value:
        return None
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _float_or_none(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _result_metadata(result: dict[str, Any]) -> dict[str, Any]:
    metadata: dict[str, Any] = {}
    for key in (
        "result_schema_version",
        "trace_schema_version",
        "optimization_profile_id",
        "currency",
        "totalCost",
        "evidenceReferences",
    ):
        if key in result:
            metadata[key] = result[key]
    return metadata


def _dict_or_empty(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _numeric_dict_or_empty(value: Any) -> dict[str, float]:
    if not isinstance(value, dict):
        return {}
    normalized: dict[str, float] = {}
    for key, item in value.items():
        if (
            not isinstance(key, str)
            or isinstance(item, bool)
            or not isinstance(item, (int, float))
        ):
            return {}
        numeric = float(item)
        if not isfinite(numeric) or numeric < 0:
            return {}
        normalized[key] = numeric
    return normalized


def _list_of_dicts(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _string_or_none(value: Any) -> str | None:
    return str(value) if value is not None else None


def _redact_payload(value: Any) -> Any:
    if isinstance(value, str):
        return redact_secret_like_text(value)
    if isinstance(value, list):
        return [_redact_payload(item) for item in value]
    if isinstance(value, dict):
        redacted: dict[Any, Any] = {}
        for key, item in value.items():
            if isinstance(key, str) and SECRET_FIELD_PATTERN.match(key):
                redacted[key] = "[REDACTED]"
            else:
                redacted[key] = _redact_payload(item)
        return redacted
    return value
