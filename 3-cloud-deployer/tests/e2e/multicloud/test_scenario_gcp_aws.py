"""
Scenario: GCP→AWS

Tests GCP as L1 sender, AWS as L2 receiver.
L1→L2 boundary: GCP Pub/Sub → AWS Lambda (via L0 connector)

Provider Configuration:
    L1: GCP (Pub/Sub)
    L2: AWS (Lambda)
    L3-Hot: Azure (CosmosDB)
    L3-Cold: GCP (Cloud Storage)
    L3-Archive: AWS (S3)
    L4: AWS (TwinMaker)
    L5: Azure (Grafana)
"""
import pytest
from ._base_scenario import BaseScenarioTest, ScenarioConfig


SCENARIO = ScenarioConfig(
    name="gcp-aws",
    description="GCP→AWS: Tests GCP as L1 sender, AWS as L2 receiver",
    providers={
        "layer_1_provider": "google",
        "layer_2_provider": "aws",
        "layer_3_hot_provider": "azure",
        "layer_3_cold_provider": "google",
        "layer_3_archive_provider": "aws",
        "layer_4_provider": "aws",
        "layer_5_provider": "azure",
    },
)


@pytest.mark.live
class TestScenarioGcpAws(BaseScenarioTest):
    """E2E test for GCP→AWS scenario."""
    SCENARIO = SCENARIO
