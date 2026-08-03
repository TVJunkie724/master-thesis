"""Generate the Phase 8.3 dark provider-profile and component registries.

The module deliberately describes repository-owned source symbols only.  It
does not compile Terraform, build packages, contact a cloud, or activate the
profile-aware runtime path.
"""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any


PROFILE_COMPONENTS = (
    ("component.ingestion", "l1_ingestion", "ingestion"),
    ("component.processing", "l2_processing", "processing"),
    ("component.hot-storage", "l3_hot_storage", "hot-storage"),
    ("component.cool-storage", "l3_cool_storage", "cool-storage"),
    ("component.archive-storage", "l3_archive_storage", "archive-storage"),
    ("component.twin-state", "l4_twin_state", "twin-state"),
    ("component.visualization", "l5_visualization", "visualization"),
)

PRICING_INTENTS = {
    "ingestion": [
        "iot.message_ingest",
        "functions.request",
        "functions.compute_gb_second",
    ],
    "processing": [
        "functions.request",
        "functions.compute_gb_second",
        "orchestration.state_transition",
        "event_bus.event_million",
    ],
    "hot-storage": [
        "storage.hot.storage_gb_month",
        "storage.hot.read_request",
        "storage.hot.write_request",
        "functions.compute_gb_second",
    ],
    "cool-storage": [
        "storage.cool.storage_gb_month",
        "functions.compute_gb_second",
    ],
    "archive-storage": [
        "storage.archive.storage_gb_month",
        "storage.archive.write_request",
        "functions.compute_gb_second",
    ],
    "twin-state": [
        "digital_twin.operation",
        "digital_twin.entity_month",
        "digital_twin.api_call",
        "digital_twin.query",
        "digital_twin.query_unit",
        "digital_twin.account_bundle_month",
    ],
    "visualization": [
        "grafana.editor_user_month",
        "grafana.viewer_user_month",
    ],
}

PROVIDER_METADATA = {
    "aws": {
        "region": "eu-central-1",
        "region_id": "region.aws.eu-central-1",
        "profile_id": "provider-profile.aws.five-layer-baseline",
        "blocked_code": "profile-target-not-implemented",
        "blocked_message": (
            "Typed L4-to-L5 datasource compilation remains owned by Phase 8.6."
        ),
    },
    "azure": {
        "region": "westeurope",
        "region_id": "region.azure.westeurope",
        "profile_id": "provider-profile.azure.five-layer-baseline",
        "blocked_code": "profile-target-not-implemented",
        "blocked_message": (
            "Typed L4-to-L5 datasource compilation remains owned by Phase 8.6."
        ),
    },
    "gcp": {
        "region": "europe-west1",
        "region_id": "region.gcp.europe-west1",
        "profile_id": "provider-profile.gcp.five-layer-baseline",
        "blocked_code": "profile-provider-capability-incomplete",
        "blocked_message": (
            "No approved deployable GCP Twin-state or visualization bundle exists."
        ),
    },
}

