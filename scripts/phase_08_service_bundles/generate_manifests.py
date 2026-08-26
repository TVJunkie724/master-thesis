#!/usr/bin/env python3
"""Generate component and pricing-ownership manifests from the frozen bundles."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
EVIDENCE_ROOT = REPOSITORY_ROOT / "docs/research/evidence/phase_08_service_bundles"
BUNDLE_PATH = EVIDENCE_ROOT / "complete-provider-bundles.json"
ROUTE_PATH = EVIDENCE_ROOT / "boundary-route-matrix.json"
MANIFEST_PATH = EVIDENCE_ROOT / "implementation-component-manifest.json"
PRICING_PATH = EVIDENCE_ROOT / "pricing-ownership-matrix.json"


TERRAFORM_TYPES: dict[str, list[str]] = {
    "aws.iot-core": ["aws_iot_thing", "aws_iot_topic_rule"],
    "aws.iot-commands": ["awscc_iot_command"],
    "aws.lambda": ["aws_lambda_function"],
    "aws.step-functions-standard": ["aws_sfn_state_machine"],
    "aws.dynamodb-on-demand-raw": ["aws_dynamodb_table"],
    "aws.dynamodb-on-demand-hourly-rollup": ["aws_dynamodb_table"],
    "aws.s3-standard-ia": ["aws_s3_bucket", "aws_s3_bucket_lifecycle_configuration"],
    "aws.s3-glacier-deep-archive": ["aws_s3_bucket_lifecycle_configuration"],
    "aws.iot-twinmaker-standard": ["awscc_iottwinmaker_workspace"],
    "aws.amazon-managed-grafana-12": ["aws_grafana_workspace"],
    "aws.lambda-raw-history-reader": ["aws_lambda_function", "aws_lambda_function_url"],
    "aws.eventbridge-scheduler": ["aws_scheduler_schedule"],
    "aws.ecs-fargate-storage-mover": ["aws_ecs_cluster", "aws_ecs_task_definition"],
    "aws.ecr-if-container-selected": [
        "aws_ecr_repository",
        "aws_s3_bucket",
        "aws_s3_bucket_lifecycle_configuration",
        "aws_s3_bucket_public_access_block",
        "aws_s3_bucket_server_side_encryption_configuration",
        "aws_iam_role",
        "aws_iam_role_policy",
        "aws_codebuild_project",
    ],
    "aws.cloudwatch": ["aws_cloudwatch_log_group"],
    "aws.iam-identity-center-layer-access": [
        "aws_ssoadmin_permission_set",
        "aws_ssoadmin_account_assignment",
    ],
    "aws.sqs-fifo": ["aws_sqs_queue"],
    "aws.lambda-event-adapter": ["aws_lambda_function"],
    "aws.kinesis-only-for-reviewed-remote-telemetry-edge": ["aws_kinesis_stream"],
    "aws.sns-fifo-only-for-reviewed-remote-control-edge": [
        "aws_sns_topic",
        "aws_sns_topic_subscription",
    ],
    "aws.kinesis-data-streams": ["aws_kinesis_stream"],
    "aws.sns-fifo": ["aws_sns_topic", "aws_sns_topic_subscription"],
    "aws.lambda-event-worker": ["aws_lambda_function"],
    "aws.s3-event-failure-store": ["aws_s3_bucket"],
    "azure.iot-hub": ["azurerm_iothub"],
    "azure.functions-flex-consumption": ["azurerm_function_app_flex_consumption"],
    "azure.logic-apps-consumption": [
        "azurerm_logic_app_workflow",
        "azurerm_logic_app_trigger_http_request",
        "azurerm_logic_app_action_custom",
    ],
    "azure.cosmos-db-nosql-raw-and-rollup": [
        "azurerm_cosmosdb_account",
        "azurerm_cosmosdb_sql_database",
        "azurerm_cosmosdb_sql_container",
        "azurerm_cosmosdb_sql_role_assignment",
    ],
    "azure.blob-cool": ["azurerm_storage_account", "azurerm_storage_container"],
    "azure.blob-archive": ["azurerm_storage_management_policy"],
    "azure.digital-twins": ["azurerm_digital_twins_instance"],
    "azure.managed-grafana-12-standard": ["azurerm_dashboard_grafana"],
    "azure.functions-flex-raw-history-reader": [
        "azurerm_function_app_flex_consumption"
    ],
    "azure.container-apps-scheduled-storage-job": [
        "azurerm_container_app_environment",
        "azurerm_container_app_job",
    ],
    "azure.acr-basic-if-container-selected": ["azurerm_container_registry"],
    "azure.monitor": ["azurerm_monitor_diagnostic_setting"],
    "azure.log-analytics-shared-workspace": ["azurerm_log_analytics_workspace"],
    "azure.entra-layer-access-bindings": ["azurerm_role_assignment"],
    "azure.service-bus-standard": [
        "azurerm_servicebus_namespace",
        "azurerm_servicebus_queue",
        "azurerm_servicebus_topic",
        "azurerm_servicebus_subscription",
    ],
    "azure.functions-flex-event-adapter": ["azurerm_function_app_flex_consumption"],
    "azure.event-hubs-only-for-reviewed-remote-telemetry-edge": [
        "azurerm_eventhub_cluster",
        "azapi_update_resource",
        "azurerm_eventhub_namespace",
        "azurerm_eventhub",
    ],
    "azure.event-hubs-standard-small-medium": [
        "azurerm_eventhub_namespace",
        "azurerm_eventhub",
    ],
    "azure.event-hubs-dedicated-large": [
        "azurerm_eventhub_cluster",
        "azapi_update_resource",
        "azurerm_eventhub_namespace",
        "azurerm_eventhub",
    ],
    "azure.functions-flex-event-worker": ["azurerm_function_app_flex_consumption"],
    "apache.bifromq-4.0.0-incubating-on-gke-standard": [
        "google_container_cluster",
        "google_container_node_pool",
        "kubernetes_namespace_v1",
        "kubernetes_deployment_v1",
    ],
    "gcp.external-load-balancer": ["kubernetes_service_v1"],
    "gcp.ordered-mqtt-pubsub-adapter": [
        "google_container_node_pool",
        "kubernetes_deployment_v1",
    ],
    "gcp.cloud-run-service": ["google_cloud_run_v2_service"],
    "gcp.workflows": ["google_workflows_workflow"],
    "gcp.firestore-native-standard-raw-and-rollup": [
        "google_firestore_database",
        "google_firestore_field",
        "google_firestore_index",
    ],
    "gcp.cloud-storage-nearline": ["google_storage_bucket"],
    "gcp.cloud-storage-archive": ["google_storage_bucket"],
    "gcp.cloud-run-twin-api-materializer": ["google_cloud_run_v2_service"],
    "gcp.firestore-native-standard-bounded-twin": [
        "google_firestore_database",
        "google_firestore_index",
    ],
    "gcp.cloud-run-iap-twin-explorer": [
        "google_cloud_run_v2_service",
        "google_cloud_run_v2_service_iam_member",
        "google_iap_web_cloud_run_service_iam_member",
    ],
    "grafana.oss-12-on-gke": [
        "google_container_cluster",
        "kubernetes_namespace_v1",
        "kubernetes_deployment_v1",
    ],
    "gcp.persistent-disk-rwo": [
        "google_compute_disk",
        "kubernetes_persistent_volume_v1",
        "kubernetes_persistent_volume_claim_v1",
    ],
    "gcp.cloud-run-raw-history-reader": ["google_cloud_run_v2_service"],
    "gcp.cloud-scheduler": ["google_cloud_scheduler_job"],
    "gcp.cloud-run-storage-job": ["google_cloud_run_v2_job"],
    "gcp.artifact-registry-if-container-selected": [
        "google_artifact_registry_repository",
        "google_artifact_registry_repository_iam_member",
        "google_storage_bucket",
        "google_storage_bucket_iam_member",
        "google_service_account",
        "google_project_iam_member",
    ],
    "gcp.cloud-logging": [],
    "gcp.cloud-monitoring": [],
    "gcp.direct-iap-layer-access": ["google_iap_web_cloud_run_service_iam_member"],
    "gcp.grafana-tls-load-balancer": [
        "google_compute_address",
        "kubernetes_service_v1",
        "kubernetes_secret_v1",
    ],
    "gcp.pubsub-separated-embedded-topics": [
        "google_pubsub_topic",
        "google_pubsub_subscription",
    ],
    "gcp.cloud-run-event-adapter": ["google_cloud_run_v2_service"],
    "gcp.pubsub-separated-event-layer-topics": [
        "google_pubsub_topic",
        "google_pubsub_subscription",
    ],
    "gcp.cloud-run-event-service-small-medium": ["google_cloud_run_v2_service"],
    "gcp.cloud-run-worker-pool-fixed-large": ["google_cloud_run_v2_worker_pool"],
    "aws.grafana-marcusolsson-json-datasource": [],
    "azure.grafana-marcusolsson-json-datasource": [],
    "grafana.yesoreyeram-infinity-datasource": [],
}

POST_TERRAFORM_OPERATIONS: dict[str, list[str]] = {
    "aws.iot-twinmaker-standard": [
        "aws_sdk_iottwinmaker_component_type_entity_and_relationship_lifecycle"
    ],
    "gcp.cloud-logging": ["provider_platform_capability_no_resource"],
    "gcp.cloud-monitoring": ["provider_platform_capability_no_resource"],
    "aws.grafana-marcusolsson-json-datasource": [
        "grafana_plugin_catalog_preflight_and_datasource_provisioning"
    ],
    "azure.grafana-marcusolsson-json-datasource": [
        "grafana_plugin_catalog_preflight_and_datasource_provisioning"
    ],
    "grafana.yesoreyeram-infinity-datasource": [
        "content_addressed_image_build_and_datasource_provisioning"
    ],
    "gcp.artifact-registry-if-container-selected": [
        "regional_cloud_build_publish_content_addressed_images"
    ],
    "aws.ecr-if-container-selected": [
        "regional_codebuild_publish_content_addressed_images"
    ],
    "azure.acr-basic-if-container-selected": [
        "regional_acr_task_publish_content_addressed_images"
    ],
}

TERRAFORM_PROVIDER_REQUIREMENTS = {
    "terraform": {
        "verified_version": "1.7.5",
        "version_constraint": ">= 1.6.0, < 2.0.0",
        "reason": "repository baseline and provider compatibility",
    },
    "aws": {
        "source": "hashicorp/aws",
        "verified_version": "5.100.0",
        "version_constraint": ">= 5.92.0, < 6.0.0",
        "reason": "retain the reviewed repository AWS v5 baseline",
    },
    "awscc": {
        "source": "hashicorp/awscc",
        "verified_version": "1.78.0",
        "version_constraint": ">= 1.78.0, < 2.0.0",
        "reason": "awscc_iot_command and awscc_iottwinmaker_workspace are verified in 1.78.0",
    },
    "azurerm": {
        "source": "hashicorp/azurerm",
        "verified_version": "4.67.0",
        "version_constraint": ">= 4.27.0, < 5.0.0",
        "reason": "azurerm_function_app_flex_consumption is verified in 4.27.0",
    },
    "google": {
        "source": "hashicorp/google",
        "verified_version": "7.22.0",
        "version_constraint": ">= 7.22.0, < 8.0.0",
        "reason": "worker-pool and direct Cloud Run IAP resources are verified together in 7.22.0",
    },
    "kubernetes": {
        "source": "hashicorp/kubernetes",
        "verified_version": "2.38.0",
        "version_constraint": ">= 2.38.0, < 3.0.0",
        "reason": "declarative BifroMQ and Grafana GKE workloads",
    },
    "tls": {
        "source": "hashicorp/tls",
        "verified_version": "4.3.0",
        "version_constraint": ">= 4.3.0, < 5.0.0",
        "reason": "deployment-generated self-signed certificate for the CIDR-scoped Grafana PoC endpoint",
    },
}

ARTIFACT_COMPONENTS = {
    "apache.bifromq-4.0.0-incubating-on-gke-standard": ["apache-bifromq-linux-amd64"],
    "grafana.oss-12-on-gke": ["grafana-oss-multiarch"],
    "grafana.yesoreyeram-infinity-datasource": ["infinity-plugin-linux-amd64"],
}


def load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def digest(value: Any) -> str:
    encoded = json.dumps(
        value, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def dimensions(component_id: str) -> list[str]:
    values = ["resource_count"]
    lowered = component_id.lower()
    mappings = (
        (("storage", "s3", "blob", "persistent-disk"), ("stored_gib_month",)),
        (("dynamodb",), ("read_requests", "write_requests", "stored_gib_month")),
        (
            ("cosmos",),
            (
                "request_units",
                "stored_gib_month",
                "capacity_mode",
                "autoscale_max_ru_per_second",
            ),
        ),
        (
            ("firestore",),
            (
                "document_reads",
                "document_writes",
                "document_deletes",
                "stored_gib_month",
                "timestamp_shards",
            ),
        ),
        (("lambda",), ("requests", "gib_seconds")),
        (("function",), ("requests", "execution_seconds")),
        (("cloud-run",), ("requests", "vcpu_seconds", "memory_gib_seconds")),
        (("grafana",), ("workspace_count", "editor_seats", "viewer_seats")),
        (("gke",), ("node_count", "node_hours")),
        (("event-hubs",), ("throughput_unit_hours", "capacity_unit_hours")),
        (
            ("kinesis",),
            ("stream_count", "shards_per_stream", "shard_hours", "payload_units"),
        ),
        (("pubsub",), ("publish_bytes", "delivery_bytes")),
        (("sqs",), ("requests",)),
        (("sns",), ("publishes", "delivery_bytes")),
        (("service-bus",), ("messaging_unit_hours", "operations")),
        (
            ("monitor", "logging", "cloudwatch", "log-analytics"),
            ("log_ingestion_gib", "retained_log_gib_month"),
        ),
        (("load-balancer",), ("rule_hours", "processed_bytes")),
        (("iot", "bifromq", "mqtt"), ("connected_devices", "messages")),
        (("twin",), ("twin_entities", "twin_operations")),
        (("scheduler",), ("scheduled_invocations",)),
        (
            ("workflow", "step-functions", "logic-apps"),
            ("workflow_executions", "workflow_transitions"),
        ),
    )
    for tokens, mapped_dimensions in mappings:
        if any(token in lowered for token in tokens):
            for dimension in mapped_dimensions:
                if dimension not in values:
                    values.append(dimension)
    if component_id == "gcp.ordered-mqtt-pubsub-adapter":
        values.extend(["node_count", "node_hours"])
    if component_id in {
        "aws.ecs-fargate-storage-mover",
        "azure.container-apps-scheduled-storage-job",
        "gcp.cloud-run-storage-job",
    }:
        values.append("task_count")
    return values


def contracts(responsibility: str) -> tuple[list[str], list[str]]:
    if responsibility == "l3_hot":
        return (
            ["canonical-telemetry.v1"],
            ["raw_history_query.v1", "twin_projection.v1"],
        )
    if responsibility == "l4_twin":
        return (["twin_projection.v1"], ["deployment-access.v1"])
    if responsibility == "l5_visualization":
        return (["raw_history_query.v1"], ["deployment-access.v1"])
    if responsibility in {"embedded_event", "event_layer"}:
        return (["canonical-domain-event.v1"], ["canonical-domain-event.v1"])
    if responsibility in {"l3_cool", "l3_archive", "support"}:
        return (["storage_transition.v1"], ["storage_transition.v1"])
    return (["resolved-deployment-specification.v2"], ["canonical-telemetry.v1"])


def network_ports(component_id: str) -> list[int]:
    if "bifromq" in component_id or "mqtt" in component_id:
        return [1883, 8883]
    if "grafana" in component_id:
        return [3000, 443]
    if any(token in component_id for token in ("reader", "twin-api", "twin-explorer")):
        return [443]
    return []


def file_targets(provider: str, component_id: str) -> list[str]:
    exact = {
        "aws.ecr-if-container-selected": [
            "3-cloud-deployer/src/terraform/aws_six_layer.tf",
            "3-cloud-deployer/src/providers/terraform/aws_v2_image_publisher.py",
            "3-cloud-deployer/src/providers/terraform/package_builders/aws_v2.py",
        ],
        "aws.ecs-fargate-storage-mover": [
            "3-cloud-deployer/src/terraform/aws_six_layer.tf",
            "3-cloud-deployer/src/providers/aws/lambda_functions/six-layer-domain/storage-mover",
        ],
        "azure.acr-basic-if-container-selected": [
            "3-cloud-deployer/src/terraform/azure_six_layer.tf",
            "3-cloud-deployer/src/providers/terraform/azure_v2_image_publisher.py",
            "3-cloud-deployer/src/providers/terraform/package_builders/azure_v2_container.py",
        ],
        "azure.container-apps-scheduled-storage-job": [
            "3-cloud-deployer/src/terraform/azure_six_layer.tf",
            "3-cloud-deployer/src/providers/azure/azure_functions/six-layer-domain/storage-mover",
        ],
        "gcp.artifact-registry-if-container-selected": [
            "3-cloud-deployer/src/terraform/gcp_six_layer.tf",
            "3-cloud-deployer/src/providers/terraform/gcp_v2_image_publisher.py",
            "3-cloud-deployer/src/providers/terraform/package_builders/gcp_v2.py",
        ],
        "gcp.cloud-run-storage-job": [
            "3-cloud-deployer/src/terraform/gcp_six_layer.tf",
            "3-cloud-deployer/src/providers/gcp/containers/six-layer-domain/storage-mover",
        ],
    }
    if component_id in exact:
        return exact[component_id]
    slug = component_id.replace(".", "_").replace("-", "_")
    return [
        f"3-cloud-deployer/src/terraform/{provider}_six_layer.tf",
        f"3-cloud-deployer/src/runtime_packages/{provider}/{slug}",
    ]


def flatten_components(bundle: dict[str, Any]) -> list[dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    for provider in bundle["providers"]:
        provider_id = provider["provider"]
        region = provider["region"]
        groups: list[tuple[str, list[str], list[str]]] = []
        for layer, ids in provider["layers"].items():
            groups.append((layer, ids, ["six-layer-eventing@1"]))
        groups.extend(
            [
                (
                    "support",
                    provider["support_components"],
                    ["six-layer-eventing@1"],
                ),
                (
                    "embedded_event",
                    provider["embedded_event_components"],
                    ["six-layer-eventing@1"],
                ),
                (
                    "event_layer",
                    provider["six_layer_event_components"],
                    ["six-layer-eventing@1"],
                ),
            ]
        )
        for responsibility, component_ids, profiles in groups:
            for component_id in component_ids:
                record = records.setdefault(
                    component_id,
                    {
                        "component_id": component_id,
                        "provider": provider_id,
                        "region": region,
                        "responsibilities": [],
                        "profile_refs": [],
                        "terraform_resource_types": TERRAFORM_TYPES.get(
                            component_id, []
                        ),
                        "post_terraform_operations": POST_TERRAFORM_OPERATIONS.get(
                            component_id, []
                        ),
                        "runtime_state": "decision_frozen_not_implemented",
                        "pricing_owner_id": f"cost::{component_id}",
                        "test_owner": "phase_08_service_bundles_and_future_phase_08_9",
                        "input_contracts": [],
                        "output_contracts": [],
                        "runtime_package": (
                            "managed_provider_api"
                            if not any(
                                token in component_id
                                for token in (
                                    "bifromq",
                                    "grafana.oss",
                                    "adapter",
                                    "reader",
                                    "worker",
                                    "storage-mover",
                                    "storage-job",
                                    "twin-api",
                                    "twin-explorer",
                                )
                            )
                            else "content_addressed_repository_package"
                        ),
                        "network_ports": network_ports(component_id),
                        "implementation_file_targets": file_targets(
                            provider_id, component_id
                        ),
                        "formula_refs": [
                            "capacity-matrix.json#formula_contract",
                            "pricing-ownership-matrix.json",
                        ],
                        "capacity_dimensions": dimensions(component_id),
                    },
                )
                record["responsibilities"] = sorted(
                    set(record["responsibilities"] + [responsibility])
                )
                record["profile_refs"] = sorted(set(record["profile_refs"] + profiles))
                inputs, outputs = contracts(responsibility)
                record["input_contracts"] = sorted(
                    set(record["input_contracts"] + inputs)
                )
                record["output_contracts"] = sorted(
                    set(record["output_contracts"] + outputs)
                )
    for component_id, record in records.items():
        if not (
            record["terraform_resource_types"] or record["post_terraform_operations"]
        ):
            raise ValueError(f"missing implementation binding for {component_id}")
        if component_id in ARTIFACT_COMPONENTS:
            record["artifact_refs"] = ARTIFACT_COMPONENTS[component_id]
    return [records[key] for key in sorted(records)]


def build_manifest(bundle: dict[str, Any], routes: dict[str, Any]) -> dict[str, Any]:
    return {
        "$schema": "./schemas/package-artifact.schema.json",
        "schema_version": "1.0.0",
        "package_id": "phase-08-complete-service-bundles@1",
        "artifact_id": "implementation-component-manifest",
        "bundle_digest": digest(bundle),
        "route_digest": digest(routes),
        "profile_targets": ["six-layer-eventing@1"],
        "terraform_provider_requirements": TERRAFORM_PROVIDER_REQUIREMENTS,
        "terraform_apply_stages": [
            {
                "stage": 1,
                "owner": "provider_image_foundation_when_required",
                "includes": "deployment registry, finite build-source storage, build identity and scoped bindings",
            },
            {
                "stage": 2,
                "owner": "provider_content_addressed_image_publication_when_required",
                "includes": "regional CodeBuild, ACR Task or Cloud Build publication and digest resolution without a local Docker socket",
                "precondition": "stage_1_registry_source_bucket_and_build_identity_available",
            },
            {
                "stage": 3,
                "owner": "cloud_provider_resources",
                "includes": "GKE cluster and all non-Kubernetes provider resources",
            },
            {
                "stage": 4,
                "owner": "kubernetes_resources",
                "includes": "BifroMQ, adapter, Grafana, services, PVC and TLS bindings",
                "precondition": "stage_3_cluster_endpoint_and_short_lived_credentials_available",
            },
            {
                "stage": 5,
                "owner": "bounded_post_terraform_operations",
                "includes": "TwinMaker children and Grafana plugin/datasource provisioning",
            },
        ],
        "components": flatten_components(bundle),
        "edge_contracts": [
            "raw_history_query.v1",
            "twin_projection.v1",
            "storage_transition.v1",
            "canonical-domain-event.v1",
        ],
        "route_classes": [item["route_class"] for item in routes["route_classes"]],
        "runtime_target_roots": [
            "contracts/architecture-profiles/definitions",
            "2-twin2clouds/backend",
            "twin2multicloud_backend",
            "3-cloud-deployer",
            "twin2multicloud_flutter",
        ],
        "activation_rule": "both_eventing_and_complete_service_digests_must_match",
    }


def build_pricing(bundle: dict[str, Any], routes: dict[str, Any]) -> dict[str, Any]:
    components = flatten_components(bundle)
    cross_pairs = routes["directed_cross_cloud_pairs"]
    route_owners = []
    for route_class in (
        "twin_projection_cross_cloud",
        "storage_hot_to_cool_cross_cloud",
        "storage_cool_to_archive_cross_cloud",
        "domain_event_cross_cloud",
    ):
        for pair in cross_pairs:
            source, destination = pair.split("->")
            route_owners.append(
                {
                    "cost_owner_id": f"cost::route::{route_class}::{pair}",
                    "route_class": route_class,
                    "pair": pair,
                    "source_provider": source,
                    "destination_provider": destination,
                    "dimensions": [
                        "source_runtime",
                        "destination_operations",
                        "cross_cloud_egress_bytes",
                    ],
                    "deduplication_key": f"{route_class}::{pair}",
                }
            )
    return {
        "$schema": "./schemas/package-artifact.schema.json",
        "schema_version": "1.0.0",
        "package_id": "phase-08-complete-service-bundles@1",
        "artifact_id": "pricing-ownership-matrix",
        "currency": "USD",
        "price_value_policy": "live_versioned_optimizer_catalog_only_no_static_fallback",
        "component_owners": [
            {
                "cost_owner_id": item["pricing_owner_id"],
                "component_id": item["component_id"],
                "provider": item["provider"],
                "region": item["region"],
                "pricing_catalog_key": item["component_id"],
                "dimensions": dimensions(item["component_id"]),
                "deduplication_key": item["component_id"],
            }
            for item in components
        ],
        "route_owners": route_owners,
        "same_provider_rule": {
            "bridge_component_count": 0,
            "cross_cloud_egress_cost": 0,
            "local_service_operations_are_still_priced": True,
        },
        "shared_support_rules": [
            "one_registry_per_selected_provider_with_platform_owned_containers",
            "one_firestore_database_per_deployment_when_gcp_l3_or_l4_is_selected",
            "one_gcp_gke_cluster_control_plane_when_l1_and_l5_are_both_gcp",
            "one_azure_log_analytics_workspace_per_selected_azure_bundle",
        ],
    }


def render(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    bundle = load_json(BUNDLE_PATH)
    routes = load_json(ROUTE_PATH)
    expected = {
        MANIFEST_PATH: render(build_manifest(bundle, routes)),
        PRICING_PATH: render(build_pricing(bundle, routes)),
    }
    stale = []
    for path, content in expected.items():
        if args.write:
            path.write_text(content, encoding="utf-8")
        elif not path.exists() or path.read_text(encoding="utf-8") != content:
            stale.append(path.relative_to(REPOSITORY_ROOT))
    if stale:
        for path in stale:
            print(f"stale generated manifest: {path}")
        return 1
    if args.write:
        print("wrote Phase 8 service component/pricing manifests")
    else:
        print("phase-08-service-bundles generated manifests: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
