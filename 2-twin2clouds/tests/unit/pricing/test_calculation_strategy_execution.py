import pytest

from backend.calculation_v2.engine import calculate_cheapest_costs
from backend.calculation_v2.strategy_context import (
    CalculationStrategyExecutionError,
    FORMULA_REF_NOT_ALLOWED,
    MISSING_PROVIDER_PRICING_CONTRACT,
    UNKNOWN_FORMULA_SET,
    resolve_calculation_strategy_execution_context,
)
from backend.pricing_registry_service import (
    PricingRegistryLookupError,
    PricingRegistryService,
)
from tests.unit.calculation_v2.test_engine_consistency import (
    REALISTIC_PRICING,
    STANDARD_PARAMS,
)
from tests.unit.pricing.transfer_fixtures import pricing_catalog_context_for


class DriftedPricingRegistryService(PricingRegistryService):
    def __init__(self, *, strategy_overrides=None, missing_formula_sets=None, missing_contracts=None):
        super().__init__()
        self.strategy_overrides = strategy_overrides or {}
        self.missing_formula_sets = set(missing_formula_sets or [])
        self.missing_contracts = set(missing_contracts or [])

    def get_calculation_strategy(self, strategy_id):
        strategy = super().get_calculation_strategy(strategy_id)
        strategy.update(self.strategy_overrides)
        return strategy

    def get_formula_set(self, formula_set_id):
        if formula_set_id in self.missing_formula_sets:
            raise PricingRegistryLookupError(f"Unknown formula set: {formula_set_id}")
        return super().get_formula_set(formula_set_id)

    def get_provider_pricing_contract_by_id(self, contract_id):
        if contract_id in self.missing_contracts:
            raise PricingRegistryLookupError(
                f"Unknown provider pricing contract: {contract_id}"
            )
        return super().get_provider_pricing_contract_by_id(contract_id)


def test_calculation_result_contains_strategy_context_metadata():
    result = calculate_cheapest_costs(
        STANDARD_PARAMS,
        REALISTIC_PRICING,
        pricing_catalog_context=pricing_catalog_context_for(REALISTIC_PRICING),
    )
    expected_contracts = PricingRegistryService().get_status()[
        "provider_pricing_contract_count"
    ]

    assert result["calculation_strategy_id"] == "cost_calculation_v2"
    assert result["calculationStrategy"]["calculation_strategy_id"] == "cost_calculation_v2"
    assert result["calculationStrategy"]["formula_set_id"] == "cost_formula_set_v1"
    assert result["calculationStrategy"]["workload_contract_id"] == "digital_twin_workload_v1"
    assert result["calculationStrategy"]["pricing_contract_group_id"] == (
        "cost_provider_pricing_contracts_v1"
    )
    assert (
        len(result["calculationStrategy"]["provider_pricing_contract_ids"])
        == expected_contracts
    )
    assert result["evidenceReferences"]["calculation_strategy"] == (
        "calculation_strategy:cost_calculation_v2"
    )
    assert result["evidenceReferences"]["formula_set"] == "formula_set:cost_formula_set_v1"


def test_unknown_formula_set_fails_before_provider_calculation():
    service = DriftedPricingRegistryService(
        strategy_overrides={"formula_set_id": "does_not_exist"},
        missing_formula_sets={"does_not_exist"},
    )

    with pytest.raises(CalculationStrategyExecutionError) as exc:
        calculate_cheapest_costs(
            STANDARD_PARAMS,
            REALISTIC_PRICING,
            pricing_catalog_context=pricing_catalog_context_for(
                REALISTIC_PRICING
            ),
            pricing_registry_service=service,
        )

    assert exc.value.error_code == UNKNOWN_FORMULA_SET


def test_missing_provider_pricing_contract_fails_before_provider_calculation():
    service = DriftedPricingRegistryService(
        missing_contracts={"aws.transfer_egress_gb.pricing_contract.v1"}
    )

    with pytest.raises(CalculationStrategyExecutionError) as exc:
        calculate_cheapest_costs(
            STANDARD_PARAMS,
            REALISTIC_PRICING,
            pricing_catalog_context=pricing_catalog_context_for(
                REALISTIC_PRICING
            ),
            pricing_registry_service=service,
        )

    assert exc.value.error_code == MISSING_PROVIDER_PRICING_CONTRACT


def test_formula_ref_outside_active_formula_set_is_rejected():
    context = resolve_calculation_strategy_execution_context()

    with pytest.raises(CalculationStrategyExecutionError) as exc:
        context.ensure_formula_ref("does_not_exist")

    assert exc.value.error_code == FORMULA_REF_NOT_ALLOWED


def test_provider_contract_lookup_requires_compatible_field():
    context = resolve_calculation_strategy_execution_context()

    with pytest.raises(CalculationStrategyExecutionError) as exc:
        context.get_provider_contract("aws", "does.not.exist")

    assert exc.value.error_code == MISSING_PROVIDER_PRICING_CONTRACT
