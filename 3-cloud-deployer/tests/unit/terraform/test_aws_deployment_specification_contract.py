"""Source-level drift gates for AWS deployment specification bindings."""

from pathlib import Path


TERRAFORM_ROOT = Path(__file__).resolve().parents[3] / "src" / "terraform"


def _source(filename: str) -> str:
    return (TERRAFORM_ROOT / filename).read_text(encoding="utf-8")


def _normalized_source(filename: str) -> str:
    return " ".join(_source(filename).split())


def test_every_aws_lambda_memory_profile_is_specification_owned():
    bindings = {
        "aws_iot.tf": ("var.aws_l1_lambda_memory_mb", 2),
        "aws_compute.tf": ("var.aws_l2_lambda_memory_mb", 7),
        "aws_storage.tf": ("var.aws_l3_reader_lambda_memory_mb", 1),
        "aws_twins.tf": ("var.aws_l4_lambda_memory_mb", 1),
        "aws_glue.tf": ("var.aws_glue_lambda_memory_mb", 5),
    }
    for filename, (variable, expected_count) in bindings.items():
        assert _source(filename).count(f"memory_size   = {variable}") == expected_count

    storage = _source("aws_storage.tf")
    assert storage.count(
        "memory_size   = var.aws_hot_to_cool_mover_memory_mb"
    ) == 1
    assert storage.count(
        "memory_size   = var.aws_cool_to_archive_mover_memory_mb"
    ) == 1

    all_aws_source = "\n".join(
        _source(path.name)
        for path in sorted(TERRAFORM_ROOT.glob("aws_*.tf"))
    )
    assert "memory_size   = 256" not in all_aws_source
    assert "memory_size   = 512" not in all_aws_source


def test_aws_storage_and_schedule_resources_use_specification_targets():
    source = _normalized_source("aws_storage.tf")
    assert "billing_mode = var.aws_dynamodb_billing_mode" in source
    assert (
        "COLD_STORAGE_CLASS = local.l3_cold_aws_enabled ? "
        'var.aws_l3_cool_storage_class : ""'
    ) in source
    assert (
        "ARCHIVE_STORAGE_CLASS = local.l3_archive_aws_enabled ? "
        'var.aws_l3_archive_storage_class : ""'
    ) in source
    assert (
        "schedule_expression = var.aws_hot_to_cool_schedule_expression"
    ) in source
    assert (
        "schedule_expression = var.aws_cool_to_archive_schedule_expression"
    ) in source
    assert 'storage_class = "GLACIER"' not in source
    assert 'storage_class = "STANDARD_IA"' not in source


def test_aws_cross_cloud_writers_receive_destination_storage_classes():
    source = _normalized_source("aws_glue.tf")
    assert "COLD_STORAGE_CLASS = var.aws_l3_cool_storage_class" in source
    assert "ARCHIVE_STORAGE_CLASS = var.aws_l3_archive_storage_class" in source


def test_transition_resources_are_owned_by_the_source_storage_provider():
    source = _normalized_source("aws_storage.tf")
    for resource_type, name in (
        ("aws_lambda_function", "l3_hot_to_cold_mover"),
        ("aws_cloudwatch_event_rule", "l3_hot_to_cold"),
        ("aws_cloudwatch_event_target", "l3_hot_to_cold"),
        ("aws_lambda_permission", "l3_hot_to_cold"),
    ):
        marker = f'resource "{resource_type}" "{name}" {{'
        block = source[source.index(marker):]
        assert "count" in block.split("}", 1)[0]
        assert "local.l3_hot_aws_enabled ? 1 : 0" in block.split("}", 1)[0]

    for resource_type, name in (
        ("aws_lambda_function", "l3_cold_to_archive_mover"),
        ("aws_cloudwatch_event_rule", "l3_cold_to_archive"),
        ("aws_cloudwatch_event_target", "l3_cold_to_archive"),
        ("aws_lambda_permission", "l3_cold_to_archive"),
    ):
        marker = f'resource "{resource_type}" "{name}" {{'
        block = source[source.index(marker):]
        assert "count" in block.split("}", 1)[0]
        assert "local.l3_cold_aws_enabled ? 1 : 0" in block.split("}", 1)[0]


def test_aws_variables_fail_closed_to_contract_values():
    source = _normalized_source("variables.tf")
    expected_validations = {
        "aws_l1_lambda_memory_mb": "256",
        "aws_l2_lambda_memory_mb": "256",
        "aws_dynamodb_billing_mode": '"PAY_PER_REQUEST"',
        "aws_l3_reader_lambda_memory_mb": "256",
        "aws_l3_cool_storage_class": '"STANDARD_IA"',
        "aws_hot_to_cool_mover_memory_mb": "512",
        "aws_hot_to_cool_schedule_expression": '"rate(1 day)"',
        "aws_l3_archive_storage_class": '"DEEP_ARCHIVE"',
        "aws_cool_to_archive_mover_memory_mb": "512",
        "aws_cool_to_archive_schedule_expression": '"rate(7 days)"',
        "aws_l4_lambda_memory_mb": "256",
        "aws_glue_lambda_memory_mb": "256",
    }
    for variable, allowed_value in expected_validations.items():
        marker = f'variable "{variable}" {{'
        block = source[source.index(marker):]
        block = block[:block.index("} }") + 3]
        assert "default = null" in block
        assert f"var.{variable} == null" in block
        assert f"var.{variable} == {allowed_value}" in block


def test_account_scoped_and_invariant_aws_values_are_not_tfvars():
    variables = _source("variables.tf")
    assert "aws_twinmaker" not in variables.lower()
    assert "aws_grafana" not in variables.lower()

    grafana = _normalized_source("aws_grafana.tf")
    assert 'grafana_version = "10.4"' in grafana
