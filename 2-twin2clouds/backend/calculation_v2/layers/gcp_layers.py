"""
GCP Layer Calculators
======================

Aggregates GCP component costs into layer-level costs (L1-L5).

Note: GCP L4 and L5 are DISABLED - self-hosted solutions are not
implemented in the deployer (future work).
"""

from typing import Dict, Any

from .contracts import (
    BaseLayerCalculatorSet,
    ComponentDeploymentSelection,
    LayerResult,
    SUPPORTED_LAYER_KEYS,
    TransitionRuntimeResult,
)

from ..components.gcp import (
    GCPPubSubCalculator,
    GCPCloudFunctionsCalculator,
    GCPCloudWorkflowsCalculator,
    GCPFirestoreCalculator,
    GCSNearlineCalculator,
    GCSArchiveCalculator,
    GCPComputeEngineCalculator,
)
from ..deployment_profiles import (
    GCP_FUNCTION_MIN_INSTANCES,
    GCP_MOVER_FUNCTION_MAX_INSTANCES,
    GCP_MOVER_FUNCTION_MEMORY_MB,
    GCP_STANDARD_FUNCTION_MAX_INSTANCES,
    GCP_STANDARD_FUNCTION_MEMORY_MB,
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
    memory_mb: int = GCP_STANDARD_FUNCTION_MEMORY_MB,
    max_instances: int = GCP_STANDARD_FUNCTION_MAX_INSTANCES,
    duration_ms: int = STANDARD_FUNCTION_DURATION_MS,
) -> ComponentDeploymentSelection:
    return _selection(
        component_id,
        **{
            "gcp.functions.memory_mb": memory_mb,
            "gcp.functions.min_instance_count": GCP_FUNCTION_MIN_INSTANCES,
            "gcp.functions.max_instance_count": max_instances,
            "gcp.functions.duration_ms": duration_ms,
        },
    )

