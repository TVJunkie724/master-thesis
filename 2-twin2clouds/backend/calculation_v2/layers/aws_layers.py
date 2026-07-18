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

from typing import Dict, Any

from .contracts import (
    BaseLayerCalculatorSet,
    ComponentDeploymentSelection,
    LayerResult,
    SUPPORTED_LAYER_KEYS,
    TransitionRuntimeResult,
)

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
from ..components.aws.twinmaker import evaluate_twinmaker_context
from ..deployment_profiles import (
    AWS_MOVER_LAMBDA_MEMORY_MB,
    AWS_STANDARD_LAMBDA_MEMORY_MB,
    MOVER_FUNCTION_DURATION_MS,
    STANDARD_FUNCTION_DURATION_MS,
)


def _selection(
    component_id: str,
    **dimensions: str | int | bool,
) -> ComponentDeploymentSelection:
    return ComponentDeploymentSelection(component_id, dimensions)


def _standard_lambda_selection(component_id: str) -> ComponentDeploymentSelection:
    return _selection(
        component_id,
        **{
            "aws.lambda.memory_mb": AWS_STANDARD_LAMBDA_MEMORY_MB,
            "aws.lambda.duration_ms": STANDARD_FUNCTION_DURATION_MS,
        },
    )


def _mover_lambda_selection(
    component_id: str,
    *,
    schedule_expression: str,
) -> ComponentDeploymentSelection:
    return _selection(
        component_id,
        **{
            "aws.lambda.memory_mb": AWS_MOVER_LAMBDA_MEMORY_MB,
            "aws.lambda.duration_ms": MOVER_FUNCTION_DURATION_MS,
            "aws.eventbridge.schedule_expression": schedule_expression,
        },
    )

