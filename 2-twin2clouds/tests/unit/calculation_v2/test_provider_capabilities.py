import pytest
from pydantic import ValidationError

from backend.calculation_v2.layers.aws_layers import AWSLayerCalculators
from backend.calculation_v2.layers.azure_layers import AzureLayerCalculators
from backend.calculation_v2.layers.gcp_layers import GCPLayerCalculators
from backend.provider_capabilities import (
    LAYER_IDS,
    CapabilityAvailability,
    CapabilityVerificationLevel,
    ProviderLayerCapability,
    get_provider_capabilities,
)


def test_capability_registry_matches_calculator_contracts():
    contract = get_provider_capabilities()
    calculators = {
        "aws": AWSLayerCalculators,
        "azure": AzureLayerCalculators,
        "gcp": GCPLayerCalculators,
    }
    calculator_layers = {
        "l1": "L1",
        "l2": "L2",
        "l3_hot": "L3_hot",
        "l3_cool": "L3_cool",
        "l3_archive": "L3_archive",
        "l4": "L4",
        "l5": "L5",
    }

    assert contract.schema_version == "provider-service-capabilities.v1"
    assert len(contract.providers) == 3
    for provider in contract.providers:
        assert tuple(layer.layer for layer in provider.layers) == LAYER_IDS
        supported = calculators[provider.provider].supported_layers
        for layer in provider.layers:
            assert (layer.availability is CapabilityAvailability.AVAILABLE) is (
                calculator_layers[layer.layer] in supported
            )


def test_gcp_l4_and_l5_are_explicitly_planned_but_not_available():
    contract = get_provider_capabilities()
    gcp = next(item for item in contract.providers if item.provider == "gcp")

    for layer_id in ("l4", "l5"):
        layer = next(item for item in gcp.layers if item.layer == layer_id)
        assert layer.availability is CapabilityAvailability.UNSUPPORTED
        assert layer.roadmap.value == "planned"
        assert layer.reason_code == "CALCULATION_NOT_IMPLEMENTED"
        assert layer.verification_level is CapabilityVerificationLevel.NOT_VERIFIED


def test_unavailable_capability_requires_actionable_reason():
    with pytest.raises(ValidationError, match="reason code and reason"):
        ProviderLayerCapability(
            layer="l4",
            availability=CapabilityAvailability.UNSUPPORTED,
            verification_level=CapabilityVerificationLevel.NOT_VERIFIED,
        )
