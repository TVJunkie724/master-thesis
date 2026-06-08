"""AWS unit and tier-aware calculation regression tests."""

import pytest

from backend.calculation_v2.components.aws import (
    AWSEventBridgeCalculator,
    AWSIoTCoreCalculator,
    AWSS3GlacierCalculator,
    AWSS3IACalculator,
    AWSStepFunctionsCalculator,
    AWSTwinMakerCalculator,
)
from backend.calculation_v2.engine import _calculate_egress_cost


def _aws_pricing(**overrides):
    base = {
        "iotCore": {
            "pricePerDeviceAndMonth": 0.25,
            "priceRulesTriggered": 0.00000015,
            "pricing_tiers": {
                "tier1": {"limit": 1_000_000_000, "pricePerMillionMessages": 1.00},
                "tier2": {"limit": 5_000_000_000, "pricePerMillionMessages": 0.80},
                "tier3": {"limit": "Infinity", "pricePerMillionMessages": 0.70},
            },
        },
        "s3InfrequentAccess": {
            "storagePrice": 0.0125,
            "writePricePer1kRequests": 0.01,
            "dataRetrievalPrice": 0.01,
        },
        "s3GlacierDeepArchive": {
            "storagePrice": 0.00099,
            "lifecycleAndWritePricePer1kRequests": 0.05,
            "dataRetrievalPrice": 0.02,
        },
        "iotTwinMaker": {
            "pricePerEntity": 0.05,
            "pricePerQuery": 0.00001,
            "pricePerUnifiedDataAccessAPICall": 0.000001,
            "modelStoragePrice": 0.023,
        },
        "stepFunctions": {"pricePer1kStateTransitions": 0.025},
        "eventBridge": {"pricePerEvent": 0.000001},
        "transfer": {
            "pricing_tiers": {
                "freeTier": {"limit": 100, "price": 0},
                "tier1": {"limit": 10_240, "price": 0.09},
                "tier2": {"limit": 51_200, "price": 0.085},
                "tier3": {"limit": "Infinity", "price": 0.07},
            }
        },
    }
    base.update(overrides)
    return {"aws": base}


class TestAWSIoTCoreTiering:
    def test_iot_core_tiers_normalize_price_per_million_messages(self):
        result = AWSIoTCoreCalculator().calculate_cost(
            number_of_devices=0,
            messages_per_month=1_500_000_000,
            average_message_size_kb=1,
            pricing=_aws_pricing(iotCore={
                "pricePerDeviceAndMonth": 0,
                "priceRulesTriggered": 0,
                "pricing_tiers": {
                    "tier1": {"limit": 1_000_000_000, "pricePerMillionMessages": 1.00},
                    "tier2": {"limit": 5_000_000_000, "pricePerMillionMessages": 0.80},
                },
            }),
        )

        assert result == pytest.approx(1_000 + 400)

    def test_iot_core_message_size_uses_5kb_billing_increments(self):
        result = AWSIoTCoreCalculator().calculate_cost(
            number_of_devices=0,
            messages_per_month=1_000_000,
            average_message_size_kb=6,
            pricing=_aws_pricing(iotCore={
                "pricePerDeviceAndMonth": 0,
                "priceRulesTriggered": 0,
                "pricing_tiers": {
                    "tier1": {"limit": "Infinity", "pricePerMillionMessages": 1.00},
                },
            }),
        )

        assert result == pytest.approx(2)

    def test_iot_core_missing_tiers_fail_visibly(self):
        with pytest.raises(ValueError, match="pricing_tiers"):
            AWSIoTCoreCalculator().calculate_cost(
                number_of_devices=1,
                messages_per_month=1,
                average_message_size_kb=1,
                pricing={"aws": {"iotCore": {"pricePerDeviceAndMonth": 0, "priceRulesTriggered": 0}}},
            )


