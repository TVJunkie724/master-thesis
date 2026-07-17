"""Contract-backed validation for pricing evidence before calculation."""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from backend.pricing_evidence import (
    DERIVED,
    FALLBACK_STATIC,
    FETCHED,
    NOT_APPLICABLE,
    OFFICIAL_CLOUD_EVIDENCE,
    validate_evidence_record,
)
from backend.pricing_registry import BUILD_PATH_SOURCE_TYPES
from backend.pricing_registry_service import (
    PricingRegistryLookupError,
    PricingRegistryService,
)


CONTRACT_VALIDATION_SCHEMA_VERSION = "pricing-contract-validation.v1"
DEFAULT_OPTIMIZATION_BUNDLE_ID = "cost_minimization_v1"
PASSED = "passed"
FAILED = "failed"
NOT_APPLICABLE_STATUS = "not_applicable"

G1_REGISTRY_COMPLETENESS = "G1_REGISTRY_COMPLETENESS"
G2_SOURCE_BUILDABILITY = "G2_SOURCE_BUILDABILITY"
G3_EVIDENCE_PRESENCE = "G3_EVIDENCE_PRESENCE"
G4_NORMALIZATION = "G4_NORMALIZATION"
G5_CONTRACT_COMPATIBILITY = "G5_CONTRACT_COMPATIBILITY"
G6_PUBLISHABILITY = "G6_PUBLISHABILITY"
G7_CALCULATION_READINESS = "G7_CALCULATION_READINESS"

GATE_ORDER = (
    G1_REGISTRY_COMPLETENESS,
    G2_SOURCE_BUILDABILITY,
    G3_EVIDENCE_PRESENCE,
    G4_NORMALIZATION,
    G5_CONTRACT_COMPATIBILITY,
    G6_PUBLISHABILITY,
    G7_CALCULATION_READINESS,
)

MISSING_PRICING_MODEL_CLASSIFICATION = "MISSING_PRICING_MODEL_CLASSIFICATION"
UNPUBLISHABLE_PRICING_MODEL_CLASSIFICATION = "UNPUBLISHABLE_PRICING_MODEL_CLASSIFICATION"
MISSING_PRICE_SOURCE_CLASSIFICATION = "MISSING_PRICE_SOURCE_CLASSIFICATION"
DISALLOWED_PRICE_SOURCE_TYPE = "DISALLOWED_PRICE_SOURCE_TYPE"
MISSING_REQUIRED_EVIDENCE_FIELD = "MISSING_REQUIRED_EVIDENCE_FIELD"
INVALID_OFFICIAL_STATIC_SOURCE = "INVALID_OFFICIAL_STATIC_SOURCE"
INVALID_CURATED_MODEL_CONSTANT = "INVALID_CURATED_MODEL_CONSTANT"
INVALID_DERIVED_FIELD = "INVALID_DERIVED_FIELD"
UNIT_SEMANTICS_MISMATCH = "UNIT_SEMANTICS_MISMATCH"
TIER_SEMANTICS_MISMATCH = "TIER_SEMANTICS_MISMATCH"
UNKNOWN_FORMULA_REF = "UNKNOWN_FORMULA_REF"
UNKNOWN_CALCULATION_COMPONENT = "UNKNOWN_CALCULATION_COMPONENT"
UNPUBLISHABLE_SOURCE_STATE = "UNPUBLISHABLE_SOURCE_STATE"
CALCULATION_NOT_READY = "CALCULATION_NOT_READY"

REGISTRY_TO_EVIDENCE_SOURCE_TYPES = {
    "provider_api": {FETCHED},
    "official_static_documentation": {OFFICIAL_CLOUD_EVIDENCE},
    "official_calculator_reference": {OFFICIAL_CLOUD_EVIDENCE},
    "curated_model_constant": {DERIVED},
    "derived_from_provider_api": {DERIVED},
    "not_applicable": {NOT_APPLICABLE},
    "unsupported": set(),
    "fallback_static": {FALLBACK_STATIC},
}


