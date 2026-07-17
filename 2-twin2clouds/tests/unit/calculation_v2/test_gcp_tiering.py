"""GCP unit and tier-aware calculation regression tests."""

import pytest

from backend.calculation_v2.components.gcp import (
    GCPCloudFunctionsCalculator,
    GCPCloudWorkflowsCalculator,
    GCPComputeEngineCalculator,
    GCPFirestoreCalculator,
    GCPPubSubCalculator,
    GCSColdlineCalculator,
    GCSNearlineCalculator,
)
from backend.calculation_v2.engine import _calculate_egress_cost
from tests.unit.pricing.transfer_fixtures import canonical_transfer_catalog


def _gcp_pricing(**overrides):
    base = {
        "iot": {
            "pricing_tiers": {
                "freeTier": {"limit": 10, "price": 0},
                "tier1": {"limit": 1_024, "price": 0.04},
                "tier2": {"limit": "Infinity", "price": 0.03},
            },
            "storagePrice": 0.27,
            "transferPrice": 0.12,
        },
        "functions": {
            "pricePerMillionRequests": 0.40,
            "gbSecondPrice": 0.0000025,
            "freeRequests": 2_000_000,
            "freeComputeTime": 400_000,
        },
        "cloudWorkflows": {
            "pricePer1kInternalSteps": 0.01,
            "pricePer1kExternalSteps": 0.025,
        },
        "storage_hot": {
            "writePricePer100kWrites": 0.18,
            "readPricePer100kReads": 0.03,
            "deletePricePer100kDeletes": 0.02,
            "indexEntryReadPricePer100kReads": 0.06,
            "storagePrice": 0.18,
            "freeStorage": 1,
        },
        "storage_cool": {
            "storagePrice": 0.01,
            "writePricePer10kRequests": 0.10,
            "readPricePer10kRequests": 0.01,
            "dataRetrievalPrice": 0.01,
        },
        "storage_archive": {
            "storagePrice": 0.0012,
            "lifecycleAndWritePricePer10kRequests": 0.50,
            "readPricePer10kRequests": 0.05,
            "dataRetrievalPrice": 0.05,
        },
        "twinmaker": {
            "e2MediumPrice": 0.0608511,
            "storagePrice": 0.20,
        },
        "grafana": {
            "e2MediumPrice": 0.0608511,
            "storagePrice": 0.20,
        },
        "transfer": canonical_transfer_catalog("gcp"),
    }
    base.update(overrides)
    return {"gcp": base}


class TestGCPPubSubTiering:
    def test_pubsub_uses_tiered_throughput_storage_and_transfer_prices(self):
        result = GCPPubSubCalculator().calculate_cost(
            data_volume_gb=1_500,
            messages_per_month=100,
            average_message_size_kb=2048,
            storage_gb=10,
            transfer_gb=5,
            pricing=_gcp_pricing(),
        )

        expected_throughput = ((1_024 - 10) * 0.04) + ((1_500 - 1_024) * 0.03)
        expected = expected_throughput + (10 * 0.27) + (5 * 0.12)
        assert result == pytest.approx(expected)

    def test_pubsub_applies_one_kb_minimum_when_message_size_is_smaller(self):
        result = GCPPubSubCalculator().calculate_cost(
            data_volume_gb=0.1,
            messages_per_month=1_048_576,
            average_message_size_kb=0.25,
            pricing=_gcp_pricing(iot={"pricePerGiB": 0.04}),
        )

        assert result == pytest.approx(1.0 * 0.04)

    def test_pubsub_missing_throughput_price_fails_visibly(self):
        with pytest.raises(ValueError, match="gcp.pubsub.throughput"):
            GCPPubSubCalculator().calculate_cost(
                data_volume_gb=1,
                pricing=_gcp_pricing(iot={}),
            )


class TestGCPCloudFunctionsUnits:
    def test_functions_normalize_per_million_request_price(self):
        result = GCPCloudFunctionsCalculator().calculate_cost(
            executions=3_000_000,
            duration_ms=1000,
            memory_mb=1024,
            pricing=_gcp_pricing(),
        )

        expected = (1_000_000 * 0.0000004) + ((3_000_000 - 400_000) * 0.0000025)
        assert result == pytest.approx(expected)

    def test_functions_missing_request_price_fails_visibly(self):
        with pytest.raises(ValueError, match="gcp.functions.request"):
            GCPCloudFunctionsCalculator().calculate_cost(
                executions=1,
                pricing=_gcp_pricing(functions={"gbSecondPrice": 0.0000025}),
            )


