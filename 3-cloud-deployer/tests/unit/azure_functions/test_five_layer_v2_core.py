"""Azure Five-layer v2 canonical envelope parity tests."""

from datetime import datetime, timezone
import importlib.util
from pathlib import Path
import uuid

import pytest


CORE_PATH = (
    Path(__file__).resolve().parents[3]
    / "src"
    / "providers"
    / "azure"
    / "azure_functions"
    / "five-layer-v2"
    / "core.py"
)
SPEC = importlib.util.spec_from_file_location("azure_five_layer_v2_core", CORE_PATH)
assert SPEC and SPEC.loader
core = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(core)


def _event(**overrides):
    event_id = str(uuid.uuid4())
    value = {
        "schema_version": "canonical-domain-event.v1",
        "event_id": event_id,
        "event_type": "telemetry.received.v1",
        "deployment_id": "deployment",
        "source_id": "device-1",
        "source_sequence": "1",
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "correlation_id": event_id,
        "causation_id": event_id,
        "producer": "component.device-ingress",
        "payload": {"device_id": "device-1", "temperature": 21.5},
    }
    value.update(overrides)
    return value


def test_accepts_exact_canonical_event_and_partition_key():
    event = _event()

    assert core.validate_canonical_event(event) == event
    assert core.partition_key(event) == "device-1"


def test_rejects_provider_route_metadata_in_domain_envelope():
    event = _event(destination_provider="aws")

    with pytest.raises(core.ContractError, match="INVALID_CANONICAL_EVENT"):
        core.validate_canonical_event(event)


def test_rejects_unknown_event_type_and_non_json_body():
    with pytest.raises(core.ContractError, match="UNKNOWN_DOMAIN_EVENT"):
        core.validate_canonical_event(_event(event_type="custom.event"))
    with pytest.raises(core.ContractError, match="INVALID_UTF8_JSON"):
        core.decode_message_body(b"not-json")


def test_derived_event_is_deterministic_and_preserves_correlation():
    source = _event()

    first = core.derive_event(
        source,
        event_type="telemetry.processed.v1",
        producer="component.telemetry-processor",
    )
    second = core.derive_event(
        source,
        event_type="telemetry.processed.v1",
        producer="component.telemetry-processor",
    )

    assert first == second
    assert first["causation_id"] == source["event_id"]
    assert first["correlation_id"] == source["correlation_id"]


def test_envelope_field_set_matches_aws_v2_runtime():
    aws_path = (
        Path(__file__).resolve().parents[3]
        / "src"
        / "providers"
        / "aws"
        / "lambda_functions"
        / "five-layer-v2"
        / "handler.py"
    )
    aws_spec = importlib.util.spec_from_file_location("aws_five_layer_v2", aws_path)
    assert aws_spec and aws_spec.loader
    aws = importlib.util.module_from_spec(aws_spec)
    aws_spec.loader.exec_module(aws)

    assert core.CANONICAL_EVENT_FIELDS == aws.CANONICAL_EVENT_FIELDS
    assert core.DOMAIN_EVENT_TYPES == aws.DOMAIN_EVENT_TYPES
