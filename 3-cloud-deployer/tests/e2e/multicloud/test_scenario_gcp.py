"""
Scenario: GCP (Single Cloud)

Tests complete GCP data flow with no cross-cloud boundaries.
All layers on GCP - validates native GCP integrations without L0 glue.

Note: GCP does not have managed Digital Twins (L4) or Grafana (L5) services,
so those layers are set to "none".

Provider Configuration:
    L1: GCP (Pub/Sub)
    L2: GCP (Cloud Functions)
    L3-Hot: GCP (Firestore)
    L3-Cold: GCP (Cloud Storage)
    L3-Archive: GCP (Cloud Storage Archive)
    L4: none (GCP has no managed Digital Twins)
    L5: none (GCP has no managed Grafana)
"""
import pytest
from ._base_scenario import BaseScenarioTest, ScenarioConfig

SCENARIO = ScenarioConfig(
    name="gcp",
    description="GCP Single Cloud: Full GCP stack, L4/L5 unavailable",
    providers={
        "layer_1_provider": "google",
        "layer_2_provider": "google",
        "layer_3_hot_provider": "google",
        "layer_3_cold_provider": "google",
        "layer_3_archive_provider": "google",
        "layer_4_provider": "none",
        "layer_5_provider": "none",
    },
)


@pytest.mark.live
class TestScenarioGcp(BaseScenarioTest):
    """E2E test for GCP single-cloud scenario."""
    SCENARIO = SCENARIO
