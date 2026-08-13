# Source-owned Azure cross-cloud bridge for five-layer-baseline@2.
#
# The existing event Function App consumes only the directional Azure outbox
# brokers. It obtains destination credentials from its user-assigned managed
# identity and never stores a cross-cloud client secret.

locals {
  azure_v2_bridge_enabled = length(local.azure_v2_outbound_event_routes) > 0
  azure_v2_bridge_destinations_selected = toset([
    for route in values(local.azure_v2_outbound_event_routes) : route.destination_provider
  ])
  azure_v2_bridge_to_aws_enabled = contains(local.azure_v2_bridge_destinations_selected, "aws")
  azure_v2_bridge_to_gcp_enabled = contains(local.azure_v2_bridge_destinations_selected, "gcp")

  azure_v2_bridge_to_aws_telemetry = anytrue([
    for route in values(local.azure_v2_outbound_event_routes) :
    route.destination_provider == "aws" && route.channel_class == "telemetry"
  ])
  azure_v2_bridge_to_aws_control = anytrue([
    for route in values(local.azure_v2_outbound_event_routes) :
    route.destination_provider == "aws" && route.channel_class == "control"
  ])
  azure_v2_bridge_to_gcp_telemetry = anytrue([
    for route in values(local.azure_v2_outbound_event_routes) :
    route.destination_provider == "gcp" && route.channel_class == "telemetry"
  ])
  azure_v2_bridge_to_gcp_control = anytrue([
    for route in values(local.azure_v2_outbound_event_routes) :
    route.destination_provider == "gcp" && route.channel_class == "control"
  ])
  azure_v2_bridge_aws_telemetry_targets = values(merge(
    anytrue([
      for route in values(local.azure_v2_outbound_event_routes) :
      route.destination_provider == "aws" && route.channel_class == "telemetry" && !endswith(route.logical_edge_id, "-to-eventing")
    ]) ? { remote = aws_kinesis_stream.aws_aws_kinesis_only_for_reviewed_remote_telemetry_edge["inbound"].arn } : {},
    anytrue([
      for route in values(local.azure_v2_outbound_event_routes) :
      route.destination_provider == "aws" && route.channel_class == "telemetry" && endswith(route.logical_edge_id, "-to-eventing") && contains(route.event_types, "telemetry.received.v1")
    ]) ? { event_received = aws_kinesis_stream.domain_telemetry["received"].arn } : {},
    anytrue([
      for route in values(local.azure_v2_outbound_event_routes) :
      route.destination_provider == "aws" && route.channel_class == "telemetry" && endswith(route.logical_edge_id, "-to-eventing") && contains(route.event_types, "telemetry.processed.v1")
    ]) ? { event_processed = aws_kinesis_stream.domain_telemetry["processed"].arn } : {},
  ))
  azure_v2_bridge_aws_control_targets = values(merge(
    anytrue([
      for route in values(local.azure_v2_outbound_event_routes) :
      route.destination_provider == "aws" && route.channel_class == "control" && !endswith(route.logical_edge_id, "-to-eventing")
    ]) ? { remote = aws_sns_topic.aws_aws_sns_fifo_only_for_reviewed_remote_control_edge["inbound"].arn } : {},
    anytrue([
      for route in values(local.azure_v2_outbound_event_routes) :
      route.destination_provider == "aws" && route.channel_class == "control" && endswith(route.logical_edge_id, "-to-eventing")
    ]) ? { event = aws_sns_topic.domain_control[0].arn } : {},
  ))
  azure_v2_bridge_gcp_topic_targets = merge(
    anytrue([
      for route in values(local.azure_v2_outbound_event_routes) :
      route.destination_provider == "gcp" && route.channel_class == "telemetry" && !endswith(route.logical_edge_id, "-to-eventing")
    ]) ? { remote_telemetry = google_pubsub_topic.gcp_gcp_pubsub_separated_embedded_topics["remote-telemetry-inbound"].name } : {},
    anytrue([
      for route in values(local.azure_v2_outbound_event_routes) :
      route.destination_provider == "gcp" && route.channel_class == "control" && !endswith(route.logical_edge_id, "-to-eventing")
    ]) ? { remote_control = google_pubsub_topic.gcp_gcp_pubsub_separated_embedded_topics["remote-control-inbound"].name } : {},
    anytrue([
      for route in values(local.azure_v2_outbound_event_routes) :
      route.destination_provider == "gcp" && route.channel_class == "telemetry" && endswith(route.logical_edge_id, "-to-eventing") && contains(route.event_types, "telemetry.received.v1")
    ]) ? { event_received = google_pubsub_topic.domain_events["received"].name } : {},
    anytrue([
      for route in values(local.azure_v2_outbound_event_routes) :
      route.destination_provider == "gcp" && route.channel_class == "telemetry" && endswith(route.logical_edge_id, "-to-eventing") && contains(route.event_types, "telemetry.processed.v1")
    ]) ? { event_processed = google_pubsub_topic.domain_events["processed"].name } : {},
    anytrue([
      for route in values(local.azure_v2_outbound_event_routes) :
      route.destination_provider == "gcp" && route.channel_class == "control" && endswith(route.logical_edge_id, "-to-eventing")
    ]) ? { event_control = google_pubsub_topic.domain_events["control"].name } : {},
  )

  azure_v2_bridge_assertion_audience = local.azure_v2_bridge_enabled ? "api://${azuread_application.azure_v2_bridge_audience[0].client_id}" : ""

  azure_v2_bridge_destinations = merge(
    local.azure_v2_bridge_to_aws_enabled ? {
      aws = {
        route_targets = {
          for route_id, route in local.azure_v2_outbound_event_routes : route_id => merge(
            route.channel_class == "telemetry" ? {
              telemetry_stream_arn = endswith(route.logical_edge_id, "-to-eventing") ? (
                contains(route.event_types, "telemetry.processed.v1") ? aws_kinesis_stream.domain_telemetry["processed"].arn : aws_kinesis_stream.domain_telemetry["received"].arn
              ) : aws_kinesis_stream.aws_aws_kinesis_only_for_reviewed_remote_telemetry_edge["inbound"].arn
            } : {},
            route.channel_class == "control" ? {
              control_topic_arn = endswith(route.logical_edge_id, "-to-eventing") ? aws_sns_topic.domain_control[0].arn : aws_sns_topic.aws_aws_sns_fifo_only_for_reviewed_remote_control_edge["inbound"].arn
            } : {},
          ) if route.destination_provider == "aws"
        }
      }
    } : {},
    local.azure_v2_bridge_to_gcp_enabled ? {
      gcp = {
        route_targets = {
          for route_id, route in local.azure_v2_outbound_event_routes : route_id => merge(
            route.channel_class == "telemetry" ? {
              telemetry_topic = endswith(route.logical_edge_id, "-to-eventing") ? (
                contains(route.event_types, "telemetry.processed.v1") ? google_pubsub_topic.domain_events["processed"].id : google_pubsub_topic.domain_events["received"].id
              ) : google_pubsub_topic.gcp_gcp_pubsub_separated_embedded_topics["remote-telemetry-inbound"].id
              api_endpoint = "europe-west1-pubsub.googleapis.com"
            } : {},
            route.channel_class == "control" ? {
              control_topic = endswith(route.logical_edge_id, "-to-eventing") ? google_pubsub_topic.domain_events["control"].id : google_pubsub_topic.gcp_gcp_pubsub_separated_embedded_topics["remote-control-inbound"].id
              api_endpoint  = "europe-west1-pubsub.googleapis.com"
            } : {},
          ) if route.destination_provider == "gcp"
        }
      }
    } : {},
  )

  azure_v2_bridge_identities = merge(
    local.azure_v2_bridge_to_aws_enabled ? {
      aws = {
        role_arn           = aws_iam_role.aws_v2_bridge_target_from_azure[0].arn
        assertion_audience = local.azure_v2_bridge_assertion_audience
      }
    } : {},
    local.azure_v2_bridge_to_gcp_enabled ? {
      gcp = {
        provider_audience                 = "//iam.googleapis.com/${google_iam_workload_identity_pool_provider.gcp_v2_bridge_from_azure[0].name}"
        service_account_impersonation_url = "https://iamcredentials.googleapis.com/v1/projects/-/serviceAccounts/${google_service_account.gcp_v2_bridge_target_from_azure[0].email}:generateAccessToken"
        source_assertion_audience         = local.azure_v2_bridge_assertion_audience
      }
    } : {},
  )

  azure_v2_bridge_failure_destination = {
    telemetry_namespace = local.azure_v2_remote_telemetry_outbound ? "${azurerm_eventhub_namespace.azure_azure_event_hubs_only_for_reviewed_remote_telemetry_edge[0].name}.servicebus.windows.net" : local.azure_v2_event_remote_telemetry_outbound ? "${local.azure_event_namespace_name}.servicebus.windows.net" : ""
    telemetry_entity    = local.azure_v2_remote_telemetry_outbound ? azurerm_eventhub.azure_v2_bridge_telemetry_failure[0].name : local.azure_v2_event_remote_telemetry_outbound ? local.azure_event_hub_names.failure : ""
    control_namespace   = local.azure_v2_remote_control_outbound ? "${azurerm_servicebus_namespace.azure_azure_service_bus_standard[0].name}.servicebus.windows.net" : local.azure_v2_event_remote_control_outbound ? "${azurerm_servicebus_namespace.eventing[0].name}.servicebus.windows.net" : ""
    control_entity      = local.azure_v2_remote_control_outbound ? azurerm_servicebus_queue.azure_v2_bridge_control_failure[0].name : local.azure_v2_event_remote_control_outbound ? azurerm_servicebus_queue.event_bridge_control_failure[0].name : ""
  }
}

