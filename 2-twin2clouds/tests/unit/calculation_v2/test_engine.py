"""
Test Engine Integration
========================

Integration tests for the new calculation engine.
"""

from datetime import datetime, timezone
from types import SimpleNamespace

import json
import pytest

from tests.unit.pricing.transfer_fixtures import (
    canonical_transfer_catalog,
    pricing_catalog_context_for,
)


DIGEST = "sha256:" + ("a" * 64)
FINGERPRINT = "sha256:" + ("b" * 64)


class TestEngineIntegration:
    """Test the new engine with mock pricing data."""
    
    @pytest.fixture
    def sample_params(self):
        """Standard test parameters."""
        return {
            "calculationRunId": "018f0f5e-7b5e-7b2d-9f0b-7f66c2a88a01",
            "numberOfDevices": 100,
            "deviceSendingIntervalInMinutes": 2.0,
            "averageSizeOfMessageInKb": 0.25,
            "hotStorageDurationInMonths": 1,
            "coolStorageDurationInMonths": 3,
            "archiveStorageDurationInMonths": 12,
            "needs3DModel": False,
            "entityCount": 1,
            "amountOfActiveEditors": 2,
            "amountOfActiveViewers": 5,
            "dashboardRefreshesPerHour": 4,
            "dashboardActiveHoursPerDay": 8,
            "currency": "USD",
            "useEventChecking": True,
            "triggerNotificationWorkflow": True,
            "integrateErrorHandling": False,
            "orchestrationActionsPerMessage": 3,
            "eventsPerMessage": 1,
            "apiCallsPerDashboardRefresh": 1,
            "allowGcpSelfHostedL4": False,
            "allowGcpSelfHostedL5": False,
            "providerPricingContexts": {
                "awsTwinMaker": {
                    "schemaVersion": "aws-twinmaker-account-pricing-context.v1",
                    "status": "available",
                    "sourceRefreshRunId": "refresh-run-1",
                    "connectionFingerprint": FINGERPRINT,
                    "providerAccountId": "123456789012",
                    "pricingRegion": "eu-central-1",
                    "catalogSnapshotDigest": DIGEST,
                    "observedAt": datetime.now(timezone.utc).isoformat(),
                    "currentPlan": {
                        "mode": "STANDARD",
                        "billableEntityCount": 1,
                        "effectiveAt": None,
                        "updatedAt": None,
                        "updateReason": None,
                        "bundle": None,
                    },
                    "pendingPlan": None,
                }
            },
        }
    
    @pytest.fixture
    def sample_pricing(self):
        """Minimal pricing data for testing."""
        return {
            "aws": {
                "iotCore": {
                    "pricePerDeviceAndMonth": 0.25,
                    "priceRulesTriggered": 0.000001,
                    "pricing_tiers": {
                        "tier1": {"limit": 1_000_000_000, "price": 0.000001},
                        "tier2": {"limit": 5_000_000_000, "price": 0.0000008},
                        "tier3": {"limit": "Infinity", "price": 0.0000007},
                    },
                },
                "lambda": {
                    "requestPrice": 0.0000002,
                    "durationPrice": 0.0000166667,
                    "freeRequests": 1000000,
                    "freeComputeTime": 400000,
                },
                "stepFunctions": {"pricePerStateTransition": 0.000025},
                "eventBridge": {"pricePerMillionEvents": 1.0},
                "dynamoDB": {
                    "writePrice": 0.0000125,
                    "readPrice": 0.00000025,
                    "storagePrice": 0.25,
                    "freeStorage": 25,
                },
                "s3InfrequentAccess": {"storagePrice": 0.0125, "requestPrice": 0.000001},
                "s3GlacierDeepArchive": {"storagePrice": 0.00099, "lifecycleAndWritePrice": 0.00005},
                "iotTwinMaker": {
                    "usageRates": {
                        "queryPrice": 0.001,
                        "entityPricePerMonth": 0.000001,
                        "unifiedDataAccessApiCallPrice": 0.000001,
                    },
                },
                "awsManagedGrafana": {"editorPrice": 9.0, "viewerPrice": 5.0},
                "transfer": canonical_transfer_catalog("aws"),
            },
            "__aws_schema__": {
                "pricing_region": "eu-central-1",
                "snapshot_digest": DIGEST,
            },
            "azure": {
                "iotHub": {
                    "pricing_tiers": {
                        "freeTier": {
                            "limit": 240_000,
                            "threshold": 240_000,
                            "price": 0,
                        },
                        "tier1": {
                            "limit": 120_000_000,
                            "threshold": 12_000_000,
                            "price": 25,
                        },
                        "tier2": {
                            "limit": 1_800_000_000,
                            "threshold": 180_000_000,
                            "price": 250,
                        },
                        "tier3": {
                            "limit": "Infinity",
                            "threshold": 9_000_000_000,
                            "price": 2500,
                        },
                    },
                },
                "functions": {
                    "requestPrice": 0.0000002,
                    "durationPrice": 0.000016,
                    "freeRequests": 1000000,
                    "freeComputeTime": 400000,
                },
                "logicApps": {"pricePerAction": 0.000025},
                "eventGrid": {"pricePerMillionOperations": 0.60},
                "cosmosDB": {
                    "requestUnitPrice": 0.25,
                    "storagePrice": 0.25,
                },
                "blobStorageCool": {"storagePrice": 0.01},
                "blobStorageArchive": {"storagePrice": 0.002},
                "azureDigitalTwins": {
                    "operationPrice": 0.0025,
                    "queryPrice": 0.0005,
                    "messagePrice": 0.001,
                },
                "azureManagedGrafana": {"editorPrice": 9.0, "viewerPrice": 5.0},
                "transfer": canonical_transfer_catalog("azure"),
            },
            "gcp": {
                "iot": {"pricePerGiB": 0.04},
                "functions": {
                    "invocationPrice": 0.0000004,
                    "gbSecondPrice": 0.0000025,
                    "freeInvocations": 2000000,
                    "freeGBSeconds": 400000,
                },
                "cloudWorkflows": {"pricePerStep": 0.00001},
                "cloudScheduler": {"jobPrice": 0.10},
                "storage_hot": {
                    "writePrice": 0.18,
                    "readPrice": 0.06,
                    "storagePrice": 0.026,
                },
                "storage_cool": {"storagePrice": 0.01, "writePrice": 0.01},
                "storage_archive": {"storagePrice": 0.004, "writePrice": 0.05},
                "twinmaker": {"e2MediumPrice": 0.0335, "storagePrice": 0.04},
                "grafana": {"e2MediumPrice": 0.0335, "storagePrice": 0.04},
                "transfer": canonical_transfer_catalog("gcp"),
            },
        }
    
    def test_calculate_aws_costs(self, sample_params, sample_pricing):
        """Test AWS cost calculation returns expected structure."""
        from backend.calculation_v2.engine import calculate_aws_costs
        
        result = calculate_aws_costs(sample_params, sample_pricing)
        
        # Verify structure
        assert "L1" in result
        assert "L2" in result
        assert "L3_hot" in result
        assert "L3_cool" in result
        assert "L3_archive" in result
        assert "L4" in result
        assert "L5" in result
        
        # Verify costs are numeric
        for layer in ["L1", "L2", "L3_hot", "L3_cool", "L3_archive", "L4", "L5"]:
            assert isinstance(result[layer]["cost"], (int, float))
            assert result[layer]["cost"] >= 0
            assert result[layer]["supported"] is True

    @pytest.mark.parametrize(
        ("provider", "supported_layers"),
        [
            (
                "AWS",
                frozenset(
                    {"L1", "L2", "L3_hot", "L3_cool", "L3_archive", "L4", "L5"}
                ),
            ),
            (
                "Azure",
                frozenset(
                    {"L1", "L2", "L3_hot", "L3_cool", "L3_archive", "L4", "L5"}
                ),
            ),
            ("GCP", frozenset({"L1", "L2", "L3_hot", "L3_cool", "L3_archive"})),
        ],
    )
    def test_provider_layer_result_matrix(
        self,
        provider,
        supported_layers,
        sample_params,
        sample_pricing,
    ):
        from backend.calculation_v2.engine import (
            calculate_aws_costs,
            calculate_azure_costs,
            calculate_gcp_costs,
        )
        from backend.deployment_specification.builder import (
            LAYER_TO_SLOT,
            _contract,
        )

        calculators = {
            "AWS": calculate_aws_costs,
            "Azure": calculate_azure_costs,
            "GCP": calculate_gcp_costs,
        }
        results = calculators[provider](sample_params, sample_pricing)
        layers = {"L1", "L2", "L3_hot", "L3_cool", "L3_archive", "L4", "L5"}
        registry = _contract()[1]

        for layer in layers:
            payload = results[layer]
            assert set(payload) >= {
                "cost",
                "components",
                "deploymentSelections",
                "supported",
            }
            assert isinstance(payload["cost"], (int, float))
            assert payload["cost"] >= 0
            assert isinstance(payload["components"], dict)
            assert isinstance(payload["deploymentSelections"], list)
            assert payload["supported"] is (layer in supported_layers)
            if layer in supported_layers:
                assert payload["deploymentSelections"]
                assert "unsupportedReason" not in payload
                requirement = registry["slot_requirements"][
                    LAYER_TO_SLOT[layer]
                ][provider.lower()]
                actual_ids = [
                    selection["componentId"]
                    for selection in payload["deploymentSelections"]
                ]
                assert actual_ids[: len(requirement["required_components"])] == (
                    requirement["required_components"]
                )
                assert set(actual_ids[len(requirement["required_components"]):]) <= (
                    set(requirement["optional_components"])
                )
                for selection in payload["deploymentSelections"]:
                    definition = registry["components"][
                        selection["componentId"]
                    ]
                    assert list(selection["dimensions"]) == list(
                        definition["dimensions"]
                    )
            else:
                assert payload["deploymentSelections"] == []
                assert payload["unsupportedReason"]
                assert provider.lower() not in registry["slot_requirements"][
                    LAYER_TO_SLOT[layer]
                ]

    def test_candidate_options_exclude_unsupported_zero_cost_result(self):
        from backend.calculation_v2.engine import _supported_provider_options

        options = _supported_provider_options(
            {
                "AWS": {"L4": {"cost": 4.0, "supported": True}},
                "Azure": {"L4": {"cost": 5.0, "supported": True}},
                "GCP": {
                    "L4": {
                        "cost": 0.0,
                        "supported": False,
                        "unsupportedReason": "Not implemented",
                    }
                },
            },
            "L4",
        )

        assert options == (("AWS", 4.0), ("Azure", 5.0))

    def test_candidate_options_fail_when_no_provider_supports_layer(self):
        from backend.calculation_v2.engine import _supported_provider_options

        with pytest.raises(ValueError, match="No provider supports architecture layer L5"):
            _supported_provider_options(
                {
                    "AWS": {
                        "L5": {
                            "cost": 0.0,
                            "supported": False,
                            "unsupportedReason": "Disabled for test",
                        }
                    },
                    "Azure": {
                        "L5": {
                            "cost": 0.0,
                            "supported": False,
                            "unsupportedReason": "Disabled for test",
                        }
                    },
                    "GCP": {
                        "L5": {
                            "cost": 0.0,
                            "supported": False,
                            "unsupportedReason": "Not implemented",
                        }
                    },
                },
                "L5",
            )

    def test_candidate_options_require_complete_provider_set(self):
        from backend.calculation_v2.engine import _supported_provider_options

        with pytest.raises(ValueError, match="canonical provider set"):
            _supported_provider_options(
                {"AWS": {"L1": {"cost": 1.0, "supported": True}}},
                "L1",
            )

    def test_candidate_options_require_unsupported_reason(self):
        from backend.calculation_v2.engine import _supported_provider_options

        with pytest.raises(ValueError, match="Unsupported GCP result for L4"):
            _supported_provider_options(
                {
                    "AWS": {"L4": {"cost": 1.0, "supported": True}},
                    "Azure": {"L4": {"cost": 2.0, "supported": True}},
                    "GCP": {"L4": {"cost": 0.0, "supported": False}},
                },
                "L4",
            )

    def test_candidate_options_reject_malformed_provider_result(self):
        from backend.calculation_v2.engine import _supported_provider_options

        with pytest.raises(ValueError, match="AWS provider cost result must be a mapping"):
            _supported_provider_options(
                {
                    "AWS": None,
                    "Azure": {"L1": {"cost": 2.0, "supported": True}},
                    "GCP": {"L1": {"cost": 3.0, "supported": True}},
                },
                "L1",
            )

    def test_gcp_unsupported_layers_are_explicit_in_engine_result(
        self,
        sample_params,
        sample_pricing,
    ):
        from backend.calculation_v2.engine import calculate_gcp_costs

        result = calculate_gcp_costs(sample_params, sample_pricing)

        for layer in ["L1", "L2", "L3_hot", "L3_cool", "L3_archive"]:
            assert result[layer]["supported"] is True
            assert "unsupportedReason" not in result[layer]

        for layer in ["L4", "L5"]:
            assert result[layer]["supported"] is False
            assert result[layer]["cost"] == 0.0
            assert result[layer]["unsupportedReason"]

    def test_missing_twinmaker_context_excludes_aws_l4_candidate(
        self,
        sample_params,
        sample_pricing,
    ):
        from backend.calculation_v2.engine import (
            calculate_aws_costs,
            calculate_cheapest_costs,
        )

        sample_params.pop("providerPricingContexts")

        aws = calculate_aws_costs(sample_params, sample_pricing)
        result = calculate_cheapest_costs(
            sample_params,
            sample_pricing,
            pricing_catalog_context=pricing_catalog_context_for(sample_pricing),
        )

        assert aws["L4"]["supported"] is False
        assert aws["L4"]["unsupportedReason"] == (
            "AWS_TWINMAKER_PLAN_UNOBSERVED"
        )
        assert aws["providerPricingContext"]["status"] == "unavailable"
        assert result["calculationResult"]["L4"] == "Azure"
        assert all(item != "L4_AWS" for item in result["cheapestPath"])
    
    def test_calculate_cheapest_costs(self, sample_params, sample_pricing):
        """Test full calculation returns expected structure."""
        from backend.calculation_v2.engine import calculate_cheapest_costs
        
        result = calculate_cheapest_costs(
            sample_params,
            sample_pricing,
            pricing_catalog_context=pricing_catalog_context_for(sample_pricing),
        )
        
        # Verify structure
        assert "calculationResult" in result
        assert "awsCosts" in result
        assert "azureCosts" in result
        assert "gcpCosts" in result
        assert "cheapestPath" in result
        assert "totalCost" in result
        assert result["optimization_profile_id"] == "cost_minimization_v1"
        assert result["result_schema_version"] == "cost-result.v1"
        assert result["trace_schema_version"] == "intent-result-trace.v1"
        assert result["optimizationProfile"]["metric_provider_ids"] == ["cost"]
        assert result["optimizationProfile"]["scoring_strategy_id"] == "min_total_cost_v1"
        assert result["evidenceReferences"]["pricing_registry"].startswith("pricing_registry:")
        assert result["evidenceReferences"]["pricing_evidence_contract"] == "pricing-evidence.v1"
        assert result["evidenceReferences"]["intent_group_ids"] == ["cost"]
        assert result["intentTrace"]["schema_version"] == "intent-result-trace.v1"
        assert result["intentTrace"]["summary"]["record_count"] > 0
        
        # Verify calculationResult has all layers
        calc_result = result["calculationResult"]
        assert "L1" in calc_result
        assert "L2" in calc_result
        assert "L3" in calc_result
        assert "L4" in calc_result
        assert "L5" in calc_result
        
        # Verify provider choices are valid
        valid_providers = ["AWS", "Azure", "GCP"]
        assert calc_result["L1"] in valid_providers
        assert calc_result["L2"] in valid_providers
        assert calc_result["L4"] in valid_providers
        assert calc_result["L5"] in valid_providers
        
        # L3 should have Hot, Cool, Archive
        assert "Hot" in calc_result["L3"]
        assert "Cool" in calc_result["L3"]
        assert "Archive" in calc_result["L3"]

    def test_winner_contains_complete_resolved_deployment_specification(
        self,
        sample_params,
        sample_pricing,
    ):
        from backend.calculation_v2.engine import calculate_cheapest_costs

        result = calculate_cheapest_costs(
            sample_params,
            sample_pricing,
            pricing_catalog_context=pricing_catalog_context_for(sample_pricing),
        )
        specification = result["resolvedDeploymentSpecification"]

        assert specification["schema_version"] == (
            "resolved-deployment-specification.v1"
        )
        assert specification["calculation_run_id"] == (
            sample_params["calculationRunId"]
        )
        assert specification["architecture_profile"] == {
            "profile_id": "five-layer-baseline",
            "profile_version": "1",
        }
        assert specification["currency"] == "USD"
        assert specification["digest"].startswith("sha256:")
        assert len(specification["digest"]) == 71

        selected_provider_by_slot = {
            "l1_ingestion": result["calculationResult"]["L1"].lower(),
            "l2_processing": result["calculationResult"]["L2"].lower(),
            "l3_hot_storage": result["calculationResult"]["L3"]["Hot"].lower(),
            "l3_cool_storage": result["calculationResult"]["L3"]["Cool"].lower(),
            "l3_archive_storage": result["calculationResult"]["L3"][
                "Archive"
            ].lower(),
            "l4_twin_state": result["calculationResult"]["L4"].lower(),
            "l5_visualization": result["calculationResult"]["L5"].lower(),
        }
        components = specification["components"]
        for slot_id, provider in selected_provider_by_slot.items():
            selected_components = [
                component
                for component in components
                if component["slot_id"] == slot_id
            ]
            assert selected_components
            assert {
                component["provider"] for component in selected_components
            } == {provider}
            assert all(component["dimensions"] for component in selected_components)

        assert any(
            component["slot_id"] == "cross_cloud_glue"
            for component in components
        )
        assert all(
            dimension["formula_reference"]
            == "formula_set:cost_formula_set_v1"
            and dimension["evidence_reference"]
            for component in components
            for dimension in component["dimensions"]
        )

    def test_function_formula_profiles_and_archive_classes_are_emitted_exactly(
        self,
        sample_params,
        sample_pricing,
    ):
        from backend.calculation_v2.deployment_profiles import (
            AWS_MOVER_LAMBDA_MEMORY_MB,
            AWS_STANDARD_LAMBDA_MEMORY_MB,
            GCP_MOVER_FUNCTION_MEMORY_MB,
            GCP_STANDARD_FUNCTION_MEMORY_MB,
            STANDARD_FUNCTION_DURATION_MS,
        )
        from backend.calculation_v2.engine import (
            calculate_aws_costs,
            calculate_cheapest_costs,
            calculate_gcp_costs,
        )
        from backend.calculation_v2.layers import (
            AWSLayerCalculators,
            AzureLayerCalculators,
            GCPLayerCalculators,
        )

        aws = calculate_aws_costs(sample_params, sample_pricing)
        gcp = calculate_gcp_costs(sample_params, sample_pricing)

        def selection(costs, layer, component_id):
            return next(
                item
                for item in costs[layer]["deploymentSelections"]
                if item["componentId"] == component_id
            )["dimensions"]

        assert selection(
            aws,
            "L1",
            "l1.aws.dispatcher_lambda",
        ) == {
            "aws.lambda.memory_mb": AWS_STANDARD_LAMBDA_MEMORY_MB,
            "aws.lambda.duration_ms": STANDARD_FUNCTION_DURATION_MS,
        }
        assert selection(
            aws,
            "L3_archive",
            "l3_archive.aws.s3",
        ) == {"aws.s3.storage_class": "DEEP_ARCHIVE"}
        assert selection(
            gcp,
            "L1",
            "l1.gcp.dispatcher_function",
        )["gcp.functions.memory_mb"] == GCP_STANDARD_FUNCTION_MEMORY_MB
        assert selection(
            gcp,
            "L3_archive",
            "l3_archive.gcp.cloud_storage",
        ) == {"gcp.storage.storage_class": "ARCHIVE"}
        assert {
            item["componentId"]
            for layer in ("L3_cool", "L3_archive")
            for item in aws[layer]["deploymentSelections"]
        } == {
            "l3_cool.aws.s3",
            "l3_archive.aws.s3",
        }
        assert {
            item["componentId"]
            for layer in ("L3_cool", "L3_archive")
            for item in gcp[layer]["deploymentSelections"]
        } == {
            "l3_cool.gcp.cloud_storage",
            "l3_archive.gcp.cloud_storage",
        }

        aws_runtime = AWSLayerCalculators().calculate_transition_runtime(
            edge_id="l3_cool_to_l3_archive",
            monthly_invocations=4,
            invocation_basis="one_weekly_source_mover_invocation",
            pricing=sample_pricing,
        )
        azure_runtime = AzureLayerCalculators().calculate_transition_runtime(
            edge_id="l3_cool_to_l3_archive",
            monthly_invocations=4,
            invocation_basis="one_weekly_source_mover_invocation",
            pricing=sample_pricing,
        )
        gcp_runtime = GCPLayerCalculators().calculate_transition_runtime(
            edge_id="l3_cool_to_l3_archive",
            monthly_invocations=4,
            invocation_basis="one_weekly_source_mover_invocation",
            pricing=sample_pricing,
        )
        assert aws_runtime.deployment_selection.component_id == (
            "transition.l3_cool_to_l3_archive.aws.runtime"
        )
        assert aws_runtime.deployment_selection.dimensions[
            "aws.lambda.memory_mb"
        ] == AWS_MOVER_LAMBDA_MEMORY_MB
        assert aws_runtime.trigger_cost == pytest.approx(0.000004)
        assert azure_runtime.trigger_cost == 0
        assert azure_runtime.deployment_selection.dimensions[
            "azure.functions.timer_schedule"
        ] == "0 0 0 * * 0"
        assert gcp_runtime.deployment_selection.component_id == (
            "transition.l3_cool_to_l3_archive.gcp.runtime"
        )
        assert gcp_runtime.deployment_selection.dimensions[
            "gcp.functions.memory_mb"
        ] == GCP_MOVER_FUNCTION_MEMORY_MB
        assert gcp_runtime.trigger_cost == pytest.approx(0.10)

        result = calculate_cheapest_costs(
            sample_params,
            sample_pricing,
            pricing_catalog_context=pricing_catalog_context_for(
                sample_pricing
            ),
        )
        runtime_components = {
            component["component_id"]: component
            for component in result["resolvedDeploymentSpecification"][
                "components"
            ]
            if component["slot_id"] == "transition_runtime"
        }
        assert len(runtime_components) == 2
        assert all(
            component_id.startswith("transition.")
            for component_id in runtime_components
        )

    def test_currency_conversion_does_not_change_deployment_specification(
        self,
        sample_params,
        sample_pricing,
    ):
        from backend.calculation_v2.engine import calculate_cheapest_costs

        context = pricing_catalog_context_for(sample_pricing)
        usd = calculate_cheapest_costs(
            sample_params,
            sample_pricing,
            pricing_catalog_context=context,
        )
        eur_params = {**sample_params, "currency": "EUR"}
        eur = calculate_cheapest_costs(
            eur_params,
            sample_pricing,
            pricing_catalog_context=context,
        )

        assert eur["currency"] == "EUR"
        assert eur["resolvedDeploymentSpecification"] == (
            usd["resolvedDeploymentSpecification"]
        )

    def test_disabled_optimization_profile_is_rejected(self, sample_params, sample_pricing):
        """Only enabled profiles may execute."""
        from backend.calculation_v2.engine import calculate_cheapest_costs
        from backend.optimization.profiles import OptimizationConfigError

        with pytest.raises(OptimizationConfigError):
            calculate_cheapest_costs(
                sample_params,
                sample_pricing,
                pricing_catalog_context=pricing_catalog_context_for(
                    sample_pricing
                ),
                optimization_profile_id="latency_minimization_v1",
            )

    def test_unimplemented_gcp_self_hosted_paths_fail_closed(
        self, sample_params, sample_pricing
    ):
        from backend.calculation_v2.engine import calculate_cheapest_costs

        sample_params["allowGcpSelfHostedL4"] = True

        with pytest.raises(ValueError, match="cannot be enabled"):
            calculate_cheapest_costs(
                sample_params,
                sample_pricing,
                pricing_catalog_context=pricing_catalog_context_for(
                    sample_pricing
                ),
            )

    def test_cost_profile_scores_complete_paths(self, sample_params, sample_pricing):
        """The enabled strategy scores complete, transfer-aware candidates."""
        from backend.calculation_v2.engine import calculate_cheapest_costs

        result = calculate_cheapest_costs(
            sample_params,
            sample_pricing,
            pricing_catalog_context=pricing_catalog_context_for(sample_pricing),
        )

        diagnostics = result["optimizationDiagnostics"]
        assert diagnostics["schemaVersion"] == "complete-path-optimization.v1"
        assert diagnostics["enumeratedPathCount"] == 972
        assert diagnostics["evaluatedPathCount"] == 972
        assert diagnostics["rejectedPathCount"] == 0
        assert diagnostics["canonicalProviderOrder"] == [
            "aws",
            "azure",
            "gcp",
        ]
        assert diagnostics["winningScore"] >= diagnostics["winningLayerCost"]
        assert len(result["transferPricingContext"]["routes"]) == 6

    def test_scoring_strategy_does_not_receive_provider_pricing_payload(
        self,
        sample_params,
        sample_pricing,
        monkeypatch,
    ):
        """Provider-specific raw pricing fields stay outside the scoring boundary."""
        from backend.calculation_v2 import engine
        from backend.optimization.metrics import CostMetricProvider

        class InspectingStrategy:
            primary_metric_id = "cost"

            def __init__(self):
                self.seen_payloads = []

            def select_best(self, candidates):
                for candidate in candidates:
                    payload = json.dumps(candidate.to_dict())
                    assert "pricePerDeviceAndMonth" not in payload
                    assert "pricePerGB" not in payload
                    assert "durationPrice" not in payload
                    assert "storagePrice" not in payload
                    assert set(candidate.metrics) == {"cost"}
                    self.seen_payloads.append(payload)
                return min(candidates, key=lambda candidate: candidate.metric_value("cost"))

        strategy = InspectingStrategy()

        class FakeProfileRegistry:
            def select_profile(self, profile_id=None):
                return SimpleNamespace(
                    profile_id="cost_minimization_v1",
                    metric_provider_ids=("cost",),
                    scoring_strategy_id="min_total_cost_v1",
                    optimization_bundle_id="cost_minimization_v1",
                    result_schema_version="cost-result.v1",
                )

            def get_metric_provider(self, metric_id):
                assert metric_id == "cost"
                return CostMetricProvider()

            def get_scoring_strategy(self, strategy_id):
                assert strategy_id == "min_total_cost_v1"
                return strategy

            def build_result_metadata(self, profile_id):
                assert profile_id == "cost_minimization_v1"
                return {
                    "config_version": "optimization-config.v1",
                    "pricing_registry_version": "test-registry.v1",
                    "profile_id": "cost_minimization_v1",
                    "profile_version": "2026.06.08",
                    "enabled": True,
                    "status": "ready",
                    "metric_provider_ids": ["cost"],
                    "calculation_model_ids": ["cost_model_v1"],
                    "scoring_strategy_id": "min_total_cost_v1",
                    "intent_group_ids": ["cost"],
                    "evidence_requirements": {"pricing": "evidence_backed"},
                    "result_schema_version": "cost-result.v1",
                    "description": "test",
                }

        monkeypatch.setattr(
            engine,
            "build_default_profile_registry",
            lambda: FakeProfileRegistry(),
        )

        result = engine.calculate_cheapest_costs(
            sample_params,
            sample_pricing,
            pricing_catalog_context=pricing_catalog_context_for(sample_pricing),
        )

        assert result["optimization_profile_id"] == "cost_minimization_v1"
        assert len(strategy.seen_payloads) >= 7

    def test_profile_primary_metric_mismatch_fails_fast(
        self,
        sample_params,
        sample_pricing,
        monkeypatch,
    ):
        """Enabled profiles may not mix scoring metrics outside the profile contract."""
        from backend.calculation_v2 import engine
        from backend.optimization.metrics import CostMetricProvider

        class MismatchedStrategy:
            primary_metric_id = "latency"

            def select_best(self, candidates):
                return candidates[0]

        class FakeProfileRegistry:
            def select_profile(self, profile_id=None):
                return SimpleNamespace(
                    profile_id="cost_minimization_v1",
                    metric_provider_ids=("cost",),
                    scoring_strategy_id="min_total_cost_v1",
                    optimization_bundle_id="cost_minimization_v1",
                    result_schema_version="cost-result.v1",
                )

            def get_metric_provider(self, metric_id):
                assert metric_id == "cost"
                return CostMetricProvider()

            def get_scoring_strategy(self, strategy_id):
                return MismatchedStrategy()

            def build_result_metadata(self, profile_id):
                return {
                    "pricing_registry_version": "test-registry.v1",
                    "profile_id": "cost_minimization_v1",
                    "metric_provider_ids": ["cost"],
                    "calculation_model_ids": ["cost_model_v1"],
                    "scoring_strategy_id": "min_total_cost_v1",
                    "intent_group_ids": ["cost"],
                    "result_schema_version": "cost-result.v1",
                }

        monkeypatch.setattr(
            engine,
            "build_default_profile_registry",
            lambda: FakeProfileRegistry(),
        )

        with pytest.raises(ValueError, match="primary metric"):
            engine.calculate_cheapest_costs(
                sample_params,
                sample_pricing,
                pricing_catalog_context=pricing_catalog_context_for(
                    sample_pricing
                ),
            )
    
    def test_total_cost_is_positive(self, sample_params, sample_pricing):
        """Total cost should be positive for non-zero usage."""
        from backend.calculation_v2.engine import calculate_cheapest_costs
        
        result = calculate_cheapest_costs(
            sample_params,
            sample_pricing,
            pricing_catalog_context=pricing_catalog_context_for(sample_pricing),
        )
        assert result["totalCost"] > 0
