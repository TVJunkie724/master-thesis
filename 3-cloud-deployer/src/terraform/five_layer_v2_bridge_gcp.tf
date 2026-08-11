# Source-owned GCP cross-cloud bridge for five-layer-baseline@2.
#
# The bridge is an additional topology-conditional instance of the reviewed
# embedded Cloud Run event-adapter family. Authenticated Pub/Sub push invokes
# it only for directional GCP outbox topics. Destination credentials are
# short-lived and derived from the bridge service account; no key is created.

locals {
  gcp_v2_bridge_enabled = length(local.gcp_v2_outbound_event_routes) > 0
  gcp_v2_bridge_destinations_selected = toset([
    for route in values(local.gcp_v2_outbound_event_routes) : route.destination_provider
  ])
  gcp_v2_bridge_to_aws_enabled   = contains(local.gcp_v2_bridge_destinations_selected, "aws")
  gcp_v2_bridge_to_azure_enabled = contains(local.gcp_v2_bridge_destinations_selected, "azure")

  gcp_v2_bridge_to_aws_telemetry = anytrue([
    for route in values(local.gcp_v2_outbound_event_routes) :
    route.destination_provider == "aws" && route.channel_class == "telemetry"
  ])
  gcp_v2_bridge_to_aws_control = anytrue([
    for route in values(local.gcp_v2_outbound_event_routes) :
    route.destination_provider == "aws" && route.channel_class == "control"
  ])
  gcp_v2_bridge_to_azure_telemetry = anytrue([
    for route in values(local.gcp_v2_outbound_event_routes) :
    route.destination_provider == "azure" && route.channel_class == "telemetry"
  ])
  gcp_v2_bridge_to_azure_control = anytrue([
    for route in values(local.gcp_v2_outbound_event_routes) :
    route.destination_provider == "azure" && route.channel_class == "control"
  ])

  gcp_v2_bridge_aws_assertion_audience = local.gcp_v2_bridge_to_aws_enabled ? "api://${random_uuid.gcp_v2_bridge_aws_audience[0].result}" : ""
  gcp_v2_event_bridge_control_types = sort(distinct(flatten([
    for route in values(local.gcp_v2_outbound_event_routes) : route.event_types
    if startswith(route.logical_edge_id, "edge.eventing-to-") && route.channel_class == "control"
  ])))

  gcp_v2_bridge_destinations = merge(
    local.gcp_v2_bridge_to_aws_enabled ? {
      aws = {
        telemetry_stream_arn = local.gcp_v2_bridge_to_aws_telemetry ? aws_kinesis_stream.aws_aws_kinesis_only_for_reviewed_remote_telemetry_edge["inbound"].arn : ""
        control_topic_arn    = local.gcp_v2_bridge_to_aws_control ? aws_sns_topic.aws_aws_sns_fifo_only_for_reviewed_remote_control_edge["inbound"].arn : ""
      }
    } : {},
    local.gcp_v2_bridge_to_azure_enabled ? {
      azure = {
        telemetry_namespace = local.gcp_v2_bridge_to_azure_telemetry ? "${azurerm_eventhub_namespace.azure_azure_event_hubs_only_for_reviewed_remote_telemetry_edge[0].name}.servicebus.windows.net" : ""
        telemetry_entity    = local.gcp_v2_bridge_to_azure_telemetry ? azurerm_eventhub.azure_azure_event_hubs_only_for_reviewed_remote_telemetry_edge["inbound"].name : ""
        control_namespace   = local.gcp_v2_bridge_to_azure_control ? "${azurerm_servicebus_namespace.azure_azure_service_bus_standard[0].name}.servicebus.windows.net" : ""
        control_entity      = local.gcp_v2_bridge_to_azure_control ? azurerm_servicebus_topic.azure_v2_remote_control["inbound"].name : ""
      }
    } : {},
  )

  gcp_v2_bridge_identities = merge(
    local.gcp_v2_bridge_to_aws_enabled ? {
      aws = {
        role_arn           = aws_iam_role.aws_v2_bridge_target_from_gcp[0].arn
        assertion_audience = local.gcp_v2_bridge_aws_assertion_audience
      }
    } : {},
    local.gcp_v2_bridge_to_azure_enabled ? {
      azure = {
        tenant_id = nonsensitive(var.azure_tenant_id)
        client_id = azurerm_user_assigned_identity.azure_v2_bridge_target_from_gcp[0].client_id
      }
    } : {},
  )

  gcp_v2_bridge_sources = merge(
    anytrue([
      for route in values(local.gcp_v2_outbound_event_routes) :
      route.channel_class == "telemetry" && !startswith(route.logical_edge_id, "edge.eventing-to-")
      ]) ? {
      telemetry = {
        topic_id = google_pubsub_topic.gcp_gcp_pubsub_separated_embedded_topics["remote-telemetry-outbound"].id
        filter   = ""
      }
    } : {},
    anytrue([
      for route in values(local.gcp_v2_outbound_event_routes) :
      route.channel_class == "control" && !startswith(route.logical_edge_id, "edge.eventing-to-")
      ]) ? {
      control = {
        topic_id = google_pubsub_topic.gcp_gcp_pubsub_separated_embedded_topics["remote-control-outbound"].id
        filter   = ""
      }
    } : {},
    local.gcp_v2_event_layer_local && anytrue([
      for route in values(local.gcp_v2_outbound_event_routes) :
      startswith(route.logical_edge_id, "edge.eventing-to-") && contains(route.event_types, "telemetry.received.v1")
      ]) ? {
      event-received = {
        topic_id = google_pubsub_topic.domain_events["received"].id
        filter   = ""
      }
    } : {},
    local.gcp_v2_event_layer_local && anytrue([
      for route in values(local.gcp_v2_outbound_event_routes) :
      startswith(route.logical_edge_id, "edge.eventing-to-") && contains(route.event_types, "telemetry.processed.v1")
      ]) ? {
      event-processed = {
        topic_id = google_pubsub_topic.domain_events["processed"].id
        filter   = ""
      }
    } : {},
    local.gcp_v2_event_layer_local && anytrue([
      for route in values(local.gcp_v2_outbound_event_routes) :
      startswith(route.logical_edge_id, "edge.eventing-to-") && route.channel_class == "control"
      ]) ? {
      for index, event_type in local.gcp_v2_event_bridge_control_types :
      "event-control-${index}" => {
        topic_id = google_pubsub_topic.domain_events["control"].id
        # One bounded filter per event type stays below Pub/Sub's 256-byte
        # subscription-filter limit for every reviewed topology.
        filter = "attributes.event_type = \"${event_type}\""
      }
    } : {},
  )
  gcp_v2_bridge_failure_topic_id = local.gcp_v2_event_layer_local ? try(
    google_pubsub_topic.domain_events["failure"].id,
    "",
    ) : try(
    google_pubsub_topic.gcp_gcp_pubsub_separated_embedded_topics["failure"].id,
    "",
  )
  gcp_v2_bridge_failure_topic_name = local.gcp_v2_event_layer_local ? try(
    google_pubsub_topic.domain_events["failure"].name,
    "",
    ) : try(
    google_pubsub_topic.gcp_gcp_pubsub_separated_embedded_topics["failure"].name,
    "",
  )
}