class PricingContractValidationService:
    """Validate evidence records against active provider pricing contracts."""

    def __init__(self, registry_service: PricingRegistryService | None = None):
        self.registry_service = registry_service or PricingRegistryService()

    def validate_field(
        self,
        *,
        provider: str,
        field: str,
        expected_unit: str,
        evidence_record: dict[str, Any] | None,
        optimization_bundle_id: str = DEFAULT_OPTIMIZATION_BUNDLE_ID,
        publishable: bool = True,
    ) -> dict[str, Any]:
        report = _empty_report(provider=provider, field=field, publishable=publishable)
        context = self._resolve_context(
            report=report,
            provider=provider,
            field=field,
            optimization_bundle_id=optimization_bundle_id,
        )
        if context is None:
            _finalize_readiness(report)
            return report

        contract = context["contract"]
        source = context["source"]
        model = context["model"]
        report.update(
            {
                "layer": contract["layer"],
                "service": contract["service"],
                "contract_id": contract["id"],
                "pricing_model_classification_id": model["id"],
                "price_source_classification_id": source["id"],
            }
        )

        self._validate_source_buildability(report, source)
        self._validate_evidence_presence(report, evidence_record, contract)
        self._validate_normalization(report, evidence_record, expected_unit, contract)
        self._validate_contract_compatibility(report, evidence_record, context)
        self._validate_publishability(report, evidence_record, model, source, publishable)
        _finalize_readiness(report)
        return report

    def _resolve_context(
        self,
        *,
        report: dict[str, Any],
        provider: str,
        field: str,
        optimization_bundle_id: str,
    ) -> dict[str, Any] | None:
        try:
            bundle = self.registry_service.get_optimization_bundle(optimization_bundle_id)
            strategy = self.registry_service.get_calculation_strategy(
                bundle["calculation_strategy_id"]
            )
            formula_set = self.registry_service.get_formula_set(bundle["formula_set_id"])
            workload_contract = self.registry_service.get_workload_contract(
                bundle["workload_contract_id"]
            )
            contract = self.registry_service.get_provider_pricing_contract_for_field(
                provider,
                field,
            )
        except PricingRegistryLookupError as exc:
            _fail(report, G1_REGISTRY_COMPLETENESS, MISSING_PRICE_SOURCE_CLASSIFICATION, str(exc))
            return None

        try:
            model = self.registry_service.get_pricing_model_classification(
                contract["pricing_model_classification_id"]
            )
        except PricingRegistryLookupError:
            _fail(
                report,
                G1_REGISTRY_COMPLETENESS,
                MISSING_PRICING_MODEL_CLASSIFICATION,
                "Missing pricing model classification.",
            )
            return None
        try:
            source = self.registry_service.get_price_source_classification(
                contract["price_source_classification_id"]
            )
        except PricingRegistryLookupError:
            _fail(
                report,
                G1_REGISTRY_COMPLETENESS,
                MISSING_PRICE_SOURCE_CLASSIFICATION,
                "Missing price source classification.",
            )
            return None

        _pass(report, G1_REGISTRY_COMPLETENESS)
        return {
            "bundle": bundle,
            "strategy": strategy,
            "formula_set": formula_set,
            "workload_contract": workload_contract,
            "contract": contract,
            "model": model,
            "source": source,
        }

    def _validate_source_buildability(
        self,
        report: dict[str, Any],
        source: dict[str, Any],
    ) -> None:
        expected_build_path = source.get("expected_build_path")
        source_type = source.get("source_type")
        if BUILD_PATH_SOURCE_TYPES.get(expected_build_path) != source_type:
            _fail(
                report,
                G2_SOURCE_BUILDABILITY,
                DISALLOWED_PRICE_SOURCE_TYPE,
                "Source type is not compatible with the declared build path.",
            )
            return
        _pass(report, G2_SOURCE_BUILDABILITY)

    def _validate_evidence_presence(
        self,
        report: dict[str, Any],
        evidence_record: dict[str, Any] | None,
        contract: dict[str, Any],
    ) -> None:
        if evidence_record is None:
            _fail(
                report,
                G3_EVIDENCE_PRESENCE,
                MISSING_REQUIRED_EVIDENCE_FIELD,
                "Missing evidence record.",
            )
            return

        for validation_error in validate_evidence_record(evidence_record):
            _fail(
                report,
                G3_EVIDENCE_PRESENCE,
                _evidence_error_code(validation_error),
                _sanitize_message(validation_error),
            )

        for field in contract.get("required_evidence_fields") or []:
            if (
                field in {"selected_row", "selected_rows"}
                and evidence_record.get("source_type") != FETCHED
            ):
                continue
            if (
                evidence_record.get("source_type") == NOT_APPLICABLE
                and field in {"normalized_value", "currency"}
            ):
                continue
            if _missing_evidence_field(evidence_record, field):
                _fail(
                    report,
                    G3_EVIDENCE_PRESENCE,
                    MISSING_REQUIRED_EVIDENCE_FIELD,
                    f"Missing required evidence field: {field}",
                )
        if report["gates"][G3_EVIDENCE_PRESENCE]["status"] != FAILED:
            _pass(report, G3_EVIDENCE_PRESENCE)

    def _validate_normalization(
        self,
        report: dict[str, Any],
        evidence_record: dict[str, Any] | None,
        expected_unit: str,
        contract: dict[str, Any],
    ) -> None:
        if evidence_record is None or evidence_record.get("source_type") == NOT_APPLICABLE:
            _not_applicable(report, G4_NORMALIZATION)
            return

        actual_unit = _normalized_unit(evidence_record)
        if actual_unit != expected_unit:
            _fail(
                report,
                G4_NORMALIZATION,
                UNIT_SEMANTICS_MISMATCH,
                f"Normalized unit mismatch: expected {expected_unit!r}, got {actual_unit!r}.",
            )
        normalization_rule = evidence_record.get("normalization_rule")
        if normalization_rule not in (contract.get("normalization_rules") or []):
            _fail(
                report,
                G4_NORMALIZATION,
                UNIT_SEMANTICS_MISMATCH,
                "Evidence normalization rule is not allowed by the provider contract.",
            )
        if report["gates"][G4_NORMALIZATION]["status"] != FAILED:
            _pass(report, G4_NORMALIZATION)

    def _validate_contract_compatibility(
        self,
        report: dict[str, Any],
        evidence_record: dict[str, Any] | None,
        context: dict[str, Any],
    ) -> None:
        contract = context["contract"]
        source = context["source"]
        model = context["model"]
        formula_set = context["formula_set"]
        workload_contract = context["workload_contract"]
        strategy = context["strategy"]

        evidence_source_type = (evidence_record or {}).get("source_type")
        allowed_evidence_types = REGISTRY_TO_EVIDENCE_SOURCE_TYPES.get(
            str(source.get("source_type")),
            set(),
        )
        if evidence_source_type not in allowed_evidence_types:
            _fail(
                report,
                G5_CONTRACT_COMPATIBILITY,
                DISALLOWED_PRICE_SOURCE_TYPE,
                "Evidence source type is not allowed by the price source classification.",
            )

        allowed_by_contract = contract.get("allowed_price_source_types_by_field", {}).get(
            contract["field"],
            [],
        )
        if source.get("source_type") not in allowed_by_contract:
            _fail(
                report,
                G5_CONTRACT_COMPATIBILITY,
                DISALLOWED_PRICE_SOURCE_TYPE,
                "Price source type is not allowed by the provider contract.",
            )

        tier_semantics = str(model.get("tier_semantics") or "")
        selected_row = (evidence_record or {}).get("selected_row") or {}
        has_tier_metadata = bool(
            (evidence_record or {}).get("tier")
            or selected_row.get("tier")
            or (evidence_record or {}).get("normalized_tiers")
        )
        if (
            evidence_source_type == FETCHED
            and "tier" in tier_semantics
            and not has_tier_metadata
        ):
            _fail(
                report,
                G5_CONTRACT_COMPATIBILITY,
                TIER_SEMANTICS_MISMATCH,
                "Fetched tiered pricing evidence must include tier metadata.",
            )

        formula_refs = set(contract.get("allowed_formula_refs") or [])
        unknown_formula_refs = sorted(formula_refs - set(formula_set.get("formulas") or {}))
        if unknown_formula_refs:
            _fail(
                report,
                G5_CONTRACT_COMPATIBILITY,
                UNKNOWN_FORMULA_REF,
                f"Unknown formula refs: {', '.join(unknown_formula_refs)}.",
            )

        workload_fields = set(contract.get("consumed_workload_fields") or [])
        unknown_workload_fields = sorted(
            workload_fields - set(workload_contract.get("fields") or {})
        )
        if unknown_workload_fields:
            _fail(
                report,
                G5_CONTRACT_COMPATIBILITY,
                CALCULATION_NOT_READY,
                f"Unknown workload fields: {', '.join(unknown_workload_fields)}.",
            )

        calculation_components = set(strategy.get("calculation_components") or [])
        if contract.get("calculation_component") not in calculation_components:
            _fail(
                report,
                G5_CONTRACT_COMPATIBILITY,
                UNKNOWN_CALCULATION_COMPONENT,
                "Calculation component is not declared by the active strategy.",
            )

        if report["gates"][G5_CONTRACT_COMPATIBILITY]["status"] != FAILED:
            _pass(report, G5_CONTRACT_COMPATIBILITY)

    def _validate_publishability(
        self,
        report: dict[str, Any],
        evidence_record: dict[str, Any] | None,
        model: dict[str, Any],
        source: dict[str, Any],
        publishable: bool,
    ) -> None:
        if not publishable:
            _not_applicable(report, G6_PUBLISHABILITY)
            return

        if not model.get("publishable"):
            _fail(
                report,
                G6_PUBLISHABILITY,
                UNPUBLISHABLE_PRICING_MODEL_CLASSIFICATION,
                "Pricing model classification is not publishable.",
            )
        if model.get("review_status") != "verified":
            _fail(
                report,
                G6_PUBLISHABILITY,
                UNPUBLISHABLE_PRICING_MODEL_CLASSIFICATION,
                "Pricing model classification review status is not verified.",
            )
        if not source.get("publishable"):
            _fail(
                report,
                G6_PUBLISHABILITY,
                UNPUBLISHABLE_SOURCE_STATE,
                "Price source classification is not publishable.",
            )
        if source.get("review_status") != "verified":
            _fail(
                report,
                G6_PUBLISHABILITY,
                UNPUBLISHABLE_SOURCE_STATE,
                "Price source classification review status is not verified.",
            )
        if source.get("verification_status") != "passed":
            _fail(
                report,
                G6_PUBLISHABILITY,
                UNPUBLISHABLE_SOURCE_STATE,
                "Price source classification verification has not passed.",
            )
        if source.get("source_type") in {"fallback_static", "unsupported"}:
            _fail(
                report,
                G6_PUBLISHABILITY,
                UNPUBLISHABLE_SOURCE_STATE,
                "Fallback or unsupported source classifications are not publishable.",
            )
        if evidence_record is not None:
            if evidence_record.get("source_type") == FALLBACK_STATIC:
                _fail(
                    report,
                    G6_PUBLISHABILITY,
                    UNPUBLISHABLE_SOURCE_STATE,
                    "fallback_static evidence is not publishable.",
                )
            if evidence_record.get("review_required"):
                _fail(
                    report,
                    G6_PUBLISHABILITY,
                    UNPUBLISHABLE_SOURCE_STATE,
                    "review_required evidence is not publishable.",
                )
        if report["gates"][G6_PUBLISHABILITY]["status"] != FAILED:
            _pass(report, G6_PUBLISHABILITY)


