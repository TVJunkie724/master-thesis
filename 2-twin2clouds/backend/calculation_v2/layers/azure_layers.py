"""
Azure Layer Calculators
========================

Aggregates Azure component costs into layer-level costs (L1-L5).
"""

from typing import Dict, Any

from .contracts import (
    BaseLayerCalculatorSet,
    ComponentDeploymentSelection,
    LayerResult,
    SUPPORTED_LAYER_KEYS,
    TransitionRuntimeResult,
)

from ..components.azure import (
    AzureIoTHubCalculator,
    AzureFunctionsCalculator,
    AzureLogicAppsCalculator,
    AzureEventGridCalculator,
    AzureCosmosDBCalculator,
    AzureBlobCoolCalculator,
    AzureBlobArchiveCalculator,
    AzureDigitalTwinsCalculator,
    AzureGrafanaCalculator,
)
from ..deployment_profiles import (
    AZURE_FUNCTION_MEMORY_MB,
    MOVER_FUNCTION_DURATION_MS,
    STANDARD_FUNCTION_DURATION_MS,
)


def _selection(
    component_id: str,
    **dimensions: str | int | bool,
) -> ComponentDeploymentSelection:
    return ComponentDeploymentSelection(component_id, dimensions)


def _function_selection(
    component_id: str,
    *,
    duration_ms: int = STANDARD_FUNCTION_DURATION_MS,
) -> ComponentDeploymentSelection:
    return _selection(
        component_id,
        **{
            "azure.functions.plan_sku": "Y1",
            "azure.functions.memory_mb": AZURE_FUNCTION_MEMORY_MB,
            "azure.functions.duration_ms": duration_ms,
        },
    )