# ----------------------------------------------------------------------------
# GCP source runtime, trigger, and bounded failure path
# ----------------------------------------------------------------------------

resource "google_service_account" "gcp_v2_bridge" {
  count        = local.gcp_v2_bridge_enabled ? 1 : 0
  project      = local.gcp_project_id
  account_id   = substr("${local.gcp_v2_name}-v2-bridge", 0, 30)
  display_name = "${var.digital_twin_name} v2 cross-cloud bridge"

  depends_on = [google_project_service.iam]
}

resource "google_cloud_run_v2_service" "gcp_v2_cross_cloud_bridge" {
  count               = local.gcp_v2_bridge_enabled ? 1 : 0
  project             = local.gcp_project_id
  location            = var.gcp_region
  name                = "${local.gcp_v2_name}-v2-event-bridge"
  description         = "Authenticated source-owned Five-layer v2 event bridge"
  deletion_protection = false
  ingress             = "INGRESS_TRAFFIC_ALL"
  labels              = local.gcp_v2_labels

  template {
    service_account                  = google_service_account.gcp_v2_bridge[0].email
    timeout                          = "60s"
    max_instance_request_concurrency = 8

    scaling {
      min_instance_count = 0
      max_instance_count = 100
    }

    containers {
      image = var.gcp_v2_platform_image

      resources {
        limits = {
          cpu    = "1"
          memory = "512Mi"
        }
        cpu_idle = true
      }

      env {
        name  = "RUNTIME_ROLE"
        value = "cross-cloud-bridge"
      }
      env {
        name  = "ARCHITECTURE_PROFILE"
        value = local.six_layer_eventing_enabled ? "six-layer-eventing@1" : "five-layer-baseline@2"
      }
      env {
        name  = "DEPLOYMENT_ID"
        value = local.deployment_suffix
      }
      env {
        name  = "BRIDGE_ROUTES_JSON"
        value = jsonencode(values(local.gcp_v2_outbound_event_routes))
      }
      env {
        name  = "BRIDGE_DESTINATIONS_JSON"
        value = jsonencode(local.gcp_v2_bridge_destinations)
      }
      env {
        name  = "BRIDGE_IDENTITIES_JSON"
        value = jsonencode(local.gcp_v2_bridge_identities)
      }
      env {
        name  = "BRIDGE_FAILURE_TOPIC"
        value = local.gcp_v2_bridge_failure_topic_id
      }
      env {
        name  = "AWS_STS_REGIONAL_ENDPOINTS"
        value = "regional"
      }
    }
  }

  depends_on = [
    google_project_service.run,
    google_pubsub_topic_iam_member.gcp_v2_bridge_failure_publisher,
    aws_iam_role_policy.aws_v2_bridge_target_from_gcp,
    azurerm_federated_identity_credential.azure_v2_bridge_from_gcp,
    azurerm_role_assignment.azure_v2_bridge_from_gcp_telemetry,
    azurerm_role_assignment.azure_v2_bridge_from_gcp_control,
  ]
}

