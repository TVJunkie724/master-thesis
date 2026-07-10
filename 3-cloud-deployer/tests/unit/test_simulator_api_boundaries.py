"""Tests for simulator API boundary helpers."""

from src.api.simulator import _normalize_simulator_provider, _resolve_payload_path


def test_simulator_provider_normalization_supports_public_aliases():
    assert _normalize_simulator_provider("aws") == "aws"
    assert _normalize_simulator_provider("azure") == "azure"
    assert _normalize_simulator_provider("gcp") == "google"
    assert _normalize_simulator_provider("google") == "google"


def test_simulator_provider_normalization_rejects_unknown_provider():
    try:
        _normalize_simulator_provider("oracle")
    except ValueError as exc:
        assert "Supported: aws, azure, gcp" in str(exc)
    else:
        raise AssertionError("Expected unsupported provider to raise ValueError")


def test_resolve_payload_path_prefers_shared_payload_file(tmp_path):
    project_path = tmp_path / "upload" / "factory-twin"
    shared_dir = project_path / "iot_device_simulator"
    legacy_dir = shared_dir / "aws"
    shared_dir.mkdir(parents=True)
    legacy_dir.mkdir()
    shared_payload = shared_dir / "payloads.json"
    legacy_payload = legacy_dir / "payloads.json"
    shared_payload.write_text("[]")
    legacy_payload.write_text("[{}]")

    result = _resolve_payload_path(str(project_path), "aws")

    assert result == str(shared_payload)


def test_resolve_payload_path_supports_legacy_provider_payload_file(tmp_path):
    project_path = tmp_path / "upload" / "factory-twin"
    legacy_dir = project_path / "iot_device_simulator" / "azure"
    legacy_dir.mkdir(parents=True)
    legacy_payload = legacy_dir / "payloads.json"
    legacy_payload.write_text("[]")

    result = _resolve_payload_path(str(project_path), "azure")

    assert result == str(legacy_payload)


def test_resolve_payload_path_returns_none_when_missing(tmp_path):
    project_path = tmp_path / "upload" / "factory-twin"
    project_path.mkdir(parents=True)

    assert _resolve_payload_path(str(project_path), "aws") is None
