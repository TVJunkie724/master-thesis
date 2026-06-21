"""Tests for simulator API boundary helpers."""

from src.api.simulator import (
    _normalize_simulator_provider,
    _resolve_payload_path,
    _resolve_simulator_script_path,
)


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


def test_resolve_simulator_script_path_returns_canonical_script(tmp_path, monkeypatch):
    simulator_dir = tmp_path / "src" / "iot_device_simulator" / "aws"
    simulator_dir.mkdir(parents=True)
    script = simulator_dir / "main.py"
    script.write_text("print('ok')\n")

    monkeypatch.setattr("src.api.simulator.state.get_project_base_path", lambda: str(tmp_path))

    assert _resolve_simulator_script_path("aws") == script.resolve()


def test_resolve_simulator_script_path_rejects_path_escape(tmp_path, monkeypatch):
    simulator_root = tmp_path / "src" / "iot_device_simulator"
    simulator_root.mkdir(parents=True)
    outside = tmp_path / "src" / "escaped"
    outside.mkdir(parents=True)
    (outside / "main.py").write_text("print('escape')\n")

    monkeypatch.setattr("src.api.simulator.state.get_project_base_path", lambda: str(tmp_path))

    try:
        _resolve_simulator_script_path("../escaped")
    except ValueError as exc:
        assert "outside the simulator source tree" in str(exc)
    else:
        raise AssertionError("Expected path escape to raise ValueError")
