"""Closed Terraform bindings for the GCP Five-layer v2 source bridge."""

from pathlib import Path


TERRAFORM_SOURCE = (
    Path(__file__).resolve().parents[3]
    / "src"
    / "terraform"
    / "five_layer_v2_bridge_gcp.tf"
)


def test_gcp_to_azure_uses_exact_route_aware_entity_scopes():
    source = TERRAFORM_SOURCE.read_text(encoding="utf-8")

    assert (
        'subject                   = google_service_account.gcp_v2_bridge[0].unique_id'
        in source
    )
    assert 'issuer                    = "https://accounts.google.com"' in source
    assert 'audience                  = ["api://AzureADTokenExchange"]' in source
    assert (
        'remote = azurerm_eventhub.azure_azure_event_hubs_only_for_reviewed_remote_telemetry_edge["inbound"].id'
        in source
    )
    assert (
        'event_received = local.azure_event_dedicated ? azurerm_eventhub.domain_telemetry_dedicated["received"].id : azurerm_eventhub.domain_telemetry_standard["received"].id'
        in source
    )
    assert (
        'event_processed = local.azure_event_dedicated ? azurerm_eventhub.domain_telemetry_dedicated["processed"].id : azurerm_eventhub.domain_telemetry_standard["processed"].id'
        in source
    )
    assert (
        'remote = azurerm_servicebus_topic.azure_v2_remote_control["inbound"].id'
        in source
    )
    assert 'event = azurerm_servicebus_topic.domain_control[0].id' in source
    assert "scope                = each.value" in source
    assert 'role_definition_name = "Azure Event Hubs Data Sender"' in source
    assert 'role_definition_name = "Azure Service Bus Data Sender"' in source


def test_gcp_to_aws_trusts_exact_route_aware_publish_targets():
    source = TERRAFORM_SOURCE.read_text(encoding="utf-8")

    assert 'Federated = "accounts.google.com"' in source
    assert (
        '"accounts.google.com:aud"  = google_service_account.gcp_v2_bridge[0].unique_id'
        in source
    )
    assert (
        '"accounts.google.com:oaud" = local.gcp_v2_bridge_aws_assertion_audience'
        in source
    )
    assert (
        '"accounts.google.com:sub"  = google_service_account.gcp_v2_bridge[0].unique_id'
        in source
    )
    assert 'Action   = ["kinesis:PutRecord"]' in source
    assert 'Action   = ["sns:Publish"]' in source
    assert (
        'remote = aws_kinesis_stream.aws_aws_kinesis_only_for_reviewed_remote_telemetry_edge["inbound"].arn'
        in source
    )
    assert (
        'event_received = aws_kinesis_stream.domain_telemetry["received"].arn'
        in source
    )
    assert (
        'event_processed = aws_kinesis_stream.domain_telemetry["processed"].arn'
        in source
    )
    assert (
        'remote = aws_sns_topic.aws_aws_sns_fifo_only_for_reviewed_remote_control_edge["inbound"].arn'
        in source
    )
    assert 'event = aws_sns_topic.domain_control[0].arn' in source
    assert "Resource = local.gcp_v2_bridge_aws_telemetry_targets" in source
    assert "Resource = local.gcp_v2_bridge_aws_control_targets" in source
    assert "google_service_account_key" not in source


def test_gcp_event_layer_can_be_the_source_of_a_directed_bridge():
    source = TERRAFORM_SOURCE.read_text(encoding="utf-8")

    assert 'google_pubsub_topic.domain_events["received"].id' in source
    assert 'google_pubsub_topic.domain_events["processed"].id' in source
    assert 'google_pubsub_topic.domain_events["control"].id' in source
    assert '"event-control-${index}"' in source
    assert 'filter = "attributes.event_type = \\"${event_type}\\""' in source
