"""Real simulator packaging contracts; no provider connections are made."""

import json
from pathlib import Path
import subprocess
import sys
import zipfile

import pytest
import yaml

from src.core.simulator_package import SimulatorPackageService


SOURCE = Path(__file__).resolve().parents[2] / "src" / "iot_device_simulator"


@pytest.mark.parametrize("provider", ["aws", "azure", "google"])
def test_container_mounts_device_configs_without_baking_credentials(provider):
    templates = SOURCE / provider / "templates"
    compose = yaml.safe_load((templates / "docker-compose.yml.template").read_text())
    service = next(iter(compose["services"].values()))
    mounts = service["volumes"]
    assert "./configs:/app/configs:ro" in mounts
    assert "./config.json:/app/config.json:ro" in mounts
    assert "./payloads.json:/app/payloads.json:ro" in mounts
    assert all(mount.endswith(":ro") for mount in mounts)
    assert service["restart"] == "no"
    dockerfile = (templates / "Dockerfile").read_text()
    copies = [line for line in dockerfile.splitlines() if line.startswith("COPY ")]
    assert set(copies) == {"COPY requirements.txt .", "COPY src/ ./src/"}
    assert '"--config", "/app/config.json"' in dockerfile
    assert (templates / ".dockerignore").read_text().splitlines() == [
        "*", "!Dockerfile", "!requirements.txt", "!src/", "!src/*.py",
    ]
    readme = (templates / "README.md.template").read_text()
    assert "--config config.json" in readme
    assert "docker compose run --build --rm" in readme


@pytest.fixture
def gcp_package(tmp_path):
    project = tmp_path / "project"
    simulator = project / "iot_device_simulator"
    runtime = simulator / "google" / "_runtime"
    runtime.mkdir(parents=True)
    (runtime / "server-ca.pem").write_text(
        "-----BEGIN CERTIFICATE-----\nPUBLIC\n-----END CERTIFICATE-----\n"
    )
    (simulator / "payloads.json").write_text('[{"iotDeviceId":"device-2"}]')
    for device in ("device-1", "device-2"):
        directory = simulator / "google" / device
        directory.mkdir()
        config = directory / "config_generated.json"
        config.write_text(json.dumps({
            "device_id": device,
            "endpoint": "203.0.113.10",
            "port": 8883,
            "username": device,
            "password": "offline-test-only",
            "telemetry_topic": f"devices/{device}/telemetry",
            "command_topic": f"devices/{device}/commands",
            "permission_scope": "deployment_device_telemetry_and_command_topics",
            "credential_class": "gcp_mqtt_deployment_credential",
            "credential_contract_version": 1,
        }))
        config.chmod(0o600)
    package = SimulatorPackageService(project_path=project, source_root=SOURCE).build(
        project_name="test-twin", provider="gcp"
    )
    extracted = tmp_path / "extracted"
    with zipfile.ZipFile(package.content) as archive:
        archive.extractall(extracted)  # Only this test's freshly generated archive.
    return extracted


def test_generated_gcp_package_starts_and_exits_without_cloud_calls(gcp_package):
    result = subprocess.run(
        [sys.executable, "-m", "src.main", "--config", "config.json"],
        cwd=gcp_package, input="5\n", text=True, capture_output=True, timeout=10,
    )
    assert result.returncode == 0, result.stderr
    assert "Exiting..." in result.stdout
    assert "offline-test-only" not in result.stdout + result.stderr
    assert (gcp_package / ".dockerignore").is_file()


def test_generated_gcp_package_resolves_second_device_and_rejects_unknown(gcp_package):
    result = subprocess.run(
        [sys.executable, "-c", "\n".join([
            "from pathlib import Path",
            "from src import globals, transmission",
            "globals.load_config('config.json')",
            "config = transmission._active_config({'iotDeviceId': 'device-2'})",
            "assert config['device_id'] == 'device-2'",
            "assert config['telemetry_topic'] == 'devices/device-2/telemetry'",
            "assert Path(config['server_ca_path']).is_file()",
            "assert Path(config['payload_path']).is_file()",
            "for device in ('unknown-device', '../outside'):",
            "    try:",
            "        transmission.load_config_for_device(device)",
            "    except ValueError:",
            "        pass",
            "    else:",
            "        raise AssertionError('Unknown/unsafe device accepted')",
        ])],
        cwd=gcp_package, text=True, capture_output=True, timeout=10,
    )
    assert result.returncode == 0, result.stderr