# One assignment-required Entra resource application scopes both federation
# targets to this deployment's source identity. The application has no secret
# and exposes only the bridge exchange role.
resource "azuread_application" "azure_v2_bridge_audience" {
  count            = local.azure_v2_bridge_enabled ? 1 : 0
  display_name     = "${var.digital_twin_name} v2 event bridge ${local.deployment_suffix}"
  description      = "Dedicated Phase 8 workload-federation audience"
  sign_in_audience = "AzureADMyOrg"
}

resource "azuread_application_identifier_uri" "azure_v2_bridge_audience" {
  count          = local.azure_v2_bridge_enabled ? 1 : 0
  application_id = azuread_application.azure_v2_bridge_audience[0].id
  identifier_uri = local.azure_v2_bridge_assertion_audience
}

resource "random_uuid" "azure_v2_bridge_exchange_role" {
  count = local.azure_v2_bridge_enabled ? 1 : 0
}

resource "azuread_application_app_role" "azure_v2_bridge_exchange" {
  count                = local.azure_v2_bridge_enabled ? 1 : 0
  application_id       = azuread_application.azure_v2_bridge_audience[0].id
  role_id              = random_uuid.azure_v2_bridge_exchange_role[0].result
  allowed_member_types = ["Application"]
  description          = "Exchange canonical five-layer v2 events with one federated destination"
  display_name         = "Event bridge exchange"
  value                = "EventBridge.Exchange"
}

