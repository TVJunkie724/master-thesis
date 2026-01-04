"""
Scenario: GCP→Azure

Tests GCP as L1 sender, Azure as L2 receiver.
L1→L2 boundary: GCP Pub/Sub → Azure Functions (via L0 connector)

Provider Configuration:
    L1: GCP (Pub/Sub)
    L2: Azure (Functions)
    L3-Hot: AWS (DynamoDB)
    L3-Cold: GCP (Cloud Storage)
    L3-Archive: Azure (Blob Storage)
    L4: Azure (Digital Twins)
    L5: AWS (Grafana)
"""
import pytest
from ._base_scenario import BaseScenarioTest, ScenarioConfig


SCENARIO = ScenarioConfig(
    name="gcp-azure",
    description="GCP→Azure: Tests GCP as L1 sender, Azure as L2 receiver",
    providers={
        "layer_1_provider": "google",
        "layer_2_provider": "azure",
        "layer_3_hot_provider": "aws",
        "layer_3_cold_provider": "google",
        "layer_3_archive_provider": "azure",
        "layer_4_provider": "azure",
        "layer_5_provider": "aws",
    },
)


@pytest.mark.live
class TestScenarioGcpAzure(BaseScenarioTest):
    """E2E test for GCP→Azure scenario."""
    SCENARIO = SCENARIO
