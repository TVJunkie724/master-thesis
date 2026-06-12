"""Calculation strategy execution context for cost calculation v2."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from backend.optimization.profiles import (
    OptimizationProfileRegistry,
    build_default_profile_registry,
)
from backend.pricing_registry_service import (
    PricingRegistryLookupError,
    PricingRegistryService,
)


class CalculationStrategyExecutionError(ValueError):
    """Raised when calculation cannot execute under the active strategy."""

    def __init__(self, error_code: str, message: str):
        self.error_code = error_code
        super().__init__(message)


MISSING_EXECUTION_CONTEXT = "MISSING_EXECUTION_CONTEXT"
DISABLED_CALCULATION_STRATEGY = "DISABLED_CALCULATION_STRATEGY"
UNKNOWN_FORMULA_SET = "UNKNOWN_FORMULA_SET"
MISSING_WORKLOAD_CONTRACT = "MISSING_WORKLOAD_CONTRACT"
MISSING_PROVIDER_PRICING_CONTRACT = "MISSING_PROVIDER_PRICING_CONTRACT"
FORMULA_REF_NOT_ALLOWED = "FORMULA_REF_NOT_ALLOWED"
INCOMPATIBLE_PROVIDER_PRICING_CONTRACT = "INCOMPATIBLE_PROVIDER_PRICING_CONTRACT"


@dataclass(frozen=True)
class CalculationStrategyExecutionContext:
    optimization_profile_id: str
    calculation_strategy_id: str
    formula_set_id: str
    workload_contract_id: str
    pricing_contract_group_id: str
    pricing_model_classification_group_id: str
    price_source_classification_group_id: str
    scoring_strategy_id: str
    result_schema_version: str
    publishable_mode: bool
    formula_refs: frozenset[str]
    provider_pricing_contract_ids: tuple[str, ...]
    provider_field_contracts: dict[tuple[str, str], dict[str, Any]]

    def ensure_formula_ref(
        self,
        formula_ref: str,
        *,
        provider: str | None = None,
        field: str | None = None,
    ) -> None:
        if formula_ref not in self.formula_refs:
            raise CalculationStrategyExecutionError(
                FORMULA_REF_NOT_ALLOWED,
                f"Formula ref {formula_ref!r} is not part of {self.formula_set_id}.",
            )
        if provider is not None and field is not None:
            contract = self.provider_field_contracts.get((provider.lower(), field))
            if contract is None:
                raise CalculationStrategyExecutionError(
                    MISSING_PROVIDER_PRICING_CONTRACT,
                    f"Missing provider pricing contract for {provider.lower()}.{field}.",
                )
            if formula_ref not in (contract.get("allowed_formula_refs") or []):
                raise CalculationStrategyExecutionError(
                    FORMULA_REF_NOT_ALLOWED,
                    f"Formula ref {formula_ref!r} is not allowed for {provider.lower()}.{field}.",
                )

    def get_provider_contract(self, provider: str, field: str) -> dict[str, Any]:
        contract = self.provider_field_contracts.get((provider.lower(), field))
        if contract is None:
            raise CalculationStrategyExecutionError(
                MISSING_PROVIDER_PRICING_CONTRACT,
                f"Missing provider pricing contract for {provider.lower()}.{field}.",
            )
        return dict(contract)

    def ensure_provider_context(self, provider: str) -> None:
        provider_id = provider.lower()
        if not any(key_provider == provider_id for key_provider, _ in self.provider_field_contracts):
            raise CalculationStrategyExecutionError(
                MISSING_PROVIDER_PRICING_CONTRACT,
                f"Missing provider pricing contracts for {provider_id}.",
            )

    def to_result_metadata(self) -> dict[str, Any]:
        return {
            "optimization_profile_id": self.optimization_profile_id,
            "calculation_strategy_id": self.calculation_strategy_id,
            "formula_set_id": self.formula_set_id,
            "workload_contract_id": self.workload_contract_id,
            "pricing_contract_group_id": self.pricing_contract_group_id,
            "pricing_model_classification_group_id": self.pricing_model_classification_group_id,
            "price_source_classification_group_id": self.price_source_classification_group_id,
            "scoring_strategy_id": self.scoring_strategy_id,
            "result_schema_version": self.result_schema_version,
            "publishable_mode": self.publishable_mode,
            "formula_refs": sorted(self.formula_refs),
            "provider_pricing_contract_ids": list(self.provider_pricing_contract_ids),
        }


def resolve_calculation_strategy_execution_context(
    *,
    optimization_profile_id: str | None = None,
    profile_registry: OptimizationProfileRegistry | None = None,
    pricing_registry_service: PricingRegistryService | None = None,
    publishable_mode: bool = True,
) -> CalculationStrategyExecutionContext:
    registry_service = pricing_registry_service or PricingRegistryService()
    registry = profile_registry or build_default_profile_registry(registry_service)
    profile = registry.select_profile(optimization_profile_id)
    bundle_id = profile.optimization_bundle_id or profile.profile_id
    bundle = registry_service.get_optimization_bundle(bundle_id)
    strategy = _get_calculation_strategy(registry_service, bundle)
    formula_set = _get_formula_set(registry_service, strategy)
    workload_contract = _get_workload_contract(registry_service, strategy)
    provider_contracts = _get_provider_contracts(registry_service, bundle)

    if bundle.get("enabled") is not True or bundle.get("status") != "ready":
        raise CalculationStrategyExecutionError(
            DISABLED_CALCULATION_STRATEGY,
            f"Optimization bundle {bundle_id} is not executable.",
        )
    if strategy.get("metric_provider_id") != "cost":
        raise CalculationStrategyExecutionError(
            DISABLED_CALCULATION_STRATEGY,
            f"Calculation strategy {strategy['id']} is not a cost strategy.",
        )

    formula_refs = frozenset((formula_set.get("formulas") or {}).keys())
    provider_field_contracts = {
        (contract["provider"], contract["field"]): contract
        for contract in provider_contracts
    }
    return CalculationStrategyExecutionContext(
        optimization_profile_id=profile.profile_id,
        calculation_strategy_id=strategy["id"],
        formula_set_id=formula_set["id"],
        workload_contract_id=workload_contract["id"],
        pricing_contract_group_id=strategy["pricing_contract_group"],
        pricing_model_classification_group_id=strategy["pricing_model_classification_group"],
        price_source_classification_group_id=strategy["price_source_classification_group"],
        scoring_strategy_id=profile.scoring_strategy_id,
        result_schema_version=profile.result_schema_version,
        publishable_mode=publishable_mode,
        formula_refs=formula_refs,
        provider_pricing_contract_ids=tuple(contract["id"] for contract in provider_contracts),
        provider_field_contracts=provider_field_contracts,
    )


def _get_calculation_strategy(
    registry_service: PricingRegistryService,
    bundle: dict[str, Any],
) -> dict[str, Any]:
    strategy_id = bundle.get("calculation_strategy_id")
    try:
        strategy = registry_service.get_calculation_strategy(str(strategy_id))
    except PricingRegistryLookupError as exc:
        raise CalculationStrategyExecutionError(
            DISABLED_CALCULATION_STRATEGY,
            f"Unknown calculation strategy {strategy_id!r}.",
        ) from exc
    if strategy.get("enabled") is not True or strategy.get("status") != "ready":
        raise CalculationStrategyExecutionError(
            DISABLED_CALCULATION_STRATEGY,
            f"Calculation strategy {strategy_id!r} is not executable.",
        )
    return strategy


def _get_formula_set(
    registry_service: PricingRegistryService,
    strategy: dict[str, Any],
) -> dict[str, Any]:
    formula_set_id = strategy.get("formula_set_id")
    try:
        return registry_service.get_formula_set(str(formula_set_id))
    except PricingRegistryLookupError as exc:
        raise CalculationStrategyExecutionError(
            UNKNOWN_FORMULA_SET,
            f"Unknown formula set {formula_set_id!r}.",
        ) from exc


def _get_workload_contract(
    registry_service: PricingRegistryService,
    strategy: dict[str, Any],
) -> dict[str, Any]:
    workload_contract_id = strategy.get("workload_contract_id")
    try:
        return registry_service.get_workload_contract(str(workload_contract_id))
    except PricingRegistryLookupError as exc:
        raise CalculationStrategyExecutionError(
            MISSING_WORKLOAD_CONTRACT,
            f"Unknown workload contract {workload_contract_id!r}.",
        ) from exc


def _get_provider_contracts(
    registry_service: PricingRegistryService,
    bundle: dict[str, Any],
) -> list[dict[str, Any]]:
    contracts = []
    for contract_id in bundle.get("provider_pricing_contract_ids") or []:
        try:
            contracts.append(registry_service.get_provider_pricing_contract_by_id(contract_id))
        except PricingRegistryLookupError as exc:
            raise CalculationStrategyExecutionError(
                MISSING_PROVIDER_PRICING_CONTRACT,
                f"Unknown provider pricing contract {contract_id!r}.",
            ) from exc
    if not contracts:
        raise CalculationStrategyExecutionError(
            MISSING_PROVIDER_PRICING_CONTRACT,
            "Calculation strategy has no provider pricing contracts.",
        )
    return contracts
