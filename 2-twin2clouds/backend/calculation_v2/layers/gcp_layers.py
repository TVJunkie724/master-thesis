"""
GCP Layer Calculators
======================

Aggregates GCP component costs into layer-level costs (L1-L5).

Note: GCP L4 and L5 are DISABLED - self-hosted solutions are not
implemented in the deployer (future work).
"""

from typing import Dict, Any
from dataclasses import dataclass, field

from ..components.gcp import (
    GCPPubSubCalculator,
    GCPCloudFunctionsCalculator,
    GCPCloudWorkflowsCalculator,
    GCPFirestoreCalculator,
    GCSNearlineCalculator,
    GCSColdlineCalculator,
    GCPComputeEngineCalculator,
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


class GCPLayerCalculators:
    """
    GCP layer cost calculators for L1-L5.
    
    Note: L4 and L5 are DISABLED - self-hosted solutions are not
    implemented in the deployer (future work).
    """
    
    def __init__(self):
        self.pubsub = GCPPubSubCalculator()
        self.cloud_functions = GCPCloudFunctionsCalculator()
        self.cloud_workflows = GCPCloudWorkflowsCalculator()
        self.firestore = GCPFirestoreCalculator()
        self.gcs_nearline = GCSNearlineCalculator()
        self.gcs_coldline = GCSColdlineCalculator()
        self.compute_engine = GCPComputeEngineCalculator()
    
    def calculate_l1_cost(
        self,
        data_volume_gb: float,
        messages_per_month: float,
        pricing: Dict[str, Any]
    ) -> LayerResult:
        """
        Calculate L1 Data Acquisition layer cost.
        
        Components:
            - Pub/Sub (messaging)
            - Dispatcher Cloud Function (routes messages to L2)
        """
        components = {}
        
        # Pub/Sub cost
        pubsub_cost = self.pubsub.calculate_cost(
            data_volume_gb=data_volume_gb,
            pricing=pricing
        )
        components["pubsub"] = pubsub_cost
        
        # Dispatcher Cloud Function - runs once per message to route to L2
        dispatcher_cost = self.cloud_functions.calculate_cost(
            executions=messages_per_month,
            pricing=pricing
        )
        components["dispatcher_function"] = dispatcher_cost
        
        total = sum(components.values())
        
        return LayerResult(
            provider="GCP",
            layer="L1",
            total_cost=total,
            data_size_gb=data_volume_gb,
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
        num_event_actions: int = 0,
        event_trigger_rate: float = 0.1
    ) -> LayerResult:
        """
        Calculate L2 Data Processing layer cost.
        
        Components:
            - Persister Cloud Function (base processing)
            - Processor Cloud Functions (one per device type)
            - Event Checker Cloud Function (optional)
            - Event Feedback Cloud Function (optional)
            - Cloud Workflows (optional - if orchestration enabled)
            - Event Action Cloud Functions (dynamic, from events config)
        
        Args:
            executions_per_month: Number of message processing executions
            pricing: Full pricing dictionary
            number_of_device_types: Number of distinct device types
            use_event_checking: Whether event checking is enabled
            use_orchestration: Whether Cloud Workflows is enabled
            return_feedback_to_device: Whether feedback to device is enabled
            num_event_actions: Number of event action functions from config
            event_trigger_rate: Fraction of messages that trigger events (0.0-1.0)
        """
        components = {}
        
        # Persister Cloud Function cost (base processing)
        persister_cost = self.cloud_functions.calculate_cost(
            executions=executions_per_month,
            pricing=pricing
        )
        components["persister_function"] = persister_cost
        
        # Processor Cloud Functions - one per device type, each runs per message
        processor_cost = self.cloud_functions.calculate_cost(
            executions=executions_per_month * number_of_device_types,
            pricing=pricing
        )
        components["processor_functions"] = processor_cost
        
        # Optional: Event Checker Cloud Function
        if use_event_checking:
            checker_cost = self.cloud_functions.calculate_cost(
                executions=executions_per_month,
                pricing=pricing
            )
            components["event_checker"] = checker_cost
        
        # Optional: Event Feedback Cloud Function
        if use_event_checking and return_feedback_to_device:
            feedback_cost = self.cloud_functions.calculate_cost(
                executions=executions_per_month * event_trigger_rate,
                pricing=pricing
            )
            components["event_feedback"] = feedback_cost
        
        # Optional: Cloud Workflows for orchestration
        if use_event_checking and use_orchestration:
            wf_cost = self.cloud_workflows.calculate_cost(
                executions=executions_per_month,
                pricing=pricing
            )
            components["cloud_workflows"] = wf_cost
        
        # Event Action Cloud Functions (dynamic, from config_events.json)
        if num_event_actions > 0:
            event_action_cost = self.cloud_functions.calculate_cost(
                executions=executions_per_month * event_trigger_rate * num_event_actions,
                pricing=pricing
            )
            components["event_action_functions"] = event_action_cost
        
        total = sum(components.values())
        
        return LayerResult(
            provider="GCP",
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
            - Firestore (storage, reads, writes)
            - Hot Reader Cloud Function (queries from L4/external)
        
        Args:
            hot_reader_queries_per_month: Number of external queries to hot storage
        """
        components = {}
        
        # Firestore cost
        firestore_cost = self.firestore.calculate_cost(
            writes_per_month=writes_per_month,
            reads_per_month=reads_per_month,
            storage_gb=storage_gb,
            pricing=pricing
        )
        components["firestore"] = firestore_cost
        
        # Hot Reader Cloud Function - serves queries from L4 and external clients
        if hot_reader_queries_per_month > 0:
            hot_reader_cost = self.cloud_functions.calculate_cost(
                executions=hot_reader_queries_per_month,
                pricing=pricing
            )
            components["hot_reader_function"] = hot_reader_cost
        
        total = sum(components.values())
        
        return LayerResult(
            provider="GCP",
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
            - GCS Nearline (storage)
            - Hot-Cold Mover Cloud Function (scheduled data migration)
            - Cloud Scheduler (trigger, minimal cost)
        
        Args:
            mover_runs_per_month: Number of times mover runs (default: daily = 30)
        """
        components = {}
        
        # GCS Nearline cost
        nearline_cost = self.gcs_nearline.calculate_cost(
            storage_gb=storage_gb,
            writes_per_month=writes_per_month,
            pricing=pricing,
            retrievals_gb=retrievals_gb
        )
        components["gcs_nearline"] = nearline_cost
        
        # Hot-Cold Mover Cloud Function (scheduled to run periodically)
        mover_cost = self.cloud_functions.calculate_cost(
            executions=mover_runs_per_month,
            pricing=pricing,
            duration_ms=5000  # Mover takes longer (5 seconds)
        )
        components["hot_cold_mover_function"] = mover_cost
        
        total = sum(components.values())
        
        return LayerResult(
            provider="GCP",
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
            - GCS Coldline (storage)
            - Cold-Archive Mover Cloud Function (scheduled archival)
            - Cloud Scheduler (trigger, minimal cost)
        
        Args:
            mover_runs_per_month: Number of times mover runs (default: weekly = 4)
        """
        components = {}
        
        # GCS Coldline cost
        coldline_cost = self.gcs_coldline.calculate_cost(
            storage_gb=storage_gb,
            writes_per_month=writes_per_month,
            pricing=pricing,
            retrievals_gb=retrievals_gb
        )
        components["gcs_coldline"] = coldline_cost
        
        # Cold-Archive Mover Cloud Function (scheduled to run periodically)
        mover_cost = self.cloud_functions.calculate_cost(
            executions=mover_runs_per_month,
            pricing=pricing,
            duration_ms=5000  # Mover takes longer (5 seconds)
        )
        components["cold_archive_mover_function"] = mover_cost
        
        total = sum(components.values())
        
        return LayerResult(
            provider="GCP",
            layer="L3_archive",
            total_cost=total,
            data_size_gb=storage_gb,
            components=components
        )
    
    def calculate_l4_cost(
        self,
        pricing: Dict[str, Any],
        hours_per_month: float = 730,
        disk_gb: float = 10.0
    ) -> LayerResult:
        """
        Calculate L4 Twin Management layer cost.
        
        DISABLED: Self-hosted Twin Management is not implemented in the deployer.
        Returns 0 cost. This is planned for future work.
        """
        return LayerResult(
            provider="GCP",
            layer="L4",
            total_cost=0.0,
            components={"disabled_future_work": 0.0}
        )
    
    def calculate_l5_cost(
        self,
        pricing: Dict[str, Any],
        hours_per_month: float = 730,
        disk_gb: float = 10.0
    ) -> LayerResult:
        """
        Calculate L5 Visualization layer cost.
        
        DISABLED: Self-hosted Grafana is not implemented in the deployer.
        Returns 0 cost. This is planned for future work.
        """
        return LayerResult(
            provider="GCP",
            layer="L5",
            total_cost=0.0,
            components={"disabled_future_work": 0.0}
        )
    
    def calculate_glue_cost(
        self,
        messages: float,
        pricing: Dict[str, Any]
    ) -> float:
        """Calculate cross-cloud glue function cost."""
        return self.cloud_functions.calculate_glue_function_cost(
            messages=messages,
            pricing=pricing
        )

