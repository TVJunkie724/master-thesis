"""Validated optimization profile registry."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from backend.optimization.config import (
    DEFAULT_ACTIVE_PROFILE_ID,
    DEFAULT_OPTIMIZATION_PROFILES,
    OPTIMIZATION_CONFIG_VERSION,
    OPTIMIZATION_PROFILE_VERSION,
)
from backend.optimization.metrics import (
    ALLOWED_EVIDENCE_LEVELS,
    DEFAULT_METRIC_DECLARATIONS,
    DEFAULT_METRIC_PROVIDERS,
    MetricProvider,
    MetricProviderDeclaration,
)
from backend.optimization.models import DEFAULT_CALCULATION_MODELS, CalculationModel
from backend.optimization.scoring import (
    DEFAULT_SCORING_STRATEGIES,
    DEFAULT_SCORING_STRATEGY_DECLARATIONS,
    ScoringStrategy,
    ScoringStrategyDeclaration,
)
from backend.pricing_registry_service import PricingRegistryService


class OptimizationConfigError(ValueError):
    """Raised when optimization profiles or strategy contracts are invalid."""

    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__("Invalid optimization configuration: " + "; ".join(errors))


@dataclass(frozen=True)
class OptimizationProfile:
    profile_id: str
    enabled: bool
    metric_provider_ids: tuple[str, ...]
    calculation_model_ids: tuple[str, ...]
    scoring_strategy_id: str
    intent_group_ids: tuple[str, ...]
    evidence_requirements: dict[str, str]
    result_schema_version: str
    description: str
    status: str = "ready"
    profile_version: str = OPTIMIZATION_PROFILE_VERSION

    @classmethod
    def from_config(cls, profile_id: str, config: dict[str, Any]) -> "OptimizationProfile":
        return cls(
            profile_id=profile_id,
            enabled=bool(config.get("enabled", False)),
            metric_provider_ids=tuple(config.get("metric_provider_ids") or ()),
            calculation_model_ids=tuple(config.get("calculation_model_ids") or ()),
            scoring_strategy_id=str(config.get("scoring_strategy_id") or ""),
            intent_group_ids=tuple(config.get("intent_group_ids") or ()),
            evidence_requirements=dict(config.get("evidence_requirements") or {}),
            result_schema_version=str(config.get("result_schema_version") or ""),
            description=str(config.get("description") or ""),
            status=str(config.get("status") or "ready"),
        )

    def to_metadata(self) -> dict[str, Any]:
        return {
            "profile_id": self.profile_id,
            "profile_version": self.profile_version,
            "enabled": self.enabled,
            "status": self.status,
            "metric_provider_ids": list(self.metric_provider_ids),
            "calculation_model_ids": list(self.calculation_model_ids),
            "scoring_strategy_id": self.scoring_strategy_id,
            "intent_group_ids": list(self.intent_group_ids),
            "evidence_requirements": dict(self.evidence_requirements),
            "result_schema_version": self.result_schema_version,
            "description": self.description,
        }


class OptimizationProfileRegistry:
    """Validates and exposes executable optimization profiles."""

    def __init__(
        self,
        *,
        pricing_registry_service: PricingRegistryService | None = None,
        active_profile_id: str = DEFAULT_ACTIVE_PROFILE_ID,
        profiles: dict[str, dict[str, Any]] | None = None,
        metric_declarations: dict[str, MetricProviderDeclaration] | None = None,
        metric_providers: dict[str, MetricProvider] | None = None,
        calculation_models: dict[str, CalculationModel] | None = None,
        scoring_strategy_declarations: dict[str, ScoringStrategyDeclaration] | None = None,
        scoring_strategies: dict[str, ScoringStrategy] | None = None,
    ):
        self.pricing_registry_service = pricing_registry_service or PricingRegistryService()
        self.active_profile_id = active_profile_id
        self.profile_configs = deepcopy(
            DEFAULT_OPTIMIZATION_PROFILES if profiles is None else profiles
        )
        self.metric_declarations = dict(
            DEFAULT_METRIC_DECLARATIONS
            if metric_declarations is None
            else metric_declarations
        )
        self.metric_providers = dict(
            DEFAULT_METRIC_PROVIDERS if metric_providers is None else metric_providers
        )
        self.calculation_models = dict(
            DEFAULT_CALCULATION_MODELS if calculation_models is None else calculation_models
        )
        self.scoring_strategy_declarations = dict(
            DEFAULT_SCORING_STRATEGY_DECLARATIONS
            if scoring_strategy_declarations is None
            else scoring_strategy_declarations
        )
        self.scoring_strategies = dict(
            DEFAULT_SCORING_STRATEGIES if scoring_strategies is None else scoring_strategies
        )
        self._profiles = {
            profile_id: OptimizationProfile.from_config(profile_id, config)
            for profile_id, config in self.profile_configs.items()
        }
        self.validate()

    def validate(self) -> None:
        errors: list[str] = []
        intent_groups = self._load_registry_intent_groups(errors)

        self._validate_metric_declarations(errors)
        self._validate_calculation_models(errors)
        self._validate_scoring_strategies(errors)
        self._validate_profiles(intent_groups, errors)

        if self.active_profile_id not in self._profiles:
            errors.append(f"Unknown active optimization profile: {self.active_profile_id}")
        elif not self._profiles[self.active_profile_id].enabled:
            errors.append(f"Active optimization profile is disabled: {self.active_profile_id}")

        if errors:
            raise OptimizationConfigError(sorted(errors))

    def get_active_profile(self) -> OptimizationProfile:
        return self.select_profile(self.active_profile_id)

    def select_profile(self, profile_id: str | None = None) -> OptimizationProfile:
        selected_id = profile_id or self.active_profile_id
        try:
            profile = self._profiles[selected_id]
        except KeyError as exc:
            raise OptimizationConfigError(
                [f"Unknown optimization profile: {selected_id}"]
            ) from exc
        if not profile.enabled:
            raise OptimizationConfigError([f"Optimization profile is disabled: {selected_id}"])
        return profile

    def list_profiles(self) -> dict[str, OptimizationProfile]:
        return dict(self._profiles)

    def get_metric_provider(self, metric_id: str) -> MetricProvider:
        try:
            return self.metric_providers[metric_id]
        except KeyError as exc:
            raise OptimizationConfigError(
                [f"No executable metric provider for {metric_id}"]
            ) from exc

    def get_scoring_strategy(self, strategy_id: str) -> ScoringStrategy:
        try:
            return self.scoring_strategies[strategy_id]
        except KeyError as exc:
            raise OptimizationConfigError(
                [f"No executable scoring strategy for {strategy_id}"]
            ) from exc

    def build_result_metadata(self, profile_id: str | None = None) -> dict[str, Any]:
        profile = self.select_profile(profile_id)
        registry_version = self.pricing_registry_service.get_registry_version()
        return {
            "config_version": OPTIMIZATION_CONFIG_VERSION,
            "pricing_registry_version": registry_version,
            **profile.to_metadata(),
        }

    def _load_registry_intent_groups(self, errors: list[str]) -> dict[str, dict[str, Any]]:
        try:
            return self.pricing_registry_service.list_intent_groups()
        except Exception as exc:  # pragma: no cover - defensive error shaping
            errors.append(f"Unable to load pricing registry intent groups: {exc}")
            return {}

    def _validate_metric_declarations(self, errors: list[str]) -> None:
        for metric_id, declaration in self.metric_declarations.items():
            if declaration.metric_id != metric_id:
                errors.append(f"Metric declaration key mismatch for {metric_id}")
            if declaration.evidence_level not in ALLOWED_EVIDENCE_LEVELS:
                errors.append(
                    f"Metric {metric_id} has unsupported evidence level "
                    f"{declaration.evidence_level!r}"
                )
            provider = self.metric_providers.get(metric_id)
            if declaration.enabled and provider is None:
                errors.append(f"Enabled metric has no executable provider: {metric_id}")
            if not declaration.enabled and provider is not None:
                errors.append(f"Disabled metric must not have executable provider: {metric_id}")
            if provider is not None and getattr(provider, "enabled", False) != declaration.enabled:
                errors.append(f"Metric provider enabled state mismatch: {metric_id}")

        undeclared = sorted(set(self.metric_providers) - set(self.metric_declarations))
        for metric_id in undeclared:
            errors.append(f"Executable metric provider is not declared: {metric_id}")

    def _validate_calculation_models(self, errors: list[str]) -> None:
        for model_id, model in self.calculation_models.items():
            if model.model_id != model_id:
                errors.append(f"Calculation model key mismatch for {model_id}")
            if model.enabled:
                for metric_id in model.compatible_metric_provider_ids:
                    declaration = self.metric_declarations.get(metric_id)
                    if declaration is None:
                        errors.append(
                            f"Calculation model {model_id} references unknown metric {metric_id}"
                        )
                    elif not declaration.enabled:
                        errors.append(
                            f"Enabled calculation model {model_id} references disabled metric "
                            f"{metric_id}"
                        )

    def _validate_scoring_strategies(self, errors: list[str]) -> None:
        for strategy_id, declaration in self.scoring_strategy_declarations.items():
            if declaration.strategy_id != strategy_id:
                errors.append(f"Scoring strategy declaration key mismatch for {strategy_id}")
            implementation = self.scoring_strategies.get(strategy_id)
            if declaration.enabled and implementation is None:
                errors.append(f"Enabled scoring strategy has no implementation: {strategy_id}")
            if not declaration.enabled and implementation is not None:
                errors.append(
                    f"Disabled scoring strategy must not have implementation: {strategy_id}"
                )
            for metric_id in declaration.compatible_metric_provider_ids:
                if metric_id not in self.metric_declarations:
                    errors.append(
                        f"Scoring strategy {strategy_id} references unknown metric {metric_id}"
                    )

        undeclared = sorted(set(self.scoring_strategies) - set(self.scoring_strategy_declarations))
        for strategy_id in undeclared:
            errors.append(f"Scoring strategy implementation is not declared: {strategy_id}")

    def _validate_profiles(
        self,
        intent_groups: dict[str, dict[str, Any]],
        errors: list[str],
    ) -> None:
        for profile_id, profile in self._profiles.items():
            if not profile.metric_provider_ids:
                errors.append(f"Profile {profile_id} must declare metric_provider_ids")
            if not profile.calculation_model_ids:
                errors.append(f"Profile {profile_id} must declare calculation_model_ids")
            if not profile.scoring_strategy_id:
                errors.append(f"Profile {profile_id} must declare scoring_strategy_id")
            if not profile.result_schema_version:
                errors.append(f"Profile {profile_id} must declare result_schema_version")

            if not profile.enabled:
                continue

            for metric_id in profile.metric_provider_ids:
                declaration = self.metric_declarations.get(metric_id)
                if declaration is None:
                    errors.append(f"Profile {profile_id} references unknown metric {metric_id}")
                elif not declaration.enabled:
                    errors.append(
                        f"Enabled profile {profile_id} references disabled metric {metric_id}"
                    )
                elif metric_id not in self.metric_providers:
                    errors.append(
                        f"Enabled profile {profile_id} lacks metric provider {metric_id}"
                    )

            for model_id in profile.calculation_model_ids:
                model = self.calculation_models.get(model_id)
                if model is None:
                    errors.append(
                        f"Profile {profile_id} references unknown calculation model {model_id}"
                    )
                    continue
                if not model.enabled:
                    errors.append(
                        f"Enabled profile {profile_id} references disabled calculation model "
                        f"{model_id}"
                    )
                missing_metrics = sorted(
                    set(profile.metric_provider_ids) - set(model.compatible_metric_provider_ids)
                )
                if missing_metrics:
                    errors.append(
                        f"Profile {profile_id} model {model_id} is incompatible with metrics "
                        f"{missing_metrics}"
                    )
                missing_groups = sorted(
                    set(profile.intent_group_ids) - set(model.compatible_intent_group_ids)
                )
                if missing_groups:
                    errors.append(
                        f"Profile {profile_id} model {model_id} is incompatible with intent "
                        f"groups {missing_groups}"
                    )

            strategy_declaration = self.scoring_strategy_declarations.get(
                profile.scoring_strategy_id
            )
            if strategy_declaration is None:
                errors.append(
                    f"Profile {profile_id} references unknown scoring strategy "
                    f"{profile.scoring_strategy_id}"
                )
            elif not strategy_declaration.enabled:
                errors.append(
                    f"Enabled profile {profile_id} references disabled scoring strategy "
                    f"{profile.scoring_strategy_id}"
                )
            else:
                missing_metrics = sorted(
                    set(profile.metric_provider_ids)
                    - set(strategy_declaration.compatible_metric_provider_ids)
                )
                if missing_metrics:
                    errors.append(
                        f"Profile {profile_id} scoring strategy "
                        f"{profile.scoring_strategy_id} is incompatible with metrics "
                        f"{missing_metrics}"
                    )

            for group_id in profile.intent_group_ids:
                if group_id not in intent_groups:
                    errors.append(
                        f"Profile {profile_id} references unknown registry intent group "
                        f"{group_id}"
                    )


def build_default_profile_registry(
    pricing_registry_service: PricingRegistryService | None = None,
) -> OptimizationProfileRegistry:
    return OptimizationProfileRegistry(pricing_registry_service=pricing_registry_service)
