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
    source = _source("gcp_five_layer_v2.tf")

    assert 'name  = "EVENT_LAYER_PROVIDER"' in source
    assert 'name  = "REMOTE_TELEMETRY_TOPIC"' in source
    assert 'name  = "TWIN_REMOTE_CONTROL_TOPIC"' in source
    assert (
        'local.six_layer_eventing_enabled && var.layer_4_provider != "google"' in source
    )
    assert (
        "local.six_layer_eventing_enabled && "
        "local.gcp_v2_remote_processed_inbound && local.gcp_v2_l2_enabled" in source
    )