COMPONENT_BINDINGS: dict[str, dict[str, dict[str, Any]]] = {
    "aws": {
        "ingestion": {
            "service": "aws.iot-core",
            "resources": [
                "aws_iot_topic_rule.dispatcher",
                "aws_lambda_function.l1_dispatcher",
            ],
            "inputs": ["aws_l1_lambda_memory_mb"],
            "output": "aws_l1_dispatcher_function_name",
            "source": "3-cloud-deployer/src/providers/aws/lambda_functions/dispatcher",
            "handler": "lambda_function.lambda_handler",
            "permission": "l1_iot",
            "formulas": ["tiered_unit_cost", "duration_compute_cost"],
        },
        "processing": {
            "service": "aws.lambda",
            "resources": [
                "aws_lambda_function.processor_wrapper",
                "aws_lambda_function.l2_persister",
                "aws_sfn_state_machine.l2_event_workflow",
            ],
            "inputs": ["aws_l2_lambda_memory_mb", "validated_extension_packages"],
            "output": "aws_l2_persister_function_name",
            "source": (
                "3-cloud-deployer/src/providers/aws/lambda_functions/"
                "processor_wrapper"
            ),
            "handler": "lambda_function.lambda_handler",
            "permission": "l2_compute",
            "formulas": ["duration_compute_cost", "tiered_unit_cost"],
        },
        "hot-storage": {
            "service": "aws.dynamodb",
            "resources": [
                "aws_dynamodb_table.l3_hot",
                "aws_lambda_function.l3_hot_reader",
            ],
            "inputs": [
                "aws_dynamodb_billing_mode",
                "aws_l3_reader_lambda_memory_mb",
            ],
            "output": "aws_dynamodb_table_name",
            "source": "3-cloud-deployer/src/providers/aws/lambda_functions/hot-reader",
            "handler": "lambda_function.lambda_handler",
            "permission": "l3_storage",
            "formulas": ["storage_capacity_cost", "request_unit_cost"],
        },
        "cool-storage": {
            "service": "aws.s3",
            "resources": [
                "aws_s3_bucket.l3_cold",
                "aws_lambda_function.l3_hot_to_cold_mover",
            ],
            "inputs": [
                "aws_l3_cool_storage_class",
                "aws_hot_to_cool_mover_memory_mb",
                "aws_hot_to_cool_schedule_expression",
            ],
            "output": "aws_s3_cold_bucket",
            "source": (
                "3-cloud-deployer/src/providers/aws/lambda_functions/"
                "hot-to-cold-mover"
            ),
            "handler": "lambda_function.lambda_handler",
            "permission": "l3_storage",
            "formulas": ["storage_capacity_cost", "duration_compute_cost"],
        },
        "archive-storage": {
            "service": "aws.s3",
            "resources": [
                "aws_s3_bucket.l3_archive",
                "aws_lambda_function.l3_cold_to_archive_mover",
            ],
            "inputs": [
                "aws_l3_archive_storage_class",
                "aws_cool_to_archive_mover_memory_mb",
                "aws_cool_to_archive_schedule_expression",
            ],
            "output": "aws_s3_archive_bucket",
            "source": (
                "3-cloud-deployer/src/providers/aws/lambda_functions/"
                "cold-to-archive-mover"
            ),
            "handler": "lambda_function.lambda_handler",
            "permission": "l3_storage",
            "formulas": ["storage_capacity_cost", "duration_compute_cost"],
        },
        "twin-state": {
            "service": "aws.iot-twinmaker",
            "resources": [
                "awscc_iottwinmaker_workspace.main",
                "aws_lambda_function.l4_connector",
            ],
            "inputs": ["aws_l4_lambda_memory_mb"],
            "output": "aws_twinmaker_workspace_id",
            "source": (
                "3-cloud-deployer/src/providers/aws/lambda_functions/"
                "digital-twin-data-connector"
            ),
            "handler": "lambda_function.lambda_handler",
            "permission": "l4_twins",
            "formulas": ["account_bundle_cost", "query_cost"],
        },
        "visualization": {
            "service": "aws.managed-grafana",
            "resources": ["aws_grafana_workspace.main"],
            "inputs": [],
            "output": "aws_grafana_endpoint",
            "source": "3-cloud-deployer/src/providers/terraform/package_builders/aws.py",
            "handler": "terraform.managed",
            "permission": "l5_grafana",
            "formulas": ["user_seat_cost"],
        },
    },
    "azure": {
        "ingestion": {
            "service": "azure.iot-hub",
            "resources": [
                "azurerm_iothub.main",
                "azurerm_linux_function_app.l1",
                "azurerm_eventgrid_system_topic_event_subscription.iothub_to_dispatcher",
            ],
            "inputs": [
                "azure_iot_hub_sku",
                "azure_iot_hub_capacity",
                "azure_l1_function_plan_sku",
            ],
            "output": "azure_iothub_name",
            "source": (
                "3-cloud-deployer/src/providers/azure/azure_functions/dispatcher"
            ),
            "handler": "function_app.main",
            "permission": "l1_iot",
            "formulas": ["tiered_unit_cost", "duration_compute_cost"],
        },
        "processing": {
            "service": "azure.functions",
            "resources": [
                "azurerm_linux_function_app.l2",
                "azurerm_linux_function_app.user",
                "azurerm_logic_app_workflow.event_notification",
            ],
            "inputs": [
                "azure_l2_function_plan_sku",
                "validated_extension_packages",
            ],
            "output": "azure_l2_function_app_name",
            "source": (
                "3-cloud-deployer/src/providers/azure/azure_functions/"
                "processor_wrapper"
            ),
            "handler": "function_app.main",
            "permission": "l2_compute",
            "formulas": ["duration_compute_cost", "tiered_unit_cost"],
        },
        "hot-storage": {
            "service": "azure.cosmos-db",
            "resources": [
                "azurerm_cosmosdb_account.main",
                "azurerm_linux_function_app.l3",
            ],
            "inputs": [
                "azure_cosmos_capacity_mode",
                "azure_l3_function_plan_sku",
            ],
            "output": "azure_cosmos_account_name",
            "source": (
                "3-cloud-deployer/src/providers/azure/azure_functions/hot-reader"
            ),
            "handler": "function_app.main",
            "permission": "l3_storage",
            "formulas": ["storage_capacity_cost", "request_unit_cost"],
        },
        "cool-storage": {
            "service": "azure.blob-storage",
            "resources": ["azurerm_storage_container.cold"],
            "inputs": [
                "azure_storage_account_tier",
                "azure_storage_replication_type",
                "azure_l3_cool_blob_tier",
                "azure_l3_function_plan_sku",
                "azure_hot_to_cool_timer_schedule",
            ],
            "output": "azure_storage_account_name",
            "source": (
                "3-cloud-deployer/src/providers/azure/azure_functions/"
                "hot-to-cold-mover"
            ),
            "handler": "function_app.main",
            "permission": "l3_storage",
            "formulas": ["storage_capacity_cost", "duration_compute_cost"],
        },
        "archive-storage": {
            "service": "azure.blob-storage",
            "resources": ["azurerm_storage_container.archive"],
            "inputs": [
                "azure_storage_account_tier",
                "azure_storage_replication_type",
                "azure_l3_archive_blob_tier",
                "azure_l3_function_plan_sku",
                "azure_cool_to_archive_timer_schedule",
            ],
            "output": "azure_archive_storage_account",
            "source": (
                "3-cloud-deployer/src/providers/azure/azure_functions/"
                "cold-to-archive-mover"
            ),
            "handler": "function_app.main",
            "permission": "l3_storage",
            "formulas": ["storage_capacity_cost", "duration_compute_cost"],
        },
        "twin-state": {
            "service": "azure.digital-twins",
            "resources": [
                "azurerm_digital_twins_instance.main",
                "azurerm_linux_function_app.l0_glue",
            ],
            "inputs": ["azure_l4_function_plan_sku"],
            "output": "azure_adt_instance_name",
            "source": (
                "3-cloud-deployer/src/providers/azure/azure_functions/adt-pusher"
            ),
            "handler": "function_app.main",
            "permission": "l4_twins",
            "formulas": ["tiered_unit_cost", "query_unit_cost"],
        },
        "visualization": {
            "service": "azure.managed-grafana",
            "resources": ["azurerm_dashboard_grafana.main"],
            "inputs": ["azure_grafana_sku"],
            "output": "azure_grafana_endpoint",
            "source": (
                "3-cloud-deployer/src/providers/terraform/package_builders/azure.py"
            ),
            "handler": "terraform.managed",
            "permission": "l5_grafana",
            "formulas": ["user_seat_cost"],
        },
    },
    "gcp": {
        "ingestion": {
            "service": "gcp.pubsub",
            "resources": [
                "google_pubsub_topic.telemetry",
                "google_cloudfunctions2_function.dispatcher",
            ],
            "inputs": [
                "gcp_l1_function_memory_mb",
                "gcp_l1_function_min_instances",
                "gcp_l1_function_max_instances",
            ],
            "output": "gcp_pubsub_telemetry_topic",
            "source": (
                "3-cloud-deployer/src/providers/gcp/cloud_functions/dispatcher"
            ),
            "handler": "main.main",
            "permission": "l1_iot",
            "formulas": ["tiered_unit_cost", "duration_compute_cost"],
        },
        "processing": {
            "service": "gcp.cloud-functions",
            "resources": [
                "google_cloudfunctions2_function.processor_wrapper",
                "google_cloudfunctions2_function.persister",
                "google_workflows_workflow.event_workflow",
            ],
            "inputs": [
                "gcp_l2_function_memory_mb",
                "gcp_l2_function_min_instances",
                "gcp_l2_function_max_instances",
                "validated_extension_packages",
            ],
            "output": "gcp_persister_url",
            "source": (
                "3-cloud-deployer/src/providers/gcp/cloud_functions/"
                "processor_wrapper"
            ),
            "handler": "main.main",
            "permission": "l2_compute",
            "formulas": ["duration_compute_cost", "tiered_unit_cost"],
        },
        "hot-storage": {
            "service": "gcp.firestore",
            "resources": [
                "google_firestore_database.main",
                "google_cloudfunctions2_function.hot_reader",
            ],
            "inputs": [
                "gcp_firestore_mode",
                "gcp_l3_reader_function_memory_mb",
                "gcp_l3_reader_function_min_instances",
                "gcp_l3_reader_function_max_instances",
            ],
            "output": "gcp_firestore_database",
            "source": (
                "3-cloud-deployer/src/providers/gcp/cloud_functions/hot-reader"
            ),
            "handler": "main.main",
            "permission": "l3_storage",
            "formulas": ["storage_capacity_cost", "request_unit_cost"],
        },
        "cool-storage": {
            "service": "gcp.cloud-storage",
            "resources": [
                "google_storage_bucket.cold",
                "google_cloudfunctions2_function.hot_to_cold_mover",
            ],
            "inputs": [
                "gcp_l3_cool_storage_class",
                "gcp_hot_to_cool_mover_memory_mb",
                "gcp_hot_to_cool_mover_min_instances",
                "gcp_hot_to_cool_mover_max_instances",
                "gcp_hot_to_cool_scheduler_cron",
            ],
            "output": "gcp_cold_bucket",
            "source": (
                "3-cloud-deployer/src/providers/gcp/cloud_functions/"
                "hot-to-cold-mover"
            ),
            "handler": "main.main",
            "permission": "l3_storage",
            "formulas": ["storage_capacity_cost", "duration_compute_cost"],
        },
        "archive-storage": {
            "service": "gcp.cloud-storage",
            "resources": [
                "google_storage_bucket.archive",
                "google_cloudfunctions2_function.cold_to_archive_mover",
            ],
            "inputs": [
                "gcp_l3_archive_storage_class",
                "gcp_cool_to_archive_mover_memory_mb",
                "gcp_cool_to_archive_mover_min_instances",
                "gcp_cool_to_archive_mover_max_instances",
                "gcp_cool_to_archive_scheduler_cron",
            ],
            "output": "gcp_archive_bucket",
            "source": (
                "3-cloud-deployer/src/providers/gcp/cloud_functions/"
                "cold-to-archive-mover"
            ),
            "handler": "main.main",
            "permission": "l3_storage",
            "formulas": ["storage_capacity_cost", "duration_compute_cost"],
        },
    },
}

