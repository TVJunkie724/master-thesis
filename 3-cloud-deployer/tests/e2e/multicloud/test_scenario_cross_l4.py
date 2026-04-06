"""
Scenario: Cross-L4 (AWS L2 → Azure L4)

This scenario specifically tests the AWS L2 → Azure L4 boundary,
which is NOT covered by the other 6 cross-cloud scenarios.

Why this matters: The optimizer may select:
- L2 = AWS (cheapest for processing workload)
- L4 = Azure ADT (cheapest for digital twins)

This boundary uses: AWS Persister → ADT Pusher (Azure) → Azure Digital Twins

Provider Configuration:
    L1: Azure (IoT Hub)
    L2: AWS (Lambda) ← KEY: Processing on AWS
    L3-Hot: GCP (Firestore)
    L3-Cold: Azure (Blob Storage)
    L3-Archive: AWS (S3 Glacier)
    L4: Azure (Digital Twins) ← KEY: Twins on Azure
    L5: Azure (Grafana)
"""
import pytest
from ._base_scenario import BaseScenarioTest, ScenarioConfig

SCENARIO = ScenarioConfig(
    name="cross-l4",
    description="Cross-L4: Tests AWS Persister → Azure ADT boundary",
    providers={
        "layer_1_provider": "azure",
        "layer_2_provider": "aws",
        "layer_3_hot_provider": "google",
        "layer_3_cold_provider": "azure",
        "layer_3_archive_provider": "aws",
        "layer_4_provider": "azure",  # KEY: ADT on Azure while L2 is AWS
        "layer_5_provider": "azure",
    },
)


@pytest.mark.live
class TestScenarioCrossL4(BaseScenarioTest):
    """E2E test for cross-cloud L2→L4 boundary (AWS→Azure ADT)."""
    SCENARIO = SCENARIO