def _empty_report(provider: str, field: str, publishable: bool) -> dict[str, Any]:
    return {
        "schema_version": CONTRACT_VALIDATION_SCHEMA_VERSION,
        "provider": provider,
        "layer": None,
        "service": None,
        "field": field,
        "status": PASSED,
        "publishable": publishable,
        "contract_id": None,
        "pricing_model_classification_id": None,
        "price_source_classification_id": None,
        "gates": {
            gate: {"gate": gate, "status": NOT_APPLICABLE_STATUS, "errors": []}
            for gate in GATE_ORDER
        },
        "errors": [],
    }


def _fail(report: dict[str, Any], gate: str, error_code: str, message: str) -> None:
    error = {
        "provider": report["provider"],
        "layer": report.get("layer"),
        "service": report.get("service"),
        "field": report["field"],
        "gate": gate,
        "error_code": error_code,
        "message": _sanitize_message(message),
    }
    report["status"] = FAILED
    report["publishable"] = False
    report["gates"][gate]["status"] = FAILED
    report["gates"][gate]["errors"].append(deepcopy(error))
    report["errors"].append(error)


def _pass(report: dict[str, Any], gate: str) -> None:
    if report["gates"][gate]["status"] != FAILED:
        report["gates"][gate]["status"] = PASSED


