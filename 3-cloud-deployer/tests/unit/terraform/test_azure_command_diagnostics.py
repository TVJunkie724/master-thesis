"""Check input wiring whose provider-computed outputs are unknown in a plan."""
from pathlib import Path

import pytest


TF = Path(__file__).resolve().parents[3] / "src/terraform"


@pytest.mark.parametrize("filename,name", [
    ("azure_eventing.tf", "event_runtime"),
    ("azure_six_layer.tf", "azure_azure_functions_flex_consumption"),
    ("azure_six_layer.tf", "azure_six_layer_extension_action"),
])
def test_command_apps_share_only_the_bounded_diagnostic_settings(filename, name):
    source = (TF / filename).read_text()
    block = source.split('resource "azurerm_function_app_flex_consumption" "' + name + '" {', 1)[1]
    block = block.split('\nresource ', 1)[0].split('\ndata ', 1)[0]
    assert "app_settings = merge({" in block
    assert "}, local.azure_command_diagnostic_settings)" in block


def test_diagnostics_reuse_capped_workspace_for_commands_or_l5():
    source = (TF / "azure_six_layer.tf").read_text()
    block = source.split('resource "azurerm_application_insights" "azure_command_diagnostics" {', 1)[1].split('\n}', 1)[0]
    normalized = " ".join(block.split())
    assert "workspace_id = azurerm_log_analytics_workspace.azure_azure_log_analytics_shared_workspace[0].id" in normalized
    assert "count = local.azure_runtime_diagnostics_enabled ? 1 : 0" in normalized
    assert "local.azure_command_diagnostics_enabled || local.azure_six_layer_l5_enabled" in source
    assert "daily_data_cap_in_gb = 0.1" in normalized
    assert "local.core_evaluation && local.azure_event_l2_local && length(var.events) > 0" in source
    assert "APPLICATIONINSIGHTS_CONNECTION_STRING = azurerm_application_insights.azure_command_diagnostics[0].connection_string" in " ".join(source.split())


def test_l5_host_logs_reuse_existing_workspace_without_warm_workers():
    source = (TF / "azure_six_layer.tf").read_text()
    targets = source.split("azure_six_layer_diagnostic_targets = merge(", 1)[1].split("\n  )", 1)[0]
    assert "local.azure_six_layer_l5_enabled ? {" in targets
    assert "visualization = azurerm_function_app_flex_consumption.azure_six_layer_visualization[0].id" in targets
    diagnostic = source.split('resource "azurerm_monitor_diagnostic_setting" "azure_azure_monitor" {', 1)[1].split("\n}", 1)[0]
    assert "azurerm_log_analytics_workspace.azure_azure_log_analytics_shared_workspace[0].id" in diagnostic
    visualization = (TF / "six_layer_visualization.tf").read_text()
    assert 'always_ready {' not in visualization
    assert 'azurerm_log_analytics_workspace"' not in visualization
    visual_app = visualization.split('resource "azurerm_function_app_flex_consumption" "azure_six_layer_visualization" {', 1)[1].split('\nmodule ', 1)[0]
    assert "maximum_instance_count = 2" in " ".join(visual_app.split())
    assert "instance_memory_in_mb = 2048" in " ".join(visual_app.split())


def test_l3_l5_trace_wiring_preserves_provider_owned_app_insights_setting():
    source = (TF / "azure_six_layer.tf").read_text()
    reader = source.split('resource "azurerm_function_app_flex_consumption" "azure_azure_functions_flex_raw_history_reader" {', 1)[1].split('\ndata ', 1)[0]
    visual = (TF / "six_layer_visualization.tf").read_text().split('resource "azurerm_function_app_flex_consumption" "azure_six_layer_visualization" {', 1)[1].split('\nmodule ', 1)[0]
    for block in (reader, visual):
        assert "application_insights_connection_string" in block
        assert "}, local.azure_l5_diagnostic_settings)" in block
        assert "APPLICATIONINSIGHTS_CONNECTION_STRING" not in block
    assert "local.azure_six_layer_l5_enabled ? azurerm_application_insights" in reader