resource "google_cloud_run_v2_service_iam_member" "gcp_v2_bridge_push_invoker" {
  count    = local.gcp_v2_bridge_enabled ? 1 : 0
  project  = local.gcp_project_id
  location = var.gcp_region
  name     = google_cloud_run_v2_service.gcp_v2_cross_cloud_bridge[0].name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.gcp_v2_bridge[0].email}"
}

resource "google_service_account_iam_member" "gcp_v2_bridge_push_token_creator" {
  count              = local.gcp_v2_bridge_enabled ? 1 : 0
  service_account_id = google_service_account.gcp_v2_bridge[0].name
  role               = "roles/iam.serviceAccountTokenCreator"
  member             = "serviceAccount:service-${data.google_project.gcp_v2_current[0].number}@gcp-sa-pubsub.iam.gserviceaccount.com"
}

resource "google_pubsub_topic_iam_member" "gcp_v2_bridge_failure_publisher" {
  count   = local.gcp_v2_bridge_enabled ? 1 : 0
  project = local.gcp_project_id
  topic   = local.gcp_v2_bridge_failure_topic_name
  role    = "roles/pubsub.publisher"
  member  = "serviceAccount:${google_service_account.gcp_v2_bridge[0].email}"
}

resource "google_pubsub_subscription" "gcp_v2_bridge_source" {
  for_each = local.gcp_v2_bridge_sources
  project  = local.gcp_project_id
  name     = "${local.gcp_v2_name}-v2-bridge-${each.key}"
  topic    = each.value.topic_id

  ack_deadline_seconds       = 60
  message_retention_duration = "1209600s"
  enable_message_ordering    = true
  retain_acked_messages      = false
  filter                     = each.value.filter
  labels                     = local.gcp_v2_labels

  push_config {
    push_endpoint = google_cloud_run_v2_service.gcp_v2_cross_cloud_bridge[0].uri
    oidc_token {
      service_account_email = google_service_account.gcp_v2_bridge[0].email
      audience              = google_cloud_run_v2_service.gcp_v2_cross_cloud_bridge[0].uri
    }
  }

  retry_policy {
    minimum_backoff = "1s"
    maximum_backoff = "32s"
  }

  dead_letter_policy {
    dead_letter_topic     = local.gcp_v2_bridge_failure_topic_id
    max_delivery_attempts = 6
  }

  depends_on = [
    google_cloud_run_v2_service_iam_member.gcp_v2_bridge_push_invoker,
    google_service_account_iam_member.gcp_v2_bridge_push_token_creator,
    google_pubsub_topic_iam_member.gcp_v2_failure_service_agent_publisher,
    google_pubsub_topic_iam_member.event_failure_service_agent_publisher,
  ]
}

resource "google_pubsub_subscription_iam_member" "gcp_v2_bridge_failure_service_agent_subscriber" {
  for_each     = local.gcp_v2_bridge_sources
  project      = local.gcp_project_id
  subscription = google_pubsub_subscription.gcp_v2_bridge_source[each.key].name
  role         = "roles/pubsub.subscriber"
  member       = "serviceAccount:service-${data.google_project.gcp_v2_current[0].number}@gcp-sa-pubsub.iam.gserviceaccount.com"
}

