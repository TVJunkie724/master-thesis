"""Source-level drift gates for GCP deployment specification bindings."""

from pathlib import Path


TERRAFORM_ROOT = Path(__file__).resolve().parents[3] / "src" / "terraform"


def _source(filename: str) -> str:
    return (TERRAFORM_ROOT / filename).read_text(encoding="utf-8")


def _normalized_source(filename: str) -> str:
    return " ".join(_source(filename).split())


def test_every_gcp_function_runtime_profile_is_specification_owned():
    expected_bindings = {
        "gcp_iot.tf": ("gcp_l1_function", 1),
        "gcp_compute.tf": ("gcp_l2_function", 6),
        "gcp_glue.tf": ("gcp_glue_function", 4),
    }
    for filename, (prefix, expected_count) in expected_bindings.items():
        source = _source(filename)
        assert source.count(
            f"available_memory      = \"${{var.{prefix}_memory_mb}}M\""
        ) == expected_count
        assert source.count(
            f"min_instance_count    = var.{prefix}_min_instances"
        ) == expected_count
        assert source.count(
            f"max_instance_count    = var.{prefix}_max_instances"
        ) == expected_count

    compute = _source("gcp_compute.tf")
    for suffix in ("memory_mb", "min_instances", "max_instances"):
        assert f"var.gcp_l1_function_{suffix}" in compute

    storage = _source("gcp_storage.tf")
    for prefix in (
        "gcp_l3_reader_function",
        "gcp_hot_to_cool_mover",
        "gcp_cool_to_archive_mover",
    ):
        for suffix in ("memory_mb", "min_instances", "max_instances"):
            assert f"var.{prefix}_{suffix}" in storage

    all_gcp_source = "\n".join(
        _source(path.name)
        for path in sorted(TERRAFORM_ROOT.glob("gcp_*.tf"))
    )
    assert 'available_memory      = "256M"' not in all_gcp_source
    assert 'available_memory      = "512M"' not in all_gcp_source
    assert "min_instance_count    = 0" not in all_gcp_source
    assert "max_instance_count    = 10" not in all_gcp_source


def test_gcp_storage_classes_schedules_and_firestore_mode_are_specification_owned():
    storage = _normalized_source("gcp_storage.tf")
    assert "type = var.gcp_firestore_mode" in storage
    assert "storage_class = var.gcp_l3_cool_storage_class" in storage
    assert "storage_class = var.gcp_l3_archive_storage_class" in storage
    assert "schedule = var.gcp_hot_to_cool_scheduler_cron" in storage
    assert "schedule = var.gcp_cool_to_archive_scheduler_cron" in storage
    assert (
        "COLD_STORAGE_CLASS = local.gcp_l3_cold_enabled ? "
        'var.gcp_l3_cool_storage_class : ""'
    ) in storage
    assert (
        "ARCHIVE_STORAGE_CLASS = local.gcp_l3_archive_enabled ? "
        'var.gcp_l3_archive_storage_class : ""'
    ) in storage
    assert 'type = "FIRESTORE_NATIVE"' not in storage
    assert 'storage_class = "NEARLINE"' not in storage
    assert 'storage_class = "ARCHIVE"' not in storage


def test_gcp_transition_resources_are_source_owned_without_duplicate_lifecycle():
    source = _normalized_source("gcp_storage.tf")
    assert "lifecycle_rule" not in source
    assert (
        'resource "google_storage_bucket" "archive" { '
        "count = local.gcp_l3_archive_enabled ? 1 : 0"
    ) in source
    assert (
        'resource "google_cloudfunctions2_function" "hot_to_cold_mover" { '
        "count = local.gcp_l3_hot_enabled ? 1 : 0"
    ) in source
    assert (
        'resource "google_cloud_scheduler_job" "hot_to_cold" { '
        "count = local.gcp_l3_hot_enabled ? 1 : 0"
    ) in source
    assert (
        'resource "google_cloudfunctions2_function" "cold_to_archive_mover" { '
        "count = local.gcp_l3_cold_enabled ? 1 : 0"
    ) in source
    assert (
        'resource "google_cloud_scheduler_job" "cold_to_archive" { '
        "count = local.gcp_l3_cold_enabled ? 1 : 0"
    ) in source
    assert "google_storage_bucket.archive[0].name" in source
    assert "try(google_storage_bucket.archive" not in source


def test_gcp_cross_cloud_writers_receive_destination_storage_classes():
    source = _normalized_source("gcp_glue.tf")
    assert (
        "COLD_STORAGE_CLASS = local.gcp_l3_cold_enabled ? "
        'var.gcp_l3_cool_storage_class : ""'
    ) in source
    assert (
        "ARCHIVE_STORAGE_CLASS = local.gcp_l3_archive_enabled ? "
        'var.gcp_l3_archive_storage_class : ""'
    ) in source


def test_gcp_variables_fail_closed_to_contract_values():
    source = _normalized_source("variables.tf")
    expected = {
        "gcp_l1_function_memory_mb": "256",
        "gcp_l1_function_min_instances": "0",
        "gcp_l1_function_max_instances": "10",
        "gcp_l2_function_memory_mb": "256",
        "gcp_l2_function_min_instances": "0",
        "gcp_l2_function_max_instances": "10",
        "gcp_firestore_mode": '"FIRESTORE_NATIVE"',
        "gcp_l3_reader_function_memory_mb": "256",
        "gcp_l3_reader_function_min_instances": "0",
        "gcp_l3_reader_function_max_instances": "10",
        "gcp_l3_cool_storage_class": '"NEARLINE"',
        "gcp_hot_to_cool_mover_memory_mb": "512",
        "gcp_hot_to_cool_mover_min_instances": "0",
        "gcp_hot_to_cool_mover_max_instances": "1",
        "gcp_hot_to_cool_scheduler_cron": '"0 2 * * *"',
        "gcp_l3_archive_storage_class": '"ARCHIVE"',
        "gcp_cool_to_archive_mover_memory_mb": "512",
        "gcp_cool_to_archive_mover_min_instances": "0",
        "gcp_cool_to_archive_mover_max_instances": "1",
        "gcp_cool_to_archive_scheduler_cron": '"0 3 * * 0"',
        "gcp_glue_function_memory_mb": "256",
        "gcp_glue_function_min_instances": "0",
        "gcp_glue_function_max_instances": "10",
    }
    for variable, allowed_value in expected.items():
        marker = f'variable "{variable}" {{'
        block = source[source.index(marker):]
        block = block[:block.index("} }") + 3]
        assert "default = null" in block
        assert f"var.{variable} == null" in block
        assert f"var.{variable} == {allowed_value}" in block


def test_gcp_guard_rejects_unsupported_l4_and_l5():
    source = _normalized_source("gcp_setup.tf")
    assert 'condition = var.layer_4_provider != "google"' in source
    assert 'condition = var.layer_5_provider != "google"' in source
    assert (
        "GCP L4 is unsupported by the canonical Deployer capability contract."
        in source
    )
    assert (
        "GCP L5 is unsupported by the canonical Deployer capability contract."
        in source
    )


def test_gcp_usage_meters_and_invariant_timeouts_are_not_tfvars():
    variables = _source("variables.tf").lower()
    assert "gcp_cloud_scheduler_job_price" not in variables
    assert "gcp_function_duration" not in variables
    assert "gcp_storage_request_price" not in variables

    source = _normalized_source("gcp_storage.tf")
    assert "timeout_seconds = 60" in source
    assert "timeout_seconds = 540" in source
