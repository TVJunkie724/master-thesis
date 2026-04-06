/// Human-readable labels for Terraform output keys.
///
/// Keys are stored WITHOUT provider prefix (aws_, azure_, gcp_ are stripped
/// by [TerraformOutputsCard._groupOutputs] before lookup).
///
/// The insertion order defines the **display order** in the UI — outputs
/// within each provider group are sorted by their position in this map.
/// Related keys are grouped together by category.
const outputLabels = <String, String>{
  // ── Setup / Resource Group ──
  'resource_group_name': 'Resource Group',
  'resource_group_id': 'Resource Group ID',
  'account_id': 'Account ID',
  'region': 'Region',
  'project_id': 'Project ID',

  // ── Identity ──
  'managed_identity_id': 'Managed Identity',
  'managed_identity_client_id': 'Managed Identity Client ID',
  'service_account_email': 'Service Account Email',
  'function_source_bucket': 'Function Source Bucket',

  // ── Storage Account ──
  'storage_account_name': 'Storage Account',

  // ── Platform User ──
  'platform_user_email': 'Platform User Email',
  'platform_user_password': 'Platform User Password',
  'platform_user_created': 'Platform User Created',
  'sso_available': 'SSO Available',

  // ── L0 Glue ──
  'l0_function_app_name': 'L0 Function App',
  'l0_function_app_url': 'L0 Function App URL',
  'l0_ingestion_function_name': 'L0 Ingestion Function',
  'l0_ingestion_url': 'L0 Ingestion URL',
  'l0_hot_writer_url': 'L0 Hot Writer URL',
  'l0_hot_reader_url': 'L0 Hot Reader URL',
  'l0_cold_writer_function_name': 'L0 Cold Writer Function',
  'l0_cold_writer_url': 'L0 Cold Writer URL',
  'l0_archive_writer_function_name': 'L0 Archive Writer Function',
  'l0_archive_writer_url': 'L0 Archive Writer URL',
  'ingestion_url': 'Ingestion URL',
  'hot_writer_url': 'Hot Writer URL',
  'cold_writer_url': 'Cold Writer URL',
  'archive_writer_url': 'Archive Writer URL',

  // ── L1 IoT ──
  'iothub_name': 'IoT Hub',
  'iothub_hostname': 'IoT Hub Hostname',
  'iothub_connection_string': 'IoT Hub Connection String',
  'l1_function_app_name': 'L1 Function App',
  'l1_dispatcher_function_name': 'L1 Dispatcher Function',
  'iot_topic_rule_name': 'IoT Topic Rule',
  'iot_role_arn': 'IAM Role (IoT)',
  'l1_connector_function_name': 'L1 Connector Function',
  'iot_endpoint': 'IoT Endpoint',
  'pubsub_telemetry_topic': 'Pub/Sub Telemetry Topic',
  'pubsub_events_topic': 'Pub/Sub Events Topic',
  'dispatcher_url': 'Dispatcher URL',
  'connector_url': 'Connector URL',

  // ── L2 Compute ──
  'l2_function_app_name': 'L2 Function App',
  'user_functions_app_name': 'User Functions App',
  'logic_app_name': 'Logic App',
  'l2_persister_function_name': 'L2 Persister Function',
  'l2_event_checker_function_name': 'L2 Event Checker Function',
  'l2_step_function_arn': 'Step Function ARN',
  'processor_url': 'Processor URL',
  'persister_url': 'Persister URL',
  'event_checker_url': 'Event Checker URL',
  'user_functions_url': 'User Functions URL',
  'event_workflow_id': 'Event Workflow ID',

  // ── L3 Storage ──
  'cosmos_account_name': 'Cosmos DB Account',
  'cosmos_endpoint': 'Cosmos DB Endpoint',
  'l3_function_app_name': 'L3 Function App',
  'l3_hot_reader_url': 'L3 Hot Reader URL',
  'l3_hot_reader_function_name': 'L3 Hot Reader Function',
  'archive_storage_account': 'Archive Storage Account',
  'dynamodb_table_name': 'DynamoDB Table',
  'dynamodb_table_arn': 'DynamoDB Table ARN',
  's3_cold_bucket': 'S3 Cold Bucket',
  's3_archive_bucket': 'S3 Archive Bucket',
  'firestore_database': 'Firestore Database',
  'cold_bucket': 'Cold Storage Bucket',
  'archive_bucket': 'Archive Storage Bucket',
  'hot_reader_url': 'Hot Reader URL',

  // ── L4 Digital Twins ──
  'adt_instance_name': 'ADT Instance',
  'adt_endpoint': 'ADT Endpoint',
  '3d_scenes_container_url': '3D Scenes Container URL',
  '3d_scenes_studio_url': '3D Scenes Studio URL',
  'adt_portal_url': 'ADT Portal URL',
  'storage_portal_url': 'Storage Portal URL',
  'adt_access_instructions': 'ADT Access Instructions',
  'twinmaker_workspace_id': 'TwinMaker Workspace ID',
  'twinmaker_workspace_arn': 'TwinMaker Workspace ARN',
  'twinmaker_scene_id': 'TwinMaker Scene ID',

  // ── L5 Visualization ──
  'grafana_name': 'Grafana Workspace',
  'grafana_endpoint': 'Grafana Endpoint',
  'grafana_workspace_id': 'Grafana Workspace ID',
  'grafana_api_key': 'Grafana API Key',
  'grafana_access_instructions': 'Grafana Access Instructions',
  'grafana_login_instructions': 'Grafana Login Instructions',
  'grafana_sso_warning': 'Grafana SSO Warning',

  // ── Cross-Cloud ──
  'digital_twin_name': 'Digital Twin Name',
  'inter_cloud_token': 'Inter-Cloud Token',

  // ── Observability ──
  'cloudwatch_log_groups': 'CloudWatch Log Groups',
  'cloudwatch_log_group_iot': 'CloudWatch IoT Log Group',
  'log_analytics_workspace_id': 'Log Analytics Workspace ID',
  'log_analytics_workspace_name': 'Log Analytics Workspace',
};

/// Returns the human-readable label for a Terraform output key.
///
/// Falls back to auto-generating a label from the key name by replacing
/// underscores with spaces and capitalizing words.
String getOutputLabel(String key) {
  return outputLabels[key] ?? _autoLabel(key);
}

String _autoLabel(String key) {
  return key
      .split('_')
      .map((w) => w.isEmpty ? '' : '${w[0].toUpperCase()}${w.substring(1)}')
      .join(' ');
}
