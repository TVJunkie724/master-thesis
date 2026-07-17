"""
Optimization strategy contracts.

This module declares the authoritative relationship between an optimization
objective, pricing intents, provider pricing fields, calculation formulas, and
evidence requirements. It does not fetch prices and it does not calculate costs;
it is the contract that prevents those concerns from drifting apart.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Dict, Iterable, Mapping, Optional, Sequence, Tuple

from backend.calculation_v2.components import FormulaType, LayerType, Provider


class OptimizationObjective(str, Enum):
    """Supported and planned optimization objectives."""

    COST = "cost"
    LATENCY = "latency"
    EMISSIONS = "emissions"
    RESILIENCE = "resilience"


class ObjectiveStatus(str, Enum):
    """Whether an optimization objective can be selected at runtime."""

    ENABLED = "enabled"
    DISABLED = "disabled"


class PricingSourceType(str, Enum):
    """How a pricing field is expected to be sourced."""

    DYNAMIC_PROVIDER_API = "dynamic_provider_api"
    STATIC_OFFICIAL_TABLE = "static_official_table"
    REVIEWED_DECISION = "reviewed_decision"
    DERIVED_CALCULATION = "derived_calculation"
    UNSUPPORTED = "unsupported"


class EvidenceRequirement(str, Enum):
    """Evidence policy for a selected pricing value."""

    REQUIRED = "required"
    NOT_APPLICABLE = "not_applicable"


@dataclass(frozen=True)
class PricingFieldContract:
    """One canonical pricing field consumed by a formula."""

    field_id: str
    key_path: Tuple[str, ...]
    canonical_unit: str
    source_unit: str
    quantity_basis: str
    source_type: PricingSourceType
    evidence: EvidenceRequirement = EvidenceRequirement.REQUIRED
    aliases: Tuple[Tuple[str, ...], ...] = ()
    normalizer: Optional[str] = None
    emergency_fallback_source_type: Optional[PricingSourceType] = None
    emergency_fallback_allowed: bool = False

    def candidate_paths(self) -> Tuple[Tuple[str, ...], ...]:
        return (self.key_path,) + self.aliases


@dataclass(frozen=True)
class PricingIntentContract:
    """Provider-specific pricing intent for a calculator component."""

    intent_id: str
    provider: Provider
    layer: LayerType
    component_id: str
    service_key: str
    description: str
    fields: Tuple[PricingFieldContract, ...]
    enabled_for_cost_path: bool = True


@dataclass(frozen=True)
class FormulaBindingContract:
    """Binding between pricing intents and a calculation formula."""

    binding_id: str
    formula_type: FormulaType
    intent_ids: Tuple[str, ...]
    calculation_entrypoint: str
    result_component: str
    required_usage_inputs: Tuple[str, ...]
    normalizer: Optional[str] = None


@dataclass(frozen=True)
class OptimizationStrategyContract:
    """Complete contract for one optimization objective."""

    objective: OptimizationObjective
    status: ObjectiveStatus
    description: str
    result_fields: Tuple[str, ...]
    pricing_intents: Tuple[PricingIntentContract, ...] = ()
    formula_bindings: Tuple[FormulaBindingContract, ...] = ()
    extension_note: Optional[str] = None

    def intent_map(self) -> Dict[str, PricingIntentContract]:
        return {intent.intent_id: intent for intent in self.pricing_intents}

    def validate(self) -> Tuple[str, ...]:
        errors = []

        intent_ids = [intent.intent_id for intent in self.pricing_intents]
        duplicate_intents = sorted({item for item in intent_ids if intent_ids.count(item) > 1})
        for intent_id in duplicate_intents:
            errors.append(f"Duplicate pricing intent id: {intent_id}")

        known_intents = set(intent_ids)
        for binding in self.formula_bindings:
            for intent_id in binding.intent_ids:
                if intent_id not in known_intents:
                    errors.append(
                        f"Formula binding {binding.binding_id} references unknown intent {intent_id}"
                    )

        if self.status == ObjectiveStatus.DISABLED:
            if self.pricing_intents or self.formula_bindings:
                errors.append(
                    f"Disabled objective {self.objective.value} must not declare active pricing bindings"
                )
            return tuple(errors)

        for intent in self.pricing_intents:
            expected_provider = intent.provider.value
            for field in intent.fields:
                if not field.key_path:
                    errors.append(f"{intent.intent_id}.{field.field_id} has an empty key path")
                    continue
                if field.key_path[0] != expected_provider:
                    errors.append(
                        f"{intent.intent_id}.{field.field_id} path starts with "
                        f"{field.key_path[0]!r}, expected {expected_provider!r}"
                    )
                if field.evidence == EvidenceRequirement.REQUIRED and not field.source_type:
                    errors.append(f"{intent.intent_id}.{field.field_id} requires a source type")

        if not self.formula_bindings:
            errors.append(f"Enabled objective {self.objective.value} has no formula bindings")

        return tuple(errors)


def _field(
    field_id: str,
    path: Sequence[str],
    canonical_unit: str,
    source_unit: str,
    quantity_basis: str,
    *,
    source_type: PricingSourceType = PricingSourceType.DYNAMIC_PROVIDER_API,
    aliases: Sequence[Sequence[str]] = (),
    normalizer: Optional[str] = None,
    emergency_fallback_source_type: Optional[PricingSourceType] = None,
    emergency_fallback_allowed: bool = False,
) -> PricingFieldContract:
    return PricingFieldContract(
        field_id=field_id,
        key_path=tuple(path),
        canonical_unit=canonical_unit,
        source_unit=source_unit,
        quantity_basis=quantity_basis,
        source_type=source_type,
        aliases=tuple(tuple(alias) for alias in aliases),
        normalizer=normalizer,
        emergency_fallback_source_type=emergency_fallback_source_type,
        emergency_fallback_allowed=emergency_fallback_allowed,
    )


def _intent(
    intent_id: str,
    provider: Provider,
    layer: LayerType,
    component_id: str,
    service_key: str,
    description: str,
    fields: Iterable[PricingFieldContract],
    *,
    enabled_for_cost_path: bool = True,
) -> PricingIntentContract:
    return PricingIntentContract(
        intent_id=intent_id,
        provider=provider,
        layer=layer,
        component_id=component_id,
        service_key=service_key,
        description=description,
        fields=tuple(fields),
        enabled_for_cost_path=enabled_for_cost_path,
    )


def _binding(
    binding_id: str,
    formula_type: FormulaType,
    intent_ids: Sequence[str],
    calculation_entrypoint: str,
    result_component: str,
    required_usage_inputs: Sequence[str],
    *,
    normalizer: Optional[str] = None,
) -> FormulaBindingContract:
    return FormulaBindingContract(
        binding_id=binding_id,
        formula_type=formula_type,
        intent_ids=tuple(intent_ids),
        calculation_entrypoint=calculation_entrypoint,
        result_component=result_component,
        required_usage_inputs=tuple(required_usage_inputs),
        normalizer=normalizer,
    )


def cost_strategy_contract() -> OptimizationStrategyContract:
    """Return the only currently enabled optimization strategy."""

    # TODO(future-optimization-entrypoint): New optimizer objectives need their
    # own strategy contract function that declares pricing/metric intents,
    # formula bindings, source units, normalizers, evidence requirements, and
    # drift tests. Do not add active formula bindings to disabled objectives.
    intents = (
        _intent(
            "aws.l1.iot_core",
            Provider.AWS,
            LayerType.L1_INGESTION,
            "iot_core",
            "iotCore",
            "AWS IoT Core message ingestion and rules charges.",
            (
                _field("device_month", ("aws", "iotCore", "pricePerDeviceAndMonth"), "usd/device_month", "usd/device_month", "connected_devices"),
                _field("rule_action", ("aws", "iotCore", "priceRulesTriggered"), "usd/action", "usd/action", "rules_triggered"),
                _field("message_tiers", ("aws", "iotCore", "pricing_tiers"), "usd/message", "tier_table", "billable_messages", normalizer="aws_iot_core_tier_table"),
            ),
        ),
        _intent(
            "azure.l1.iot_hub",
            Provider.AZURE,
            LayerType.L1_INGESTION,
            "iot_hub",
            "iotHub",
            "Azure IoT Hub unit tiers normalized to message pricing.",
            (
                _field("message_tiers", ("azure", "iotHub", "pricing_tiers"), "usd/message", "tier_table", "billable_messages", normalizer="azure_iot_hub_tier_table"),
            ),
        ),
        _intent(
            "gcp.l1.pubsub",
            Provider.GCP,
            LayerType.L1_INGESTION,
            "pubsub",
            "iot",
            "GCP Pub/Sub volume-based ingestion pricing.",
            (
                _field("data_volume", ("gcp", "iot", "pricePerGiB"), "usd/gib", "usd/gib", "ingested_gib", aliases=(("gcp", "iot", "pricePerGB"),), normalizer="gb_to_gib_volume_if_source_uses_gb"),
                _field("device_month", ("gcp", "iot", "pricePerDeviceAndMonth"), "usd/device_month", "usd/device_month", "connected_devices"),
            ),
        ),
        _intent(
            "aws.l2.lambda",
            Provider.AWS,
            LayerType.L2_PROCESSING,
            "lambda",
            "lambda",
            "AWS Lambda request and GB-second pricing.",
            (
                _field("request", ("aws", "lambda", "requestPrice"), "usd/invocation", "usd/invocation", "executions"),
                _field("duration", ("aws", "lambda", "durationPrice"), "usd/gb_second", "usd/gb_second", "gb_seconds"),
                _field("free_requests", ("aws", "lambda", "freeRequests"), "invocation", "invocation", "free_tier"),
                _field("free_compute", ("aws", "lambda", "freeComputeTime"), "gb_second", "gb_second", "free_tier"),
            ),
        ),
        _intent(
            "azure.l2.functions",
            Provider.AZURE,
            LayerType.L2_PROCESSING,
            "functions",
            "functions",
            "Azure Functions request and GB-second pricing.",
            (
                _field("request", ("azure", "functions", "requestPrice"), "usd/invocation", "usd/invocation", "executions"),
                _field("duration", ("azure", "functions", "durationPrice"), "usd/gb_second", "usd/gb_second", "gb_seconds"),
                _field("free_requests", ("azure", "functions", "freeRequests"), "invocation", "invocation", "free_tier"),
                _field("free_compute", ("azure", "functions", "freeComputeTime"), "gb_second", "gb_second", "free_tier"),
            ),
        ),
        _intent(
            "gcp.l2.functions",
            Provider.GCP,
            LayerType.L2_PROCESSING,
            "cloud_functions",
            "functions",
            "GCP Cloud Functions request and GB-second pricing.",
            (
                _field("request", ("gcp", "functions", "requestPrice"), "usd/invocation", "usd/invocation", "executions", aliases=(("gcp", "functions", "invocationPrice"),)),
                _field("duration", ("gcp", "functions", "durationPrice"), "usd/gb_second", "usd/gb_second", "gb_seconds", aliases=(("gcp", "functions", "gbSecondPrice"),)),
                _field("free_requests", ("gcp", "functions", "freeRequests"), "invocation", "invocation", "free_tier", aliases=(("gcp", "functions", "freeInvocations"),)),
                _field("free_compute", ("gcp", "functions", "freeComputeTime"), "gb_second", "gb_second", "free_tier", aliases=(("gcp", "functions", "freeGBSeconds"),)),
            ),
        ),
        _intent(
            "aws.l2.step_functions",
            Provider.AWS,
            LayerType.L2_PROCESSING,
            "step_functions",
            "stepFunctions",
            "AWS Step Functions state transition pricing.",
            (
                _field("state_transition", ("aws", "stepFunctions", "pricePerStateTransition"), "usd/action", "usd/action", "state_transitions", aliases=(("aws", "stepFunctions", "pricePer1kStateTransitions"),), normalizer="price_per_1k_to_price_per_action"),
            ),
        ),
        _intent(
            "azure.l2.logic_apps",
            Provider.AZURE,
            LayerType.L2_PROCESSING,
            "logic_apps",
            "logicApps",
            "Azure Logic Apps action pricing.",
            (
                _field("state_transition", ("azure", "logicApps", "pricePerStateTransition"), "usd/action", "usd/action", "state_transitions", aliases=(("azure", "logicApps", "pricePer1kStateTransitions"),), normalizer="price_per_1k_to_price_per_action"),
            ),
        ),
        _intent(
            "gcp.l2.workflows",
            Provider.GCP,
            LayerType.L2_PROCESSING,
            "cloud_workflows",
            "cloudWorkflows",
            "GCP Cloud Workflows step pricing.",
            (
                _field("step", ("gcp", "cloudWorkflows", "stepPrice"), "usd/action", "usd/action", "workflow_steps", aliases=(("gcp", "cloudWorkflows", "pricePerStep"),)),
            ),
        ),
        _intent(
            "aws.l2.eventbridge",
            Provider.AWS,
            LayerType.L2_PROCESSING,
            "eventbridge",
            "eventBridge",
            "AWS EventBridge event pricing.",
            (
                _field("event", ("aws", "eventBridge", "pricePerMillionEvents"), "usd/action", "usd/million_actions", "events", normalizer="price_per_million_to_price_per_action"),
            ),
        ),
        _intent(
            "azure.l2.event_grid",
            Provider.AZURE,
            LayerType.L2_PROCESSING,
            "event_grid",
            "eventGrid",
            "Azure Event Grid operation pricing.",
            (
                _field("event", ("azure", "eventGrid", "pricePerMillionEvents"), "usd/action", "usd/million_actions", "events", aliases=(("azure", "eventGrid", "pricePerMillionOperations"),), normalizer="price_per_million_to_price_per_action"),
            ),
        ),
        _intent(
            "aws.l3.dynamodb",
            Provider.AWS,
            LayerType.L3_HOT_STORAGE,
            "dynamodb",
            "dynamoDB",
            "AWS DynamoDB read, write, and storage pricing.",
            (
                _field("write", ("aws", "dynamoDB", "writePrice"), "usd/action", "usd/action", "writes"),
                _field("read", ("aws", "dynamoDB", "readPrice"), "usd/action", "usd/action", "reads"),
                _field("storage", ("aws", "dynamoDB", "storagePrice"), "usd/gb_month", "usd/gb_month", "stored_gb_month"),
                _field("free_storage", ("aws", "dynamoDB", "freeStorage"), "gb_month", "gb_month", "free_tier"),
            ),
        ),
        _intent(
            "azure.l3.cosmos_db",
            Provider.AZURE,
            LayerType.L3_HOT_STORAGE,
            "cosmos_db",
            "cosmosDB",
            "Azure Cosmos DB request unit and storage pricing.",
            (
                _field("request_unit", ("azure", "cosmosDB", "requestPrice"), "usd/ru", "usd/million_ru", "request_units", aliases=(("azure", "cosmosDB", "requestUnitPrice"),), normalizer="price_per_million_to_price_per_action"),
                _field("ru_per_read", ("azure", "cosmosDB", "RUsPerRead"), "ru/read", "ru/read", "read_weight"),
                _field("ru_per_write", ("azure", "cosmosDB", "RUsPerWrite"), "ru/write", "ru/write", "write_weight"),
                _field("storage", ("azure", "cosmosDB", "storagePrice"), "usd/gb_month", "usd/gb_month", "stored_gb_month"),
            ),
        ),
        _intent(
            "gcp.l3.firestore",
            Provider.GCP,
            LayerType.L3_HOT_STORAGE,
            "firestore",
            "storage_hot",
            "GCP Firestore operation and storage pricing.",
            (
                _field("write", ("gcp", "storage_hot", "writePrice"), "usd/action", "usd/100k_actions", "writes", aliases=(("gcp", "storage_hot", "documentWritePrice"),), normalizer="price_per_100k_to_price_per_action"),
                _field("read", ("gcp", "storage_hot", "readPrice"), "usd/action", "usd/100k_actions", "reads", aliases=(("gcp", "storage_hot", "documentReadPrice"),), normalizer="price_per_100k_to_price_per_action"),
                _field("storage", ("gcp", "storage_hot", "storagePrice"), "usd/gb_month", "usd/gb_month", "stored_gb_month"),
            ),
        ),
        _intent(
            "aws.l3.s3_ia",
            Provider.AWS,
            LayerType.L3_COOL_STORAGE,
            "s3_ia",
            "s3InfrequentAccess",
            "AWS S3 Infrequent Access storage, request, and retrieval pricing.",
            (
                _field("storage", ("aws", "s3InfrequentAccess", "storagePrice"), "usd/gb_month", "usd/gb_month", "stored_gb_month"),
                _field("write", ("aws", "s3InfrequentAccess", "requestPrice"), "usd/action", "usd/action", "writes", aliases=(("aws", "s3InfrequentAccess", "writePrice"),)),
                _field("retrieval", ("aws", "s3InfrequentAccess", "dataRetrievalPrice"), "usd/gb", "usd/gb", "retrieved_gb"),
            ),
        ),
        _intent(
            "azure.l3.blob_cool",
            Provider.AZURE,
            LayerType.L3_COOL_STORAGE,
            "blob_cool",
            "blobStorageCool",
            "Azure Blob Storage Cool storage, operation, and retrieval pricing.",
            (
                _field("storage", ("azure", "blobStorageCool", "storagePrice"), "usd/gb_month", "usd/gb_month", "stored_gb_month"),
                _field("write", ("azure", "blobStorageCool", "writePrice"), "usd/action", "usd/action", "writes"),
                _field("retrieval", ("azure", "blobStorageCool", "dataRetrievalPrice"), "usd/gb", "usd/gb", "retrieved_gb"),
            ),
        ),
        _intent(
            "gcp.l3.gcs_nearline",
            Provider.GCP,
            LayerType.L3_COOL_STORAGE,
            "gcs_nearline",
            "storage_cool",
            "GCP Cloud Storage Nearline storage, request, and retrieval pricing.",
            (
                _field("storage", ("gcp", "storage_cool", "storagePrice"), "usd/gb_month", "usd/gb_month", "stored_gb_month"),
                _field("write", ("gcp", "storage_cool", "requestPrice"), "usd/action", "usd/action", "writes", aliases=(("gcp", "storage_cool", "writePrice"),)),
                _field("retrieval", ("gcp", "storage_cool", "dataRetrievalPrice"), "usd/gb", "usd/gb", "retrieved_gb", aliases=(("gcp", "storage_cool", "retrievalPrice"),)),
            ),
        ),
        _intent(
            "aws.l3.s3_glacier",
            Provider.AWS,
            LayerType.L3_ARCHIVE_STORAGE,
            "s3_glacier",
            "s3GlacierDeepArchive",
            "AWS S3 Glacier Deep Archive storage, lifecycle, and retrieval pricing.",
            (
                _field("storage", ("aws", "s3GlacierDeepArchive", "storagePrice"), "usd/gb_month", "usd/gb_month", "stored_gb_month"),
                _field("lifecycle_write", ("aws", "s3GlacierDeepArchive", "lifecycleAndWritePrice"), "usd/action", "usd/action", "writes", aliases=(("aws", "s3GlacierDeepArchive", "writePrice"),)),
                _field("retrieval", ("aws", "s3GlacierDeepArchive", "dataRetrievalPrice"), "usd/gb", "usd/gb", "retrieved_gb"),
            ),
        ),
        _intent(
            "azure.l3.blob_archive",
            Provider.AZURE,
            LayerType.L3_ARCHIVE_STORAGE,
            "blob_archive",
            "blobStorageArchive",
            "Azure Blob Storage Archive storage, operation, and retrieval pricing.",
            (
                _field("storage", ("azure", "blobStorageArchive", "storagePrice"), "usd/gb_month", "usd/gb_month", "stored_gb_month"),
                _field("write", ("azure", "blobStorageArchive", "writePrice"), "usd/action", "usd/action", "writes"),
                _field("retrieval", ("azure", "blobStorageArchive", "dataRetrievalPrice"), "usd/gb", "usd/gb", "retrieved_gb"),
            ),
        ),
        _intent(
            "gcp.l3.gcs_coldline",
            Provider.GCP,
            LayerType.L3_ARCHIVE_STORAGE,
            "gcs_coldline",
            "storage_archive",
            "GCP Cloud Storage Coldline storage, lifecycle, and retrieval pricing.",
            (
                _field("storage", ("gcp", "storage_archive", "storagePrice"), "usd/gb_month", "usd/gb_month", "stored_gb_month"),
                _field("lifecycle_write", ("gcp", "storage_archive", "lifecycleAndWritePrice"), "usd/action", "usd/action", "writes", aliases=(("gcp", "storage_archive", "writePrice"),)),
                _field("retrieval", ("gcp", "storage_archive", "dataRetrievalPrice"), "usd/gb", "usd/gb", "retrieved_gb", aliases=(("gcp", "storage_archive", "retrievalPrice"),)),
            ),
        ),
        _intent(
            "aws.l4.twinmaker",
            Provider.AWS,
            LayerType.L4_TWIN_MANAGEMENT,
            "twinmaker",
            "iotTwinMaker",
            "AWS IoT TwinMaker entity, query, and API pricing.",
            (
                _field("entity", ("aws", "iotTwinMaker", "usageRates", "entityPricePerMonth"), "usd/entity_month", "usd/entity_month", "entities"),
                _field("query", ("aws", "iotTwinMaker", "usageRates", "queryPrice"), "usd/query", "usd/query", "queries"),
                _field("api_call", ("aws", "iotTwinMaker", "usageRates", "unifiedDataAccessApiCallPrice"), "usd/action", "usd/action", "api_calls"),
            ),
        ),
        _intent(
            "azure.l4.digital_twins_operations",
            Provider.AZURE,
            LayerType.L4_TWIN_MANAGEMENT,
            "digital_twins_operations",
            "azureDigitalTwins",
            "Azure Digital Twins billable operation pricing.",
            (
                _field("operation", ("azure", "azureDigitalTwins", "pricePerOperation"), "usd/action", "usd/action", "operations"),
            ),
        ),
        _intent(
            "azure.l4.digital_twins_messages",
            Provider.AZURE,
            LayerType.L4_TWIN_MANAGEMENT,
            "digital_twins_routed_messages",
            "azureDigitalTwins",
            "Azure Digital Twins routed-message pricing.",
            (
                _field("message", ("azure", "azureDigitalTwins", "pricePerMessage"), "usd/message", "usd/message", "messages"),
            ),
        ),
        _intent(
            "azure.l4.digital_twins_query_units",
            Provider.AZURE,
            LayerType.L4_TWIN_MANAGEMENT,
            "digital_twins_query_units",
            "azureDigitalTwins",
            "Azure Digital Twins query-unit pricing.",
            (
                _field("query", ("azure", "azureDigitalTwins", "pricePerQueryUnit"), "usd/query_unit", "usd/query_unit", "query_units"),
            ),
        ),
        _intent(
            "gcp.l4.self_hosted_twin",
            Provider.GCP,
            LayerType.L4_TWIN_MANAGEMENT,
            "self_hosted_twin",
            "twinmaker",
            "GCP self-hosted twin service pricing, selectable only when explicitly enabled.",
            (
                _field("vm_hour", ("gcp", "twinmaker", "e2MediumPrice"), "usd/hour", "usd/hour", "vm_hours"),
                _field("storage", ("gcp", "twinmaker", "storagePrice"), "usd/gb_month", "usd/gb_month", "disk_gb_month"),
            ),
            enabled_for_cost_path=False,
        ),
        _intent(
            "aws.l5.grafana",
            Provider.AWS,
            LayerType.L5_VISUALIZATION,
            "grafana",
            "awsManagedGrafana",
            "AWS Managed Grafana seat pricing.",
            (
                _field("editor", ("aws", "awsManagedGrafana", "editorPrice"), "usd/editor_month", "usd/editor_month", "editors"),
                _field("viewer", ("aws", "awsManagedGrafana", "viewerPrice"), "usd/viewer_month", "usd/viewer_month", "viewers"),
            ),
        ),
        _intent(
            "azure.l5.grafana",
            Provider.AZURE,
            LayerType.L5_VISUALIZATION,
            "grafana",
            "azureManagedGrafana",
            "Azure Managed Grafana user and workspace pricing.",
            (
                _field("user", ("azure", "azureManagedGrafana", "userPrice"), "usd/user_month", "usd/user_month", "users"),
                _field("hour", ("azure", "azureManagedGrafana", "hourlyPrice"), "usd/hour", "usd/hour", "workspace_hours"),
            ),
        ),
        _intent(
            "gcp.l5.self_hosted_grafana",
            Provider.GCP,
            LayerType.L5_VISUALIZATION,
            "self_hosted_grafana",
            "grafana",
            "GCP self-hosted Grafana pricing, selectable only when explicitly enabled.",
            (
                _field("vm_hour", ("gcp", "grafana", "e2MediumPrice"), "usd/hour", "usd/hour", "vm_hours"),
                _field("storage", ("gcp", "grafana", "storagePrice"), "usd/gb_month", "usd/gb_month", "disk_gb_month"),
            ),
            enabled_for_cost_path=False,
        ),
        _intent(
            "aws.transfer.egress",
            Provider.AWS,
            LayerType.L0_GLUE,
            "transfer",
            "transfer",
            "AWS cross-cloud egress pricing.",
            (
                _field(
                    "catalog",
                    ("aws", "transfer"),
                    "transfer_catalog",
                    "transfer_catalog",
                    "egress_bytes",
                    normalizer="canonical_transfer_catalog",
                ),
            ),
        ),
        _intent(
            "azure.transfer.egress",
            Provider.AZURE,
            LayerType.L0_GLUE,
            "transfer",
            "transfer",
            "Azure cross-cloud egress pricing.",
            (
                _field(
                    "catalog",
                    ("azure", "transfer"),
                    "transfer_catalog",
                    "transfer_catalog",
                    "egress_bytes",
                    normalizer="canonical_transfer_catalog",
                ),
            ),
        ),
        _intent(
            "gcp.transfer.egress",
            Provider.GCP,
            LayerType.L0_GLUE,
            "transfer",
            "transfer",
            "GCP cross-cloud egress pricing.",
            (
                _field(
                    "catalog",
                    ("gcp", "transfer"),
                    "transfer_catalog",
                    "transfer_catalog",
                    "egress_bytes",
                    normalizer="canonical_transfer_catalog",
                ),
            ),
        ),
    )

    bindings = (
        _binding("cost.aws.l1.iot_core", FormulaType.CM, ("aws.l1.iot_core",), "AWSIoTCoreCalculator.calculate_cost", "L1.iot_core", ("number_of_devices", "messages_per_month", "average_message_size_kb"), normalizer="aws_iot_core_tier_table"),
        _binding("cost.azure.l1.iot_hub", FormulaType.CM, ("azure.l1.iot_hub",), "AzureIoTHubCalculator.calculate_cost", "L1.iot_hub", ("messages_per_month", "units"), normalizer="azure_iot_hub_tier_table"),
        _binding("cost.gcp.l1.pubsub", FormulaType.CTRANSFER, ("gcp.l1.pubsub",), "GCPPubSubCalculator.calculate_cost", "L1.pubsub", ("data_volume_gb",)),
        _binding("cost.aws.l2.lambda", FormulaType.CE, ("aws.l2.lambda",), "AWSLambdaCalculator.calculate_cost", "L2.lambda", ("executions", "duration_ms", "memory_mb")),
        _binding("cost.azure.l2.functions", FormulaType.CE, ("azure.l2.functions",), "AzureFunctionsCalculator.calculate_cost", "L2.functions", ("executions", "duration_ms", "memory_mb")),
        _binding("cost.gcp.l2.functions", FormulaType.CE, ("gcp.l2.functions",), "GCPCloudFunctionsCalculator.calculate_cost", "L2.cloud_functions", ("executions", "duration_ms", "memory_mb")),
        _binding("cost.aws.l2.step_functions", FormulaType.CA, ("aws.l2.step_functions",), "AWSStepFunctionsCalculator.calculate_cost", "L2.step_functions", ("executions", "states_per_execution"), normalizer="price_per_1k_to_price_per_action"),
        _binding("cost.azure.l2.logic_apps", FormulaType.CA, ("azure.l2.logic_apps",), "AzureLogicAppsCalculator.calculate_cost", "L2.logic_apps", ("executions", "actions_per_execution"), normalizer="price_per_1k_to_price_per_action"),
        _binding("cost.gcp.l2.workflows", FormulaType.CA, ("gcp.l2.workflows",), "GCPCloudWorkflowsCalculator.calculate_cost", "L2.cloud_workflows", ("executions", "steps_per_execution")),
        _binding("cost.aws.l2.eventbridge", FormulaType.CA, ("aws.l2.eventbridge",), "AWSEventBridgeCalculator.calculate_cost", "L2.eventbridge", ("events",), normalizer="price_per_million_to_price_per_action"),
        _binding("cost.azure.l2.event_grid", FormulaType.CA, ("azure.l2.event_grid",), "AzureEventGridCalculator.calculate_cost", "L2.event_grid", ("events",), normalizer="price_per_million_to_price_per_action"),
        _binding("cost.aws.l3.dynamodb", FormulaType.CA, ("aws.l3.dynamodb",), "AWSDynamoDBCalculator.calculate_cost", "L3_hot.dynamodb", ("writes_per_month", "reads_per_month", "storage_gb")),
        _binding("cost.azure.l3.cosmos_db", FormulaType.CA, ("azure.l3.cosmos_db",), "AzureCosmosDBCalculator.calculate_cost", "L3_hot.cosmos_db", ("writes_per_month", "reads_per_month", "storage_gb"), normalizer="price_per_million_to_price_per_action"),
        _binding("cost.gcp.l3.firestore", FormulaType.CA, ("gcp.l3.firestore",), "GCPFirestoreCalculator.calculate_cost", "L3_hot.firestore", ("writes_per_month", "reads_per_month", "storage_gb"), normalizer="price_per_100k_to_price_per_action"),
        _binding("cost.aws.l3.s3_ia", FormulaType.CS, ("aws.l3.s3_ia",), "AWSS3IACalculator.calculate_cost", "L3_cool.s3_ia", ("storage_gb", "writes_per_month", "retrievals_gb")),
        _binding("cost.azure.l3.blob_cool", FormulaType.CS, ("azure.l3.blob_cool",), "AzureBlobCoolCalculator.calculate_cost", "L3_cool.blob_cool", ("storage_gb", "writes_per_month", "retrievals_gb")),
        _binding("cost.gcp.l3.gcs_nearline", FormulaType.CS, ("gcp.l3.gcs_nearline",), "GCSNearlineCalculator.calculate_cost", "L3_cool.gcs_nearline", ("storage_gb", "writes_per_month", "retrievals_gb")),
        _binding("cost.aws.l3.s3_glacier", FormulaType.CS, ("aws.l3.s3_glacier",), "AWSS3GlacierCalculator.calculate_cost", "L3_archive.s3_glacier", ("storage_gb", "writes_per_month", "retrievals_gb")),
        _binding("cost.azure.l3.blob_archive", FormulaType.CS, ("azure.l3.blob_archive",), "AzureBlobArchiveCalculator.calculate_cost", "L3_archive.blob_archive", ("storage_gb", "writes_per_month", "retrievals_gb")),
        _binding("cost.gcp.l3.gcs_coldline", FormulaType.CS, ("gcp.l3.gcs_coldline",), "GCSColdlineCalculator.calculate_cost", "L3_archive.gcs_coldline", ("storage_gb", "writes_per_month", "retrievals_gb")),
        _binding("cost.aws.l4.twinmaker", FormulaType.CA, ("aws.l4.twinmaker",), "AWSTwinMakerCalculator.calculate_cost", "L4.twinmaker", ("entity_count", "queries_per_month", "api_calls_per_month")),
        _binding("cost.azure.l4.digital_twins_operations", FormulaType.CA, ("azure.l4.digital_twins_operations",), "AzureDigitalTwinsCalculator.calculate_breakdown", "L4.digital_twins_operations", ("billable_operations",)),
        _binding("cost.azure.l4.digital_twins_messages", FormulaType.CM, ("azure.l4.digital_twins_messages",), "AzureDigitalTwinsCalculator.calculate_breakdown", "L4.digital_twins_routed_messages", ("billable_messages",)),
        _binding("cost.azure.l4.digital_twins_query_units", FormulaType.CA, ("azure.l4.digital_twins_query_units",), "AzureDigitalTwinsCalculator.calculate_breakdown", "L4.digital_twins_query_units", ("billable_query_units",)),
        _binding("cost.gcp.l4.self_hosted_twin", FormulaType.CU, ("gcp.l4.self_hosted_twin",), "GCPComputeEngineCalculator.calculate_twinmaker_cost", "L4.self_hosted_twin", ("hours_per_month", "disk_gb")),
        _binding("cost.aws.l5.grafana", FormulaType.CU, ("aws.l5.grafana",), "AWSGrafanaCalculator.calculate_cost", "L5.grafana", ("num_editors", "num_viewers")),
        _binding("cost.azure.l5.grafana", FormulaType.CU, ("azure.l5.grafana",), "AzureGrafanaCalculator.calculate_cost", "L5.grafana", ("num_editors", "num_viewers", "hours_per_month")),
        _binding("cost.gcp.l5.self_hosted_grafana", FormulaType.CU, ("gcp.l5.self_hosted_grafana",), "GCPComputeEngineCalculator.calculate_grafana_cost", "L5.self_hosted_grafana", ("hours_per_month", "disk_gb")),
        _binding("cost.transfer.egress", FormulaType.CTRANSFER, ("aws.transfer.egress", "azure.transfer.egress", "gcp.transfer.egress"), "calculation_v2.path_optimizer.evaluate_complete_paths", "transfer.egress", ("volume_bytes", "source_provider", "destination_provider", "catalog_snapshot_id"), normalizer="canonical_transfer_catalog"),
    )

    return OptimizationStrategyContract(
        objective=OptimizationObjective.COST,
        status=ObjectiveStatus.ENABLED,
        description="Cheapest-path cost optimization across provider/layer combinations.",
        result_fields=("calculationResult", "awsCosts", "azureCosts", "gcpCosts", "transferCosts", "cheapestPath", "totalCost"),
        pricing_intents=intents,
        formula_bindings=bindings,
    )


def _disabled_strategy(objective: OptimizationObjective, note: str) -> OptimizationStrategyContract:
    return OptimizationStrategyContract(
        objective=objective,
        status=ObjectiveStatus.DISABLED,
        description=f"{objective.value} optimization is intentionally disabled.",
        result_fields=(),
        extension_note=note,
    )


def strategy_contracts() -> Mapping[OptimizationObjective, OptimizationStrategyContract]:
    """Return all known strategy contracts keyed by objective."""

    contracts = {
        OptimizationObjective.COST: cost_strategy_contract(),
        OptimizationObjective.LATENCY: _disabled_strategy(
            OptimizationObjective.LATENCY,
            "Requires measured or declared latency sources before it can be enabled.",
        ),
        OptimizationObjective.EMISSIONS: _disabled_strategy(
            OptimizationObjective.EMISSIONS,
            "Requires region/provider carbon intensity and workload energy models.",
        ),
        OptimizationObjective.RESILIENCE: _disabled_strategy(
            OptimizationObjective.RESILIENCE,
            "Requires availability, redundancy, and failure-domain scoring models.",
        ),
    }
    return contracts


def enabled_strategy_contracts() -> Tuple[OptimizationStrategyContract, ...]:
    """Return strategies that can be selected by runtime code."""

    return tuple(
        contract
        for contract in strategy_contracts().values()
        if contract.status == ObjectiveStatus.ENABLED
    )


def get_strategy_contract(objective: OptimizationObjective | str) -> OptimizationStrategyContract:
    """Return one strategy contract by enum value or string value."""

    normalized = (
        objective
        if isinstance(objective, OptimizationObjective)
        else OptimizationObjective(str(objective))
    )
    return strategy_contracts()[normalized]
