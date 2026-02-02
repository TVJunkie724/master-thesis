"""
Scenario: AWS (Single Cloud)

Tests complete AWS data flow with no cross-cloud boundaries.
All layers on AWS - validates native AWS integrations without L0 glue.

Provider Configuration:
    L1: AWS (IoT Core)
    L2: AWS (Lambda)
    L3-Hot: AWS (DynamoDB)
    L3-Cold: AWS (S3)
    L3-Archive: AWS (S3 Glacier)
    L4: AWS (TwinMaker)
    L5: AWS (Grafana)
"""
import pytest
from ._base_scenario import BaseScenarioTest, ScenarioConfig

SCENARIO = ScenarioConfig(
    name="aws",
    description="AWS Single Cloud: Full AWS stack, no cross-cloud boundaries",
    providers={
        "layer_1_provider": "aws",
        "layer_2_provider": "aws",
        "layer_3_hot_provider": "aws",
        "layer_3_cold_provider": "aws",
        "layer_3_archive_provider": "aws",
        "layer_4_provider": "aws",
        "layer_5_provider": "aws",
    },
)


@pytest.mark.live
class TestScenarioAws(BaseScenarioTest):
    """E2E test for AWS single-cloud scenario."""
    SCENARIO = SCENARIO
