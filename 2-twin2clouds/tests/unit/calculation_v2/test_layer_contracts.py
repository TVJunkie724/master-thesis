import pytest

from backend.calculation_v2.layers import (
    AWSLayerCalculators,
    AzureLayerCalculators,
    GCPLayerCalculators,
    LayerCalculatorSet,
    LayerResult,
    SUPPORTED_LAYER_KEYS,
)


@pytest.mark.parametrize(
    ("calculator", "provider", "supported_layers"),
    [
        (AWSLayerCalculators(), "AWS", SUPPORTED_LAYER_KEYS),
        (AzureLayerCalculators(), "Azure", SUPPORTED_LAYER_KEYS),
        (
            GCPLayerCalculators(),
            "GCP",
            SUPPORTED_LAYER_KEYS - {"L4", "L5"},
        ),
    ],
)
def test_provider_calculators_share_capability_contract(
    calculator,
    provider,
    supported_layers,
):
    assert isinstance(calculator, LayerCalculatorSet)
    assert calculator.provider == provider
    assert calculator.supported_layers == supported_layers


def test_gcp_marks_unimplemented_layers_as_unsupported():
    calculator = GCPLayerCalculators()

    l4 = calculator.calculate_l4_cost({})
    l5 = calculator.calculate_l5_cost({})

    assert not l4.supported
    assert not l5.supported
    assert "not implemented" in l4.unsupported_reason
    assert "not implemented" in l5.unsupported_reason
    assert "L4" not in calculator.supported_layers
    assert "L5" not in calculator.supported_layers


@pytest.mark.parametrize(
    "kwargs",
    [
        {"provider": "AWS", "layer": "L9", "total_cost": 1.0},
        {"provider": "AWS", "layer": "L1", "total_cost": -1.0},
        {"provider": "AWS", "layer": "L1", "total_cost": float("inf")},
        {
            "provider": "AWS",
            "layer": "L1",
            "total_cost": 1.0,
            "supported": False,
        },
    ],
)
def test_layer_result_rejects_invalid_or_ambiguous_values(kwargs):
    with pytest.raises(ValueError):
        LayerResult(**kwargs)
