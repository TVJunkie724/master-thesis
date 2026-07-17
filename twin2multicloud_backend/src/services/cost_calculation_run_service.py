from __future__ import annotations

from datetime import datetime, timezone
import json
import re
from typing import Any

from sqlalchemy.orm import Session

from src.clients.optimizer_client import OptimizerClient
from src.models.cost_calculation import CostCalculationResultItem, CostCalculationRun
from src.models.optimizer_config import OptimizerConfiguration
from src.repositories.twin_repository import TwinRepository
from src.schemas.optimizer_calculation import OptimizerCalculationParams
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
    TwinNotFound,
)
from src.services.secret_redaction import SECRET_FIELD_NAMES, redact_secret_like_text


SUCCESS = "succeeded"
FAILED = "failed"
SELECTABLE_STATUSES = {SUCCESS}
ENABLED_OPTIMIZATION_PROFILES = {"cost_minimization_v1"}
SECRET_FIELD_PATTERN = re.compile(rf"(?i)^({SECRET_FIELD_NAMES})$")


class CostCalculationRunService:
    """Owns Management API persistence for optimizer calculation runs."""

    def __init__(
        self,
        db: Session,
        optimizer_client: OptimizerClient | None = None,
        aws_twinmaker_contexts: AwsTwinMakerPricingContextService | None = None,
    ):
        self.db = db
        self.optimizer_client = optimizer_client or OptimizerClient()
        self.twin_repository = TwinRepository(db)
        self.aws_twinmaker_contexts = (
            aws_twinmaker_contexts
            or AwsTwinMakerPricingContextService(
                db,
                optimizer_client=self.optimizer_client,
            )
        )

    async def create_run(
        self,
        twin_id: str,
        user_id: str,
        params: OptimizerCalculationParams,
        *,
        pricing_snapshots: dict[str, Any] | None = None,
        pricing_timestamps: dict[str, Any] | None = None,
        pricing_evidence_version: str | None = None,
    ) -> CostCalculationRun:
        twin = self.twin_repository.get_with_configs_for_user(twin_id, user_id)
        if not twin:
            raise TwinNotFound("Twin not found")

        optimizer_params = params.to_optimizer_payload()
        persisted_params = params.to_persisted_payload()
        aws_context = await self.aws_twinmaker_contexts.resolve(user_id)
        optimizer_params["providerPricingContexts"] = {
            "awsTwinMaker": aws_context.payload
        }

        try:
            optimizer_payload = await self.optimizer_client.calculate(optimizer_params)
        except (ExternalServiceUnavailable, ExternalServiceError):
            raise

        result = self._extract_optimizer_result(optimizer_payload)
        contract = self._validate_optimizer_result(result)
        _validate_optimizer_aws_selection_context(result, aws_context)
        cheapest_path = self._extract_cheapest_path(result)
        result_items = self._build_result_items(
            result, cheapest_path, contract["currency"]
        )

        now = datetime.now(timezone.utc)
        try:
            config = twin.optimizer_config or OptimizerConfiguration(twin_id=twin_id)
            self.db.add(config)
            self.db.flush()

            run = CostCalculationRun(
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
                created_at=now,
                completed_at=now,
            )
            self.db.add(run)
            self.db.flush()

            for item in result_items:
                self.db.add(CostCalculationResultItem(run_id=run.id, **item))

            self._update_optimizer_config_compatibility(
                config,
                params=persisted_params,
                result=result,
                cheapest_path=cheapest_path,
                pricing_snapshots=pricing_snapshots or {},
                pricing_timestamps=pricing_timestamps or {},
                calculated_at=now,
            )
            self._before_commit()
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        self.db.refresh(run)
        return run

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
                "summary": _dict_or_empty(trace_payload.get("summary")),
                "field_trace_schema_version": _string_or_none(
                    result.get("resultTraceSchemaVersion")
                ),
                "field_trace_available": field_trace_available,
                "field_trace_records": field_trace_records,
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
        if _selected_l4_provider(result) == "aws":
            current_context = await self.aws_twinmaker_contexts.resolve(user_id)
            _validate_selected_aws_context(run, result, current_context)
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

        config = run.optimizer_config
        if config:
            cheapest_path = _json_loads(run.cheapest_path_json) or {}
            self._apply_cheapest_path(config, cheapest_path)

        try:
            self.db.commit()
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
        return {
            "l1": calculation.get("L1"),
            "l2": calculation.get("L2"),
            "l3_hot": l3.get("Hot"),
            "l3_cool": l3.get("Cool"),
            "l3_archive": l3.get("Archive"),
            "l4": calculation.get("L4"),
            "l5": calculation.get("L5"),
        }

    def _build_result_items(
        self,
        result: dict[str, Any],
        cheapest_path: dict[str, Any],
        currency: str,
    ) -> list[dict[str, Any]]:
        provider_costs = {
            "AWS": result.get("awsCosts") or {},
            "Azure": result.get("azureCosts") or {},
            "GCP": result.get("gcpCosts") or {},
        }
        explicit_items = result.get("resultItems") or result.get("costItems")
        if isinstance(explicit_items, list) and explicit_items:
            return [
                self._normalize_result_item(item, currency)
                for item in explicit_items
                if isinstance(item, dict)
            ]

        layer_mapping = {
            "l1": "L1",
            "l2": "L2",
            "l3_hot": "L3_hot",
            "l3_cool": "L3_cool",
            "l3_archive": "L3_archive",
            "l4": "L4",
            "l5": "L5",
        }
        items: list[dict[str, Any]] = []
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

        for transfer_key, transfer_cost in (result.get("transferCosts") or {}).items():
            items.append(
                {
                    "layer": transfer_key,
                    "component": "transfer",
                    "provider": None,
                    "cost_amount": _float_or_none(transfer_cost),
                    "currency": currency,
                    "unit": "month",
                    "calculation_notes_json": _json_dumps(
                        {"source": "optimizer_transfer_cost"}
                    ),
                    "review_status": "pending_evidence",
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

    def _update_optimizer_config_compatibility(
        self,
        config: OptimizerConfiguration,
        *,
        params: dict[str, Any],
        result: dict[str, Any],
        cheapest_path: dict[str, Any],
        pricing_snapshots: dict[str, Any],
        pricing_timestamps: dict[str, Any],
        calculated_at: datetime,
    ) -> None:
        config.params = _json_dumps(params)
        config.result_json = _json_dumps(result)
        self._apply_cheapest_path(config, cheapest_path)
        config.pricing_aws_snapshot = _json_dumps_or_none(pricing_snapshots.get("aws"))
        config.pricing_azure_snapshot = _json_dumps_or_none(
            pricing_snapshots.get("azure")
        )
        config.pricing_gcp_snapshot = _json_dumps_or_none(pricing_snapshots.get("gcp"))
        config.pricing_aws_updated_at = _parse_iso_safe(pricing_timestamps.get("aws"))
        config.pricing_azure_updated_at = _parse_iso_safe(
            pricing_timestamps.get("azure")
        )
        config.pricing_gcp_updated_at = _parse_iso_safe(pricing_timestamps.get("gcp"))
        config.calculated_at = calculated_at
        self.db.add(config)

    def _apply_cheapest_path(
        self,
        config: OptimizerConfiguration,
        cheapest_path: dict[str, Any],
    ) -> None:
        config.cheapest_l1 = cheapest_path.get("l1")
        config.cheapest_l2 = cheapest_path.get("l2")
        config.cheapest_l3_hot = cheapest_path.get("l3_hot")
        config.cheapest_l3_cool = cheapest_path.get("l3_cool")
        config.cheapest_l3_archive = cheapest_path.get("l3_archive")
        config.cheapest_l4 = cheapest_path.get("l4")
        config.cheapest_l5 = cheapest_path.get("l5")

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
            current.payload.get("reasonCode")
            or "AWS_TWINMAKER_PLAN_UNOBSERVED"
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


def _json_dumps(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _json_dumps_or_none(value: Any) -> str | None:
    if value is None:
        return None
    return _json_dumps(value)


def _json_loads(value: str | None) -> dict[str, Any] | None:
    if not value:
        return None
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _parse_iso_safe(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


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
