"""
Scenario: AWS→Azure

Tests AWS as L1 sender, Azure as L2 receiver.
L1→L2 boundary: AWS IoT Core → Azure Functions (via L0 connector)

Provider Configuration:
    L1: AWS (IoT Core)
    L2: Azure (Functions)
    L3-Hot: GCP (Firestore)
    L3-Cold: AWS (S3)
    L3-Archive: Azure (Blob Storage)
    L4: Azure (Digital Twins)
    L5: AWS (Grafana)
"""
import pytest
from ._base_scenario import BaseScenarioTest, ScenarioConfig


SCENARIO = ScenarioConfig(
    name="aws-azure",
    description="AWS→Azure: Tests AWS as L1 sender, Azure as L2 receiver",
    providers={
        "layer_1_provider": "aws",
        "layer_2_provider": "azure",
        "layer_3_hot_provider": "google",
        "layer_3_cold_provider": "aws",
        "layer_3_archive_provider": "azure",
        "layer_4_provider": "azure",
        "layer_5_provider": "aws",
    },
)


@pytest.mark.live
class TestScenarioAwsAzure(BaseScenarioTest):
    """E2E test for AWS→Azure scenario."""
    SCENARIO = SCENARIO
