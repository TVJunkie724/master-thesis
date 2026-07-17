"""Source contracts for the canonical Azure L4 update topology."""

from pathlib import Path


TERRAFORM_ROOT = Path(__file__).resolve().parents[3] / "src/terraform"


def _normalized_source(filename: str) -> str:
    source = (TERRAFORM_ROOT / filename).read_text(encoding="utf-8")
    return " ".join(source.split())


def test_azure_l2_receives_pusher_settings_exactly_when_l4_is_azure():
    source = _normalized_source("azure_compute.tf")
    assert (
        'REMOTE_ADT_PUSHER_URL = var.layer_4_provider == "azure" ? '
        '( "${local.azure_l0_glue_url}/${local.api_paths.adt_pusher}" ) : ""'
    ) in source
    assert (
        'ADT_PUSHER_TOKEN = var.layer_4_provider == "azure" ? '
        '( local.inter_cloud_token_value ) : ""'
    ) in source


def test_aws_l2_receives_pusher_settings_for_aws_to_azure_l4():
    source = _normalized_source("aws_compute.tf")
    assert (
        'REMOTE_ADT_PUSHER_URL = var.layer_2_provider == "aws" && '
        'var.layer_4_provider == "azure" ?'
    ) in source
    assert (
        '"https://${try(azurerm_linux_function_app.l0_glue[0].default_hostname, '
        '"")}/${local.api_paths.adt_pusher}"'
    ) in source
    assert (
        'ADT_PUSHER_TOKEN = var.layer_4_provider == "azure" ? '
        '( local.inter_cloud_token_value ) : ""'
    ) in source


def test_gcp_l2_receives_pusher_settings_for_gcp_to_azure_l4():
    source = _normalized_source("gcp_compute.tf")
    assert (
        'REMOTE_ADT_PUSHER_URL = var.layer_2_provider == "google" && '
        'var.layer_4_provider == "azure" ?'
    ) in source
    assert (
        '"https://${try(azurerm_linux_function_app.l0_glue[0].default_hostname, '
        '"")}/${local.api_paths.adt_pusher}"'
    ) in source
    assert (
        'ADT_PUSHER_TOKEN = var.layer_4_provider == "azure" ? '
        '( local.inter_cloud_token_value ) : ""'
    ) in source


def test_azure_l0_pusher_receives_adt_endpoint_and_managed_identity():
    source = _normalized_source("azure_glue.tf")
    assert (
        'ADT_INSTANCE_URL = var.layer_4_provider == "azure" ? '
        'local.azure_adt_url : ""'
    ) in source
    assert (
        "identity { type = \"UserAssigned\" identity_ids = "
        "[azurerm_user_assigned_identity.main[0].id] }"
    ) in source
    assert (
        "AZURE_CLIENT_ID = azurerm_user_assigned_identity.main[0].client_id"
    ) in source


def test_active_terraform_contains_no_dead_adt_updater_or_event_subscription():
    source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted(TERRAFORM_ROOT.glob("*.tf"))
    ).lower()
    assert "adt-updater" not in source
    assert 'resource "azurerm_linux_function_app" "l4' not in source
    assert 'resource "azurerm_eventgrid_topic" "adt_events"' not in source

