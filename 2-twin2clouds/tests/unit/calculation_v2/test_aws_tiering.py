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
from backend.calculation_v2.components.aws.twinmaker import (
    DEDICATED_ACCOUNT_FULL_COST,
    calculate_tiered_bundle_account_cost,
)
from backend.calculation_v2.engine import _calculate_egress_cost
from backend.calculation_v2.layers.aws_layers import AWSLayerCalculators
from tests.unit.pricing.transfer_fixtures import canonical_transfer_catalog


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
            "usageRates": {
                "entityPricePerMonth": 0.05,
                "queryPrice": 0.00001,
                "unifiedDataAccessApiCallPrice": 0.000001,
            },
            "tieredBundle": {
                "tiers": [
                    {
                        "tierId": "TIER_1",
                        "minimumEntities": 1,
                        "maximumEntities": 1000,
                        "monthlyBasePrice": 231.0,
                        "includedQueries": 3_800_000,
                        "includedApiCalls": 25_000_000,
                        "queryOveragePrice": 0.0000525,
                        "apiCallOveragePrice": 0.00000165,
                    },
                    {
                        "tierId": "TIER_2",
                        "minimumEntities": 1001,
                        "maximumEntities": 5000,
                        "monthlyBasePrice": 682.5,
                        "includedQueries": 9_000_000,
                        "includedApiCalls": 60_000_000,
                        "queryOveragePrice": 0.0000525,
                        "apiCallOveragePrice": 0.00000165,
                    },
                    {
                        "tierId": "TIER_3",
                        "minimumEntities": 5001,
                        "maximumEntities": 10000,
                        "monthlyBasePrice": 1155.0,
                        "includedQueries": 14_300_000,
                        "includedApiCalls": 95_000_000,
                        "queryOveragePrice": 0.0000525,
                        "apiCallOveragePrice": 0.00000165,
                    },
                    {
                        "tierId": "TIER_4",
                        "minimumEntities": 10001,
                        "maximumEntities": 20000,
                        "monthlyBasePrice": 2047.5,
                        "includedQueries": 24_000_000,
                        "includedApiCalls": 160_000_000,
                        "queryOveragePrice": 0.0000525,
                        "apiCallOveragePrice": 0.00000165,
                    },
                ]
            },
        },
        "stepFunctions": {"pricePer1kStateTransitions": 0.025},
        "eventBridge": {"pricePerEvent": 0.000001},
        "transfer": canonical_transfer_catalog("aws"),
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
            pricing=_aws_pricing(),
        )

        expected = (10 * 0.05) + (20_000 * 0.00001) + (30_000 * 0.000001)
        assert result == pytest.approx(expected)

    def test_twinmaker_rejects_flat_legacy_keys(self):
        with pytest.raises(ValueError, match="usageRates"):
            AWSTwinMakerCalculator().calculate_cost(
                entity_count=1,
                queries_per_month=10_000,
                api_calls_per_month=1_000_000,
                pricing=_aws_pricing(
                    iotTwinMaker={
                        "entityPrice": 0.05,
                        "queryPrice": 0.00005,
                        "unifiedDataAccessAPICallsPrice": 0.0000012,
                    }
                ),
            )

    def test_twinmaker_missing_api_price_fails_visibly(self):
        with pytest.raises(ValueError, match="unifiedDataAccessApiCall"):
            AWSTwinMakerCalculator().calculate_cost(
                entity_count=1,
                queries_per_month=1,
                api_calls_per_month=1,
                pricing=_aws_pricing(
                    iotTwinMaker={
                        "usageRates": {
                            "entityPricePerMonth": 0.05,
                            "queryPrice": 0.00001,
                        }
                    }
                ),
            )

    def test_twinmaker_missing_model_storage_price_fails_when_storage_is_used(self):
        with pytest.raises(ValueError, match="no approved pricing contract"):
            AWSTwinMakerCalculator().calculate_cost(
                entity_count=1,
                queries_per_month=1,
                api_calls_per_month=1,
                model_storage_gb=1,
                pricing=_aws_pricing(),
            )

    def test_twinmaker_bundle_calculates_full_dedicated_account_cost(self):
        result = calculate_tiered_bundle_account_cost(
            observed_tier="TIER_1",
            account_entity_count=500,
            account_queries_per_month=4_000_000,
            account_api_calls_per_month=26_000_000,
            allocation_policy=DEDICATED_ACCOUNT_FULL_COST,
            pricing=_aws_pricing(),
        )

        assert result.monthly_base_price == 231.0
        assert result.query_overage == 200_000
        assert result.api_call_overage == 1_000_000
        assert result.total == pytest.approx(
            231.0 + (200_000 * 0.0000525) + (1_000_000 * 0.00000165)
        )

    @pytest.mark.parametrize(
        (
            "tier",
            "entities",
            "base_price",
            "included_queries",
            "included_api_calls",
        ),
        [
            ("TIER_1", 1, 231.0, 3_800_000, 25_000_000),
            ("TIER_1", 1_000, 231.0, 3_800_000, 25_000_000),
            ("TIER_2", 1_001, 682.5, 9_000_000, 60_000_000),
            ("TIER_2", 5_000, 682.5, 9_000_000, 60_000_000),
            ("TIER_3", 5_001, 1155.0, 14_300_000, 95_000_000),
            ("TIER_3", 10_000, 1155.0, 14_300_000, 95_000_000),
            ("TIER_4", 10_001, 2047.5, 24_000_000, 160_000_000),
            ("TIER_4", 20_000, 2047.5, 24_000_000, 160_000_000),
        ],
    )
    def test_twinmaker_bundle_covers_every_entity_and_included_usage_boundary(
        self,
        tier,
        entities,
        base_price,
        included_queries,
        included_api_calls,
    ):
        at_boundary = calculate_tiered_bundle_account_cost(
            observed_tier=tier,
            account_entity_count=entities,
            account_queries_per_month=included_queries,
            account_api_calls_per_month=included_api_calls,
            allocation_policy=DEDICATED_ACCOUNT_FULL_COST,
            pricing=_aws_pricing(),
        )
        first_overage = calculate_tiered_bundle_account_cost(
            observed_tier=tier,
            account_entity_count=entities,
            account_queries_per_month=included_queries + 1,
            account_api_calls_per_month=included_api_calls + 1,
            allocation_policy=DEDICATED_ACCOUNT_FULL_COST,
            pricing=_aws_pricing(),
        )

        assert at_boundary.total == base_price
        assert at_boundary.query_overage == 0
        assert at_boundary.api_call_overage == 0
        assert first_overage.total == pytest.approx(
            base_price + 0.0000525 + 0.00000165
        )

    @pytest.mark.parametrize("entities", [0, 20_001])
    def test_twinmaker_bundle_rejects_entities_outside_supported_tiers(
        self,
        entities,
    ):
        with pytest.raises(ValueError, match="does not belong"):
            calculate_tiered_bundle_account_cost(
                observed_tier="TIER_1" if entities == 0 else "TIER_4",
                account_entity_count=entities,
                account_queries_per_month=0,
                account_api_calls_per_month=0,
                allocation_policy=DEDICATED_ACCOUNT_FULL_COST,
                pricing=_aws_pricing(),
            )

    def test_twinmaker_bundle_rejects_incomplete_tier_schedule(self):
        pricing = _aws_pricing()
        pricing["aws"]["iotTwinMaker"]["tieredBundle"]["tiers"].pop()

        with pytest.raises(ValueError, match="exactly four tiers"):
            calculate_tiered_bundle_account_cost(
                observed_tier="TIER_1",
                account_entity_count=1,
                account_queries_per_month=0,
                account_api_calls_per_month=0,
                allocation_policy=DEDICATED_ACCOUNT_FULL_COST,
                pricing=pricing,
            )

    def test_twinmaker_bundle_rejects_entity_tier_mismatch(self):
        with pytest.raises(ValueError, match="does not belong"):
            calculate_tiered_bundle_account_cost(
                observed_tier="TIER_1",
                account_entity_count=1_001,
                account_queries_per_month=0,
                account_api_calls_per_month=0,
                allocation_policy=DEDICATED_ACCOUNT_FULL_COST,
                pricing=_aws_pricing(),
            )

    def test_twinmaker_bundle_rejects_implicit_allocation(self):
        with pytest.raises(ValueError, match=DEDICATED_ACCOUNT_FULL_COST):
            calculate_tiered_bundle_account_cost(
                observed_tier="TIER_1",
                account_entity_count=1,
                account_queries_per_month=0,
                account_api_calls_per_month=0,
                allocation_policy="PROPORTIONAL",
                pricing=_aws_pricing(),
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

    def test_transition_runtime_does_not_use_custom_event_bus_pricing(self):
        calculator = AWSLayerCalculators()
        lambda_pricing = {
            "requestPrice": 0.0000002,
            "durationPrice": 0.0000166667,
            "freeRequests": 0,
            "freeComputeTime": 0,
        }
        low_price = calculator.calculate_transition_runtime(
            edge_id="l3_hot_to_l3_cool",
            monthly_invocations=30,
            invocation_basis="one_daily_source_mover_invocation",
            pricing=_aws_pricing(**{
                "lambda": lambda_pricing,
                "eventBridge": {"pricePerMillionEvents": 1.0},
            }),
        )
        high_price = calculator.calculate_transition_runtime(
            edge_id="l3_hot_to_l3_cool",
            monthly_invocations=30,
            invocation_basis="one_daily_source_mover_invocation",
            pricing=_aws_pricing(**{
                "lambda": lambda_pricing,
                "eventBridge": {"pricePerMillionEvents": 999.0},
            }),
        )

        assert low_price.trigger_cost == 0
        assert high_price.trigger_cost == 0
        assert low_price.total_cost == pytest.approx(high_price.total_cost)
        assert "aws.eventBridge" not in low_price.evidence_references


class TestAWSTransferTiering:
    def test_aws_egress_uses_tiered_transfer_pricing(self):
        result = _calculate_egress_cost(
            data_gb=10_500,
            pricing=_aws_pricing(),
            source_provider="AWS",
        )

        expected = ((10_240 - 100) * 0.09) + ((10_500 - 10_240) * 0.085)
        assert result == pytest.approx(expected)