resource "azuread_service_principal" "azure_v2_bridge_audience" {
  count                        = local.azure_v2_bridge_enabled ? 1 : 0
  client_id                    = azuread_application.azure_v2_bridge_audience[0].client_id
  app_role_assignment_required = true

  depends_on = [
    azuread_application_identifier_uri.azure_v2_bridge_audience,
    azuread_application_app_role.azure_v2_bridge_exchange,
  ]
}

resource "azuread_app_role_assignment" "azure_v2_bridge_source" {
  count               = local.azure_v2_bridge_enabled ? 1 : 0
  app_role_id         = random_uuid.azure_v2_bridge_exchange_role[0].result
  principal_object_id = azurerm_user_assigned_identity.main[0].principal_id
  resource_object_id  = azuread_service_principal.azure_v2_bridge_audience[0].object_id
}

# The source keeps bounded, provider-native failure destinations. They are not
# additional transport layers: only records that exhaust bridge processing are
# written here for the PoC evidence trail.
resource "azurerm_eventhub" "azure_v2_bridge_telemetry_failure" {
  count             = local.azure_v2_remote_telemetry_outbound ? 1 : 0
  name              = "remote-telemetry-bridge-failure"
  namespace_id      = azurerm_eventhub_namespace.azure_azure_event_hubs_only_for_reviewed_remote_telemetry_edge[0].id
  partition_count   = local.azure_v2_event_hub_partitions
  message_retention = 1
}

resource "azurerm_servicebus_queue" "azure_v2_bridge_control_failure" {
  count                                   = local.azure_v2_remote_control_outbound ? 1 : 0
  name                                    = "remote-control-bridge-failure"
  namespace_id                            = azurerm_servicebus_namespace.azure_azure_service_bus_standard[0].id
  requires_session                        = true
  requires_duplicate_detection            = true
  duplicate_detection_history_time_window = "PT10M"
  dead_lettering_on_message_expiration    = true
  default_message_ttl                     = "P14D"
}

# -----------------------------------------------------------------------------
# AWS destination trust and exact inbound publishing rights
# -----------------------------------------------------------------------------

resource "aws_iam_openid_connect_provider" "azure_v2_bridge" {
  count          = local.azure_v2_bridge_to_aws_enabled ? 1 : 0
  url            = "https://sts.windows.net/${nonsensitive(var.azure_tenant_id)}/"
  client_id_list = [local.azure_v2_bridge_assertion_audience]
  tags           = local.aws_v2_tags

  depends_on = [azuread_app_role_assignment.azure_v2_bridge_source]
}