GLUE_BINDINGS: dict[str, dict[str, Any]] = {
    "aws": {
        "service": "aws.lambda",
        "resources": [
            "aws_lambda_function.l0_ingestion",
            "aws_lambda_function_url.l0_ingestion",
            "aws_lambda_function.l0_hot_writer",
            "aws_lambda_function_url.l0_hot_writer",
            "aws_lambda_function.l0_cold_writer",
            "aws_lambda_function_url.l0_cold_writer",
            "aws_lambda_function.l0_archive_writer",
            "aws_lambda_function_url.l0_archive_writer",
        ],
        "inputs": ["aws_glue_lambda_memory_mb"],
        "output": "aws_l0_ingestion_url",
        "permission": "l0_glue",
        "handler": "lambda_function.lambda_handler",
        "formulas": ["duration_compute_cost", "tiered_unit_cost"],
        "sources": {
            "ingestion": "3-cloud-deployer/src/providers/aws/lambda_functions/ingestion",
            "hot-writer": "3-cloud-deployer/src/providers/aws/lambda_functions/hot-writer",
            "cold-writer": "3-cloud-deployer/src/providers/aws/lambda_functions/cold-writer",
            "archive-writer": "3-cloud-deployer/src/providers/aws/lambda_functions/archive-writer",
        },
    },
    "azure": {
        "service": "azure.functions",
        "resources": ["azurerm_service_plan.l0"],
        "inputs": ["azure_glue_function_plan_sku"],
        "output": "azure_l0_function_app_url",
        "permission": "l0_glue",
        "handler": "function_app.main",
        "formulas": ["duration_compute_cost", "tiered_unit_cost"],
        "sources": {
            "ingestion": "3-cloud-deployer/src/providers/azure/azure_functions/ingestion",
            "hot-writer": "3-cloud-deployer/src/providers/azure/azure_functions/hot-writer",
            "cold-writer": "3-cloud-deployer/src/providers/azure/azure_functions/cold-writer",
            "archive-writer": "3-cloud-deployer/src/providers/azure/azure_functions/archive-writer",
        },
    },
    "gcp": {
        "service": "gcp.cloud_functions_gen2",
        "resources": [
            "google_cloudfunctions2_function.ingestion",
            "google_cloudfunctions2_function.hot_writer",
            "google_cloudfunctions2_function.cold_writer",
            "google_cloudfunctions2_function.archive_writer",
        ],
        "inputs": [
            "gcp_glue_function_memory_mb",
            "gcp_glue_function_min_instances",
            "gcp_glue_function_max_instances",
        ],
        "output": "gcp_ingestion_url",
        "permission": "l2_compute",
        "handler": "main.main",
        "formulas": ["duration_compute_cost", "tiered_unit_cost"],
        "sources": {
            "ingestion": "3-cloud-deployer/src/providers/gcp/cloud_functions/ingestion",
            "hot-writer": "3-cloud-deployer/src/providers/gcp/cloud_functions/hot-writer",
            "cold-writer": "3-cloud-deployer/src/providers/gcp/cloud_functions/cold-writer",
            "archive-writer": "3-cloud-deployer/src/providers/gcp/cloud_functions/archive-writer",
        },
    },
}

PERSISTER_BINDINGS = {
    "aws": {
        "source": "3-cloud-deployer/src/providers/aws/lambda_functions/persister",
        "handler": "lambda_function.lambda_handler",
    },
    "azure": {
        "source": "3-cloud-deployer/src/providers/azure/azure_functions/persister",
        "handler": "function_app.main",
    },
    "gcp": {
        "source": "3-cloud-deployer/src/providers/gcp/cloud_functions/persister",
        "handler": "main.main",
    },
}

AUXILIARY_ARTIFACTS = {
    "aws": (
        (
            "ingestion-connector",
            "ingestion",
            "3-cloud-deployer/src/providers/aws/lambda_functions/connector",
            "lambda_function.lambda_handler",
        ),
        (
            "hot-storage-last-entry",
            "hot-storage",
            "3-cloud-deployer/src/providers/aws/lambda_functions/hot-reader-last-entry",
            "lambda_function.lambda_handler",
        ),
        (
            "twin-state-last-entry",
            "twin-state",
            "3-cloud-deployer/src/providers/aws/lambda_functions/digital-twin-data-connector-last-entry",
            "lambda_function.lambda_handler",
        ),
    ),
    "azure": (
        (
            "ingestion-connector",
            "ingestion",
            "3-cloud-deployer/src/providers/azure/azure_functions/connector",
            "function_app.main",
        ),
        (
            "hot-storage-last-entry",
            "hot-storage",
            "3-cloud-deployer/src/providers/azure/azure_functions/hot-reader-last-entry",
            "function_app.main",
        ),
    ),
    "gcp": (
        (
            "ingestion-connector",
            "ingestion",
            "3-cloud-deployer/src/providers/gcp/cloud_functions/connector",
            "main.main",
        ),
        (
            "hot-storage-last-entry",
            "hot-storage",
            "3-cloud-deployer/src/providers/gcp/cloud_functions/hot-reader-last-entry",
            "main.main",
        ),
    ),
}

EXTENSION_ARTIFACTS = (
    (
        "aws",
        "default-processor",
        "3-cloud-deployer/src/providers/aws/lambda_functions/default-processor",
        "lambda_function.lambda_handler",
        "implementation.aws.user-package-base.default-processor",
    ),
    (
        "gcp",
        "default-processor",
        "3-cloud-deployer/src/providers/gcp/cloud_functions/default-processor",
        "main.main",
        "implementation.gcp.user-package-base.default-processor",
    ),
    *(
        (
            "platform",
            f"template-{name}",
            "3-cloud-deployer/templates/digital-twin/cloud_functions/processors/"
            f"{name}",
            "provider-selected.user-package",
            "implementation.platform.user-template.processors-"
            f"{name.replace('_', '-')}",
        )
        for name in (
            "default_processor",
            "pressure-sensor-1",
            "temperature-sensor-1",
            "temperature-sensor-2",
        )
    ),
)


