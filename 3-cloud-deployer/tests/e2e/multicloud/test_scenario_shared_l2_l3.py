"""
Scenario: Shared-L2-L3 (L2 = L3-Cold)

Tests the edge case where L2 and L3-Cold are on the same provider
while L3-Hot is on a different provider. This triggers the cold-writer
cross-cloud boundary (L3-Hot → L3-Cold) which was previously broken
when the registry used the wrong boundary (L2 → L3-Cold).

Provider Configuration:
    L1: GCP (IoT Core)
    L2: AWS (Lambda)
    L3-Hot: GCP (Firestore)
    L3-Cold: AWS (S3) — same as L2!
    L3-Archive: Azure (Blob Storage)
    L4: AWS (TwinMaker)
    L5: AWS (Grafana)

Key boundary tested:
    L3-Hot(GCP) → L3-Cold(AWS): cold-writer must be built for AWS
    despite L2 also being AWS (old bug: L2 == L3-Cold skipped the build)
"""
import pytest
from ._base_scenario import BaseScenarioTest, ScenarioConfig


SCENARIO = ScenarioConfig(
    name="shared-l2-l3",
    description="Shared-L2-L3: Tests L2=L3-Cold same provider with L3-Hot on different cloud",
    providers={
        "layer_1_provider": "google",
        "layer_2_provider": "aws",
        "layer_3_hot_provider": "google",
        "layer_3_cold_provider": "aws",
        "layer_3_archive_provider": "azure",
        "layer_4_provider": "aws",
        "layer_5_provider": "aws",
    },
)


@pytest.mark.live
class TestScenarioSharedL2L3(BaseScenarioTest):
    """E2E test for Shared-L2-L3 scenario."""
    SCENARIO = SCENARIO