resource "aws_iam_role" "aws_v2_bridge_target_from_azure" {
  count = local.azure_v2_bridge_to_aws_enabled ? 1 : 0
  name  = "${local.aws_v2_name}-v2-from-azure-${local.deployment_suffix}"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = "sts:AssumeRoleWithWebIdentity"
      Principal = {
        Federated = aws_iam_openid_connect_provider.azure_v2_bridge[0].arn
      }
      Condition = {
        StringEquals = {
          "sts.windows.net/${nonsensitive(var.azure_tenant_id)}/:aud" = local.azure_v2_bridge_assertion_audience
          "sts.windows.net/${nonsensitive(var.azure_tenant_id)}/:sub" = azurerm_user_assigned_identity.main[0].principal_id
        }
      }
    }]
  })
  tags = local.aws_v2_tags
}

resource "aws_iam_role_policy" "aws_v2_bridge_target_from_azure" {
  count = local.azure_v2_bridge_to_aws_enabled ? 1 : 0
  name  = "exact-inbound-event-publish"
  role  = aws_iam_role.aws_v2_bridge_target_from_azure[0].id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = concat(
      length(local.azure_v2_bridge_aws_telemetry_targets) > 0 ? [{
        Effect   = "Allow"
        Action   = ["kinesis:PutRecord"]
        Resource = local.azure_v2_bridge_aws_telemetry_targets
      }] : [],
      length(local.azure_v2_bridge_aws_control_targets) > 0 ? [{
        Effect   = "Allow"
        Action   = ["sns:Publish"]
        Resource = local.azure_v2_bridge_aws_control_targets
      }] : [],
    )
  })
}

# -----------------------------------------------------------------------------
# GCP destination trust and exact inbound publishing rights
# -----------------------------------------------------------------------------

resource "google_service_account" "gcp_v2_bridge_target_from_azure" {
  count        = local.azure_v2_bridge_to_gcp_enabled ? 1 : 0
  project      = local.gcp_project_id
  account_id   = substr("${local.gcp_v2_name}-v2-from-azure", 0, 30)
  display_name = "${var.digital_twin_name} v2 bridge target from Azure"

  depends_on = [google_project_service.iam]
}

resource "google_iam_workload_identity_pool" "gcp_v2_bridge_from_azure" {
  count                     = local.azure_v2_bridge_to_gcp_enabled ? 1 : 0
  project                   = local.gcp_project_id
  workload_identity_pool_id = "${substr(local.gcp_v2_name, 0, 14)}-azure-bridge"
  display_name              = "Azure event bridge"
  description               = "Five-layer v2 source-owned Azure event bridge"

  depends_on = [google_project_service.gcp_v2_required]
}

resource "google_iam_workload_identity_pool_provider" "gcp_v2_bridge_from_azure" {
  count                              = local.azure_v2_bridge_to_gcp_enabled ? 1 : 0
  project                            = local.gcp_project_id
  workload_identity_pool_id          = google_iam_workload_identity_pool.gcp_v2_bridge_from_azure[0].workload_identity_pool_id
  workload_identity_pool_provider_id = "azure-event-bridge"
  display_name                       = "Azure event bridge"
  description                        = "Trust only the deployment Azure bridge identity"
  attribute_mapping = {
    "google.subject"      = "assertion.sub"
    "attribute.azure_oid" = "assertion.oid"
  }
  attribute_condition = "assertion.sub == '${azurerm_user_assigned_identity.main[0].principal_id}' && assertion.oid == '${azurerm_user_assigned_identity.main[0].principal_id}' && assertion.tid == '${nonsensitive(var.azure_tenant_id)}'"
  oidc {
    issuer_uri        = "https://sts.windows.net/${nonsensitive(var.azure_tenant_id)}/"
    allowed_audiences = [local.azure_v2_bridge_assertion_audience]
  }

  depends_on = [
    azuread_app_role_assignment.azure_v2_bridge_source,
    google_project_service.gcp_v2_required,
  ]
}

resource "google_service_account_iam_member" "gcp_v2_bridge_from_azure" {
  count              = local.azure_v2_bridge_to_gcp_enabled ? 1 : 0
  service_account_id = google_service_account.gcp_v2_bridge_target_from_azure[0].name
  role               = "roles/iam.workloadIdentityUser"
  member             = "principal://iam.googleapis.com/${google_iam_workload_identity_pool.gcp_v2_bridge_from_azure[0].name}/subject/${azurerm_user_assigned_identity.main[0].principal_id}"
}

resource "google_pubsub_topic_iam_member" "gcp_v2_bridge_from_azure" {
  for_each = local.azure_v2_bridge_gcp_topic_targets
  project  = local.gcp_project_id
  topic    = each.value
  role     = "roles/pubsub.publisher"
  member   = "serviceAccount:${google_service_account.gcp_v2_bridge_target_from_azure[0].email}"
}
