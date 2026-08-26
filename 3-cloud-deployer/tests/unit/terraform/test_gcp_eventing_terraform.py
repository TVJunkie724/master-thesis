"""Static topology guards for the GCP Six-layer Event Layer."""

from pathlib import Path


TERRAFORM_ROOT = Path(__file__).resolve().parents[3] / "src" / "terraform"


def _source(name: str) -> str:
    return (TERRAFORM_ROOT / name).read_text(encoding="utf-8")


def test_gcp_event_layer_assigns_consumers_to_l1_l2_and_hot_owners():
    source = _source("gcp_eventing.tf")

    assert "local.six_layer_eventing_enabled" in source
    assert 'var.event_layer_provider == "google"' in source
    assert "gcp_event_local_processed_roles" in source
    assert '"historical-persistence"' in source
    assert '"twin-state-update"' in source
    assert 'local.gcp_event_l2_local ? ["rule-evaluator"]' in source
    assert "gcp_event_local_control_event_types" in source
    assert "EVENT_LOCAL_CONTROL_TYPES_JSON" in source
    assert "gcp_event_twin_local" not in source


def test_gcp_six_layer_processing_returns_to_event_and_hot_projects_directly():
    source = _source("gcp_six_layer.tf")

    assert 'name  = "EVENT_LAYER_PROVIDER"' in source
    assert 'name  = "REMOTE_TELEMETRY_TOPIC"' in source
    assert 'name  = "TWIN_REMOTE_CONTROL_TOPIC"' in source
    assert (
        'local.six_layer_eventing_enabled && var.layer_4_provider != "google"' in source
    )
    assert (
        "local.six_layer_eventing_enabled && "
        "local.gcp_six_layer_remote_processed_inbound && local.gcp_six_layer_l2_enabled"
        in source
    )


def test_gcp_l2_rule_evaluator_can_return_matches_to_selected_event_layer():
    source = _source("gcp_six_layer.tf")
    processor = source.split(
        'resource "google_cloud_run_v2_service" "gcp_gcp_cloud_run_service"',
        maxsplit=1,
    )[1].split(
        'resource "google_cloud_run_v2_service" "gcp_six_layer_processor_extension"',
        maxsplit=1,
    )[0]

    assert 'name  = "EVENT_LAYER_PROVIDER"' in processor
    assert 'name  = "PROCESSED_TOPIC"' in processor
    assert 'name  = "REMOTE_TELEMETRY_TOPIC"' in processor
    assert 'name  = "REMOTE_CONTROL_TOPIC"' in processor
    assert 'google_pubsub_topic.domain_events["control"].id' in processor


def test_gcp_remote_event_layer_grants_ingress_control_outbox_publish():
    source = _source("gcp_six_layer.tf")
    ingress_policy = source.split(
        'resource "google_pubsub_topic_iam_member" '
        '"gcp_six_layer_ingress_domain_publisher"',
        maxsplit=1,
    )[1].split(
        'resource "google_pubsub_topic_iam_member" '
        '"gcp_six_layer_processor_publishers"',
        maxsplit=1,
    )[0]

    assert "local.six_layer_eventing_enabled" in ingress_policy
    assert '"remote-control-outbound"' in ingress_policy
    assert '"domain"' in ingress_policy
    assert 'gcp_six_layer_runtime["ingress"].email' in ingress_policy


def test_gcp_large_bridge_uses_pull_workers_only_for_telemetry_sources():
    eventing = _source("gcp_eventing.tf")
    bridge = _source("six_layer_bridge_gcp.tf")

    assert "gcp_event_local_worker_count" in eventing
    assert "local.gcp_six_layer_bridge_worker_count" in eventing
    assert (
        'resource "google_cloud_run_v2_worker_pool" "gcp_six_layer_cross_cloud_bridge"'
        in bridge
    )
    assert "gcp_six_layer_bridge_worker_channel_ids" in bridge
    assert "gcp_six_layer_bridge_worker_sources" in bridge
    assert "gcp_six_layer_bridge_push_sources" in bridge
    assert 'name  = "BRIDGE_SUBSCRIPTION"' in bridge
    assert "from phase8_eventing.gcp.runtime import run_worker; run_worker()" in bridge
    assert 'role         = "roles/pubsub.subscriber"' in bridge