# ----------------------------------------------------------------------------
# AWS destination trust and exact inbound publishing rights
# ----------------------------------------------------------------------------

resource "random_uuid" "gcp_v2_bridge_aws_audience" {
  count = local.gcp_v2_bridge_to_aws_enabled ? 1 : 0
}

resource "aws_iam_role" "aws_v2_bridge_target_from_gcp" {
  count = local.gcp_v2_bridge_to_aws_enabled ? 1 : 0
  name  = "${local.aws_v2_name}-v2-from-gcp-${local.deployment_suffix}"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = "sts:AssumeRoleWithWebIdentity"
      Principal = {
        Federated = "accounts.google.com"
      }
      Condition = {
        StringEquals = {
          # Google service-account ID tokens set azp to the numeric account ID.
          # AWS maps azp to :aud and the requested aud claim to :oaud.
          "accounts.google.com:aud"  = google_service_account.gcp_v2_bridge[0].unique_id
          "accounts.google.com:oaud" = local.gcp_v2_bridge_aws_assertion_audience
          "accounts.google.com:sub"  = google_service_account.gcp_v2_bridge[0].unique_id
        }
      }
    }]
  })
  tags = local.aws_v2_tags
}

resource "aws_iam_role_policy" "aws_v2_bridge_target_from_gcp" {
  count = local.gcp_v2_bridge_to_aws_enabled ? 1 : 0
  name  = "exact-inbound-event-publish"
  role  = aws_iam_role.aws_v2_bridge_target_from_gcp[0].id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = concat(
      local.gcp_v2_bridge_to_aws_telemetry ? [{
        Effect   = "Allow"
        Action   = ["kinesis:PutRecord"]
        Resource = aws_kinesis_stream.aws_aws_kinesis_only_for_reviewed_remote_telemetry_edge["inbound"].arn
      }] : [],
      local.gcp_v2_bridge_to_aws_control ? [{
        Effect   = "Allow"
        Action   = ["sns:Publish"]
        Resource = aws_sns_topic.aws_aws_sns_fifo_only_for_reviewed_remote_control_edge["inbound"].arn
      }] : [],
    )
  })
}

# ----------------------------------------------------------------------------
# Azure destination trust and exact inbound publishing rights
# ----------------------------------------------------------------------------

resource "azurerm_user_assigned_identity" "azure_v2_bridge_target_from_gcp" {
  count               = local.gcp_v2_bridge_to_azure_enabled ? 1 : 0
  name                = "${local.azure_v2_name}-v2-from-gcp-${local.deployment_suffix}"
  resource_group_name = azurerm_resource_group.main[0].name
  location            = azurerm_resource_group.main[0].location
  tags                = local.azure_v2_tags
}

resource "azurerm_federated_identity_credential" "azure_v2_bridge_from_gcp" {
  count                     = local.gcp_v2_bridge_to_azure_enabled ? 1 : 0
  name                      = "gcp-event-bridge"
  user_assigned_identity_id = azurerm_user_assigned_identity.azure_v2_bridge_target_from_gcp[0].id
  issuer                    = "https://accounts.google.com"
  subject                   = google_service_account.gcp_v2_bridge[0].unique_id
  audience                  = ["api://AzureADTokenExchange"]
}

resource "azurerm_role_assignment" "azure_v2_bridge_from_gcp_telemetry" {
  count                = local.gcp_v2_bridge_to_azure_telemetry ? 1 : 0
  scope                = azurerm_eventhub.azure_azure_event_hubs_only_for_reviewed_remote_telemetry_edge["inbound"].id
  role_definition_name = "Azure Event Hubs Data Sender"
  principal_id         = azurerm_user_assigned_identity.azure_v2_bridge_target_from_gcp[0].principal_id
  principal_type       = "ServicePrincipal"
}

resource "azurerm_role_assignment" "azure_v2_bridge_from_gcp_control" {
  count                = local.gcp_v2_bridge_to_azure_control ? 1 : 0
  scope                = azurerm_servicebus_topic.azure_v2_remote_control["inbound"].id
  role_definition_name = "Azure Service Bus Data Sender"
  principal_id         = azurerm_user_assigned_identity.azure_v2_bridge_target_from_gcp[0].principal_id
  principal_type       = "ServicePrincipal"
}
