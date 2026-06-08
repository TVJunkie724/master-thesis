"""Cross-provider validation for the evidence-backed cost optimizer path."""
from __future__ import annotations

from collections import Counter
from typing import Any, Iterable

from backend.optimization.profiles import (
    OptimizationConfigError,
    OptimizationProfileRegistry,
    build_default_profile_registry,
)
from backend.pricing_evidence import (
    FALLBACK_STATIC,
    FETCHED,
    NOT_APPLICABLE,
    validate_evidence_record,
)
from backend.pricing_registry import SUPPORTED_PROVIDERS
from backend.pricing_registry_service import PricingRegistryService


CROSS_PROVIDER_COST_VALIDATION_SCHEMA_VERSION = "cross-provider-cost-validation.v1"
REQUIRED_COST_PROFILE_ID = "cost_minimization_v1"
REQUIRED_COST_RESULT_SCHEMA_VERSION = "cost-result.v1"
REQUIRED_COST_INTENT_GROUP = "cost"
PUBLISHABLE = "publishable"
REVIEW_REQUIRED = "review_required"
FAILED = "failed"
MISSING = "missing"
NON_APPLICABLE = "non_applicable"


def build_cross_provider_cost_validation(
    evidence_reports: dict[str, dict[str, Any]],
    *,
    pricing_registry_service: PricingRegistryService | None = None,
    profile_registry: OptimizationProfileRegistry | None = None,
    calculation_result: dict[str, Any] | None = None,
    optimization_profile_id: str = REQUIRED_COST_PROFILE_ID,
    providers: Iterable[str] = SUPPORTED_PROVIDERS,
    publishable: bool = True,
) -> dict[str, Any]:
    """Validate cost evidence coverage and optimizer metadata across providers."""
    registry_service = pricing_registry_service or PricingRegistryService()
    provider_ids = tuple(provider.lower() for provider in providers)
    summary: dict[str, Any] = {
        "schema_version": CROSS_PROVIDER_COST_VALIDATION_SCHEMA_VERSION,
        "status": FAILED,
        "publishable": False,
        "required_profile_id": REQUIRED_COST_PROFILE_ID,
        "requested_profile_id": optimization_profile_id,
        "providers": list(provider_ids),
        "pricing_registry_version": _safe_registry_version(registry_service),
        "optimization_profile": None,
        "intent_count": 0,
        "records": [],
        "counts": {},
        "errors": [],
        "warnings": [],
        "management_run_compatibility": None,
    }

    profile_errors, profile_metadata = _validate_cost_profile(
        registry_service=registry_service,
        profile_registry=profile_registry,
        optimization_profile_id=optimization_profile_id,
    )
    summary["optimization_profile"] = profile_metadata
    summary["errors"].extend(profile_errors)

    intents = registry_service.list_intents(metric="cost")
    summary["intent_count"] = len(intents)
    evidence_by_provider = {
        provider: _index_evidence_report(evidence_reports.get(provider))
        for provider in provider_ids
    }

    for intent_id in sorted(intents):
        intent = intents[intent_id]
        intent_summary = {
            "intent_id": intent_id,
            "description": intent.get("description"),
            "normalized_unit": intent.get("normalized_unit"),
            "expected_providers": list(intent.get("expected_providers") or provider_ids),
            "providers": {},
            "status": PUBLISHABLE,
            "errors": [],
        }
        expected_providers = _expected_providers(intent, provider_ids)
        for provider in expected_providers:
            provider_summary = _validate_provider_intent(
                provider=provider,
                intent_id=intent_id,
                expected_unit=str(intent.get("normalized_unit") or ""),
                evidence_index=evidence_by_provider.get(provider),
                publishable=publishable,
            )
            intent_summary["providers"][provider] = provider_summary
            if provider_summary["status"] == FAILED:
                intent_summary["errors"].extend(provider_summary["errors"])
            elif provider_summary["status"] == REVIEW_REQUIRED:
                intent_summary["status"] = REVIEW_REQUIRED

        if intent_summary["errors"]:
            intent_summary["status"] = FAILED
            summary["errors"].extend(
                f"{intent_id}.{provider}: {error}"
                for provider, provider_summary in intent_summary["providers"].items()
                for error in provider_summary["errors"]
            )
        summary["records"].append(intent_summary)

    summary["counts"] = _count_statuses(summary["records"])
    summary["management_run_compatibility"] = _validate_management_run_compatibility(
        calculation_result=calculation_result,
        validation_summary=summary,
        publishable=publishable,
    )
    if summary["management_run_compatibility"]["status"] == FAILED:
        summary["errors"].extend(summary["management_run_compatibility"]["errors"])

    if summary["errors"]:
        summary["status"] = FAILED
    elif summary["counts"].get(REVIEW_REQUIRED, 0):
        summary["status"] = REVIEW_REQUIRED
    else:
        summary["status"] = PUBLISHABLE
        summary["publishable"] = True

    return summary


