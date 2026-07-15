"""Tests for the simulator API's validated runtime boundary."""

from __future__ import annotations

import json

import pytest

from src.api.simulator import _normalize_simulator_provider
from src.simulator.session import (
    SimulatorSessionInvalid,
    SimulatorSessionNotFound,
    resolve_simulator_session,
)


def _project(tmp_path, provider="aws", devices=("device-b", "device-a")):
    project = tmp_path / "upload" / "factory-twin"
    simulator = project / "iot_device_simulator"
    provider_dir = simulator / provider
    for device_id in devices:
        device = provider_dir / device_id
        device.mkdir(parents=True)
        config = device / "config_generated.json"
        config.write_text(json.dumps({"device_id": device_id}), encoding="utf-8")
        if provider == "azure":
            config.chmod(0o600)
    (simulator / "payloads.json").write_text("[]", encoding="utf-8")
    return project, provider_dir


def test_simulator_provider_normalization_supports_public_aliases():
    assert _normalize_simulator_provider("aws") == "aws"
    assert _normalize_simulator_provider("azure") == "azure"
    assert _normalize_simulator_provider("gcp") == "google"
    assert _normalize_simulator_provider("google") == "google"


def test_simulator_provider_normalization_rejects_unknown_provider():
    with pytest.raises(ValueError, match="Supported: aws, azure, gcp"):
        _normalize_simulator_provider("oracle")


def test_resolver_selects_first_device_deterministically(tmp_path):
    _, provider_dir = _project(tmp_path)
    (provider_dir / "_runtime").mkdir()

    spec = resolve_simulator_session(
        project_name="factory-twin",
        provider="aws",
        repository_root=tmp_path,
    )

    assert spec.device_id == "device-a"
    assert spec.module == "src.iot_device_simulator.aws.main"
    assert spec.config_path.name == "config_generated.json"


def test_resolver_honors_explicit_device_and_gcp_alias(tmp_path):
    _project(tmp_path, provider="google")

    spec = resolve_simulator_session(
        project_name="factory-twin",
        provider="gcp",
        device_id="device-b",
        repository_root=tmp_path,
    )

    assert spec.internal_provider == "google"
    assert spec.public_provider == "gcp"
    assert spec.device_id == "device-b"


def test_resolver_rejects_missing_or_unsafe_device(tmp_path):
    _project(tmp_path)

    with pytest.raises(SimulatorSessionNotFound, match="missing"):
        resolve_simulator_session(
            project_name="factory-twin",
            provider="aws",
            device_id="missing",
            repository_root=tmp_path,
        )
    with pytest.raises(SimulatorSessionInvalid, match="device ID"):
        resolve_simulator_session(
            project_name="factory-twin",
            provider="aws",
            device_id="../admin",
            repository_root=tmp_path,
        )


def test_resolver_rejects_identity_mismatch_and_invalid_payload(tmp_path):
    _, provider_dir = _project(tmp_path, devices=("device-a",))
    config = provider_dir / "device-a" / "config_generated.json"
    config.write_text('{"device_id":"other"}', encoding="utf-8")

    with pytest.raises(SimulatorSessionInvalid, match="identity"):
        resolve_simulator_session(
            project_name="factory-twin",
            provider="aws",
            repository_root=tmp_path,
        )

    config.write_text('{"device_id":"device-a"}', encoding="utf-8")
    (tmp_path / "upload" / "factory-twin" / "iot_device_simulator" / "payloads.json").write_text(
        "{}",
        encoding="utf-8",
    )
    with pytest.raises(SimulatorSessionInvalid, match="JSON array"):
        resolve_simulator_session(
            project_name="factory-twin",
            provider="aws",
            repository_root=tmp_path,
        )


def test_resolver_rejects_symlinked_config_and_protected_template(tmp_path):
    _, provider_dir = _project(tmp_path, devices=("device-a",))
    config = provider_dir / "device-a" / "config_generated.json"
    target = provider_dir / "target.json"
    target.write_text('{"device_id":"device-a"}', encoding="utf-8")
    config.unlink()
    config.symlink_to(target)

    with pytest.raises(SimulatorSessionInvalid, match="regular file"):
        resolve_simulator_session(
            project_name="factory-twin",
            provider="aws",
            repository_root=tmp_path,
        )
    with pytest.raises(SimulatorSessionInvalid, match="protected template"):
        resolve_simulator_session(
            project_name="template",
            provider="aws",
            repository_root=tmp_path,
        )


def test_resolver_enforces_sensitive_azure_config_permissions(tmp_path):
    _, provider_dir = _project(tmp_path, provider="azure", devices=("device-a",))
    (provider_dir / "device-a" / "config_generated.json").chmod(0o644)

    with pytest.raises(SimulatorSessionInvalid, match="permissions"):
        resolve_simulator_session(
            project_name="factory-twin",
            provider="azure",
            repository_root=tmp_path,
        )
