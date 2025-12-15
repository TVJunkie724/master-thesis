"""
Azure Layer Calculators
========================

Aggregates Azure component costs into layer-level costs (L1-L5).
"""

from typing import Dict, Any
from dataclasses import dataclass, field

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


@dataclass
class LayerResult:
    """Result of a layer cost calculation."""
    provider: str
    layer: str
    total_cost: float
    data_size_gb: float = 0.0
    messages: float = 0.0
    components: Dict[str, float] = field(default_factory=dict)


class AzureLayerCalculators:
    """
    Azure layer cost calculators for L1-L5.
    """
    
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
        units: int = 1
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
        hub_cost = self.iot_hub.calculate_cost(
            messages_per_month=messages_per_month,
            pricing=pricing,
            units=units
        )
        components["iot_hub"] = hub_cost
        
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
        
        return LayerResult(
            provider="Azure",
            layer="L1",
            total_cost=total,
            messages=messages_per_month,
            components=components
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
        
        return LayerResult(
            provider="Azure",
            layer="L2",
            total_cost=total,
            messages=executions_per_month,
            components=components
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
        
        return LayerResult(
            provider="Azure",
            layer="L3_hot",
            total_cost=total,
            data_size_gb=storage_gb,
            components=components
        )
    
    def calculate_l3_cool_cost(
        self,
        storage_gb: float,
        writes_per_month: float,
        pricing: Dict[str, Any],
        retrievals_gb: float = 0.0,
        mover_runs_per_month: int = 30
    ) -> LayerResult:
        """
        Calculate L3 Cool Storage layer cost.
        
        Components:
            - Blob Storage Cool tier
            - Hot-Cold Mover Function (scheduled data migration)
        
        Args:
            mover_runs_per_month: Number of times mover runs (default: daily = 30)
        """
        components = {}
        
        # Blob Cool cost
        blob_cost = self.blob_cool.calculate_cost(
            storage_gb=storage_gb,
            writes_per_month=writes_per_month,
            pricing=pricing,
            retrievals_gb=retrievals_gb
        )
        components["blob_cool"] = blob_cost
        
        # Hot-Cold Mover Function (scheduled to run periodically)
        mover_cost = self.functions.calculate_cost(
            executions=mover_runs_per_month,
            pricing=pricing,
            duration_ms=5000  # Mover takes longer (5 seconds)
        )
        components["hot_cold_mover_function"] = mover_cost
        
        total = sum(components.values())
        
        return LayerResult(
            provider="Azure",
            layer="L3_cool",
            total_cost=total,
            data_size_gb=storage_gb,
            components=components
        )
    
    def calculate_l3_archive_cost(
        self,
        storage_gb: float,
        writes_per_month: float,
        pricing: Dict[str, Any],
        retrievals_gb: float = 0.0,
        mover_runs_per_month: int = 4
    ) -> LayerResult:
        """
        Calculate L3 Archive Storage layer cost.
        
        Components:
            - Blob Storage Archive tier
            - Cold-Archive Mover Function (scheduled archival)
        
        Args:
            mover_runs_per_month: Number of times mover runs (default: weekly = 4)
        """
        components = {}
        
        # Blob Archive cost
        archive_cost = self.blob_archive.calculate_cost(
            storage_gb=storage_gb,
            writes_per_month=writes_per_month,
            pricing=pricing,
            retrievals_gb=retrievals_gb
        )
        components["blob_archive"] = archive_cost
        
        # Cold-Archive Mover Function (scheduled to run periodically)
        mover_cost = self.functions.calculate_cost(
            executions=mover_runs_per_month,
            pricing=pricing,
            duration_ms=5000  # Mover takes longer (5 seconds)
        )
        components["cold_archive_mover_function"] = mover_cost
        
        total = sum(components.values())
        
        return LayerResult(
            provider="Azure",
            layer="L3_archive",
            total_cost=total,
            data_size_gb=storage_gb,
            components=components
        )
    
    def calculate_l4_cost(
        self,
        operations_per_month: float,
        queries_per_month: float,
        messages_per_month: float,
        pricing: Dict[str, Any]
    ) -> LayerResult:
        """
        Calculate L4 Twin Management layer cost.
        
        Components:
            - Azure Digital Twins (operations, queries, messages)
            - ADT Updater Function (updates twins from storage)
            - Event Grid Subscription (triggers ADT Updater)
        """
        components = {}
        
        # Azure Digital Twins cost
        adt_cost = self.digital_twins.calculate_cost(
            operations_per_month=operations_per_month,
            queries_per_month=queries_per_month,
            messages_per_month=messages_per_month,
            pricing=pricing
        )
        components["digital_twins"] = adt_cost
        
        # ADT Updater Function - runs for each data update
        adt_updater_cost = self.functions.calculate_cost(
            executions=messages_per_month,
            pricing=pricing
        )
        components["adt_updater_function"] = adt_updater_cost
        
        # Event Grid Subscription (connects L3 to L4)
        eg_cost = self.event_grid.calculate_cost(
            events=messages_per_month,
            pricing=pricing
        )
        components["event_grid_subscription"] = eg_cost
        
        total = sum(components.values())
        
        return LayerResult(
            provider="Azure",
            layer="L4",
            total_cost=total,
            components=components
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
        
        return LayerResult(
            provider="Azure",
            layer="L5",
            total_cost=grafana_cost,
            components={"grafana": grafana_cost}
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

