"""
AWS Layer Calculators
======================

Aggregates AWS component costs into layer-level costs (L1-L5).

Each layer calculator:
1. Instantiates the required component calculators
2. Takes input parameters and pricing
3. Calculates total layer cost by summing component costs
4. Returns structured LayerResult with breakdown
"""

from typing import Dict, Any, Optional
from dataclasses import dataclass, field

from ..components.aws import (
    AWSIoTCoreCalculator,
    AWSLambdaCalculator,
    AWSStepFunctionsCalculator,
    AWSEventBridgeCalculator,
    AWSDynamoDBCalculator,
    AWSS3IACalculator,
    AWSS3GlacierCalculator,
    AWSTwinMakerCalculator,
    AWSGrafanaCalculator,
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


class AWSLayerCalculators:
    """
    AWS layer cost calculators for L1-L5.
    
    This class aggregates component calculators to produce
    layer-level costs matching the Twin2Clouds architecture.
    """
    
    def __init__(self):
        # Initialize all component calculators
        self.iot_core = AWSIoTCoreCalculator()
        self.lambda_calc = AWSLambdaCalculator()
        self.step_functions = AWSStepFunctionsCalculator()
        self.eventbridge = AWSEventBridgeCalculator()
        self.dynamodb = AWSDynamoDBCalculator()
        self.s3_ia = AWSS3IACalculator()
        self.s3_glacier = AWSS3GlacierCalculator()
        self.twinmaker = AWSTwinMakerCalculator()
        self.grafana = AWSGrafanaCalculator()
    
    def calculate_l1_cost(
        self,
        number_of_devices: int,
        messages_per_month: float,
        average_message_size_kb: float,
        pricing: Dict[str, Any]
    ) -> LayerResult:
        """
        Calculate L1 Data Acquisition layer cost.
        
        Components:
            - IoT Core (messaging, connectivity, rules)
            - Dispatcher Lambda (routes messages to L2)
        """
        data_size_gb = (messages_per_month * average_message_size_kb) / (1024 * 1024)
        components = {}
        
        # IoT Core cost
        iot_cost = self.iot_core.calculate_cost(
            number_of_devices=number_of_devices,
            messages_per_month=messages_per_month,
            average_message_size_kb=average_message_size_kb,
            pricing=pricing
        )
        components["iot_core"] = iot_cost
        
        # Dispatcher Lambda - runs once per message to route to L2
        dispatcher_cost = self.lambda_calc.calculate_cost(
            executions=messages_per_month,
            pricing=pricing
        )
        components["dispatcher_lambda"] = dispatcher_cost
        
        total = sum(components.values())
        
        return LayerResult(
            provider="AWS",
            layer="L1",
            total_cost=total,
            data_size_gb=data_size_gb,
            messages=messages_per_month,
            components=components
        )
    
    def calculate_l2_cost(
        self,
        executions_per_month: float,
        pricing: Dict[str, Any],
        number_of_device_types: int = 1,
        use_event_checking: bool = False,
        trigger_notification_workflow: bool = False,
        return_feedback_to_device: bool = False,
        integrate_error_handling: bool = False,
        num_event_actions: int = 0,
        events_per_message: int = 1,
        orchestration_actions: int = 3,
        event_trigger_rate: float = 0.1
    ) -> LayerResult:
        """
        Calculate L2 Data Processing layer cost.
        
        Components:
            - Persister Lambda (base processing)
            - Processor Lambda (one per device type)
            - Event Checker Lambda (optional)
            - Event Feedback Lambda (optional)
            - Step Functions (optional - if orchestration enabled)
            - EventBridge (optional - if error handling enabled)
            - Event Action Lambdas (dynamic, from events config)
        
        Args:
            executions_per_month: Number of message processing executions
            pricing: Full pricing dictionary
            number_of_device_types: Number of distinct device types (Processor per type)
            use_event_checking: Whether event checking is enabled
            trigger_notification_workflow: Whether notification workflow is enabled
            return_feedback_to_device: Whether feedback to device is enabled
            integrate_error_handling: Whether error handling is enabled
            num_event_actions: Number of event action lambdas from config
            events_per_message: Average events per message
            orchestration_actions: Actions per Step Function execution
            event_trigger_rate: Fraction of messages that trigger events (0.0-1.0)
        """
        components = {}
        
        # Persister Lambda cost (base processing)
        persister_cost = self.lambda_calc.calculate_cost(
            executions=executions_per_month,
            pricing=pricing
        )
        components["persister_lambda"] = persister_cost
        
        # Processor Lambdas - one per device type, each runs per message
        processor_cost = self.lambda_calc.calculate_cost(
            executions=executions_per_month * number_of_device_types,
            pricing=pricing
        )
        components["processor_lambdas"] = processor_cost
        
        # Optional: Event checker Lambda
        if use_event_checking:
            checker_cost = self.lambda_calc.calculate_cost(
                executions=executions_per_month,
                pricing=pricing
            )
            components["event_checker"] = checker_cost
        
        # Optional: Event Feedback Lambda (when returnFeedbackToDevice enabled)
        if use_event_checking and return_feedback_to_device:
            # Event feedback runs for messages that trigger events
            feedback_cost = self.lambda_calc.calculate_cost(
                executions=executions_per_month * event_trigger_rate,
                pricing=pricing
            )
            components["event_feedback"] = feedback_cost
        
        # Optional: Step Functions for orchestration
        if use_event_checking and trigger_notification_workflow:
            sf_cost = self.step_functions.calculate_cost(
                executions=executions_per_month,
                pricing=pricing,
                actions_per_execution=orchestration_actions
            )
            components["step_functions"] = sf_cost
        
        # Optional: EventBridge for error handling
        if integrate_error_handling:
            eb_cost = self.eventbridge.calculate_cost(
                events=executions_per_month * events_per_message,
                pricing=pricing
            )
            components["eventbridge"] = eb_cost
            
            # Error handler Lambda
            error_lambda_cost = self.lambda_calc.calculate_cost(
                executions=executions_per_month * events_per_message,
                pricing=pricing
            )
            components["error_handler"] = error_lambda_cost
        
        # Event Action Lambdas (dynamic, from config_events.json)
        if num_event_actions > 0:
            # Each event action Lambda runs when its event is triggered
            event_action_cost = self.lambda_calc.calculate_cost(
                executions=executions_per_month * event_trigger_rate * num_event_actions,
                pricing=pricing
            )
            components["event_action_lambdas"] = event_action_cost
        
        total = sum(components.values())
        
        return LayerResult(
            provider="AWS",
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
            - DynamoDB (storage, reads, writes)
            - Hot Reader Lambda (queries from L4/external)
            - Hot Reader Last Entry Lambda (latest value queries)
        
        Args:
            hot_reader_queries_per_month: Number of external queries to hot storage
        """
        components = {}
        
        # DynamoDB cost
        ddb_cost = self.dynamodb.calculate_cost(
            writes_per_month=writes_per_month,
            reads_per_month=reads_per_month,
            storage_gb=storage_gb,
            pricing=pricing
        )
        components["dynamodb"] = ddb_cost
        
        # Hot Reader Lambdas (2) - serve queries from L4 and external clients
        if hot_reader_queries_per_month > 0:
            # Hot Reader Lambda (full data queries)
            hot_reader_cost = self.lambda_calc.calculate_cost(
                executions=hot_reader_queries_per_month * 0.3,  # 30% full queries
                pricing=pricing
            )
            components["hot_reader_lambda"] = hot_reader_cost
            
            # Hot Reader Last Entry Lambda (latest value queries)
            last_entry_cost = self.lambda_calc.calculate_cost(
                executions=hot_reader_queries_per_month * 0.7,  # 70% last entry
                pricing=pricing
            )
            components["hot_reader_last_entry_lambda"] = last_entry_cost
        
        total = sum(components.values())
        
        return LayerResult(
            provider="AWS",
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
            - S3 Infrequent Access (storage)
            - Hot-Cold Mover Lambda (scheduled data migration)
            - EventBridge Rule (scheduler trigger)
        
        Args:
            mover_runs_per_month: Number of times mover runs (default: daily = 30)
        """
        components = {}
        
        # S3 IA cost
        s3_cost = self.s3_ia.calculate_cost(
            storage_gb=storage_gb,
            writes_per_month=writes_per_month,
            pricing=pricing,
            retrievals_gb=retrievals_gb
        )
        components["s3_ia"] = s3_cost
        
        # Hot-Cold Mover Lambda (scheduled to run periodically)
        # Data movers typically run longer than normal Lambdas
        mover_cost = self.lambda_calc.calculate_cost(
            executions=mover_runs_per_month,
            pricing=pricing,
            duration_ms=5000  # Mover takes longer (5 seconds)
        )
        components["hot_cold_mover_lambda"] = mover_cost
        
        # EventBridge Rule (minimal cost for scheduler)
        eb_cost = self.eventbridge.calculate_cost(
            events=mover_runs_per_month,
            pricing=pricing
        )
        components["eventbridge_scheduler"] = eb_cost
        
        total = sum(components.values())
        
        return LayerResult(
            provider="AWS",
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
            - S3 Glacier Deep Archive (storage)
            - Cold-Archive Mover Lambda (scheduled archival)
            - EventBridge Rule (scheduler trigger)
        
        Args:
            mover_runs_per_month: Number of times mover runs (default: weekly = 4)
        """
        components = {}
        
        # S3 Glacier cost
        glacier_cost = self.s3_glacier.calculate_cost(
            storage_gb=storage_gb,
            writes_per_month=writes_per_month,
            pricing=pricing,
            retrievals_gb=retrievals_gb
        )
        components["s3_glacier"] = glacier_cost
        
        # Cold-Archive Mover Lambda (scheduled to run periodically)
        mover_cost = self.lambda_calc.calculate_cost(
            executions=mover_runs_per_month,
            pricing=pricing,
            duration_ms=5000  # Mover takes longer (5 seconds)
        )
        components["cold_archive_mover_lambda"] = mover_cost
        
        # EventBridge Rule (minimal cost for scheduler)
        eb_cost = self.eventbridge.calculate_cost(
            events=mover_runs_per_month,
            pricing=pricing
        )
        components["eventbridge_scheduler"] = eb_cost
        
        total = sum(components.values())
        
        return LayerResult(
            provider="AWS",
            layer="L3_archive",
            total_cost=total,
            data_size_gb=storage_gb,
            components=components
        )
    
    def calculate_l4_cost(
        self,
        entity_count: int,
        queries_per_month: float,
        api_calls_per_month: float,
        pricing: Dict[str, Any]
    ) -> LayerResult:
        """
        Calculate L4 Twin Management layer cost.
        
        Components: IoT TwinMaker
        """
        tm_cost = self.twinmaker.calculate_cost(
            entity_count=entity_count,
            queries_per_month=queries_per_month,
            api_calls_per_month=api_calls_per_month,
            pricing=pricing
        )
        
        return LayerResult(
            provider="AWS",
            layer="L4",
            total_cost=tm_cost,
            components={"twinmaker": tm_cost}
        )
    
    def calculate_l5_cost(
        self,
        num_editors: int,
        num_viewers: int,
        pricing: Dict[str, Any]
    ) -> LayerResult:
        """
        Calculate L5 Visualization layer cost.
        
        Components: Managed Grafana
        """
        grafana_cost = self.grafana.calculate_cost(
            num_editors=num_editors,
            num_viewers=num_viewers,
            pricing=pricing
        )
        
        return LayerResult(
            provider="AWS",
            layer="L5",
            total_cost=grafana_cost,
            components={"grafana": grafana_cost}
        )
    
    def calculate_glue_cost(
        self,
        messages: float,
        pricing: Dict[str, Any]
    ) -> float:
        """
        Calculate cross-cloud glue function cost.
        
        Glue functions use Lambda pricing.
        """
        return self.lambda_calc.calculate_glue_function_cost(
            messages=messages,
            pricing=pricing
        )