class AzureLayerCalculators(BaseLayerCalculatorSet):
    """
    Azure layer cost calculators for L1-L5.
    """
    
    provider = "Azure"
    supported_layers = SUPPORTED_LAYER_KEYS

    def __init__(self):
        self.iot_hub = AzureIoTHubCalculator()
        self.functions = AzureFunctionsCalculator()
        self.logic_apps = AzureLogicAppsCalculator()
        self.event_grid = AzureEventGridCalculator()
        self.cosmos_db = AzureCosmosDBCalculator()
        self.blob_cool = AzureBlobCoolCalculator()
        self.blob_archive = AzureBlobArchiveCalculator()
        self.digital_twins = AzureDigitalTwinsCalculator()
        self.grafana = AzureGrafanaCalculator()
    
    def calculate_l1_cost(
        self,
        messages_per_month: float,
        pricing: Dict[str, Any],
        units: int = 1,
        average_message_size_kb: float | None = None,
    ) -> LayerResult:
        """
        Calculate L1 Data Acquisition layer cost.
        
        Components:
            - IoT Hub (messaging)
            - Dispatcher Function (routes messages to L2)
            - Event Grid Subscription (connects IoT Hub to Dispatcher)
        """
        components = {}
        
        # IoT Hub cost
        hub_selection = self.iot_hub.calculate_selection(
            messages_per_month=messages_per_month,
            pricing=pricing,
            units=units,
            average_message_size_kb=average_message_size_kb,
        )
        components["iot_hub"] = hub_selection.total_cost
        
        # Dispatcher Function - runs once per message to route to L2
        dispatcher_cost = self.functions.calculate_cost(
            executions=messages_per_month,
            pricing=pricing
        )
        components["dispatcher_function"] = dispatcher_cost
        
        # Event Grid Subscription (connects IoT Hub events to Dispatcher)
        eg_cost = self.event_grid.calculate_cost(
            events=messages_per_month,
            pricing=pricing
        )
        components["event_grid_subscription"] = eg_cost
        
        total = sum(components.values())
        
        return self._result(
            layer="L1",
            total_cost=total,
            messages=messages_per_month,
            components=components,
            details={
                "tierSelection": {
                    "sku": hub_selection.sku,
                    "capacity": hub_selection.capacity,
                    "physicalMessages": messages_per_month,
                    "billableMessages": hub_selection.billable_quantity,
                    "includedMessagesPerUnit": (
                        hub_selection.included_quantity_per_unit
                    ),
                }
            },
            deployment_selections=(
                _selection(
                    "l1.azure.iot_hub",
                    **{
                        "azure.iot_hub.sku": hub_selection.sku,
                        "azure.iot_hub.capacity": hub_selection.capacity,
                    },
                ),
                _function_selection("l1.azure.function_plan"),
                _selection(
                    "l1.azure.event_grid",
                    **{"azure.event_grid.billing": "operations"},
                ),
            ),
        )
    
    def calculate_l2_cost(
        self,
        executions_per_month: float,
        pricing: Dict[str, Any],
        number_of_device_types: int = 1,
        use_event_checking: bool = False,
        use_orchestration: bool = False,
        return_feedback_to_device: bool = False,
        use_error_handling: bool = False,
        num_event_actions: int = 0,
        event_trigger_rate: float = 0.1
    ) -> LayerResult:
        """
        Calculate L2 Data Processing layer cost.
        
        Components:
            - Persister Function (base processing)
            - Processor Functions (one per device type)
            - Event Checker Function (optional)
            - Event Feedback Function (optional)
            - Logic Apps (optional - if orchestration enabled)
            - Event Grid (optional - if error handling enabled)
            - Event Action Functions (dynamic, from events config)
        
        Args:
            executions_per_month: Number of message processing executions
            pricing: Full pricing dictionary
            number_of_device_types: Number of distinct device types
            use_event_checking: Whether event checking is enabled
            use_orchestration: Whether Logic Apps workflow is enabled
            return_feedback_to_device: Whether feedback to device is enabled
            use_error_handling: Whether error handling is enabled
            num_event_actions: Number of event action functions from config
            event_trigger_rate: Fraction of messages that trigger events (0.0-1.0)
        """
        components = {}
        
        # Persister Function cost (base processing)
        persister_cost = self.functions.calculate_cost(
            executions=executions_per_month,
            pricing=pricing
        )
        components["persister_function"] = persister_cost
        
        # Processor Functions - one per device type, each runs per message
        processor_cost = self.functions.calculate_cost(
            executions=executions_per_month * number_of_device_types,
            pricing=pricing
        )
        components["processor_functions"] = processor_cost
        
        # Optional: Event Checker Function
        if use_event_checking:
            checker_cost = self.functions.calculate_cost(
                executions=executions_per_month,
                pricing=pricing
            )
            components["event_checker"] = checker_cost
        
        # Optional: Event Feedback Function (when returnFeedbackToDevice enabled)
        if use_event_checking and return_feedback_to_device:
            feedback_cost = self.functions.calculate_cost(
                executions=executions_per_month * event_trigger_rate,
                pricing=pricing
            )
            components["event_feedback"] = feedback_cost
        
        # Optional: Logic Apps for orchestration
        if use_event_checking and use_orchestration:
            la_cost = self.logic_apps.calculate_cost(
                executions=executions_per_month,
                pricing=pricing
            )
            components["logic_apps"] = la_cost
        
        # Optional: Event Grid for error handling
        if use_error_handling:
            eg_cost = self.event_grid.calculate_cost(
                events=executions_per_month,
                pricing=pricing
            )
            components["event_grid"] = eg_cost
        
        # Event Action Functions (dynamic, from config_events.json)
        if num_event_actions > 0:
            event_action_cost = self.functions.calculate_cost(
                executions=executions_per_month * event_trigger_rate * num_event_actions,
                pricing=pricing
            )
            components["event_action_functions"] = event_action_cost
        
        total = sum(components.values())
        
        deployment_selections = [
            _function_selection("l2.azure.function_plan")
        ]
        if use_event_checking and use_orchestration:
            deployment_selections.append(
                _selection(
                    "l2.azure.logic_apps",
                    **{"azure.logic_apps.billing": "actions"},
                )
            )
        if use_error_handling:
            deployment_selections.append(
                _selection(
                    "l2.azure.event_grid",
                    **{"azure.event_grid.billing": "operations"},
                )
            )

        return self._result(
            layer="L2",
            total_cost=total,
            messages=executions_per_month,
            components=components,
            deployment_selections=tuple(deployment_selections),
        )
    
    def calculate_l3_hot_cost(
        self,
        writes_per_month: float,
        reads_per_month: float,
        storage_gb: float,
        pricing: Dict[str, Any],
        hot_reader_queries_per_month: float = 0
    ) -> LayerResult:
        """
        Calculate L3 Hot Storage layer cost.
        
        Components:
            - Cosmos DB (storage, reads, writes)
            - Hot Reader Function (queries from L4/external)
        
        Args:
            hot_reader_queries_per_month: Number of external queries to hot storage
        """
        components = {}
        
        # Cosmos DB cost
        cosmos_cost = self.cosmos_db.calculate_cost(
            writes_per_month=writes_per_month,
            reads_per_month=reads_per_month,
            storage_gb=storage_gb,
            pricing=pricing
        )
        components["cosmos_db"] = cosmos_cost
        
        # Hot Reader Function - serves queries from L4 and external clients
        if hot_reader_queries_per_month > 0:
            hot_reader_cost = self.functions.calculate_cost(
                executions=hot_reader_queries_per_month,
                pricing=pricing
            )
            components["hot_reader_function"] = hot_reader_cost
        
        total = sum(components.values())
        
        return self._result(
            layer="L3_hot",
            total_cost=total,
            data_size_gb=storage_gb,
            components=components,
            deployment_selections=(
                _selection(
                    "l3_hot.azure.cosmos_db",
                    **{"azure.cosmos_db.capacity_mode": "serverless"},
                ),
                _function_selection("l3_hot.azure.function_plan"),
            ),
        )
    
    def calculate_l3_cool_cost(
        self,
        storage_gb: float,
        writes_per_month: float,
        pricing: Dict[str, Any],
        retrievals_gb: float = 0.0,
    ) -> LayerResult:
        """Calculate destination-independent Blob Storage Cool cost."""
        components = {}
        
        # Blob Cool cost
        blob_cost = self.blob_cool.calculate_cost(
            storage_gb=storage_gb,
            writes_per_month=writes_per_month,
            pricing=pricing,
            retrievals_gb=retrievals_gb
        )
        components["blob_cool"] = blob_cost

        return self._result(
            layer="L3_cool",
            total_cost=blob_cost,
            data_size_gb=storage_gb,
            components=components,
            deployment_selections=(
                _selection(
                    "l3_cool.azure.blob_storage",
                    **{
                        "azure.storage.account_tier": "Standard",
                        "azure.storage.replication_type": "LRS",
                        "azure.blob.tier": "Cool",
                    },
                ),
            ),
        )
    
    def calculate_l3_archive_cost(
        self,
        storage_gb: float,
        writes_per_month: float,
        pricing: Dict[str, Any],
        retrievals_gb: float = 0.0,
    ) -> LayerResult:
        """Calculate destination-independent Blob Storage Archive cost."""
        components = {}
        
        # Blob Archive cost
        archive_cost = self.blob_archive.calculate_cost(
            storage_gb=storage_gb,
            writes_per_month=writes_per_month,
            pricing=pricing,
            retrievals_gb=retrievals_gb
        )
        components["blob_archive"] = archive_cost

        return self._result(
            layer="L3_archive",
            total_cost=archive_cost,
            data_size_gb=storage_gb,
            components=components,
            deployment_selections=(
                _selection(
                    "l3_archive.azure.blob_storage",
                    **{
                        "azure.storage.account_tier": "Standard",
                        "azure.storage.replication_type": "LRS",
                        "azure.blob.tier": "Archive",
                    },
                ),
            ),
        )

    def calculate_transition_runtime(
        self,
        *,
        edge_id: str,
        monthly_invocations: int,
        invocation_basis: str,
        pricing: Dict[str, Any],
    ) -> TransitionRuntimeResult:
        """Calculate the source Function timer runtime for one storage edge."""

        runtime_profiles = {
            "l3_hot_to_l3_cool": (
                "transition.l3_hot_to_l3_cool.azure.runtime",
                "0 0 0 * * *",
            ),
            "l3_cool_to_l3_archive": (
                "transition.l3_cool_to_l3_archive.azure.runtime",
                "0 0 0 * * 0",
            ),
        }
        try:
            component_id, timer_schedule = runtime_profiles[edge_id]
        except KeyError as exc:
            raise ValueError(
                f"Unsupported Azure transition runtime edge: {edge_id!r}"
            ) from exc

        function_cost = self.functions.calculate_cost(
            executions=monthly_invocations,
            pricing=pricing,
            duration_ms=MOVER_FUNCTION_DURATION_MS,
            memory_mb=AZURE_FUNCTION_MEMORY_MB,
        )
        return TransitionRuntimeResult(
            edge_id=edge_id,
            provider=self.provider,
            monthly_invocations=monthly_invocations,
            invocation_basis=invocation_basis,
            function_cost=function_cost,
            trigger_cost=0.0,
            total_cost=function_cost,
            formula_references=(
                "execution_based_cost",
                "timer_trigger_included_in_consumption_plan",
            ),
            evidence_references=(
                "azure.functions",
                "deployment_registry:resolved-deployment-dimensions.v1",
            ),
            deployment_selection=_selection(
                component_id,
                **{
                    "azure.functions.plan_sku": "Y1",
                    "azure.functions.memory_mb": AZURE_FUNCTION_MEMORY_MB,
                    "azure.functions.duration_ms": MOVER_FUNCTION_DURATION_MS,
                    "azure.functions.timer_schedule": timer_schedule,
                },
            ),
        )
    
    def calculate_l4_cost(
        self,
        billable_operations: float,
        billable_query_units: float,
        billable_messages: float,
        telemetry_updates_per_month: float,
        pricing: Dict[str, Any]
    ) -> LayerResult:
        """Calculate the canonical Azure L4 ADT and pusher components."""
        components = {}

        adt = self.digital_twins.calculate_breakdown(
            billable_operations=billable_operations,
            billable_query_units=billable_query_units,
            billable_messages=billable_messages,
            pricing=pricing,
        )
        components["digital_twins_operations"] = adt.operation_cost
        components["digital_twins_query_units"] = adt.query_unit_cost
        components["digital_twins_routed_messages"] = adt.routed_message_cost

        components["adt_pusher_function"] = self.functions.calculate_cost(
            executions=telemetry_updates_per_month,
            pricing=pricing,
        )

        total = sum(components.values())

        return self._result(
            layer="L4",
            total_cost=total,
            components=components,
            deployment_selections=(
                _selection(
                    "l4.azure.digital_twins",
                    **{
                        "azure.digital_twins.billing": (
                            "operations_query_units_and_messages"
                        )
                    },
                ),
                _function_selection("l4.azure.pusher_function"),
            ),
        )
    
    def calculate_l5_cost(
        self,
        num_editors: int,
        num_viewers: int,
        pricing: Dict[str, Any]
    ) -> LayerResult:
        """Calculate L5 Visualization layer cost."""
        grafana_cost = self.grafana.calculate_cost(
            num_editors=num_editors,
            num_viewers=num_viewers,
            pricing=pricing
        )
        
        return self._result(
            layer="L5",
            total_cost=grafana_cost,
            components={"grafana": grafana_cost},
            deployment_selections=(
                _selection(
                    "l5.azure.managed_grafana",
                    **{"azure.grafana.sku": "Standard"},
                ),
            ),
        )
    
    def calculate_glue_cost(
        self,
        messages: float,
        pricing: Dict[str, Any]
    ) -> float:
        """Calculate cross-cloud glue function cost."""
        return self.functions.calculate_glue_function_cost(
            messages=messages,
            pricing=pricing
        )

    def glue_deployment_selection(self) -> ComponentDeploymentSelection:
        return _function_selection("glue.azure.functions")
