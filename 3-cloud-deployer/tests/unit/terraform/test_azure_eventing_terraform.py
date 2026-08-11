"""Source-level gates for the reviewed Azure Event Layer bundle."""

from pathlib import Path


TERRAFORM_ROOT = Path(__file__).resolve().parents[3] / "src" / "terraform"


def _source(filename: str) -> str:
    return (TERRAFORM_ROOT / filename).read_text(encoding="utf-8")


def test_azure_event_layer_owns_exact_reviewed_resource_symbols():
    source = _source("azure_eventing.tf")
    required = {
        'resource "azapi_resource" "event_hubs_dedicated_cluster"',
        'resource "azurerm_eventhub" "domain_telemetry_dedicated"',
        'resource "azurerm_eventhub" "domain_telemetry_standard"',
        'resource "azurerm_eventhub_consumer_group" "domain_dedicated"',
        'resource "azurerm_eventhub_consumer_group" "domain_standard"',
        'resource "azurerm_eventhub_namespace" "eventing_dedicated"',
        'resource "azurerm_eventhub_namespace" "eventing_standard"',
        'resource "azurerm_function_app_flex_consumption" "event_runtime"',
        'resource "azurerm_log_analytics_workspace" "eventing"',
        'resource "azurerm_monitor_diagnostic_setting" "eventing"',
        'resource "azurerm_servicebus_namespace" "eventing"',
        'resource "azurerm_servicebus_subscription" "domain_control"',
        'resource "azurerm_servicebus_topic" "domain_control"',
        'resource "azurerm_user_assigned_identity" "event_runtime"',
    }
    assert all(symbol in source for symbol in required)
    assert 'resource "azurerm_eventgrid' not in source


def test_azure_event_layer_is_profile_and_provider_gated():
    source = _source("azure_eventing.tf")
    assert "local.six_layer_eventing_enabled" in source
    assert 'var.event_layer_provider == "azure"' in source
    assert "azure_event_l1_local" in source
    assert "azure_event_l2_local" in source


def test_azure_event_layer_uses_reviewed_tiers_and_failure_paths():
    source = _source("azure_eventing.tf")
    assert 'received  = "domain-telemetry-received"' in source
    assert 'processed = "domain-telemetry-processed"' in source
    assert 'failure   = "domain-telemetry-failure"' in source
    assert "azure_event_dedicated_capacity_units == 6" in source
    assert "contains([1, 11], local.azure_event_throughput_units)" in source
    assert '"historical-persistence"' in source
    assert '"twin-state-update"' in source
    assert '"rule-evaluator"' in source
    assert 'name            = "$Default"' in source
    assert "max_delivery_count" in source
    assert "EVENT_FAILURE_HUB_NAME" in source
    assert "EVENT_DOMAIN_DELIVERY_KEY" in source
    assert "azurerm_function_app_host_keys.azure_event_domain_target" in source


def test_inherited_azure_runtime_replaces_embedded_transport_for_six_layer():
    terraform = _source("azure_five_layer_v2.tf")
    runtime = (
        TERRAFORM_ROOT.parent
        / "providers"
        / "azure"
        / "azure_functions"
        / "five-layer-v2"
        / "function_app.py"
    ).read_text(encoding="utf-8")
    assert "azure_v2_embedded_event_enabled" in terraform
    assert "V2_EVENTING_RECEIVED_HUB_NAME" in terraform
    assert "V2_EVENTING_PROCESSED_HUB_NAME" in terraform
    assert "V2_EVENTING_CONTROL_TOPIC_NAME" in terraform
    assert "V2_EVENTING_DELIVERY_ENDPOINT_ENABLED" in terraform
    assert "def _publish_eventing_stream" in runtime
    assert "def _publish_eventing_control" in runtime
    assert "def _consume_eventing_delivery" in runtime
    assert 'route="eventing-delivery/v1"' in runtime


def test_azure_event_layer_can_be_the_source_of_a_directed_bridge():
    terraform = _source("azure_eventing.tf")
    function_app = (
        TERRAFORM_ROOT.parent
        / "providers"
        / "azure"
        / "azure_functions"
        / "five-layer-v2"
        / "function_app.py"
    ).read_text(encoding="utf-8")
    assert "bridge-received" in terraform
    assert "bridge-processed" in terraform
    assert 'resource "azurerm_servicebus_subscription" "event_bridge_control"' in terraform
    assert 'resource "azurerm_role_assignment" "azure_event_bridge"' in terraform
    assert 'name="v2-cross-cloud-event-received-bridge"' in function_app
    assert 'name="v2-cross-cloud-event-processed-bridge"' in function_app
    assert 'name="v2-cross-cloud-event-control-bridge"' in function_app