class TestAWSS3Units:
    def test_s3_ia_normalizes_per_1k_request_price(self):
        result = AWSS3IACalculator().calculate_cost(
            storage_gb=100,
            writes_per_month=20_000,
            retrievals_gb=10,
            pricing=_aws_pricing(),
        )

        assert result == pytest.approx(1.25 + 0.20 + 0.10)

    def test_s3_ia_missing_request_price_fails_visibly(self):
        with pytest.raises(ValueError, match="s3InfrequentAccess.write"):
            AWSS3IACalculator().calculate_cost(
                storage_gb=100,
                writes_per_month=20_000,
                pricing=_aws_pricing(s3InfrequentAccess={"storagePrice": 0.0125}),
            )

    def test_s3_ia_missing_retrieval_price_fails_when_retrievals_are_used(self):
        with pytest.raises(ValueError, match="dataRetrieval"):
            AWSS3IACalculator().calculate_cost(
                storage_gb=100,
                writes_per_month=20_000,
                retrievals_gb=1,
                pricing=_aws_pricing(s3InfrequentAccess={
                    "storagePrice": 0.0125,
                    "requestPrice": 0.000001,
                }),
            )

    def test_s3_glacier_normalizes_lifecycle_per_1k_request_price(self):
        result = AWSS3GlacierCalculator().calculate_cost(
            storage_gb=100,
            writes_per_month=20_000,
            retrievals_gb=10,
            pricing=_aws_pricing(),
        )

        assert result == pytest.approx(0.099 + 1.0 + 0.20)


class TestAWSTwinMakerUnits:
    def test_twinmaker_dimensions_are_calculated_separately(self):
        result = AWSTwinMakerCalculator().calculate_cost(
            entity_count=10,
            queries_per_month=20_000,
            api_calls_per_month=30_000,
            model_storage_gb=2,
            pricing=_aws_pricing(),
        )

        expected = (10 * 0.05) + (20_000 * 0.00001) + (30_000 * 0.000001) + (2 * 0.023)
        assert result == pytest.approx(expected)

    def test_twinmaker_supports_per_block_legacy_keys(self):
        result = AWSTwinMakerCalculator().calculate_cost(
            entity_count=1,
            queries_per_month=10_000,
            api_calls_per_month=1_000_000,
            pricing=_aws_pricing(iotTwinMaker={
                "entityPrice": 0.05,
                "queryPricePer10k": 0.50,
                "unifiedDataAccessAPICallsPricePerMillion": 1.20,
            }),
        )

        assert result == pytest.approx(0.05 + 0.50 + 1.20)

    def test_twinmaker_missing_api_price_fails_visibly(self):
        with pytest.raises(ValueError, match="unifiedDataAccessApiCall"):
            AWSTwinMakerCalculator().calculate_cost(
                entity_count=1,
                queries_per_month=1,
                api_calls_per_month=1,
                pricing=_aws_pricing(iotTwinMaker={
                    "entityPrice": 0.05,
                    "queryPrice": 0.00001,
                }),
            )

    def test_twinmaker_missing_model_storage_price_fails_when_storage_is_used(self):
        with pytest.raises(ValueError, match="modelStorage"):
            AWSTwinMakerCalculator().calculate_cost(
                entity_count=1,
                queries_per_month=1,
                api_calls_per_month=1,
                model_storage_gb=1,
                pricing=_aws_pricing(iotTwinMaker={
                    "entityPrice": 0.05,
                    "queryPrice": 0.00001,
                    "unifiedDataAccessAPICallsPrice": 0.000001,
                }),
            )


class TestAWSActionUnits:
    def test_step_functions_normalizes_per_1k_state_transitions(self):
        result = AWSStepFunctionsCalculator().calculate_cost(
            executions=10,
            actions_per_execution=5,
            pricing=_aws_pricing(),
        )

        assert result == pytest.approx(50 * 0.000025)

    def test_eventbridge_prefers_explicit_per_event_key(self):
        result = AWSEventBridgeCalculator().calculate_cost(
            events=2_000_000,
            pricing=_aws_pricing(),
        )

        assert result == pytest.approx(2.0)

    def test_eventbridge_supports_true_per_million_legacy_key(self):
        result = AWSEventBridgeCalculator().calculate_cost(
            events=2_000_000,
            pricing=_aws_pricing(eventBridge={"pricePerMillionEvents": 1.0}),
        )

        assert result == pytest.approx(2.0)

    def test_eventbridge_missing_price_fails_visibly(self):
        with pytest.raises(ValueError, match="eventBridge.event"):
            AWSEventBridgeCalculator().calculate_cost(
                events=1,
                pricing=_aws_pricing(eventBridge={}),
            )


class TestAWSTransferTiering:
    def test_aws_egress_uses_tiered_transfer_pricing(self):
        result = _calculate_egress_cost(
            data_gb=10_500,
            pricing=_aws_pricing(),
            source_provider="AWS",
        )

        expected = ((10_240 - 100) * 0.09) + ((10_500 - 10_240) * 0.085)
        assert result == pytest.approx(expected)