class TestGCPFirestoreUnits:
    def test_firestore_normalizes_operation_blocks_and_free_storage(self):
        result = GCPFirestoreCalculator().calculate_cost(
            writes_per_month=200_000,
            reads_per_month=300_000,
            deletes_per_month=100_000,
            index_entry_reads_per_month=50_000,
            storage_gb=3,
            pricing=_gcp_pricing(),
        )

        expected = (2 * 0.18) + (3 * 0.03) + 0.02 + (0.5 * 0.06) + (2 * 0.18)
        assert result == pytest.approx(expected)

    def test_firestore_missing_storage_price_fails_visibly(self):
        with pytest.raises(ValueError, match="gcp.firestore.storage"):
            GCPFirestoreCalculator().calculate_cost(
                writes_per_month=1,
                reads_per_month=1,
                storage_gb=1,
                pricing=_gcp_pricing(storage_hot={
                    "writePrice": 0.0000018,
                    "readPrice": 0.0000003,
                }),
            )


class TestGCPCloudStorageUnits:
    def test_nearline_normalizes_operation_blocks_and_retrieval(self):
        result = GCSNearlineCalculator().calculate_cost(
            storage_gb=100,
            writes_per_month=20_000,
            reads_per_month=30_000,
            retrievals_gb=10,
            pricing=_gcp_pricing(),
        )

        expected = 1.0 + (2 * 0.10) + (3 * 0.01) + (10 * 0.01)
        assert result == pytest.approx(expected)

    def test_coldline_normalizes_lifecycle_operation_blocks_and_retrieval(self):
        result = GCSColdlineCalculator().calculate_cost(
            storage_gb=100,
            writes_per_month=20_000,
            reads_per_month=10_000,
            retrievals_gb=10,
            pricing=_gcp_pricing(),
        )

        expected = 0.12 + (2 * 0.50) + 0.05 + (10 * 0.05)
        assert result == pytest.approx(expected)

    def test_nearline_missing_request_price_fails_visibly(self):
        with pytest.raises(ValueError, match="gcp.storage_cool.write"):
            GCSNearlineCalculator().calculate_cost(
                storage_gb=1,
                writes_per_month=1,
                pricing=_gcp_pricing(storage_cool={"storagePrice": 0.01}),
            )


class TestGCPWorkflowsUnits:
    def test_workflows_distinguish_internal_and_external_step_prices(self):
        result = GCPCloudWorkflowsCalculator().calculate_cost(
            executions=10,
            steps_per_execution=5,
            external_steps_per_execution=2,
            pricing=_gcp_pricing(),
        )

        expected = (30 * 0.00001) + (20 * 0.000025)
        assert result == pytest.approx(expected)

    def test_workflows_legacy_per_step_key_remains_supported(self):
        result = GCPCloudWorkflowsCalculator().calculate_cost(
            executions=10,
            steps_per_execution=5,
            pricing=_gcp_pricing(cloudWorkflows={"stepPrice": 0.000001}),
        )

        assert result == pytest.approx(50 * 0.000001)

    def test_workflows_missing_step_price_fails_visibly(self):
        with pytest.raises(ValueError, match="gcp.workflows.step"):
            GCPCloudWorkflowsCalculator().calculate_cost(
                executions=1,
                pricing=_gcp_pricing(cloudWorkflows={}),
            )


class TestGCPComputeUnits:
    def test_compute_separates_vm_hours_and_disk_storage(self):
        result = GCPComputeEngineCalculator().calculate_twinmaker_cost(
            pricing=_gcp_pricing(),
            hours_per_month=100,
            disk_gb=20,
        )

        assert result == pytest.approx((100 * 0.0608511) + (20 * 0.20))

    def test_compute_missing_disk_price_fails_visibly_when_disk_is_used(self):
        with pytest.raises(ValueError, match="gcp.compute.twinmaker.disk_storage"):
            GCPComputeEngineCalculator().calculate_twinmaker_cost(
                pricing=_gcp_pricing(twinmaker={"e2MediumPrice": 0.0608511}),
                disk_gb=1,
            )


class TestGCPTransferTiering:
    def test_gcp_egress_converts_decimal_gb_to_provider_gib_tiers(self):
        result = _calculate_egress_cost(
            data_gb=1_181.1160064,
            pricing=_gcp_pricing(),
            source_provider="GCP",
        )

        expected = (1_024 - 1) * 0.12 + (1_100 - 1_024) * 0.11
        assert result == pytest.approx(expected)

    def test_gcp_egress_missing_price_fails_visibly(self):
        with pytest.raises(ValueError, match="gcp.transfer.catalog"):
            _calculate_egress_cost(
                data_gb=1,
                pricing=_gcp_pricing(transfer={}),
                source_provider="GCP",
            )
