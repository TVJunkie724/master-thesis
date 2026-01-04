"""
Scenario: AWS→GCP

Tests AWS as L1 sender, GCP as L2 receiver.
L1→L2 boundary: AWS IoT Core → GCP Cloud Functions (via L0 connector)

Provider Configuration:
    L1: AWS (IoT Core)
    L2: GCP (Cloud Functions)
    L3-Hot: Azure (CosmosDB)
    L3-Cold: AWS (S3)
    L3-Archive: GCP (Cloud Storage)
    L4: AWS (TwinMaker)
    L5: Azure (Grafana)
"""
import pytest
from ._base_scenario import BaseScenarioTest, ScenarioConfig


SCENARIO = ScenarioConfig(
    name="aws-gcp",
    description="AWS→GCP: Tests AWS as L1 sender, GCP as L2 receiver",
    providers={
        "layer_1_provider": "aws",
        "layer_2_provider": "google",
        "layer_3_hot_provider": "azure",
        "layer_3_cold_provider": "aws",
        "layer_3_archive_provider": "google",
        "layer_4_provider": "aws",
        "layer_5_provider": "azure",
    },
)


@pytest.mark.live
class TestScenarioAwsGcp(BaseScenarioTest):
    """E2E test for AWS→GCP scenario."""
    SCENARIO = SCENARIO