def _safe_id(value: str) -> str:
    return value.replace("_", "-")


def _decision_id_for_dimension(component_id: str) -> str:
    suffix = component_id.replace(".", "-").replace("_", "-")
    return f"implementation.catalog.{suffix}"


def _artifact_digest(root: Path, source: str) -> str:
    source_path = root / source
    if not source_path.exists() or source_path.is_symlink():
        raise RuntimeError(f"CATALOG_PACKAGE_REFERENCE_INVALID: {source}")
    paths = [source_path] if source_path.is_file() else sorted(source_path.rglob("*"))
    digest = hashlib.sha256()
    included = 0
    for path in paths:
        if path.is_symlink():
            raise RuntimeError(f"CATALOG_PACKAGE_REFERENCE_INVALID: {path}")
        if (
            not path.is_file()
            or "__pycache__" in path.parts
            or ".git" in path.parts
            or path.suffix.lower() == ".zip"
            or path.name.startswith(".git")
            or path.name == ".DS_Store"
        ):
            continue
        relative = path.relative_to(root).as_posix()
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
        included += 1
    if included == 0:
        raise RuntimeError(f"CATALOG_PACKAGE_REFERENCE_INVALID: {source}")
    return f"sha256:{digest.hexdigest()}"


def _artifact(root: Path, provider: str, name: str, binding: dict[str, Any]) -> dict[str, Any]:
    source = binding["source"]
    source_path = root / source
    included = [source_path.name] if source_path.is_file() else ["**/*"]
    return {
        "artifact_id": f"artifact.{provider}.{name}",
        "artifact_version": "1",
        "decision_implementation_ids": sorted(
            binding.get("decision_implementation_ids", [])
        ),
        "repository_source_path": source,
        "platform_handler": binding["handler"],
        "digest_policy": "sha256.canonical-source.v1",
        "source_digest": _artifact_digest(root, source),
        "included_paths": included,
        "excluded_paths": [
            "**/__pycache__/**",
            "**/*.zip",
            "**/.git*",
            "**/.DS_Store",
        ],
        "dependency_artifact_refs": binding.get(
            "dependency_artifact_refs",
            (
                [{"id": f"artifact.{provider}.shared-runtime", "version": "1"}]
                if binding["handler"] != "terraform.managed"
                and name != "shared-runtime"
                else []
            ),
        ),
        "builder_adapter_id": binding.get(
            "builder_adapter_id", f"builder.{provider}.static.v1"
        ),
        "supported_runtimes": binding.get(
            "supported_runtimes",
            [
                "runtime.terraform-managed"
                if binding["handler"] == "terraform.managed"
                else f"runtime.{provider}.python311"
            ],
        ),
        "user_source_policy": binding.get(
            "user_source_policy",
            "validated_extension_slot" if name == "processing" else "platform_only",
        ),
        "compatibility": {
            "component_versions": ["1"],
            "builder_versions": ["1"],
        },
    }


def _catalog_port(sync: Any, provider: str, port_id: str) -> dict[str, Any]:
    return sync._catalog_port(provider, port_id, "catalog")


def _deployment_specs(
    dimensions: dict[str, Any], slot: str, provider: str, name: str
) -> list[str]:
    requirements = dimensions["slot_requirements"].get(slot, {}).get(provider)
    if not requirements:
        return []
    component_ids = [
        *requirements["required_components"],
        *requirements["optional_components"],
    ]
    if name == "cool-storage":
        component_ids.append(f"transition.l3_hot_to_l3_cool.{provider}.runtime")
    elif name == "archive-storage":
        component_ids.append(f"transition.l3_cool_to_l3_archive.{provider}.runtime")
    return sorted(component_ids)