def evidence_id_for_record(provider: str, record: dict[str, Any]) -> str:
    """Build a deterministic evidence id for report-selected provider evidence."""
    selected_row = record.get("selected_row") or {}
    candidate_id = (
        selected_row.get("candidate_id")
        or selected_row.get("meterId")
        or selected_row.get("skuId")
        or selected_row.get("sku")
        or record.get("source_type")
    )
    return f"{provider}:{record.get('intent_id')}:{candidate_id}"


def _validate_cost_profile(
    *,
    registry_service: PricingRegistryService,
    profile_registry: OptimizationProfileRegistry | None,
    optimization_profile_id: str,
) -> tuple[list[str], dict[str, Any] | None]:
    errors: list[str] = []
    metadata: dict[str, Any] | None = None
    try:
        registry = profile_registry or build_default_profile_registry(registry_service)
        profile = registry.select_profile(optimization_profile_id)
        metadata = registry.build_result_metadata(profile.profile_id)
    except OptimizationConfigError as exc:
        return list(exc.errors), metadata

    if profile.profile_id != REQUIRED_COST_PROFILE_ID:
        errors.append(
            f"Unsupported optimization profile for publishable cost validation: "
            f"{profile.profile_id}"
        )
    if REQUIRED_COST_INTENT_GROUP not in profile.intent_group_ids:
        errors.append(
            f"Optimization profile {profile.profile_id} is not compatible with cost intents"
        )
    if profile.result_schema_version != REQUIRED_COST_RESULT_SCHEMA_VERSION:
        errors.append(
            f"Optimization profile {profile.profile_id} has incompatible result schema "
            f"{profile.result_schema_version}"
        )
    if set(profile.metric_provider_ids) != {"cost"}:
        errors.append(
            f"Optimization profile {profile.profile_id} must use only the cost metric"
        )
    return errors, metadata


def _validate_provider_intent(
    *,
    provider: str,
    intent_id: str,
    expected_unit: str,
    evidence_index: dict[str, dict[str, Any]] | None,
    publishable: bool,
) -> dict[str, Any]:
    if evidence_index is None:
        return _provider_status(provider, intent_id, MISSING, ["Missing provider evidence report"])

    record = evidence_index.get(intent_id)
    if record is None:
        return _provider_status(provider, intent_id, MISSING, ["Missing provider intent evidence"])

    errors = validate_evidence_record(record)
    source_type = record.get("source_type")
    status = PUBLISHABLE
    if source_type == FALLBACK_STATIC:
        errors.append("fallback_static is not publishable")
    elif record.get("review_required"):
        status = REVIEW_REQUIRED
        if publishable:
            errors.append("review_required evidence is not publishable")
    elif source_type == NOT_APPLICABLE:
        status = NON_APPLICABLE
    elif source_type != FETCHED and not record.get("source_reference"):
        errors.append(f"Unsupported publishable source_type: {source_type}")

    unit_compatible, actual_unit = _unit_compatible(record, expected_unit)
    if source_type != NOT_APPLICABLE and not unit_compatible:
        errors.append(
            f"Normalized unit mismatch: expected {expected_unit!r}, got {actual_unit!r}"
        )

    if errors:
        status = FAILED

    return {
        "provider": provider,
        "intent_id": intent_id,
        "status": status,
        "source_type": source_type,
        "source_api": record.get("source_api"),
        "match_status": record.get("match_status"),
        "review_required": bool(record.get("review_required")),
        "normalization_rule": record.get("normalization_rule"),
        "normalized_unit": actual_unit,
        "normalized_value": record.get("normalized_value"),
        "unit_compatible": unit_compatible,
        "evidence_id": evidence_id_for_record(provider, record),
        "selected_row": _selected_row_identity(record.get("selected_row")),
        "candidate_count": len(record.get("candidate_rows") or []),
        "rejected_count": len(record.get("rejected_rows") or []),
        "errors": errors,
    }