class AWSLayerCalculators(BaseLayerCalculatorSet):
    """
    AWS layer cost calculators for L1-L5.
    
    This class aggregates component calculators to produce
    layer-level costs matching the Twin2Clouds architecture.
    """
    
    provider = "AWS"
    supported_layers = SUPPORTED_LAYER_KEYS

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
        
        return self._result(
            layer="L1",
            total_cost=total,
            data_size_gb=data_size_gb,
            messages=messages_per_month,
            components=components,
            deployment_selections=(
                _selection(
                    "l1.aws.iot_core",
                    **{"aws.iot_core.message_pricing": "progressive_usage"},
                ),
                _standard_lambda_selection("l1.aws.dispatcher_lambda"),
            ),
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
        
        deployment_selections = [
            _standard_lambda_selection("l2.aws.processing_lambdas")
        ]
        if use_event_checking and trigger_notification_workflow:
            deployment_selections.append(
                _selection(
                    "l2.aws.step_functions",
                    **{"aws.step_functions.billing": "state_transitions"},
                )
            )
        if integrate_error_handling:
            deployment_selections.append(
                _selection(
                    "l2.aws.eventbridge",
                    **{"aws.eventbridge.billing": "events"},
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
        
        return self._result(
            layer="L3_hot",
            total_cost=total,
            data_size_gb=storage_gb,
            components=components,
            deployment_selections=(
                _selection(
                    "l3_hot.aws.dynamodb",
                    **{"aws.dynamodb.billing_mode": "PAY_PER_REQUEST"},
                ),
                _standard_lambda_selection("l3_hot.aws.reader_lambdas"),
            ),
        )
    
    def calculate_l3_cool_cost(
        self,
        storage_gb: float,
        writes_per_month: float,
        pricing: Dict[str, Any],
        retrievals_gb: float = 0.0,
    ) -> LayerResult:
        """Calculate destination-independent S3 Infrequent Access cost."""
        components = {}
        
        # S3 IA cost
        s3_cost = self.s3_ia.calculate_cost(
            storage_gb=storage_gb,
            writes_per_month=writes_per_month,
            pricing=pricing,
            retrievals_gb=retrievals_gb
        )
        components["s3_ia"] = s3_cost

        return self._result(
            layer="L3_cool",
            total_cost=s3_cost,
            data_size_gb=storage_gb,
            components=components,
            deployment_selections=(
                _selection(
                    "l3_cool.aws.s3",
                    **{"aws.s3.storage_class": "STANDARD_IA"},
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
        """Calculate destination-independent S3 Glacier archive cost."""
        components = {}
        
        # S3 Glacier cost
        glacier_cost = self.s3_glacier.calculate_cost(
            storage_gb=storage_gb,
            writes_per_month=writes_per_month,
            pricing=pricing,
            retrievals_gb=retrievals_gb
        )
        components["s3_glacier"] = glacier_cost

        return self._result(
            layer="L3_archive",
            total_cost=glacier_cost,
            data_size_gb=storage_gb,
            components=components,
            deployment_selections=(
                _selection(
                    "l3_archive.aws.s3",
                    **{"aws.s3.storage_class": "DEEP_ARCHIVE"},
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
        """Calculate the Lambda and EventBridge runtime owned by source storage."""

        runtime_profiles = {
            "l3_hot_to_l3_cool": (
                "transition.l3_hot_to_l3_cool.aws.runtime",
                "rate(1 day)",
            ),
            "l3_cool_to_l3_archive": (
                "transition.l3_cool_to_l3_archive.aws.runtime",
                "rate(7 days)",
            ),
        }
        try:
            component_id, schedule_expression = runtime_profiles[edge_id]
        except KeyError as exc:
            raise ValueError(
                f"Unsupported AWS transition runtime edge: {edge_id!r}"
            ) from exc

        function_cost = self.lambda_calc.calculate_cost(
            executions=monthly_invocations,
            pricing=pricing,
            duration_ms=MOVER_FUNCTION_DURATION_MS,
            memory_mb=AWS_MOVER_LAMBDA_MEMORY_MB,
        )
        # Terraform deploys a legacy same-account scheduled rule, not custom
        # event ingestion. The custom EventBridge event-bus row therefore does
        # not describe this trigger and must not be charged here.
        trigger_cost = 0.0
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
            ),
            evidence_references=(
                "aws.lambda",
            ),
            deployment_selection=_mover_lambda_selection(
                component_id,
                schedule_expression=schedule_expression,
            ),
        )
    
    def calculate_l4_cost(
        self,
        entity_count: int,
        queries_per_month: float,
        api_calls_per_month: float,
        pricing: Dict[str, Any],
        account_pricing_context: Dict[str, Any] | None = None,
    ) -> LayerResult:
        """
        Calculate L4 Twin Management layer cost.
        
        Components: IoT TwinMaker
        """
        evaluation = evaluate_twinmaker_context(
            account_pricing_context,
            pricing,
        )
        if not evaluation.comparable:
            return self._result(
                layer="L4",
                total_cost=0,
                components={},
                details={"pricingContext": dict(evaluation.diagnostic)},
                unsupported_reason=evaluation.reason_code,
            )

        breakdown = self.twinmaker.calculate_standard_cost(
            entity_count=entity_count,
            queries_per_month=queries_per_month,
            api_calls_per_month=api_calls_per_month,
            pricing=pricing
        )
        
        return self._result(
            layer="L4",
            total_cost=breakdown.total,
            components={
                "twinmaker": breakdown.total,
                "twinmaker_entities": breakdown.entity_cost,
                "twinmaker_queries": breakdown.query_cost,
                "twinmaker_api_calls": breakdown.api_call_cost,
            },
            details={
                "pricingContext": dict(evaluation.diagnostic),
                "calculation": {
                    "pricingMode": "STANDARD",
                    "currency": "USD",
                    "period": "month",
                    "dimensions": [
                        {
                            "intentId": "digital_twin.entity_month",
                            "quantity": breakdown.entity_count,
                            "unit": "entity_month",
                            "unitPrice": breakdown.entity_price_per_month,
                            "contribution": breakdown.entity_cost,
                        },
                        {
                            "intentId": "digital_twin.query",
                            "quantity": breakdown.queries_per_month,
                            "unit": "query",
                            "unitPrice": breakdown.query_price,
                            "contribution": breakdown.query_cost,
                        },
                        {
                            "intentId": "digital_twin.api_call",
                            "quantity": breakdown.api_calls_per_month,
                            "unit": "api_call",
                            "unitPrice": breakdown.api_call_price,
                            "contribution": breakdown.api_call_cost,
                        },
                    ],
                },
            },
            deployment_selections=(
                _selection(
                    "l4.aws.twinmaker",
                    **{"aws.twinmaker.account_plan": "STANDARD"},
                ),
                _selection(
                    "l4.aws.connector_lambda",
                    **{"aws.lambda.memory_mb": AWS_STANDARD_LAMBDA_MEMORY_MB},
                ),
            ),
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
        
        return self._result(
            layer="L5",
            total_cost=grafana_cost,
            components={"grafana": grafana_cost},
            deployment_selections=(
                _selection(
                    "l5.aws.managed_grafana",
                    **{"aws.grafana.user_billing": "licensed_users"},
                ),
            ),
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

    def glue_deployment_selection(self) -> ComponentDeploymentSelection:
        return _standard_lambda_selection("glue.aws.lambda")
