"""
Scenario: Azure→GCP

Tests Azure as L1 sender, GCP as L2 receiver.
L1→L2 boundary: Azure IoT Hub → GCP Cloud Functions (via L0 connector)

Provider Configuration:
    L1: Azure (IoT Hub)
    L2: GCP (Cloud Functions)
    L3-Hot: AWS (DynamoDB)
    L3-Cold: Azure (Blob Storage)
    L3-Archive: GCP (Cloud Storage)
    L4: Azure (Digital Twins)
    L5: AWS (Grafana)
"""
import pytest
from ._base_scenario import BaseScenarioTest, ScenarioConfig


SCENARIO = ScenarioConfig(
    name="azure-gcp",
    description="Azure→GCP: Tests Azure as L1 sender, GCP as L2 receiver",
    providers={
        "layer_1_provider": "azure",
        "layer_2_provider": "google",
        "layer_3_hot_provider": "aws",
        "layer_3_cold_provider": "azure",
        "layer_3_archive_provider": "google",
        "layer_4_provider": "azure",
        "layer_5_provider": "aws",
    },
)


@pytest.mark.live
class TestScenarioAzureGcp(BaseScenarioTest):
    """E2E test for Azure→GCP scenario."""
    SCENARIO = SCENARIO