def _not_applicable(report: dict[str, Any], gate: str) -> None:
    if report["gates"][gate]["status"] != FAILED:
        report["gates"][gate]["status"] = NOT_APPLICABLE_STATUS


def _finalize_readiness(report: dict[str, Any]) -> None:
    required_gates = GATE_ORDER[:-1]
    failed_gates = [
        gate
        for gate in required_gates
        if report["gates"][gate]["status"] == FAILED
    ]
    if failed_gates:
        _fail(
            report,
            G7_CALCULATION_READINESS,
            CALCULATION_NOT_READY,
            "Field failed required validation gates before calculation.",
        )
    else:
        _pass(report, G7_CALCULATION_READINESS)
        report["status"] = PASSED


def _evidence_error_code(validation_error: str) -> str:
    if "Official cloud evidence" in validation_error:
        return INVALID_OFFICIAL_STATIC_SOURCE
    if "Derived evidence" in validation_error:
        return INVALID_DERIVED_FIELD
    if "Unsupported source_type" in validation_error:
        return DISALLOWED_PRICE_SOURCE_TYPE
    return MISSING_REQUIRED_EVIDENCE_FIELD


def _missing_evidence_field(record: dict[str, Any], field: str) -> bool:
    if field not in record:
        return True
    value = record.get(field)
    return value is None or value == "" or value == {}


def _normalized_unit(record: dict[str, Any]) -> str | None:
    normalization = record.get("normalization") or {}
    actual_unit = normalization.get("target_unit")
    if actual_unit is None:
        actual_unit = record.get("normalized_unit")
    return actual_unit


def _sanitize_message(message: str) -> str:
    sanitized = str(message)
    sensitive_markers = (
        "private_key",
        "client_secret",
        "access_key",
        "secret_access_key",
        "credential",
        "/Users/",
    )
    for marker in sensitive_markers:
        sanitized = sanitized.replace(marker, "[redacted]")
    return sanitized
