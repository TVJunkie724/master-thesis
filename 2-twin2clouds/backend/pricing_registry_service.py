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

    @staticmethod
    def _validate_provider(provider: str) -> None:
        if provider not in SUPPORTED_PROVIDERS:
            raise PricingRegistryLookupError(f"Unsupported provider: {provider}")
