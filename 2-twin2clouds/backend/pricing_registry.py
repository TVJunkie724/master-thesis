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

SUPPORTED_PROVIDERS = ("aws", "azure", "gcp")
SUPPORTED_REVIEW_STATUSES = {"draft", "reviewed", "review_required", "rejected"}
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
    provider_mappings = _index_provider_mappings(provider_docs, errors)

    errors.extend(_validate_intents(intent_groups, intents))
    errors.extend(_validate_normalization_rules(normalization_rules))
    errors.extend(_validate_service_models(service_models, intents, intent_groups))
    errors.extend(_validate_provider_mappings(provider_mappings, intents, normalization_rules))
    errors.extend(_validate_provider_coverage(provider_mappings, intents))
    errors.extend(_validate_review_decisions(review_decisions, intents))

    registry_versions = {
        str(intents_doc.get("registry_version") or ""),
        str(normalization_doc.get("registry_version") or ""),
        str(service_models_doc.get("registry_version") or ""),
        str(review_decisions_doc.get("registry_version") or ""),
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
            loaded = yaml.load(handle, Loader=_UniqueKeyLoader)  # nosec B506
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
