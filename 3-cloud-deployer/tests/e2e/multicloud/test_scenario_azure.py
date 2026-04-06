"""
Scenario: Azure (Single Cloud)

Tests complete Azure data flow with no cross-cloud boundaries.
All layers on Azure - validates native Azure integrations without L0 glue.

Provider Configuration:
    L1: Azure (IoT Hub)
    L2: Azure (Functions)
    L3-Hot: Azure (Cosmos DB)
    L3-Cold: Azure (Blob Storage)
    L3-Archive: Azure (Blob Archive)
    L4: Azure (Digital Twins)
    L5: Azure (Grafana)
"""
import pytest
from ._base_scenario import BaseScenarioTest, ScenarioConfig

SCENARIO = ScenarioConfig(
    name="azure",
    description="Azure Single Cloud: Full Azure stack, no cross-cloud boundaries",
    providers={
        "layer_1_provider": "azure",
        "layer_2_provider": "azure",
        "layer_3_hot_provider": "azure",
        "layer_3_cold_provider": "azure",
        "layer_3_archive_provider": "azure",
        "layer_4_provider": "azure",
        "layer_5_provider": "azure",
    },
)


@pytest.mark.live
class TestScenarioAzure(BaseScenarioTest):
    """E2E test for Azure single-cloud scenario."""
    SCENARIO = SCENARIO
