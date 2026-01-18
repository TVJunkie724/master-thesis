"""
Scenario: Azure→AWS

Tests Azure as L1 sender, AWS as L2 receiver.
L1→L2 boundary: Azure IoT Hub → AWS Lambda (via L0 connector)

Provider Configuration:
    L1: Azure (IoT Hub)
    L2: AWS (Lambda)
    L3-Hot: GCP (Firestore)
    L3-Cold: Azure (Blob Storage)
    L3-Archive: AWS (S3)
    L4: AWS (TwinMaker)
    L5: Azure (Grafana)
"""
import pytest
from ._base_scenario import BaseScenarioTest, ScenarioConfig


SCENARIO = ScenarioConfig(
    name="azure-aws",
    description="Azure→AWS: Tests Azure as L1 sender, AWS as L2 receiver",
    providers={
        "layer_1_provider": "azure",
        "layer_2_provider": "aws",
        "layer_3_hot_provider": "google",
        "layer_3_cold_provider": "azure",
        "layer_3_archive_provider": "aws",
        "layer_4_provider": "aws",
        "layer_5_provider": "azure",
    },
)


@pytest.mark.live
class TestScenarioAzureAws(BaseScenarioTest):
    """E2E test for Azure→AWS scenario."""
    SCENARIO = SCENARIO
