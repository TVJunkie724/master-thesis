"""Contract tests for trusted Optimizer transfer-pricing evidence."""

from copy import deepcopy

import pytest

from src.services.errors import OptimizerContractError
from src.services.optimizer_transfer_pricing_contract import (
    validate_optimizer_transfer_pricing_result,
)
from tests.optimizer_transfer_pricing_test_data import optimizer_transfer_result
from tests.pricing_catalog_test_data import catalog_context, catalog_reference


def _validate(result=None):
    return validate_optimizer_transfer_pricing_result(
        result or optimizer_transfer_result(),
        catalog_context(),
    )


def test_valid_complete_path_transfer_contract_is_accepted():
    validated = _validate()

    assert len(validated.context.routes) == 6
    assert {pool.provider for pool in validated.context.pools} == {
        "aws",
        "azure",
        "gcp",
    }
    assert validated.diagnostics.winning_candidate_id == (
        "aws|azure|gcp|aws|azure|azure|azure"
    )


def test_all_same_provider_path_requires_no_pricing_pool():
    result = optimizer_transfer_result(
        calculation_result={
            "L1": "Azure",
            "L2": "Azure",
            "L3": {
                "Hot": "Azure",
                "Cool": "Azure",
                "Archive": "Azure",
            },
            "L4": "Azure",
            "L5": "Azure",
        }
    )

    validated = _validate(result)

    assert validated.context.pools == ()
    assert result["transferCosts"] == {}
    assert all(
        route.route_class == "same_provider_same_region"
        for route in validated.context.routes
    )


@pytest.mark.parametrize(
    ("field", "mutate"),
    [
        (
            "transferPricingContext.routes.L1_to_L2.source.region",
            lambda result: result["transferPricingContext"]["routes"][0].update(
                {"source": {
                    **result["transferPricingContext"]["routes"][0]["source"],
                    "region": "eu-west-1",
                }}
            ),
        ),
        (
            "transferPricingContext.routes.L1_to_L2.catalogSnapshotId",
            lambda result: result["transferPricingContext"]["routes"][0].update(
                {
                    "catalogSnapshotId": catalog_reference(
                        "aws",
                        identity_hex="d",
                    ).snapshot_id
                }
            ),
        ),
        (
            "transferPricingContext.pools.pool:aws:test.aggregateVolumeBytes",
            lambda result: result["transferPricingContext"]["pools"][0].update(
                {"aggregateVolumeBytes": 1}
            ),
        ),
        (
            (
                "transferPricingContext.pools."
                "pool:aws:test.tierContributions"
            ),
            lambda result: result["transferPricingContext"]["routes"][0].update(
                {"tierContributions": []}
            ),
        ),
        (
            "transferCosts.L1_to_L2",
            lambda result: result["transferCosts"].update({"L1_to_L2": 1.0}),
        ),
        (
            "optimizationDiagnostics.winningCandidateId",
            lambda result: result["optimizationDiagnostics"].update(
                {
                    "winningCandidateId": (
                        "azure|azure|azure|azure|azure|azure|azure"
                    )
                }
            ),
        ),
    ],
)
def test_cross_contract_mismatches_fail_closed(field, mutate):
    result = deepcopy(optimizer_transfer_result())
    mutate(result)

    with pytest.raises(OptimizerContractError) as exc_info:
        _validate(result)

    assert any(
        error["field"] == field for error in exc_info.value.errors
    )


def test_missing_baseline_route_is_rejected():
    result = deepcopy(optimizer_transfer_result())
    result["transferPricingContext"]["routes"].pop()
    result["transferCosts"].pop("L4_to_L5", None)

    with pytest.raises(OptimizerContractError) as exc_info:
        _validate(result)

    assert any(
        error["field"].startswith("transferPricingContext.routes")
        for error in exc_info.value.errors
    )


def test_route_provider_must_match_selected_complete_path():
    result = deepcopy(optimizer_transfer_result())
    result["calculationResult"]["L1"] = "Azure"

    with pytest.raises(OptimizerContractError) as exc_info:
        _validate(result)

    assert any(
        error["message"]
        == "Route providers do not match the selected complete path"
        for error in exc_info.value.errors
    )


def test_non_string_selected_provider_fails_closed_without_internal_error():
    result = deepcopy(optimizer_transfer_result())
    result["calculationResult"]["L1"] = ["AWS"]

    with pytest.raises(OptimizerContractError) as exc_info:
        _validate(result)

    assert {
        "field": "calculationResult.L1",
        "message": "Selected provider is invalid",
    } in exc_info.value.errors


def test_flat_transfer_cost_rejects_numeric_string_coercion():
    result = deepcopy(optimizer_transfer_result())
    result["transferCosts"]["L1_to_L2"] = "0"

    with pytest.raises(OptimizerContractError) as exc_info:
        _validate(result)

    assert {
        "field": "transferCosts.L1_to_L2",
        "message": "Transfer cost does not match exact route evidence",
    } in exc_info.value.errors


def test_validation_errors_do_not_echo_unknown_secret_values():
    result = deepcopy(optimizer_transfer_result())
    result["transferPricingContext"]["SHOULD_NOT_LEAK"] = "SHOULD_NOT_LEAK"

    with pytest.raises(OptimizerContractError) as exc_info:
        _validate(result)

    assert "SHOULD_NOT_LEAK" not in str(exc_info.value.errors)
    assert any(
        error["field"] == "transferPricingContext"
        for error in exc_info.value.errors
    )
