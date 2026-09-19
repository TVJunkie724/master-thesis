"""Generate native mock plans from the actual offline Core preparer."""

import hashlib
import importlib.util
import json
from pathlib import Path


def write_core_mock_plans(terraform_dir: Path, project_path: Path) -> int:
    root = Path(__file__).resolve().parents[3]
    path = root / "scripts/prepare_core_evaluation.py"
    if not path.is_file():
        path = Path("/workspace/scripts/prepare_core_evaluation.py")
    if not path.is_file():
        raise RuntimeError(
            "Core mock plans require the repository root mounted at /workspace"
        )
    spec = importlib.util.spec_from_file_location("prepare_core_evaluation", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    header = (
        (terraform_dir / "tests/gcp_eventing.tftest.hcl").read_text().split('run "')[0]
    )
    overrides = """
  override_data {
    target = data.aws_caller_identity.current
    values = {
      account_id = "123456789012"
      arn = "arn:aws:iam::123456789012:user/mock"
      user_id = "mock"
    }
  }
  override_resource {
    target = azurerm_container_registry.azure_azure_acr_basic_if_container_selected
    values = { login_server = "coremock.azurecr.io" }
  }
"""
    assertions = """
  assert {
    condition = (
      alltrue([for schedule in aws_scheduler_schedule.aws_aws_eventbridge_scheduler :
        schedule.state == "DISABLED" && schedule.target[0].retry_policy[0].maximum_retry_attempts == 0]) &&
      alltrue([for project in aws_codebuild_project.aws_aws_ecr_if_container_selected : project.build_timeout == 5]) &&
      alltrue([for command in awscc_iot_command.aws_aws_iot_commands :
        command.preprocessor.aws_json_substitution.output_format == "JSON"]) &&
      alltrue([for logs in aws_cloudwatch_log_group.aws_six_layer_core_build : logs.retention_in_days == 1]) &&
      alltrue([for job in azurerm_container_app_job.azure_azure_container_apps_scheduled_storage_job :
        length(job.schedule_trigger_config) == 0 && length(job.manual_trigger_config) == 1 &&
        job.replica_timeout_in_seconds == 300 && job.replica_retry_limit == 0]) &&
      alltrue([for schedule in google_cloud_scheduler_job.gcp_gcp_cloud_scheduler :
        schedule.paused && schedule.retry_config[0].retry_count == 0]) &&
      alltrue([for job in google_cloud_run_v2_job.gcp_gcp_cloud_run_storage_job :
        job.template[0].template[0].timeout == "300s" && job.template[0].template[0].max_retries == 0]) &&
      alltrue([for bucket in google_storage_bucket.gcp_six_layer_cloud_build_sources :
        bucket.soft_delete_policy[0].retention_duration_seconds == 0])
    )
    error_message = "Core must not start recurring storage work and must bound builds/jobs without retained build objects."
  }
  assert {
    condition = (
      alltrue([for app in concat(
        azurerm_function_app_flex_consumption.azure_azure_functions_flex_event_adapter,
        azurerm_function_app_flex_consumption.azure_azure_functions_flex_consumption,
        values(azurerm_function_app_flex_consumption.azure_six_layer_processor_extension),
        azurerm_function_app_flex_consumption.azure_six_layer_extension_action,
        azurerm_function_app_flex_consumption.azure_azure_functions_flex_raw_history_reader,
        azurerm_function_app_flex_consumption.event_runtime) : app.maximum_instance_count == 1]) &&
      alltrue([for service in concat(
        values(google_cloud_run_v2_service.gcp_gcp_cloud_run_event_adapter),
        google_cloud_run_v2_service.gcp_six_layer_processor_extension,
        google_cloud_run_v2_service.gcp_gcp_cloud_run_service,
        google_cloud_run_v2_service.gcp_six_layer_action_sink,
        google_cloud_run_v2_service.gcp_gcp_cloud_run_raw_history_reader,
        google_cloud_run_v2_service.event_runtime) :
        service.template[0].scaling[0].min_instance_count == 0 &&
        service.template[0].scaling[0].max_instance_count == 1])
    )
    error_message = "Tiny Core smoke runtimes must scale to zero and cap scale-out at one instance per group/revision."
  }
  assert {
    condition = length(toset(concat(
      [for container in values(azurerm_storage_container.azure_six_layer_function_package) : container.name],
      [for container in azurerm_storage_container.azure_event_function_package : container.name]
    ))) == length(azurerm_service_plan.azure_six_layer_flex)
    error_message = "Each Azure Flex app must own a distinct deployment container to prevent OneDeploy package collisions."
  }
  assert {
    condition = alltrue([for app in concat(
      azurerm_function_app_flex_consumption.azure_azure_functions_flex_raw_history_reader,
      azurerm_function_app_flex_consumption.azure_azure_functions_flex_consumption,
      values(azurerm_function_app_flex_consumption.azure_six_layer_processor_extension)) :
      length(app.always_ready) == 1 && app.always_ready[0].name == "http" && app.always_ready[0].instance_count == 1])
    error_message = "The bounded Core integration check keeps one HTTP instance warm at each telemetry-path HTTP boundary."
  }
  assert {
    condition = alltrue([for key, index in google_firestore_index.gcp_gcp_firestore_native_standard_raw_and_rollup :
      alltrue([for field in index.fields : field.order == "ASCENDING" if field.field_path == "stored_at"])
      if key == "raw_history"])
    error_message = "The GCP raw-history index must match the reader's ascending stored_at order."
  }
  assert {
    condition = alltrue([for service in google_cloud_run_v2_service.gcp_gcp_cloud_run_service :
      lookup({for setting in service.template[0].containers[0].env : setting.name => setting.value}, "L2_PROVIDER", "") == "google"])
    error_message = "The GCP processor must receive the provider setting required by its Event-Layer consumer."
  }
  assert {
    condition = (
      alltrue([for service in concat(
        google_cloud_run_v2_service.gcp_six_layer_processor_extension,
        google_cloud_run_v2_service.gcp_six_layer_action_sink) :
        service.ingress == "INGRESS_TRAFFIC_ALL" && service.invoker_iam_disabled == false]) &&
      alltrue([for binding in google_cloud_run_v2_service_iam_member.gcp_six_layer_processor_extension_invoker :
        binding.role == "roles/run.invoker"]) &&
      alltrue([for binding in google_cloud_run_v2_service_iam_member.gcp_six_layer_action_sink_invoker :
        binding.role == "roles/run.invoker"])
    )
    error_message = "Cloud Run HTTP calls without VPC egress need reachable endpoints with mandatory, service-account-bound IAM."
  }
  assert {
    condition = alltrue([for service in kubernetes_service_v1.gcp_six_layer_bifromq_auth :
      service.spec[0].publish_not_ready_addresses])
    error_message = "The private broker auth webhook must be reachable before MQTT subscription readiness."
  }
  assert {
    condition = (
      alltrue([for hub in azurerm_iothub.azure_azure_iot_hub :
        length(hub.fallback_route) == 1 && hub.fallback_route[0].enabled &&
        toset(hub.fallback_route[0].endpoint_names) == toset(["events"])]) &&
      alltrue([for policy in azurerm_iothub_shared_access_policy.azure_six_layer_ingress :
        policy.service_connect && !policy.device_connect && !policy.registry_read && !policy.registry_write])
    )
    error_message = "Azure IoT ingress needs an enabled built-in route and a ServiceConnect-only policy."
  }
  assert {
    condition = (
      length(awscc_iottwinmaker_workspace.aws_aws_iot_twinmaker_standard) == 0 &&
      length(aws_s3_bucket.aws_six_layer_twinmaker) == 0 &&
      length(aws_iam_role.aws_six_layer_twinmaker) == 0 &&
      length(aws_ssoadmin_permission_set.aws_aws_iam_identity_center_layer_access) == 0 &&
      length(azurerm_digital_twins_instance.azure_azure_digital_twins) == 0 &&
      length(google_cloud_run_v2_service.gcp_gcp_cloud_run_twin_api_materializer) == 0 &&
      length(google_cloud_run_v2_service.gcp_gcp_cloud_run_iap_twin_explorer) == 0 &&
      length(google_pubsub_topic_iam_member.gcp_six_layer_persistence_domain_publisher) == 0 &&
      length(google_firestore_index.gcp_gcp_firestore_native_standard_bounded_twin) == 0
    )
    error_message = "Core must create no L4 resources or Twin-only access bindings."
  }
  assert {
    condition = (
      !contains(keys(aws_lambda_function.event_runtime), "twin-state-update") &&
      !contains(keys(azurerm_eventhub_consumer_group.domain_standard), "twin-state-update") &&
      !contains(keys(azurerm_eventhub_consumer_group.domain_dedicated), "twin-state-update") &&
      !contains(keys(google_pubsub_subscription.domain_events), "twin-state-update") &&
      output.evaluation_scope.includes_all_layers == false &&
      output.aws_component_visualization_output == null &&
      output.azure_component_visualization_output == null &&
      output.gcp_component_visualization_output == null
    )
    error_message = "Core must omit Twin consumers and must not claim L5/full-profile evidence."
  }
  assert {
    condition = (
      length(aws_iot_topic_rule.aws_aws_iot_core) +
      length(azurerm_iothub.azure_azure_iot_hub) +
      length(google_container_cluster.gcp_apache_bifromq_4_0_0_incubating_on_gke_standard) == 1 &&
      length(aws_lambda_function.aws_aws_lambda) +
      length(azurerm_function_app_flex_consumption.azure_azure_functions_flex_consumption) +
      length(google_cloud_run_v2_service.gcp_gcp_cloud_run_service) == 1
    )
    error_message = "Core must retain exactly one ingestion and one processing implementation."
  }
  assert {
    condition = (
      length(aws_lambda_function.aws_aws_lambda_raw_history_reader) +
      length(azurerm_function_app_flex_consumption.azure_azure_functions_flex_raw_history_reader) +
      length(google_cloud_run_v2_service.gcp_gcp_cloud_run_raw_history_reader) == 1
    )
    error_message = "Exactly one L3 storage reader must survive the Core cut."
  }
"""
    runs = []
    for name in module.SCENARIOS:
        values = module.materialize(name)["tfvars"]
        # Synthetic references exist only in tests; never exported as real images.
        values.update(
            {
                "digital_twin_name": "drift-test",
                "project_path": str(project_path),
                "gcp_project_id": "phase8-poc-project",
                "gcp_deployment_principal_email": "deployer@phase8-poc-project.iam.gserviceaccount.com",
                "aws_six_layer_storage_mover_image": "123456789012.dkr.ecr.eu-central-1.amazonaws.com/mock@sha256:"
                + "a" * 64,
                "aws_six_layer_bridge_image": "123456789012.dkr.ecr.eu-central-1.amazonaws.com/mock@sha256:"
                + "b" * 64,
                "azure_six_layer_storage_mover_image": "coremock.azurecr.io/storage-mover@sha256:"
                + "c" * 64,
                "aws_outbound_identity_required": True,
                "aws_outbound_identity_destinations": ["azure"],
                "aws_outbound_identity_issuer": "https://issuer.example.test",
                "enable_aws_logging": False,
                "enable_azure_logging": False,
                "enable_gcp_logging": False,
            }
        )
        for key in (
            "gcp_six_layer_platform_image",
            "gcp_six_layer_processor_extension_image",
            "gcp_six_layer_storage_mover_image",
            "gcp_event_runtime_image",
        ):
            values[key] = (
                "europe-west1-docker.pkg.dev/phase8-poc-project/drift-test-v2/mock@sha256:"
                + "d" * 64
            )
        target = module.SCENARIOS[name][1]
        package = (
            project_path
            / ".build"
            / ("aws" if target == "aws" else "azure")
            / "six-layer-domain.zip"
        )
        values["validated_extension_packages"] = [
            {
                "slot_id": "processor.telemetry",
                "slot_version": "1",
                "artifact_id": "44444444-4444-4444-8444-444444444444",
                "artifact_digest": "sha256:" + "4" * 64,
                "package_path": str(package),
                "package_digest": "sha256:"
                + hashlib.sha256(package.read_bytes()).hexdigest(),
                "adapter_id": f"adapter.{target}.python311",
                "adapter_version": "1",
            }
        ]
        block = "\n".join(
            f"    {key} = {json.dumps(value)}" for key, value in values.items()
        )
        runs.append(
            f'run "{name.replace("-", "_")}" {{\n command = plan\n{overrides}\n variables {{\n{block}\n }}\n{assertions}\n}}'
        )
        if name == "core-small-local-aws":
            for label, changes in {
                "full_cannot_omit_access_layers": {
                    "evaluation_scope": "full",
                    "platform_user_email": "test@example.test",
                },
                "core_cannot_include_l5": {"layer_5_provider": "aws"},
                "core_cannot_select_larger_capacity": {"aws_event_kinesis_shards": 6},
            }.items():
                negative = {**values, **changes}
                negative_block = "\n".join(
                    f"    {key} = {json.dumps(value)}"
                    for key, value in negative.items()
                )
                runs.append(
                    f'run "{label}" {{\n command = plan\n{overrides}\n variables {{\n{negative_block}\n }}\n expect_failures = [terraform_data.evaluation_scope_guard]\n}}'
                )
        if name == "core-small-aws-to-gcp":
            missing_return = dict(
                values,
                resolved_cross_cloud_routes=values["resolved_cross_cloud_routes"][:1],
            )
            negative_block = "\n".join(
                f"    {key} = {json.dumps(value)}"
                for key, value in missing_return.items()
            )
            runs.append(
                f'run "core_requires_all_return_routes" {{\n command = plan\n{overrides}\n variables {{\n{negative_block}\n }}\n expect_failures = [terraform_data.evaluation_scope_guard]\n}}'
            )
    for index, run in enumerate(runs):
        (terraform_dir / f"tests/core_evaluation_{index:02}.tftest.hcl").write_text(
            header + run
        )
    return len(runs)