def _validate_management_run_compatibility(
    *,
    calculation_result: dict[str, Any] | None,
    validation_summary: dict[str, Any],
    publishable: bool,
) -> dict[str, Any]:
    required_fields = [
        "optimization_profile_id",
        "result_schema_version",
        "optimizationProfile",
        "evidenceReferences",
        "cheapestPath",
        "totalCost",
    ]
    result = {
        "status": PUBLISHABLE,
        "required_fields": required_fields,
        "evidence_reference_count": _evidence_reference_count(validation_summary),
        "errors": [],
    }
    if calculation_result is None:
        if publishable:
            result["status"] = FAILED
            result["errors"].append("Calculation result is required for publishable validation")
        else:
            result["status"] = REVIEW_REQUIRED
        return result

    for field in required_fields:
        if field not in calculation_result:
            result["errors"].append(f"Calculation result missing {field}")

    profile = calculation_result.get("optimizationProfile") or {}
    if calculation_result.get("optimization_profile_id") != REQUIRED_COST_PROFILE_ID:
        result["errors"].append("Calculation result uses incompatible optimization profile")
    if calculation_result.get("result_schema_version") != REQUIRED_COST_RESULT_SCHEMA_VERSION:
        result["errors"].append("Calculation result uses incompatible result schema")
    if REQUIRED_COST_INTENT_GROUP not in (profile.get("intent_group_ids") or []):
        result["errors"].append("Calculation result profile is missing cost intent group")

    evidence_references = calculation_result.get("evidenceReferences")
    if not isinstance(evidence_references, dict):
        result["errors"].append("Calculation result evidenceReferences must be an object")
    elif not evidence_references.get("pricing_registry"):
        result["errors"].append("Calculation result missing pricing registry evidence reference")

    if result["errors"]:
        result["status"] = FAILED
    return result


def _index_evidence_report(report: dict[str, Any] | None) -> dict[str, dict[str, Any]] | None:
    if not isinstance(report, dict):
        return None
    records = report.get("records")
    if not isinstance(records, list):
        return None
    return {
        str(record.get("intent_id")): record
        for record in records
        if isinstance(record, dict) and record.get("intent_id")
    }


def _unit_compatible(record: dict[str, Any], expected_unit: str) -> tuple[bool, str | None]:
    normalization = record.get("normalization") or {}
    actual_unit = normalization.get("target_unit")
    if actual_unit is None:
        actual_unit = record.get("normalized_unit")
    return actual_unit == expected_unit, actual_unit


def _expected_providers(
    intent: dict[str, Any],
    default_providers: tuple[str, ...],
) -> tuple[str, ...]:
    providers = intent.get("expected_providers")
    if not providers:
        return default_providers
    return tuple(str(provider).lower() for provider in providers)


def _provider_status(
    provider: str,
    intent_id: str,
    status: str,
    errors: list[str],
) -> dict[str, Any]:
    return {
        "provider": provider,
        "intent_id": intent_id,
        "status": FAILED if status == MISSING else status,
        "source_type": None,
        "source_api": None,
        "match_status": None,
        "review_required": False,
        "normalization_rule": None,
        "normalized_unit": None,
        "normalized_value": None,
        "unit_compatible": False,
        "evidence_id": None,
        "selected_row": None,
        "candidate_count": 0,
        "rejected_count": 0,
        "errors": errors,
    }


def _selected_row_identity(selected_row: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(selected_row, dict):
        return None
    keys = (
        "candidate_id",
        "meterId",
        "skuId",
        "sku",
        "rateCode",
        "serviceName",
        "serviceDisplayName",
        "description",
        "unit",
    )
    return {key: selected_row[key] for key in keys if key in selected_row}


def _count_statuses(records: list[dict[str, Any]]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    provider_counts: Counter[str] = Counter()
    for record in records:
        counts[record["status"]] += 1
        for provider_summary in record["providers"].values():
            provider_counts[provider_summary["status"]] += 1
    return {
        "intents": len(records),
        **dict(sorted(counts.items())),
        "provider_records": sum(provider_counts.values()),
        "provider_statuses": dict(sorted(provider_counts.items())),
    }


def _evidence_reference_count(validation_summary: dict[str, Any]) -> int:
    count = 0
    for record in validation_summary.get("records") or []:
        for provider_summary in (record.get("providers") or {}).values():
            if provider_summary.get("evidence_id"):
                count += 1
    return count


def _safe_registry_version(registry_service: PricingRegistryService) -> str | None:
    try:
        return registry_service.get_registry_version()
    except Exception:  # pragma: no cover - defensive summary metadata
        return None
