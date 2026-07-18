"""Source-level drift gates for Azure deployment specification bindings."""

from pathlib import Path


TERRAFORM_ROOT = Path(__file__).resolve().parents[3] / "src" / "terraform"


def _source(filename: str) -> str:
    return (TERRAFORM_ROOT / filename).read_text(encoding="utf-8")


def _normalized_source(filename: str) -> str:
    return " ".join(_source(filename).split())


def test_azure_resource_selections_are_specification_owned():
    iot = _normalized_source("azure_iot.tf")
    assert "name = var.azure_iot_hub_sku" in iot
    assert "capacity = var.azure_iot_hub_capacity" in iot
    assert "sku_name = var.azure_l1_function_plan_sku" in iot
    assert 'name = "S1"' not in iot
    assert "capacity = 1" not in iot

    compute = _normalized_source("azure_compute.tf")
    assert "sku_name = var.azure_l2_function_plan_sku" in compute

    storage = _normalized_source("azure_storage.tf")
    assert (
        'dynamic "capabilities" { for_each = '
        'var.azure_cosmos_capacity_mode == "serverless" ? [1] : []'
    ) in storage
    assert 'name = "EnableServerless"' in storage
    assert '"unsupported"' not in storage
    assert "sku_name = var.azure_l3_function_plan_sku" in storage

    grafana = _normalized_source("azure_grafana.tf")
    assert "sku = var.azure_grafana_sku" in grafana
    assert 'sku = "Standard"' not in grafana


def test_azure_blob_and_timer_runtime_settings_use_specification_targets():
    storage = _normalized_source("azure_storage.tf")
    expected = (
        "HOT_TO_COOL_TIMER_SCHEDULE",
        "COOL_TO_ARCHIVE_TIMER_SCHEDULE",
        "COLD_BLOB_TIER",
        "ARCHIVE_BLOB_TIER",
    )
    for setting in expected:
        assert setting in storage

    glue = _normalized_source("azure_glue.tf")
    assert (
        'COLD_BLOB_TIER = var.layer_3_cold_provider == "azure" ? '
        'var.azure_l3_cool_blob_tier : ""'
    ) in glue
    assert (
        'ARCHIVE_BLOB_TIER = var.layer_3_archive_provider == "azure" ? '
        'var.azure_l3_archive_blob_tier : ""'
    ) in glue


def test_azure_l0_is_derived_from_registered_receiver_topology():
    setup = _normalized_source("azure_setup.tf")
    for condition in (
        'var.layer_1_provider != var.layer_2_provider && var.layer_2_provider == "azure"',
        'var.layer_2_provider != var.layer_3_hot_provider && var.layer_3_hot_provider == "azure"',
        'var.layer_3_hot_provider != var.layer_3_cold_provider && var.layer_3_cold_provider == "azure"',
        'var.layer_3_cold_provider != var.layer_3_archive_provider && var.layer_3_archive_provider == "azure"',
        'var.layer_4_provider != var.layer_3_hot_provider && var.layer_3_hot_provider == "azure"',
    ):
        assert condition in setup
    assert (
        'azure_l0_enabled = local.azure_cross_cloud_receiver_required || '
        'var.layer_4_provider == "azure"'
    ) in setup

    glue = _normalized_source("azure_glue.tf")
    assert glue.count("count = local.azure_l0_enabled ? 1 : 0") == 2
    assert "sku_name = local.azure_l0_function_plan_sku" in glue
    assert "count = local.deploy_azure ? 1 : 0" not in glue


def test_azure_storage_distinguishes_costed_blob_from_function_host_support():
    setup = _normalized_source("azure_setup.tf")
    assert (
        'azure_blob_storage_enabled = ( var.layer_3_cold_provider == "azure" '
        '|| var.layer_3_archive_provider == "azure" )'
    ) in setup
    assert (
        'local.azure_blob_storage_enabled ? '
        'coalesce(var.azure_storage_account_tier, "Standard") : "Standard"'
    ) in setup
    assert (
        'local.azure_blob_storage_enabled ? '
        'coalesce(var.azure_storage_replication_type, "LRS") : "LRS"'
    ) in setup
    assert "account_tier = local.azure_effective_storage_account_tier" in setup
    assert (
        "account_replication_type = "
        "local.azure_effective_storage_replication_type"
    ) in setup


def test_azure_variables_fail_closed_to_contract_values():
    source = _normalized_source("variables.tf")
    expected = {
        "azure_iot_hub_sku": 'contains(["F1", "S1", "S2", "S3"]',
        "azure_iot_hub_capacity": "var.azure_iot_hub_capacity <= 200",
        "azure_l1_function_plan_sku": '"Y1"',
        "azure_l2_function_plan_sku": '"Y1"',
        "azure_cosmos_capacity_mode": '"serverless"',
        "azure_l3_function_plan_sku": '"Y1"',
        "azure_storage_account_tier": '"Standard"',
        "azure_storage_replication_type": '"LRS"',
        "azure_l3_cool_blob_tier": '"Cool"',
        "azure_hot_to_cool_timer_schedule": '"0 0 0 * * *"',
        "azure_l3_archive_blob_tier": '"Archive"',
        "azure_cool_to_archive_timer_schedule": '"0 0 0 * * 0"',
        "azure_l4_function_plan_sku": '"Y1"',
        "azure_grafana_sku": '"Standard"',
        "azure_glue_function_plan_sku": '"Y1"',
    }
    for variable, validation_fragment in expected.items():
        marker = f'variable "{variable}" {{'
        block = source[source.index(marker):]
        block = block[:block.index("} }") + 3]
        assert "default = null" in block
        assert f"var.{variable} == null" in block
        assert validation_fragment in block


def test_azure_usage_meters_remain_non_deployable_evidence():
    variables = _source("variables.tf").lower()
    assert "azure_event_grid" not in variables
    assert "azure_logic_apps" not in variables
    assert "azure_digital_twins" not in variables
