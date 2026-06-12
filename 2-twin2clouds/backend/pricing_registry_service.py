"""Typed access boundary for the editable pricing registry."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from backend.pricing_evidence import validate_evidence_report
from backend.pricing_registry import (
    REGISTRY_ROOT,
    SUPPORTED_PROVIDERS,
    PricingRegistry,
    load_pricing_registry,
)


class PricingRegistryLookupError(LookupError):
    """Raised when a registry item does not exist."""


class PricingRegistryService:
    """Read-only service facade over the editable pricing registry files."""

    def __init__(self, root: Path | str = REGISTRY_ROOT):
        self.root = Path(root)

    def load(self) -> PricingRegistry:
        return load_pricing_registry(self.root)

    def get_registry_version(self) -> str:
        return self.load().registry_version

    def get_status(self) -> dict[str, Any]:
        registry = self.load()
        return {
            "status": "valid",
            "registry_version": registry.registry_version,
            "intent_count": len(registry.intents),
            "normalization_rule_count": len(registry.normalization_rules),
            "service_model_count": len(registry.service_models),
            "pricing_model_classification_count": len(
                registry.pricing_model_classifications
            ),
            "price_source_classification_count": len(
                registry.price_source_classifications
            ),
            "optimization_bundle_count": len(registry.optimization_bundles),
            "calculation_strategy_count": len(registry.calculation_strategies),
            "formula_set_count": len(registry.formula_sets),
            "workload_contract_count": len(registry.workload_contracts),
            "provider_pricing_contract_count": len(registry.provider_pricing_contracts),
            "providers": list(SUPPORTED_PROVIDERS),
            "provider_mapping_counts": {
                provider: len(registry.provider_mappings.get(provider, {}))
                for provider in SUPPORTED_PROVIDERS
            },
        }

    def list_intents(self, metric: str | None = None) -> dict[str, dict[str, Any]]:
        registry = self.load()
        if metric is None:
            return deepcopy(registry.intents)
        groups = {
            group_id
            for group_id, group in registry.intent_groups.items()
            if group.get("metric") == metric
        }
        return {
            intent_id: deepcopy(intent)
            for intent_id, intent in registry.intents.items()
            if intent.get("group") in groups
        }

    def list_intent_groups(self) -> dict[str, dict[str, Any]]:
        return deepcopy(self.load().intent_groups)

    def get_intent(self, intent_id: str) -> dict[str, Any]:
        registry = self.load()
        try:
            return deepcopy(registry.intents[intent_id])
        except KeyError as exc:
            raise PricingRegistryLookupError(f"Unknown pricing intent: {intent_id}") from exc

    def list_service_models(self) -> dict[str, dict[str, Any]]:
        return deepcopy(self.load().service_models)

    def get_service_model(self, service_model_id: str) -> dict[str, Any]:
        registry = self.load()
        try:
            return deepcopy(registry.service_models[service_model_id])
        except KeyError as exc:
            raise PricingRegistryLookupError(
                f"Unknown service model: {service_model_id}"
            ) from exc

    def list_normalization_rules(self) -> dict[str, dict[str, Any]]:
        return deepcopy(self.load().normalization_rules)

    def get_normalization_rule(self, rule_id: str) -> dict[str, Any]:
        registry = self.load()
        try:
            return deepcopy(registry.normalization_rules[rule_id])
        except KeyError as exc:
            raise PricingRegistryLookupError(
                f"Unknown normalization rule: {rule_id}"
            ) from exc

    def list_pricing_model_classifications(
        self,
        provider: str | None = None,
    ) -> dict[str, dict[str, Any]]:
        items = self.load().pricing_model_classifications
        return self._filter_by_provider(items, provider)

    def get_pricing_model_classification(self, classification_id: str) -> dict[str, Any]:
        registry = self.load()
        try:
            return deepcopy(registry.pricing_model_classifications[classification_id])
        except KeyError as exc:
            raise PricingRegistryLookupError(
                f"Unknown pricing model classification: {classification_id}"
            ) from exc

    def list_price_source_classifications(
        self,
        provider: str | None = None,
    ) -> dict[str, dict[str, Any]]:
        items = self.load().price_source_classifications
        return self._filter_by_provider(items, provider)

    def get_price_source_classification(self, classification_id: str) -> dict[str, Any]:
        registry = self.load()
        try:
            return deepcopy(registry.price_source_classifications[classification_id])
        except KeyError as exc:
            raise PricingRegistryLookupError(
                f"Unknown price source classification: {classification_id}"
            ) from exc

    def build_field_verification_matrix(
        self,
        provider: str | None = None,
    ) -> list[dict[str, Any]]:
        registry = self.load()
        if provider is not None:
            self._validate_provider(provider)
        rows = []
        for source_id, source in sorted(registry.price_source_classifications.items()):
            if provider is not None and source.get("provider") != provider:
                continue
            model_id = source["pricing_model_classification_id"]
            model = registry.pricing_model_classifications[model_id]
            rows.append(
                {
                    "provider": source["provider"],
                    "layer": source["layer"],
                    "service": source["service"],
                    "field": source["field"],
                    "pricing_model_classification_id": model_id,
                    "price_source_classification_id": source_id,
                    "allowed_source_types": list(source["allowed_source_types"]),
                    "selected_source_type": source["source_type"],
                    "expected_build_path": source["expected_build_path"],
                    "required_evidence_refs": list(source.get("required_evidence_refs") or []),
                    "normalization_rule_refs": list(source.get("normalization_rule_refs") or []),
                    "publishable": bool(source["publishable"] and model["publishable"]),
                    "review_status": source["review_status"],
                    "verification_status": source["verification_status"],
                    "failure_reason": source.get("failure_reason") or "",
                }
            )
        return rows

    def list_optimization_bundles(self) -> dict[str, dict[str, Any]]:
        return deepcopy(self.load().optimization_bundles)

    def get_optimization_bundle(self, bundle_id: str) -> dict[str, Any]:
        registry = self.load()
        try:
            return deepcopy(registry.optimization_bundles[bundle_id])
        except KeyError as exc:
            raise PricingRegistryLookupError(
                f"Unknown optimization bundle: {bundle_id}"
            ) from exc

    def get_optimization_bundle_for_profile(self, profile_id: str) -> dict[str, Any]:
        matches = [
            bundle
            for bundle in self.load().optimization_bundles.values()
            if bundle.get("profile_id") == profile_id
        ]
        if not matches:
            raise PricingRegistryLookupError(
                f"Unknown optimization bundle for profile: {profile_id}"
            )
        if len(matches) > 1:
            raise PricingRegistryLookupError(
                f"Multiple optimization bundles for profile: {profile_id}"
            )
        return deepcopy(matches[0])

    def get_calculation_strategy(self, strategy_id: str) -> dict[str, Any]:
        registry = self.load()
        try:
            return deepcopy(registry.calculation_strategies[strategy_id])
        except KeyError as exc:
            raise PricingRegistryLookupError(
                f"Unknown calculation strategy: {strategy_id}"
            ) from exc

    def get_formula_set(self, formula_set_id: str) -> dict[str, Any]:
        registry = self.load()
        try:
            return deepcopy(registry.formula_sets[formula_set_id])
        except KeyError as exc:
            raise PricingRegistryLookupError(
                f"Unknown formula set: {formula_set_id}"
            ) from exc

    def get_workload_contract(self, workload_contract_id: str) -> dict[str, Any]:
        registry = self.load()
        try:
            return deepcopy(registry.workload_contracts[workload_contract_id])
        except KeyError as exc:
            raise PricingRegistryLookupError(
                f"Unknown workload contract: {workload_contract_id}"
            ) from exc

    def list_provider_pricing_contracts(
        self,
        provider: str | None = None,
    ) -> dict[str, dict[str, Any]]:
        items = self.load().provider_pricing_contracts
        return self._filter_by_provider(items, provider)

    def get_provider_pricing_contract(
        self,
        provider: str,
        layer: str,
        service: str,
        field: str | None = None,
    ) -> dict[str, Any]:
        self._validate_provider(provider)
        matches = [
            contract
            for contract in self.load().provider_pricing_contracts.values()
            if contract.get("provider") == provider
            and contract.get("layer") == layer
            and contract.get("service") == service
            and (field is None or contract.get("field") == field)
        ]
        if not matches:
            suffix = f".{field}" if field is not None else ""
            raise PricingRegistryLookupError(
                f"Unknown provider pricing contract: {provider}.{layer}.{service}{suffix}"
            )
        if len(matches) > 1:
            raise PricingRegistryLookupError(
                "Multiple provider pricing contracts match "
                f"{provider}.{layer}.{service}; provide field"
            )
        return deepcopy(matches[0])

    def get_provider_pricing_contract_for_field(
        self,
        provider: str,
        field: str,
    ) -> dict[str, Any]:
        self._validate_provider(provider)
        matches = [
            contract
            for contract in self.load().provider_pricing_contracts.values()
            if contract.get("provider") == provider and contract.get("field") == field
        ]
        if not matches:
            raise PricingRegistryLookupError(
                f"Unknown provider pricing contract field: {provider}.{field}"
            )
        if len(matches) > 1:
            raise PricingRegistryLookupError(
                f"Multiple provider pricing contracts for field: {provider}.{field}"
            )
        return deepcopy(matches[0])

    def list_provider_mappings(self, provider: str) -> dict[str, dict[str, Any]]:
        registry = self.load()
        self._validate_provider(provider)
        return deepcopy(registry.provider_mappings[provider])

    def get_provider_mapping(self, provider: str, intent_id: str) -> dict[str, Any]:
        registry = self.load()
        self._validate_provider(provider)
        try:
            return deepcopy(registry.provider_mappings[provider][intent_id])
        except KeyError as exc:
            raise PricingRegistryLookupError(
                f"Unknown provider mapping: {provider}.{intent_id}"
            ) from exc

    def validate_publishability(self, evidence_report: list[dict[str, Any]]) -> list[str]:
        return validate_evidence_report(evidence_report, publishable=True)

    def _filter_by_provider(
        self,
        items: dict[str, dict[str, Any]],
        provider: str | None,
    ) -> dict[str, dict[str, Any]]:
        if provider is None:
            return deepcopy(items)
        self._validate_provider(provider)
        return {
            item_id: deepcopy(item)
            for item_id, item in items.items()
            if item.get("provider") == provider
        }

    @staticmethod
    def _validate_provider(provider: str) -> None:
        if provider not in SUPPORTED_PROVIDERS:
            raise PricingRegistryLookupError(f"Unsupported provider: {provider}")
