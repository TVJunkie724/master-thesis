import pytest

from backend.calculation_v2.layers import (
    AWSLayerCalculators,
    AzureLayerCalculators,
    BaseLayerCalculatorSet,
    ComponentDeploymentSelection,
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
    for layer in SUPPORTED_LAYER_KEYS:
        assert calculator.supports(layer) is (layer in supported_layers)


def test_capability_contract_rejects_unknown_layer():
    with pytest.raises(ValueError, match="Unknown architecture layer"):
        AWSLayerCalculators().supports("L9")


def test_base_contract_rejects_invalid_provider_declaration():
    with pytest.raises(TypeError, match="Unknown layer calculator provider"):

        class InvalidProviderCalculators(BaseLayerCalculatorSet):
            provider = "Other"
            supported_layers = frozenset({"L1"})


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
        {"provider": "Other", "layer": "L1", "total_cost": 1.0},
        {"provider": "AWS", "layer": "L1", "total_cost": True},
        {
            "provider": "AWS",
            "layer": "L1",
            "total_cost": 1.0,
            "supported": 1,
        },
        {
            "provider": "AWS",
            "layer": "L1",
            "total_cost": 1.0,
            "supported": False,
            "unsupported_reason": 42,
        },
        {
            "provider": "AWS",
            "layer": "L1",
            "total_cost": 1.0,
            "components": {"": 1.0},
        },
        {
            "provider": "AWS",
            "layer": "L1",
            "total_cost": 1.0,
            "components": None,
        },
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


def test_layer_result_owns_an_immutable_component_snapshot():
    components = {"service": 1}
    result = LayerResult(
        provider="AWS",
        layer="L1",
        total_cost=1,
        components=components,
    )

    components["service"] = 2

    assert result.components == {"service": 1.0}
    with pytest.raises(TypeError):
        result.components["service"] = 3


def test_layer_result_owns_a_deeply_immutable_detail_snapshot():
    details = {"diagnostic": {"states": ["ready"]}}
    result = LayerResult(
        provider="AWS",
        layer="L1",
        total_cost=1,
        details=details,
    )

    details["diagnostic"]["states"].append("changed")

    assert result.details_as_dict() == {
        "diagnostic": {"states": ["ready"]}
    }
    with pytest.raises(TypeError):
        result.details["diagnostic"]["state"] = "changed"


def test_component_deployment_selection_owns_an_immutable_snapshot():
    dimensions = {"aws.lambda.memory_mb": 256}
    selection = ComponentDeploymentSelection(
        "l1.aws.dispatcher_lambda",
        dimensions,
    )

    dimensions["aws.lambda.memory_mb"] = 512

    assert selection.as_dict() == {
        "componentId": "l1.aws.dispatcher_lambda",
        "dimensions": {"aws.lambda.memory_mb": 256},
    }
    with pytest.raises(TypeError):
        selection.dimensions["aws.lambda.memory_mb"] = 128


@pytest.mark.parametrize(
    ("component_id", "dimensions"),
    [
        ("", {"dimension": 1}),
        ("component", {}),
        ("component", {"": 1}),
        ("component", {"dimension": 1.0}),
        ("component", {"dimension": []}),
        ("component", {"dimension": ""}),
    ],
)
def test_component_deployment_selection_rejects_invalid_values(
    component_id,
    dimensions,
):
    with pytest.raises(ValueError):
        ComponentDeploymentSelection(component_id, dimensions)


def test_layer_result_requires_unique_typed_deployment_selections():
    selection = ComponentDeploymentSelection(
        "l1.aws.iot_core",
        {"aws.iot_core.message_pricing": "progressive_usage"},
    )

    with pytest.raises(ValueError, match="must be a tuple"):
        LayerResult(
            provider="AWS",
            layer="L1",
            total_cost=1,
            deployment_selections=[selection],
        )
    with pytest.raises(ValueError, match="must be unique"):
        LayerResult(
            provider="AWS",
            layer="L1",
            total_cost=1,
            deployment_selections=(selection, selection),
        )