class GCPLayerCalculators(BaseLayerCalculatorSet):
    """
    GCP layer cost calculators for L1-L5.
    
    Note: L4 and L5 are DISABLED - self-hosted solutions are not
    implemented in the deployer (future work).
    """
    
    provider = "GCP"
    supported_layers = SUPPORTED_LAYER_KEYS - {"L4", "L5"}

    def __init__(self):
        self.pubsub = GCPPubSubCalculator()
        self.cloud_functions = GCPCloudFunctionsCalculator()
        self.cloud_workflows = GCPCloudWorkflowsCalculator()
        self.firestore = GCPFirestoreCalculator()
        self.gcs_nearline = GCSNearlineCalculator()
        self.gcs_archive = GCSArchiveCalculator()
        self.compute_engine = GCPComputeEngineCalculator()
    
    def calculate_l1_cost(
        self,
        data_volume_gb: float,
        messages_per_month: float,
        pricing: Dict[str, Any],
        average_message_size_kb: float | None = None,
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
            pricing=pricing,
            messages_per_month=messages_per_month,
            average_message_size_kb=average_message_size_kb,
        )
        components["pubsub"] = pubsub_cost
        
        # Dispatcher Cloud Function - runs once per message to route to L2
        dispatcher_cost = self.cloud_functions.calculate_cost(
            executions=messages_per_month,
            pricing=pricing
        )
        components["dispatcher_function"] = dispatcher_cost
        
        total = sum(components.values())
        
        return self._result(
            layer="L1",
            total_cost=total,
            data_size_gb=data_volume_gb,
            messages=messages_per_month,
            components=components,
            deployment_selections=(
                _selection(
                    "l1.gcp.pubsub",
                    **{"gcp.pubsub.billing": "throughput"},
                ),
                _function_selection("l1.gcp.dispatcher_function"),
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
        
        deployment_selections = [
            _function_selection("l2.gcp.processing_functions")
        ]
        if use_event_checking and use_orchestration:
            deployment_selections.append(
                _selection(
                    "l2.gcp.workflows",
                    **{"gcp.workflows.billing": "steps"},
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
        
        return self._result(
            layer="L3_hot",
            total_cost=total,
            data_size_gb=storage_gb,
            components=components,
            deployment_selections=(
                _selection(
                    "l3_hot.gcp.firestore",
                    **{"gcp.firestore.mode": "FIRESTORE_NATIVE"},
                ),
                _function_selection("l3_hot.gcp.reader_function"),
            ),
        )
    
    def calculate_l3_cool_cost(
        self,
        storage_gb: float,
        writes_per_month: float,
        pricing: Dict[str, Any],
        retrievals_gb: float = 0.0,
    ) -> LayerResult:
        """Calculate destination-independent GCS Nearline cost."""
        components = {}
        
        # GCS Nearline cost
        nearline_cost = self.gcs_nearline.calculate_cost(
            storage_gb=storage_gb,
            writes_per_month=writes_per_month,
            pricing=pricing,
            retrievals_gb=retrievals_gb
        )
        components["gcs_nearline"] = nearline_cost

        return self._result(
            layer="L3_cool",
            total_cost=nearline_cost,
            data_size_gb=storage_gb,
            components=components,
            deployment_selections=(
                _selection(
                    "l3_cool.gcp.cloud_storage",
                    **{"gcp.storage.storage_class": "NEARLINE"},
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
        """Calculate destination-independent GCS Archive cost."""
        components = {}
        
        archive_cost = self.gcs_archive.calculate_cost(
            storage_gb=storage_gb,
            writes_per_month=writes_per_month,
            pricing=pricing,
            retrievals_gb=retrievals_gb
        )
        components["gcs_archive"] = archive_cost

        return self._result(
            layer="L3_archive",
            total_cost=archive_cost,
            data_size_gb=storage_gb,
            components=components,
            deployment_selections=(
                _selection(
                    "l3_archive.gcp.cloud_storage",
                    **{"gcp.storage.storage_class": "ARCHIVE"},
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
        """Calculate the source Cloud Function and Scheduler runtime."""

        runtime_profiles = {
            "l3_hot_to_l3_cool": (
                "transition.l3_hot_to_l3_cool.gcp.runtime",
                "0 2 * * *",
            ),
            "l3_cool_to_l3_archive": (
                "transition.l3_cool_to_l3_archive.gcp.runtime",
                "0 3 * * 0",
            ),
        }
        try:
            component_id, scheduler_cron = runtime_profiles[edge_id]
        except KeyError as exc:
            raise ValueError(
                f"Unsupported GCP transition runtime edge: {edge_id!r}"
            ) from exc

        function_cost = self.cloud_functions.calculate_cost(
            executions=monthly_invocations,
            pricing=pricing,
            duration_ms=MOVER_FUNCTION_DURATION_MS,
            memory_mb=GCP_MOVER_FUNCTION_MEMORY_MB,
        )
        scheduler_pricing = pricing["gcp"].get("cloudScheduler")
        if not isinstance(scheduler_pricing, dict):
            raise ValueError("Missing gcp.cloudScheduler pricing")
        job_price = scheduler_pricing.get("jobPrice")
        if (
            isinstance(job_price, bool)
            or not isinstance(job_price, (int, float))
            or job_price < 0
        ):
            raise ValueError("gcp.cloudScheduler.jobPrice must be non-negative")
        trigger_cost = float(job_price)
        return TransitionRuntimeResult(
            edge_id=edge_id,
            provider=self.provider,
            monthly_invocations=monthly_invocations,
            invocation_basis=invocation_basis,
            function_cost=function_cost,
            trigger_cost=trigger_cost,
            total_cost=function_cost + trigger_cost,
            formula_references=(
                "execution_based_cost",
                "fixed_job_month_cost",
            ),
            evidence_references=(
                "gcp.functions",
                "gcp.cloudScheduler",
            ),
            deployment_selection=_selection(
                component_id,
                **{
                    "gcp.functions.memory_mb": GCP_MOVER_FUNCTION_MEMORY_MB,
                    "gcp.functions.min_instance_count": GCP_FUNCTION_MIN_INSTANCES,
                    "gcp.functions.max_instance_count": (
                        GCP_MOVER_FUNCTION_MAX_INSTANCES
                    ),
                    "gcp.functions.duration_ms": MOVER_FUNCTION_DURATION_MS,
                    "gcp.scheduler.cron": scheduler_cron,
                },
            ),
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
        return self._result(
            layer="L4",
            total_cost=0.0,
            components={},
            unsupported_reason="GCP self-hosted L4 is not implemented by the Deployer",
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
        return self._result(
            layer="L5",
            total_cost=0.0,
            components={},
            unsupported_reason="GCP self-hosted L5 is not implemented by the Deployer",
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

    def glue_deployment_selection(self) -> ComponentDeploymentSelection:
        return _function_selection("glue.gcp.functions")