def build_definitions(root: Path, sync: Any) -> dict[str, Any]:
    dimensions = json.loads(
        (
            root
            / "contracts"
            / "resolved-deployment-specification"
            / "v1"
            / "deployment-dimensions.json"
        ).read_text(encoding="utf-8")
    )
    decision = json.loads(
        (
            root
            / "contracts"
            / "architecture-inventory"
            / "v1"
            / "five-layer-baseline-v1-decision.json"
        ).read_text(encoding="utf-8")
    )
    profile = sync._architecture_profile()
    artifacts = []
    components = []
    component_by_provider_logical: dict[tuple[str, str], dict[str, Any]] = {}
    for provider in ("aws", "azure", "gcp"):
        shared_parent = {
            "aws": "aws/lambda_functions",
            "azure": "azure/azure_functions",
            "gcp": "gcp/cloud_functions",
        }[provider]
        artifacts.append(
            _artifact(
                root,
                provider,
                "shared-runtime",
                {
                    "source": (
                        "3-cloud-deployer/src/providers/"
                        f"{shared_parent}/_shared"
                    ),
                    "handler": "provider.shared-runtime",
                },
            )
        )
        persister_artifact = _artifact(
            root,
            provider,
            "processing-persister",
            PERSISTER_BINDINGS[provider],
        )
        artifacts.append(persister_artifact)
        auxiliary_by_owner: dict[str, list[dict[str, Any]]] = {}
        for (
            auxiliary_name,
            owner_name,
            auxiliary_source,
            auxiliary_handler,
        ) in AUXILIARY_ARTIFACTS[provider]:
            auxiliary = _artifact(
                root,
                provider,
                auxiliary_name,
                {
                    "source": auxiliary_source,
                    "handler": auxiliary_handler,
                },
            )
            artifacts.append(auxiliary)
            auxiliary_by_owner.setdefault(owner_name, []).append(auxiliary)
        for logical_id, slot, name in PROFILE_COMPONENTS:
            binding = COMPONENT_BINDINGS.get(provider, {}).get(name)
            if binding is None:
                continue
            artifact_binding = binding
            if name == "processing":
                artifact_binding = {
                    **binding,
                    "dependency_artifact_refs": [
                        {
                            "id": f"artifact.{provider}.shared-runtime",
                            "version": "1",
                        },
                        {
                            "id": persister_artifact["artifact_id"],
                            "version": "1",
                        },
                    ],
                }
            elif name in auxiliary_by_owner:
                artifact_binding = {
                    **binding,
                    "dependency_artifact_refs": [
                        {
                            "id": f"artifact.{provider}.shared-runtime",
                            "version": "1",
                        },
                        *(
                            {
                                "id": item["artifact_id"],
                                "version": item["artifact_version"],
                            }
                            for item in auxiliary_by_owner[name]
                        ),
                    ],
                }
            artifact = _artifact(root, provider, name, artifact_binding)
            artifacts.append(artifact)
            input_ports, output_ports = sync.PORTS_BY_COMPONENT[logical_id]
            specification_ids = _deployment_specs(dimensions, slot, provider, name)
            service_ids = sorted(
                {
                    dimensions["components"][specification_id]["service_id"]
                    for specification_id in specification_ids
                }
            )
            decision_implementation_ids = [
                _decision_id_for_dimension(specification_id)
                for specification_id in specification_ids
            ]
            if name == "processing":
                decision_implementation_ids.append(
                    f"implementation.{provider}.function.processor-wrapper"
                )
            component = {
                "deployment_component_id": f"deployment.{provider}.{name}",
                "component_version": "1",
                "provider": provider,
                "logical_component_ids": [logical_id],
                "decision_implementation_ids": sorted(
                    decision_implementation_ids
                ),
                "service_id": service_ids[0],
                "service_ids": service_ids,
                "component_kind": next(
                    {
                        "ingress": "managed_service",
                        "processor": "serverless_function",
                        "storage": "storage_service",
                        "twin_state": "twin_service",
                        "visualization": "visualization_service",
                    }[kind]
                    for candidate, _, kind, _ in sync.LOGICAL_COMPONENTS
                    if candidate == logical_id
                ),
                "package_artifact_ref": {
                    "id": artifact["artifact_id"],
                    "version": "1",
                },
                "terraform_binding": {
                    "resource_addresses": sorted(binding["resources"]),
                    "module_addresses": [],
                    "allowed_input_variable_ids": [
                        f"input.{_safe_id(variable)}"
                        for variable in binding["inputs"]
                    ],
                    "input_bindings": [
                        {
                            "input_id": f"input.{_safe_id(variable)}",
                            "terraform_variable": variable,
                            "sensitive": False,
                        }
                        for variable in binding["inputs"]
                    ],
                    "outputs": [
                        {
                            "output_id": f"output.{_safe_id(binding['output'])}",
                            "terraform_output": binding["output"],
                            "sensitive": False,
                        }
                    ],
                    "dependency_keys": [],
                },
                "runtime_contract": {
                    "provider_runtime_id": (
                        "runtime.terraform-managed"
                        if binding["handler"] == "terraform.managed"
                        else f"runtime.{provider}.python311"
                    ),
                    "platform_handler_adapter_id": (
                        f"adapter.{provider}.python311"
                        if binding["handler"] != "terraform.managed"
                        else "adapter.terraform.managed"
                    ),
                    "timeout_seconds_min": 1,
                    "timeout_seconds_max": 900,
                    "memory_mb_min": 128,
                    "memory_mb_max": 4096,
                    "trigger_adapter_id": f"trigger.{provider}.baseline",
                    "package_layout_id": f"package-layout.{provider}.v1",
                    "user_override_allowed": False,
                },
                "configuration_schema_ref": {
                    "id": f"configuration.{provider}.{name}",
                    "version": "1",
                },
                "input_ports": [
                    _catalog_port(sync, provider, port_id) for port_id in input_ports
                ],
                "output_ports": [
                    _catalog_port(sync, provider, port_id) for port_id in output_ports
                ],
                "required_permission_capabilities": [
                    (
                        f"permission.{provider}.thesis-demo-v1."
                        f"{_safe_id(binding['permission'])}"
                    )
                ],
                "pricing_model_refs": [
                    f"pricing-intent.{intent}" for intent in PRICING_INTENTS[name]
                ],
                "formula_refs": binding["formulas"],
                "deployment_specification_bindings": [
                    {
                        "specification_schema_version": (
                            "resolved-deployment-specification.v1"
                        ),
                        "component_id": specification_id,
                        "slot_id": dimensions["components"][specification_id][
                            "slot_id"
                        ],
                    }
                    for specification_id in specification_ids
                ],
                "extension_slot_refs": (
                    [{"id": "processor.telemetry", "version": "1"}]
                    if name == "processing"
                    else []
                ),
                "error_contract_ref": {
                    "id": "architecture-runtime-errors",
                    "version": "1",
                },
                "observability_contract_ref": {
                    "id": "observability.baseline",
                    "version": "1",
                },
                "cleanup_contract_ref": {"id": "cleanup.baseline", "version": "1"},
                "compatibility": {
                    "architecture_profile_versions": [
                        {"id": "five-layer-baseline", "version": "1"}
                    ],
                    "provider_profile_versions": [
                        {
                            "id": PROVIDER_METADATA[provider]["profile_id"],
                            "version": "1",
                        }
                    ],
                    "deployment_specification_versions": [
                        "resolved-deployment-specification.v1"
                    ],
                },
            }
            components.append(component)
            component_by_provider_logical[(provider, logical_id)] = component

    glue_component_by_provider: dict[str, dict[str, Any]] = {}
    for provider, binding in GLUE_BINDINGS.items():
        endpoint_artifact_ids = {
            endpoint: f"artifact.{provider}.glue-{endpoint}"
            for endpoint in binding["sources"]
        }
        primary_artifact: dict[str, Any] | None = None
        for endpoint, source in binding["sources"].items():
            dependencies = [
                {"id": f"artifact.{provider}.shared-runtime", "version": "1"}
            ]
            if endpoint == "ingestion":
                dependencies.extend(
                    {
                        "id": artifact_id,
                        "version": "1",
                    }
                    for other, artifact_id in endpoint_artifact_ids.items()
                    if other != endpoint
                )
            artifact = _artifact(
                root,
                provider,
                f"glue-{endpoint}",
                {
                    "source": source,
                    "handler": binding["handler"],
                    "dependency_artifact_refs": dependencies,
                },
            )
            artifacts.append(artifact)
            if endpoint == "ingestion":
                primary_artifact = artifact
        if primary_artifact is None:
            raise RuntimeError(
                f"CATALOG_PACKAGE_REFERENCE_INVALID: {provider} glue ingestion"
            )
        specification_id = f"glue.{provider}.{'lambda' if provider == 'aws' else 'functions'}"
        specification = dimensions["components"][specification_id]
        input_ports, _ = sync.PORTS_BY_COMPONENT["component.processing"]
        _, output_ports = sync.PORTS_BY_COMPONENT["component.hot-storage"]
        glue_component = {
            "deployment_component_id": f"deployment.{provider}.cross-cloud-glue",
            "component_version": "1",
            "provider": provider,
            "logical_component_ids": [
                "component.processing",
                "component.hot-storage",
                "component.cool-storage",
                "component.archive-storage",
                "component.twin-state",
            ],
            "decision_implementation_ids": [
                _decision_id_for_dimension(specification_id)
            ],
            "service_id": specification["service_id"],
            "service_ids": [specification["service_id"]],
            "component_kind": "adapter",
            "package_artifact_ref": {
                "id": primary_artifact["artifact_id"],
                "version": "1",
            },
            "terraform_binding": {
                "resource_addresses": sorted(binding["resources"]),
                "module_addresses": [],
                "allowed_input_variable_ids": [
                    f"input.{_safe_id(variable)}" for variable in binding["inputs"]
                ],
                "input_bindings": [
                    {
                        "input_id": f"input.{_safe_id(variable)}",
                        "terraform_variable": variable,
                        "sensitive": False,
                    }
                    for variable in binding["inputs"]
                ],
                "outputs": [
                    {
                        "output_id": f"output.{_safe_id(binding['output'])}",
                        "terraform_output": binding["output"],
                        "sensitive": False,
                    }
                ],
                "dependency_keys": [],
            },
            "runtime_contract": {
                "provider_runtime_id": f"runtime.{provider}.python311",
                "platform_handler_adapter_id": f"adapter.{provider}.python311",
                "timeout_seconds_min": 1,
                "timeout_seconds_max": 900,
                "memory_mb_min": 128,
                "memory_mb_max": 4096,
                "trigger_adapter_id": f"trigger.{provider}.cross-cloud",
                "package_layout_id": f"package-layout.{provider}.v1",
                "user_override_allowed": False,
            },
            "configuration_schema_ref": {
                "id": f"configuration.{provider}.cross-cloud-glue",
                "version": "1",
            },
            "input_ports": [
                _catalog_port(sync, provider, port_id) for port_id in input_ports
            ],
            "output_ports": [
                _catalog_port(sync, provider, port_id) for port_id in output_ports
            ],
            "required_permission_capabilities": [
                (
                    f"permission.{provider}.thesis-demo-v1."
                    f"{_safe_id(binding['permission'])}"
                )
            ],
            "pricing_model_refs": [
                "pricing-intent.functions.request",
                "pricing-intent.functions.compute_gb_second",
                "pricing-intent.transfer.egress_gb",
            ],
            "formula_refs": binding["formulas"],
            "deployment_specification_bindings": [
                {
                    "specification_schema_version": (
                        "resolved-deployment-specification.v1"
                    ),
                    "component_id": specification_id,
                    "slot_id": specification["slot_id"],
                }
            ],
            "extension_slot_refs": [],
            "error_contract_ref": {
                "id": "architecture-runtime-errors",
                "version": "1",
            },
            "observability_contract_ref": {
                "id": "observability.baseline",
                "version": "1",
            },
            "cleanup_contract_ref": {"id": "cleanup.baseline", "version": "1"},
            "compatibility": {
                "architecture_profile_versions": [
                    {"id": "five-layer-baseline", "version": "1"}
                ],
                "provider_profile_versions": [
                    {
                        "id": PROVIDER_METADATA[provider]["profile_id"],
                        "version": "1",
                    }
                ],
                "deployment_specification_versions": [
                    "resolved-deployment-specification.v1"
                ],
            },
        }
        components.append(glue_component)
        glue_component_by_provider[provider] = glue_component

    for provider, name, source, handler, decision_id in EXTENSION_ARTIFACTS:
        artifacts.append(
            _artifact(
                root,
                provider,
                name,
                {
                    "source": source,
                    "handler": handler,
                    "decision_implementation_ids": [decision_id],
                    "dependency_artifact_refs": [],
                    "user_source_policy": "validated_extension_slot",
                    **(
                        {
                            "builder_adapter_id": (
                                "builder.provider-selected.user-package"
                            ),
                            "supported_runtimes": [
                                "runtime.aws.python311",
                                "runtime.azure.python311",
                                "runtime.gcp.python311",
                            ],
                        }
                        if provider == "platform"
                        else {}
                    ),
                },
            )
        )

    component_by_id = {
        component["deployment_component_id"]: component for component in components
    }
    component_by_decision_id = {
        decision_id: component
        for component in components
        for decision_id in component["decision_implementation_ids"]
    }
    function_component_names = {
        "dispatcher": "ingestion",
        "processor-wrapper": "processing",
        "persister": "processing",
        "hot-to-cold-mover": "cool-storage",
        "cold-writer": "cool-storage",
        "cold-to-archive-mover": "archive-storage",
        "archive-writer": "archive-storage",
    }

    def resolve_component_id(implementation_id: str) -> str:
        component = component_by_decision_id.get(implementation_id)
        if component is not None:
            return component["deployment_component_id"]
        parts = implementation_id.split(".")
        if len(parts) >= 4 and parts[1] in PROVIDER_METADATA and parts[2] == "function":
            name = function_component_names.get(parts[3])
            if name is not None:
                return f"deployment.{parts[1]}.{name}"
        if implementation_id.startswith("implementation.platform."):
            return implementation_id.removeprefix("implementation.")
        raise RuntimeError(
            "CATALOG_COMPONENT_MISSING: no deployment owner for "
            f"{implementation_id}"
        )

    logical_edge_by_suffix = {
        "l1-to-l2": "edge.ingestion-to-processing",
        "function-dispatcher-to-processor-wrapper": (
            "edge.ingestion-to-processing"
        ),
        "l2-to-l3-hot": "edge.processing-to-hot-storage",
        "function-processor-wrapper-to-persister": (
            "edge.processing-to-hot-storage"
        ),
        "l3-hot-to-l3-cool": "edge.hot-to-cool-storage",
        "function-hot-to-cold-mover-to-cold-writer": (
            "edge.hot-to-cool-storage"
        ),
        "l3-cool-to-l3-archive": "edge.cool-to-archive-storage",
        "function-cold-to-archive-mover-to-archive-writer": (
            "edge.cool-to-archive-storage"
        ),
        "l3-hot-to-l4": "edge.hot-storage-to-twin-state",
        "l4-to-l5": "edge.twin-state-to-visualization",
    }
    logical_edge_contracts = {
        edge["edge_id"]: edge for edge in profile["edges"]
    }
    logical_edge_ports = {
        edge_id: (source_port, destination_port)
        for (
            edge_id,
            _source_logical,
            source_port,
            _destination_logical,
            destination_port,
            _mechanism,
            _mode,
        ) in sync.LOGICAL_EDGES
    }

    def edge_provider(component_id: str) -> str:
        component = component_by_id.get(component_id)
        return component["provider"] if component is not None else "platform"

    edges = []
    phase_edges = [
        item
        for item in decision["edge_decisions"]
        if (
            item["implementation_owner_phase"] == "Phase 8.3"
            or (
                item["implementation_owner_phase"] == "Phase 8.6"
                and str(item.get("target_edge_id") or "").endswith(
                    "l4-to-l5"
                )
            )
        )
    ]
    for edge_decision in phase_edges:
        decision_edge_id = edge_decision["target_edge_id"]
        source_component_id = resolve_component_id(
            edge_decision["source_target_implementation_id"]
        )
        destination_component_id = resolve_component_id(
            edge_decision["destination_target_implementation_id"]
        )
        source_provider = edge_provider(source_component_id)
        destination_provider = edge_provider(destination_component_id)
        logical_edge_id = next(
            (
                logical_id
                for candidate_suffix, logical_id in logical_edge_by_suffix.items()
                if decision_edge_id.endswith(candidate_suffix)
            ),
            None,
        )
        if logical_edge_id is None:
            source_port = "port.platform.api-request"
            destination_port = "port.platform.api-response"
            delivery_requirements = {
                "mode": "synchronous",
                "timeout_policy": "bounded",
                "retry_policy": "bounded_backoff",
                "dead_letter_policy": "not_applicable",
                "idempotency": "required",
                "ordering": "not_required",
                "replay": "not_supported",
            }
        else:
            source_port, destination_port = logical_edge_ports[logical_edge_id]
            delivery_requirements = copy.deepcopy(
                logical_edge_contracts[logical_edge_id]["delivery_requirements"]
            )
        cloud_providers = sorted(
            {
                provider
                for provider in (source_provider, destination_provider)
                if provider in PROVIDER_METADATA
            }
        )
        provider_scope = (
            destination_provider
            if destination_provider in PROVIDER_METADATA
            else source_provider
        )
        cross_provider = len(cloud_providers) > 1
        glue_provider = (
            source_provider
            if logical_edge_id == "edge.hot-storage-to-twin-state"
            else destination_provider
        )
        glue_component_ids = (
            [
                glue_component_by_provider[glue_provider][
                    "deployment_component_id"
                ]
            ]
            if cross_provider
            else []
        )
        permission_refs = (
            glue_component_by_provider[glue_provider][
                "required_permission_capabilities"
            ]
            if cross_provider
            else (
                ["permission.platform.authenticated-api"]
                if provider_scope == "platform"
                else [
                    f"permission.{provider_scope}."
                    "thesis-demo-v1.observability"
                ]
            )
        )
        provider_profile_versions = [
            {
                "id": PROVIDER_METADATA[provider]["profile_id"],
                "version": "1",
            }
            for provider in (
                cloud_providers
                if cloud_providers
                else ("aws", "azure", "gcp")
            )
        ]
        edge_slug = decision_edge_id.removeprefix("target.edge.runtime.")
        source_port_id = f"catalog.{source_provider}.{source_port}"
        destination_port_id = (
            f"catalog.{destination_provider}.{destination_port}"
        )
        is_platform = provider_scope == "platform"
        source_component = component_by_id.get(source_component_id)
        declared_source_output_id = (
            source_component["terraform_binding"]["outputs"][0]["output_id"]
            if logical_edge_id is not None
            and source_component is not None
            and source_component["terraform_binding"]["outputs"]
            else f"binding.{edge_slug}.source"
        )
        declared_destination_input_id = (
            destination_port_id
            if logical_edge_id is not None
            else f"binding.{edge_slug}.destination"
        )
        edges.append(
            {
                "edge_implementation_id": f"edge-implementation.{edge_slug}",
                "edge_implementation_version": "1",
                "provider": provider_scope,
                "decision_edge_ids": [decision_edge_id],
                "logical_edge_ids": (
                    [logical_edge_id] if logical_edge_id is not None else []
                ),
                "mechanism": edge_decision["mechanism"],
                "source_component_ids": [source_component_id],
                "destination_component_ids": [destination_component_id],
                "source_output_port_id": source_port_id,
                "destination_input_port_id": destination_port_id,
                "terraform_binding": {
                    "source_output_id": declared_source_output_id,
                    "destination_input_id": declared_destination_input_id,
                    "dependency_keys": [f"dependency.{edge_slug}"],
                },
                "transfer_route_class": (
                    "cross_provider"
                    if cross_provider
                    else "same_provider_same_region"
                ),
                "payload_contract_ref": {
                    "id": edge_decision["payload_envelope"]["schema_id"],
                    "version": edge_decision["payload_envelope"]["version"],
                },
                "delivery_requirements": delivery_requirements,
                "trust_contract_ref": {
                    "id": edge_decision["trust_boundary_id"],
                    "version": "1",
                },
                "pricing_model_refs": [
                    (
                        "pricing-intent.api.request_million"
                        if is_platform
                        else "pricing-intent.transfer.egress_gb"
                    )
                ],
                "formula_refs": [
                    "request_unit_cost" if is_platform else "transfer_tier_cost"
                ],
                "required_permission_capabilities": permission_refs,
                "glue_component_ids": glue_component_ids,
                "error_contract_ref": {
                    "id": "architecture-runtime-errors",
                    "version": "1",
                },
                "observability_contract_ref": {
                    "id": "observability.baseline",
                    "version": "1",
                },
                "compatibility": {
                    "architecture_profile_versions": [
                        {"id": "five-layer-baseline", "version": "1"}
                    ],
                    "provider_profile_versions": provider_profile_versions,
                    "deployment_specification_versions": [
                        "resolved-deployment-specification.v1"
                    ],
                },
            }
        )

    provider_profiles = {}
    all_capabilities = {
        capability
        for component in profile["components"]
        for capability in component["required_capability_ids"]
    }
    for provider in ("aws", "azure", "gcp"):
        mappings = []
        for logical_id, slot, _name in PROFILE_COMPONENTS:
            component = component_by_provider_logical.get((provider, logical_id))
            if component is None:
                continue
            logical = next(
                item for item in profile["components"] if item["component_id"] == logical_id
            )
            mappings.append(
                {
                    "component_id": logical_id,
                    "deployment_component_candidates": [
                        component["deployment_component_id"]
                    ],
                    "required_capability_ids": logical["required_capability_ids"],
                    "provided_capability_ids": logical["required_capability_ids"],
                    "service_model_refs": ["cost_model_v1"],
                    "formula_refs": component["formula_refs"],
                    "supported_region_ids": [
                        PROVIDER_METADATA[provider]["region_id"]
                    ],
                    "deployment_specification_component_ids": [
                        binding["component_id"]
                        for binding in component[
                            "deployment_specification_bindings"
                        ]
                    ],
                    "deployment_specification_slot_ids": [slot],
                }
            )
        edge_mappings = []
        required_provider_edge_ids = {
            f"target.{edge_id}"
            for edge_id in next(
                scenario["required_edge_ids"]
                for scenario in decision["required_scenarios"]
                if scenario["scenario_id"] == f"scenario.all-{provider}"
            )
        }
        for edge in edges:
            if edge["decision_edge_ids"][0] not in required_provider_edge_ids:
                continue
            logical_edge_id = edge["logical_edge_ids"][0]
            logical_edge = next(
                item for item in profile["edges"] if item["edge_id"] == logical_edge_id
            )
            edge_mappings.append(
                {
                    "edge_id": logical_edge_id,
                    "edge_implementation_id": edge["edge_implementation_id"],
                    "source_deployment_component_ids": edge["source_component_ids"],
                    "destination_deployment_component_ids": (
                        edge["destination_component_ids"]
                    ),
                    "mechanism": edge["mechanism"],
                    "catalog_input_port_id": edge["destination_input_port_id"],
                    "catalog_output_port_id": edge["source_output_port_id"],
                    "transfer_route_class": edge["transfer_route_class"],
                    "cost_owner_ids": logical_edge["cost_owner_ids"],
                }
            )
        provided = {
            capability
            for mapping in mappings
            for capability in mapping["provided_capability_ids"]
        }
        supported = provider in {"aws", "azure"}
        profile_document = {
            "schema_version": "provider-implementation-profile.v1",
            "implementation_profile_id": PROVIDER_METADATA[provider]["profile_id"],
            "implementation_profile_version": "1",
            "architecture_profile_ref": {
                "id": profile["profile_id"],
                "version": profile["profile_version"],
                "digest": profile["content_digest"],
            },
            "provider": provider,
            "lifecycle_status": "active",
            "region_policy_ref": {
                "id": f"region-policy.{provider}.baseline",
                "version": "1",
            },
            "permission_set_ref": {
                "id": f"permission-set.{provider}.thesis-demo-v1",
                "version": "1",
            },
            "supported": supported,
            "component_mappings": mappings,
            "edge_mappings": edge_mappings,
            "capability_claims": {
                "required_capability_ids": sorted(all_capabilities),
                "provided_capability_ids": sorted(provided),
                "extra_capability_ids": [],
                "missing_capability_ids": sorted(all_capabilities - provided),
                "evidence_refs": [
                    f"evidence.{provider}.phase-8-1-baseline-decision"
                ],
            },
            "unsupported_reasons": (
                []
                if supported
                else [
                    {
                        "reason_code": PROVIDER_METADATA[provider][
                            "blocked_code"
                        ],
                        "message": PROVIDER_METADATA[provider][
                            "blocked_message"
                        ],
                    }
                ]
            ),
            "compatibility": {
                "compatible_catalog_versions": [
                    {"id": "baseline-component-catalog", "version": "1"}
                ],
                "compatible_resolver_versions": ["1"],
                "compatible_runtime_versions": ["1"],
                "compatible_deployment_specification_versions": [
                    "resolved-deployment-specification.v1"
                ],
            },
            "content_digest": "",
        }
        provider_profiles[provider] = sync._redigest(profile_document)

    catalog = {
        "schema_version": "deployment-component-catalog.v1",
        "catalog_id": "baseline-component-catalog",
        "catalog_version": "1",
        "lifecycle_status": "active",
        "components": components,
        "edge_implementations": edges,
        "package_artifacts": artifacts,
        "compatibility": {
            "architecture_profile_schema_versions": ["architecture-profile.v1"],
            "provider_profile_schema_versions": [
                "provider-implementation-profile.v1"
            ],
            "resolver_versions": ["1"],
            "deployer_runtime_versions": ["1"],
            "deployment_specification_versions": [
                "resolved-deployment-specification.v1"
            ],
        },
        "content_digest": "",
    }
    catalog = sync._redigest(catalog)
    scenario_status = {
        item["candidate_id"].removeprefix("candidate."): {
            "expected_status": item["status"],
            "reason_code": item["unsupported_error_code"],
            "message": item["unsupported_reason"],
        }
        for item in decision["provider_admissibility"]
    }
    user_processor_state = next(
        item
        for item in decision["required_scenarios"]
        if item["scenario_id"] == "scenario.user-processor"
    )
    scenario_status["user-processor"] = {
        "expected_status": user_processor_state["status"],
        "reason_code": user_processor_state["reason_code"],
        "message": (
            "The completed #113 contract and Phase 8.3 provider mappings bind "
            "processor.telemetry@1 without activating profile selection."
        ),
    }
    fixtures = {}
    for filename, scenario in (
        ("all-aws.json", "all-aws"),
        ("all-azure.json", "all-azure"),
        ("mixed-providers.json", "mixed-provider"),
        ("all-gcp.json", "all-gcp"),
        ("user-processor.json", "user-processor"),
    ):
        state = scenario_status[scenario]
        fixtures[filename] = {
            "fixture_version": "architecture-profile-completeness.v1",
            "scenario_id": f"scenario.{scenario}",
            "architecture_profile_ref": {
                "id": profile["profile_id"],
                "version": profile["profile_version"],
                "digest": profile["content_digest"],
            },
            "catalog_ref": {
                "id": catalog["catalog_id"],
                "version": catalog["catalog_version"],
                "digest": catalog["content_digest"],
            },
            "expected_status": state["expected_status"],
            "expected_reason_code": state["reason_code"],
            "message": state["message"],
        }
    return {
        "profile": profile,
        "provider_profiles": provider_profiles,
        "catalog": catalog,
        "fixtures": fixtures,
    }


