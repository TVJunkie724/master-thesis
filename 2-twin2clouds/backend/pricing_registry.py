"""Editable pricing registry loader and validator.

The registry files are the source of truth for pricing intents, normalization
rules, provider mappings, service models, and reviewed mapping decisions.
Generated pricing and evidence artifacts may be inspected, but they must not
become editable pricing truth.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


REGISTRY_ROOT = Path(__file__).resolve().parents[1] / "pricing_registry"

INTENTS_SCHEMA_VERSION = "pricing-registry-intents.v1"
NORMALIZATION_SCHEMA_VERSION = "pricing-registry-normalization.v1"
SERVICE_MODELS_SCHEMA_VERSION = "pricing-registry-service-models.v1"
PROVIDER_MAPPINGS_SCHEMA_VERSION = "pricing-registry-provider-mappings.v1"
REVIEW_DECISIONS_SCHEMA_VERSION = "pricing-registry-review-decisions.v1"
PRICING_MODEL_CLASSIFICATIONS_SCHEMA_VERSION = "pricing-registry-pricing-model-classifications.v1"
PRICE_SOURCE_CLASSIFICATIONS_SCHEMA_VERSION = "pricing-registry-price-source-classifications.v1"

SUPPORTED_PROVIDERS = ("aws", "azure", "gcp")
SUPPORTED_REVIEW_STATUSES = {"draft", "reviewed", "review_required", "rejected"}
SUPPORTED_CLASSIFICATION_REVIEW_STATUSES = {
    "verified",
    "review_required",
    "ambiguous",
    "unsupported",
    "deprecated",
    "stale",
}
SUPPORTED_PRICE_SOURCE_TYPES = {
    "provider_api",
    "official_static_documentation",
    "official_calculator_reference",
    "curated_model_constant",
    "derived_from_provider_api",
    "not_applicable",
    "unsupported",
    "fallback_static",
}
SUPPORTED_BUILD_PATHS = {
    "fetched_from_provider_api",
    "loaded_from_official_static_documentation",
    "loaded_from_official_calculator_reference",
    "loaded_from_curated_model_constant",
    "derived_from_provider_api",
    "declared_not_applicable",
    "declared_unsupported",
    "diagnostic_fallback_only",
}
SUPPORTED_VERIFICATION_STATUSES = {"passed", "failed", "not_applicable"}
BUILD_PATH_SOURCE_TYPES = {
    "fetched_from_provider_api": "provider_api",
    "loaded_from_official_static_documentation": "official_static_documentation",
    "loaded_from_official_calculator_reference": "official_calculator_reference",
    "loaded_from_curated_model_constant": "curated_model_constant",
    "derived_from_provider_api": "derived_from_provider_api",
    "declared_not_applicable": "not_applicable",
    "declared_unsupported": "unsupported",
    "diagnostic_fallback_only": "fallback_static",
}
NON_PUBLISHABLE_CLASSIFICATION_STATUSES = {
    "review_required",
    "ambiguous",
    "unsupported",
    "deprecated",
    "stale",
}
NON_PUBLISHABLE_SOURCE_TYPES = {"fallback_static", "unsupported"}
SUPPORTED_CARDINALITIES = {
    "one_per_region",
    "one_or_more_per_region",
    "zero_or_one_per_region",
    "not_applicable",
}
FORBIDDEN_REVIEW_DECISION_KEYS = {
    "amount",
    "normalized_value",
    "price",
    "price_override",
    "raw_price",
    "retail_price",
    "unit_price",
}


class PricingRegistryError(ValueError):
    """Raised when the editable pricing registry is invalid."""

    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__("Invalid pricing registry: " + "; ".join(errors))


class DuplicateKeyError(PricingRegistryError):
    """Raised when a YAML file contains duplicate keys."""


class _UniqueKeyLoader(yaml.SafeLoader):
    pass


def _construct_mapping(loader: _UniqueKeyLoader, node: yaml.Node, deep: bool = False):
    mapping: dict[Any, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in mapping:
            mark = key_node.start_mark
            raise DuplicateKeyError(
                [f"{mark.name}:{mark.line + 1}: duplicate key {key!r}"]
            )
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


_UniqueKeyLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _construct_mapping,
)


@dataclass(frozen=True)
class PricingRegistry:
    registry_version: str
    intents: dict[str, dict[str, Any]]
    intent_groups: dict[str, dict[str, Any]]
    normalization_rules: dict[str, dict[str, Any]]
    service_models: dict[str, dict[str, Any]]
    provider_mappings: dict[str, dict[str, dict[str, Any]]]
    review_decisions: list[dict[str, Any]]
    pricing_model_classifications: dict[str, dict[str, Any]]
    price_source_classifications: dict[str, dict[str, Any]]

    def mapping_for(self, provider: str, intent_id: str) -> dict[str, Any]:
        try:
            return self.provider_mappings[provider][intent_id]
        except KeyError as exc:
            raise KeyError(f"No mapping for {provider}.{intent_id}") from exc


def load_pricing_registry(root: Path | str = REGISTRY_ROOT) -> PricingRegistry:
    """Load and validate the editable pricing registry."""
    root_path = Path(root)
    intents_doc = _load_yaml_document(root_path / "intents.yaml")
    normalization_doc = _load_yaml_document(root_path / "normalization.yaml")
    service_models_doc = _load_yaml_document(root_path / "service_models.yaml")
    review_decisions_doc = _load_yaml_document(root_path / "review_decisions.yaml")
    pricing_model_classifications_doc = _load_yaml_document(
        root_path / "pricing_model_classifications.yaml"
    )
    price_source_classifications_doc = _load_yaml_document(
        root_path / "price_source_classifications.yaml"
    )
    provider_docs = {
        provider: _load_yaml_document(root_path / "providers" / provider / "mappings.yaml")
        for provider in SUPPORTED_PROVIDERS
    }

    errors: list[str] = []
    errors.extend(_validate_schema(intents_doc, INTENTS_SCHEMA_VERSION, "intents.yaml"))
    errors.extend(
        _validate_schema(normalization_doc, NORMALIZATION_SCHEMA_VERSION, "normalization.yaml")
    )
    errors.extend(
        _validate_schema(service_models_doc, SERVICE_MODELS_SCHEMA_VERSION, "service_models.yaml")
    )
    errors.extend(
        _validate_schema(
            review_decisions_doc,
            REVIEW_DECISIONS_SCHEMA_VERSION,
            "review_decisions.yaml",
        )
    )
    errors.extend(
        _validate_schema(
            pricing_model_classifications_doc,
            PRICING_MODEL_CLASSIFICATIONS_SCHEMA_VERSION,
            "pricing_model_classifications.yaml",
        )
    )
    errors.extend(
        _validate_schema(
            price_source_classifications_doc,
            PRICE_SOURCE_CLASSIFICATIONS_SCHEMA_VERSION,
            "price_source_classifications.yaml",
        )
    )
    for provider, doc in provider_docs.items():
        errors.extend(
            _validate_schema(
                doc,
                PROVIDER_MAPPINGS_SCHEMA_VERSION,
                f"providers/{provider}/mappings.yaml",
            )
        )

    intent_groups = intents_doc.get("intent_groups") or {}
    intents = intents_doc.get("intents") or {}
    normalization_rules = normalization_doc.get("rules") or {}
    service_models = service_models_doc.get("service_models") or {}
    review_decisions = review_decisions_doc.get("decisions") or []
    pricing_model_classifications = (
        pricing_model_classifications_doc.get("classifications") or {}
    )
    price_source_classifications = (
        price_source_classifications_doc.get("classifications") or {}
    )
    provider_mappings = _index_provider_mappings(provider_docs, errors)

    errors.extend(_validate_intents(intent_groups, intents))
    errors.extend(_validate_normalization_rules(normalization_rules))
    errors.extend(_validate_service_models(service_models, intents, intent_groups))
    errors.extend(_validate_provider_mappings(provider_mappings, intents, normalization_rules))
    errors.extend(_validate_provider_coverage(provider_mappings, intents))
    errors.extend(_validate_review_decisions(review_decisions, intents))
    errors.extend(
        _validate_pricing_model_classifications(
            pricing_model_classifications,
            provider_mappings,
        )
    )
    errors.extend(
        _validate_price_source_classifications(
            price_source_classifications,
            pricing_model_classifications,
            provider_mappings,
            normalization_rules,
        )
    )

    registry_versions = {
        str(intents_doc.get("registry_version") or ""),
        str(normalization_doc.get("registry_version") or ""),
        str(service_models_doc.get("registry_version") or ""),
        str(review_decisions_doc.get("registry_version") or ""),
        str(pricing_model_classifications_doc.get("registry_version") or ""),
        str(price_source_classifications_doc.get("registry_version") or ""),
    }
    if "" in registry_versions:
        errors.append("All registry documents must declare registry_version")
    if len(registry_versions - {""}) > 1:
        errors.append(
            "Registry documents must share one registry_version: "
            + ", ".join(sorted(registry_versions - {""}))
        )

    if errors:
        raise PricingRegistryError(sorted(errors))

    return PricingRegistry(
        registry_version=next(iter(registry_versions - {""})),
        intents=intents,
        intent_groups=intent_groups,
        normalization_rules=normalization_rules,
        service_models=service_models,
        provider_mappings=provider_mappings,
        review_decisions=review_decisions,
        pricing_model_classifications=pricing_model_classifications,
        price_source_classifications=price_source_classifications,
    )


def validate_pricing_registry(root: Path | str = REGISTRY_ROOT) -> list[str]:
    """Return validation errors instead of raising."""
    try:
        load_pricing_registry(root)
    except PricingRegistryError as exc:
        return list(exc.errors)
    return []


def _load_yaml_document(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise PricingRegistryError([f"{path}: missing registry file"])
    try:
        with path.open("r", encoding="utf-8") as handle:
            loaded = yaml.load(handle, Loader=_UniqueKeyLoader)
    except PricingRegistryError:
        raise
    except yaml.YAMLError as exc:
        raise PricingRegistryError([f"{path}: malformed YAML: {exc}"]) from exc
    if not isinstance(loaded, dict):
        raise PricingRegistryError([f"{path}: registry document must be an object"])
    return loaded


def _validate_schema(doc: dict[str, Any], expected: str, label: str) -> list[str]:
    actual = doc.get("schema_version")
    if actual != expected:
        return [f"{label}: expected schema_version {expected!r}, got {actual!r}"]
    return []


def _index_provider_mappings(
    provider_docs: dict[str, dict[str, Any]],
    errors: list[str],
) -> dict[str, dict[str, dict[str, Any]]]:
    indexed: dict[str, dict[str, dict[str, Any]]] = {}
    for expected_provider, doc in provider_docs.items():
        provider = doc.get("provider")
        if provider != expected_provider:
            errors.append(
                f"providers/{expected_provider}/mappings.yaml: provider must be "
                f"{expected_provider!r}, got {provider!r}"
            )
        provider_index: dict[str, dict[str, Any]] = {}
        mappings = doc.get("mappings")
        if not isinstance(mappings, list) or not mappings:
            errors.append(f"providers/{expected_provider}/mappings.yaml: mappings must be a non-empty list")
            indexed[expected_provider] = provider_index
            continue
        for idx, mapping in enumerate(mappings):
            if not isinstance(mapping, dict):
                errors.append(
                    f"providers/{expected_provider}/mappings.yaml: mapping #{idx + 1} must be an object"
                )
                continue
            intent_id = mapping.get("intent_id")
            if not intent_id:
                errors.append(
                    f"providers/{expected_provider}/mappings.yaml: mapping #{idx + 1} missing intent_id"
                )
                continue
            if intent_id in provider_index:
                errors.append(
                    f"providers/{expected_provider}/mappings.yaml: duplicate mapping for {intent_id}"
                )
            mapping = dict(mapping)
            mapping["provider"] = expected_provider
            mapping["mapping_version"] = doc.get("mapping_version")
            provider_index[str(intent_id)] = mapping
        indexed[expected_provider] = provider_index
    return indexed


def _validate_intents(
    intent_groups: dict[str, dict[str, Any]],
    intents: dict[str, dict[str, Any]],
) -> list[str]:
    errors: list[str] = []
    if not intent_groups:
        errors.append("intents.yaml: at least one intent group is required")
    if not intents:
        errors.append("intents.yaml: at least one intent is required")
    for intent_id, intent in intents.items():
        if not isinstance(intent, dict):
            errors.append(f"intents.yaml: {intent_id} must be an object")
            continue
        group = intent.get("group")
        if group not in intent_groups:
            errors.append(f"intents.yaml: {intent_id} references unknown group {group!r}")
        expected_providers = intent.get("expected_providers")
        if not isinstance(expected_providers, list) or not expected_providers:
            errors.append(f"intents.yaml: {intent_id} must declare expected_providers")
            continue
        unknown = sorted(set(expected_providers) - set(SUPPORTED_PROVIDERS))
        if unknown:
            errors.append(f"intents.yaml: {intent_id} has unsupported providers {unknown}")
    return errors


def _validate_normalization_rules(rules: dict[str, dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    if not rules:
        return ["normalization.yaml: at least one normalization rule is required"]
    for rule_id, rule in rules.items():
        if not isinstance(rule, dict):
            errors.append(f"normalization.yaml: {rule_id} must be an object")
            continue
        if not isinstance(rule.get("source_units"), list) or not rule["source_units"]:
            errors.append(f"normalization.yaml: {rule_id} must declare source_units")
        if not rule.get("target_unit"):
            errors.append(f"normalization.yaml: {rule_id} must declare target_unit")
        multiplier = rule.get("multiplier")
        if not isinstance(multiplier, (int, float)):
            errors.append(f"normalization.yaml: {rule_id} multiplier must be numeric")
    return errors


def _validate_service_models(
    service_models: dict[str, dict[str, Any]],
    intents: dict[str, dict[str, Any]],
    intent_groups: dict[str, dict[str, Any]],
) -> list[str]:
    errors: list[str] = []
    if not service_models:
        return ["service_models.yaml: at least one service model is required"]
    for model_id, model in service_models.items():
        if not isinstance(model, dict):
            errors.append(f"service_models.yaml: {model_id} must be an object")
            continue
        for group in model.get("intent_groups") or []:
            if group not in intent_groups:
                errors.append(
                    f"service_models.yaml: {model_id} references unknown intent group {group!r}"
                )
        for intent_id in model.get("intents") or []:
            if intent_id not in intents:
                errors.append(
                    f"service_models.yaml: {model_id} references unknown intent {intent_id!r}"
                )
    return errors


def _validate_provider_mappings(
    provider_mappings: dict[str, dict[str, dict[str, Any]]],
    intents: dict[str, dict[str, Any]],
    normalization_rules: dict[str, dict[str, Any]],
) -> list[str]:
    errors: list[str] = []
    for provider, mappings in provider_mappings.items():
        for intent_id, mapping in mappings.items():
            label = f"providers/{provider}/mappings.yaml:{intent_id}"
            if intent_id not in intents:
                errors.append(f"{label}: unknown intent")
            normalization_rule = mapping.get("normalization_rule")
            if normalization_rule not in normalization_rules:
                errors.append(f"{label}: unknown normalization_rule {normalization_rule!r}")
            else:
                target_unit = normalization_rules[normalization_rule].get("target_unit")
                intent_unit = (intents.get(intent_id) or {}).get("normalized_unit")
                if target_unit != intent_unit and not _valid_quantity_transform(
                    mapping.get("quantity_transform"),
                    intent_unit,
                    target_unit,
                ):
                    errors.append(
                        f"{label}: normalization target_unit {target_unit!r} does not "
                        f"match intent normalized_unit {intent_unit!r}; declare a valid "
                        "quantity_transform for intentional unit conversion"
                    )
            review_status = mapping.get("review_status")
            if review_status not in SUPPORTED_REVIEW_STATUSES:
                errors.append(f"{label}: unsupported review_status {review_status!r}")
            cardinality = mapping.get("expected_cardinality")
            if cardinality not in SUPPORTED_CARDINALITIES:
                errors.append(f"{label}: unsupported expected_cardinality {cardinality!r}")
            if not isinstance(mapping.get("match"), dict) or not mapping["match"]:
                errors.append(f"{label}: match must be a non-empty object")
            if not mapping.get("mapping_version"):
                errors.append(f"{label}: mapping_version is required")
    return errors


def _valid_quantity_transform(
    transform: Any,
    intent_unit: str | None,
    target_unit: str | None,
) -> bool:
    if not isinstance(transform, dict):
        return False
    return (
        transform.get("from_unit") == intent_unit
        and transform.get("to_unit") == target_unit
        and bool(transform.get("reason"))
    )


def _validate_provider_coverage(
    provider_mappings: dict[str, dict[str, dict[str, Any]]],
    intents: dict[str, dict[str, Any]],
) -> list[str]:
    errors: list[str] = []
    for intent_id, intent in intents.items():
        for provider in intent.get("expected_providers") or []:
            if intent_id not in provider_mappings.get(provider, {}):
                errors.append(f"Missing provider mapping for {provider}.{intent_id}")
    return errors


def _validate_review_decisions(
    decisions: Any,
    intents: dict[str, dict[str, Any]],
) -> list[str]:
    if not isinstance(decisions, list):
        return ["review_decisions.yaml: decisions must be a list"]
    errors: list[str] = []
    for idx, decision in enumerate(decisions):
        label = f"review_decisions.yaml: decision #{idx + 1}"
        if not isinstance(decision, dict):
            errors.append(f"{label} must be an object")
            continue
        intent_id = decision.get("intent_id")
        if intent_id and intent_id not in intents:
            errors.append(f"{label} references unknown intent {intent_id!r}")
        forbidden = sorted(_find_forbidden_review_keys(decision))
        if forbidden:
            errors.append(f"{label} contains forbidden price override keys {forbidden}")
    return errors


def _validate_pricing_model_classifications(
    classifications: dict[str, dict[str, Any]],
    provider_mappings: dict[str, dict[str, dict[str, Any]]],
) -> list[str]:
    errors: list[str] = []
    if not classifications:
        return ["pricing_model_classifications.yaml: at least one classification is required"]

    covered = _coverage_counts(classifications)
    for provider, mappings in provider_mappings.items():
        for intent_id in mappings:
            count = covered.get((provider, intent_id), 0)
            if count == 0:
                errors.append(
                    "pricing_model_classifications.yaml: missing classification "
                    f"for {provider}.{intent_id}"
                )
            elif count > 1:
                errors.append(
                    "pricing_model_classifications.yaml: duplicate field coverage "
                    f"for {provider}.{intent_id}"
                )

    seen_ids: set[str] = set()
    for classification_id, item in classifications.items():
        label = f"pricing_model_classifications.yaml:{classification_id}"
        if not isinstance(item, dict):
            errors.append(f"{label}: classification must be an object")
            continue
        declared_id = item.get("id")
        if declared_id != classification_id:
            errors.append(f"{label}: id must match key")
        if classification_id in seen_ids:
            errors.append(f"{label}: duplicate classification id")
        seen_ids.add(classification_id)
        provider = item.get("provider")
        if provider not in SUPPORTED_PROVIDERS:
            errors.append(f"{label}: unsupported provider {provider!r}")
        intent_id = item.get("field")
        if provider in SUPPORTED_PROVIDERS and intent_id not in provider_mappings.get(provider, {}):
            errors.append(f"{label}: unknown provider field {provider}.{intent_id}")
        _require_string_fields(
            item,
            label,
            errors,
            (
                "layer",
                "service",
                "field",
                "pricing_model_type",
                "billing_unit_semantics",
                "tier_semantics",
                "included_usage_semantics",
                "region_scope",
                "currency",
                "effective_date",
            ),
        )
        evidence_refs = item.get("evidence_source_refs")
        if not isinstance(evidence_refs, list) or not evidence_refs:
            errors.append(f"{label}: evidence_source_refs must be a non-empty list")
        _validate_classification_publishability(item, label, errors)
    return errors


def _validate_price_source_classifications(
    classifications: dict[str, dict[str, Any]],
    model_classifications: dict[str, dict[str, Any]],
    provider_mappings: dict[str, dict[str, dict[str, Any]]],
    normalization_rules: dict[str, dict[str, Any]],
) -> list[str]:
    errors: list[str] = []
    if not classifications:
        return ["price_source_classifications.yaml: at least one classification is required"]

    covered = _coverage_counts(classifications)
    for provider, mappings in provider_mappings.items():
        for intent_id in mappings:
            count = covered.get((provider, intent_id), 0)
            if count == 0:
                errors.append(
                    "price_source_classifications.yaml: missing classification "
                    f"for {provider}.{intent_id}"
                )
            elif count > 1:
                errors.append(
                    "price_source_classifications.yaml: duplicate field coverage "
                    f"for {provider}.{intent_id}"
                )

    seen_ids: set[str] = set()
    for classification_id, item in classifications.items():
        label = f"price_source_classifications.yaml:{classification_id}"
        if not isinstance(item, dict):
            errors.append(f"{label}: classification must be an object")
            continue
        declared_id = item.get("id")
        if declared_id != classification_id:
            errors.append(f"{label}: id must match key")
        if classification_id in seen_ids:
            errors.append(f"{label}: duplicate classification id")
        seen_ids.add(classification_id)
        provider = item.get("provider")
        if provider not in SUPPORTED_PROVIDERS:
            errors.append(f"{label}: unsupported provider {provider!r}")
        field = item.get("field")
        if provider in SUPPORTED_PROVIDERS and field not in provider_mappings.get(provider, {}):
            errors.append(f"{label}: unknown provider field {provider}.{field}")
        model_id = item.get("pricing_model_classification_id")
        if model_id not in model_classifications:
            errors.append(f"{label}: unknown pricing_model_classification_id {model_id!r}")
        else:
            model = model_classifications[model_id]
            if model.get("provider") != provider or model.get("field") != field:
                errors.append(
                    f"{label}: pricing_model_classification_id {model_id!r} "
                    "does not match provider/field"
                )
        _require_string_fields(
            item,
            label,
            errors,
            (
                "layer",
                "service",
                "field",
                "region_scope",
                "currency",
                "effective_date",
                "reviewed_at",
                "source_url",
            ),
        )
        source_type = item.get("source_type")
        if source_type not in SUPPORTED_PRICE_SOURCE_TYPES:
            errors.append(f"{label}: unsupported source_type {source_type!r}")
        build_path = item.get("expected_build_path")
        if build_path not in SUPPORTED_BUILD_PATHS:
            errors.append(f"{label}: unsupported expected_build_path {build_path!r}")
        elif source_type in SUPPORTED_PRICE_SOURCE_TYPES and BUILD_PATH_SOURCE_TYPES[build_path] != source_type:
            errors.append(
                f"{label}: expected_build_path {build_path!r} is incompatible "
                f"with source_type {source_type!r}"
            )
        allowed_source_types = item.get("allowed_source_types")
        if not isinstance(allowed_source_types, list) or not allowed_source_types:
            errors.append(f"{label}: allowed_source_types must be a non-empty list")
        else:
            unknown = sorted(set(allowed_source_types) - SUPPORTED_PRICE_SOURCE_TYPES)
            if unknown:
                errors.append(f"{label}: unsupported allowed_source_types {unknown}")
            if source_type in SUPPORTED_PRICE_SOURCE_TYPES and source_type not in allowed_source_types:
                errors.append(f"{label}: selected source_type must be allowed")
        normalization_rule_refs = item.get("normalization_rule_refs")
        if not isinstance(normalization_rule_refs, list):
            errors.append(f"{label}: normalization_rule_refs must be a list")
        else:
            unknown_rules = sorted(set(normalization_rule_refs) - set(normalization_rules))
            if unknown_rules:
                errors.append(f"{label}: unknown normalization_rule_refs {unknown_rules}")
        evidence_refs = item.get("required_evidence_refs")
        if source_type == "provider_api" and not evidence_refs:
            errors.append(f"{label}: provider_api source requires required_evidence_refs")
        if source_type == "official_static_documentation" and not item.get("source_url"):
            errors.append(f"{label}: official_static_documentation requires source_url")
        if source_type == "curated_model_constant" and item.get("value_kind") != "non_price_model_assumption":
            errors.append(f"{label}: curated_model_constant must be non-price model data")
        if source_type == "derived_from_provider_api" and not item.get("derived_from"):
            errors.append(f"{label}: derived_from_provider_api requires derived_from")
        if source_type == "not_applicable" and not item.get("reason"):
            errors.append(f"{label}: not_applicable requires reason")
        if source_type == "unsupported" and item.get("publishable") is True:
            errors.append(f"{label}: unsupported source cannot be publishable")
        if source_type == "fallback_static" and item.get("publishable") is True:
            errors.append(f"{label}: fallback_static source cannot be publishable")
        verification_status = item.get("verification_status")
        if verification_status not in SUPPORTED_VERIFICATION_STATUSES:
            errors.append(
                f"{label}: unsupported verification_status {verification_status!r}"
            )
        if verification_status == "failed" and not item.get("failure_reason"):
            errors.append(f"{label}: failed verification requires failure_reason")
        _validate_classification_publishability(item, label, errors)
    return errors


def _coverage_counts(
    classifications: dict[str, dict[str, Any]],
) -> dict[tuple[str, str], int]:
    counts: dict[tuple[str, str], int] = {}
    for item in classifications.values():
        if isinstance(item, dict):
            key = (str(item.get("provider")), str(item.get("field")))
            counts[key] = counts.get(key, 0) + 1
    return counts


def _require_string_fields(
    item: dict[str, Any],
    label: str,
    errors: list[str],
    fields: tuple[str, ...],
) -> None:
    for field in fields:
        if not isinstance(item.get(field), str) or not item[field]:
            errors.append(f"{label}: {field} must be a non-empty string")


def _validate_classification_publishability(
    item: dict[str, Any],
    label: str,
    errors: list[str],
) -> None:
    review_status = item.get("review_status")
    if review_status not in SUPPORTED_CLASSIFICATION_REVIEW_STATUSES:
        errors.append(f"{label}: unsupported review_status {review_status!r}")
    publishable = item.get("publishable")
    if not isinstance(publishable, bool):
        errors.append(f"{label}: publishable must be boolean")
    if publishable is True and review_status in NON_PUBLISHABLE_CLASSIFICATION_STATUSES:
        errors.append(f"{label}: review_status {review_status!r} cannot be publishable")
    source_type = item.get("source_type")
    if publishable is True and source_type in NON_PUBLISHABLE_SOURCE_TYPES:
        errors.append(f"{label}: source_type {source_type!r} cannot be publishable")


def _find_forbidden_review_keys(value: Any) -> set[str]:
    found: set[str] = set()
    if isinstance(value, dict):
        for key, nested in value.items():
            if str(key) in FORBIDDEN_REVIEW_DECISION_KEYS:
                found.add(str(key))
            found.update(_find_forbidden_review_keys(nested))
    elif isinstance(value, list):
        for item in value:
            found.update(_find_forbidden_review_keys(item))
    return found