def write_definitions(root: Path, sync: Any) -> None:
    definitions = build_definitions(root, sync)
    base = root / "contracts" / "architecture-profiles" / "definitions"
    paths = {
        base / "profiles" / "five-layer-baseline" / "1" / "profile.json": (
            definitions["profile"]
        ),
        base / "component-catalogs" / "baseline" / "1" / "catalog.json": (
            definitions["catalog"]
        ),
    }
    for provider, document in definitions["provider_profiles"].items():
        paths[
            base
            / "provider-implementations"
            / "five-layer-baseline"
            / "1"
            / provider
            / "1.json"
        ] = document
    for filename, document in definitions["fixtures"].items():
        group = "unsupported" if filename == "all-gcp.json" else "resolved"
        paths[base / "fixtures" / group / filename] = document
    decision = json.loads(
        (
            root
            / "contracts"
            / "architecture-inventory"
            / "v1"
            / "five-layer-baseline-v1-decision.json"
        ).read_text(encoding="utf-8")
    )
    inventory = json.loads(
        (
            root
            / "contracts"
            / "architecture-inventory"
            / "v1"
            / "current-graph.json"
        ).read_text(encoding="utf-8")
    )
    manifest = {
        "manifest_version": "architecture-profile-definitions.v1",
        "source_digests": {
            "baseline_decision": decision["content_digest"],
            "architecture_inventory": inventory["content_digest"],
            "deployment_dimensions": sync._file_digest(
                root
                / "contracts"
                / "resolved-deployment-specification"
                / "v1"
                / "deployment-dimensions.json"
            ),
            "user_function_extension": sync._file_digest(
                root
                / "contracts"
                / "user-function-extension"
                / "v1"
                / "registry.json"
            ),
            "package_builders": {
                name: sync._file_digest(
                    root
                    / "3-cloud-deployer"
                    / "src"
                    / "providers"
                    / "terraform"
                    / "package_builders"
                    / f"{name}.py"
                )
                for name in ("aws", "azure", "common", "gcp", "user")
            },
            "pricing_registries": {
                name: sync._file_digest(
                    root
                    / "2-twin2clouds"
                    / "pricing_registry"
                    / f"{name}.yaml"
                )
                for name in (
                    "optimization_bundles",
                    "calculation_strategies",
                    "formula_sets",
                    "intents",
                    "service_models",
                    "workload_contracts",
                )
            },
        },
        "definition_digests": {
            "profile": definitions["profile"]["content_digest"],
            "catalog": definitions["catalog"]["content_digest"],
            "providers": {
                provider: document["content_digest"]
                for provider, document in definitions["provider_profiles"].items()
            },
        },
        "counts": {
            "logical_components": len(definitions["profile"]["components"]),
            "logical_edges": len(definitions["profile"]["edges"]),
            "deployment_components": len(definitions["catalog"]["components"]),
            "edge_implementations": len(
                definitions["catalog"]["edge_implementations"]
            ),
            "package_artifacts": len(definitions["catalog"]["package_artifacts"]),
            "provider_profiles": len(definitions["provider_profiles"]),
        },
    }
    paths[base / "manifest.json"] = manifest
    for path, document in paths.items():
        sync._write_json(path, document)
