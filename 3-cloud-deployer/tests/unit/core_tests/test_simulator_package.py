"""Security and provider contract tests for simulator package assembly."""

from __future__ import annotations

import base64
import io
import json
import zipfile
from pathlib import Path

import pytest

from src.core.simulator_package import (
    MAX_PAYLOAD_FILE_BYTES,
    SimulatorPackageInvalid,
    SimulatorPackageNotFound,
    SimulatorPackageService,
)


def _source_root(tmp_path: Path, provider: str) -> Path:
    root = tmp_path / "source"
    provider_dir = root / provider
    templates = provider_dir / "templates"
    templates.mkdir(parents=True)
    for name in ("main.py", "transmission.py", "globals.py"):
        (provider_dir / name).write_text(f"# {name}\n", encoding="utf-8")
    for name in ("README.md.template", "requirements.txt", "Dockerfile", "docker-compose.yml.template"):
        (templates / name).write_text("project={{project_name}}\n", encoding="utf-8")
    if provider == "aws":
        (provider_dir / "AmazonRootCA1.pem").write_text(
            "-----BEGIN CERTIFICATE-----\nROOT\n-----END CERTIFICATE-----\n",
            encoding="utf-8",
        )
    return root


def _project(tmp_path: Path, provider: str, config: dict) -> tuple[Path, Path]:
    project = tmp_path / "project"
    simulator = project / "iot_device_simulator"
    device = simulator / provider / "device-1"
    device.mkdir(parents=True)
    (simulator / "payloads.json").write_text('[{"iotDeviceId":"device-1"}]', encoding="utf-8")
    config = dict(config)
    credential_classes = {
        "aws": "aws_iot_device_certificate",
        "azure": "azure_iot_hub_device_identity",
        "google": "gcp_pubsub_topic_publisher",
    }
    config.setdefault("credential_class", credential_classes[provider])
    config.setdefault("credential_contract_version", 1)
    if provider == "aws":
        config.setdefault("permission_scope", "exact_client_and_telemetry_topic")
    config_path = device / "config_generated.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")
    if provider == "azure":
        config_path.chmod(0o600)
    return project, device


def _build(tmp_path: Path, provider: str, config: dict):
    project, device = _project(tmp_path, provider, config)
    source = _source_root(tmp_path, provider)
    package = SimulatorPackageService(project_path=project, source_root=source).build(
        project_name="factory-twin",
        provider=provider,
    )
    return project, device, package


def _entries(content: io.BytesIO) -> dict[str, bytes]:
    with zipfile.ZipFile(content) as archive:
        return {name: archive.read(name) for name in archive.namelist()}


def test_builds_azure_archive_with_only_device_identity_and_allowlisted_files(tmp_path):
    key = base64.b64encode(b"device-secret").decode()
    _, _, package = _build(
        tmp_path,
        "azure",
        {
            "device_id": "device-1",
            "connection_string": (
                "HostName=factory.azure-devices.net;DeviceId=device-1;"
                f"SharedAccessKey={key}"
            ),
            "digital_twin_name": "factory-twin",
        },
    )

    entries = _entries(package.content)

    assert package.provider == "azure"
    assert package.credential_class == "azure_iot_hub_device_identity"
    assert sorted(entries) == [
        "Dockerfile",
        "README.md",
        "config.json",
        "configs/device-1/config.json",
        "docker-compose.yml",
        "payloads.json",
        "requirements.txt",
        "src/globals.py",
        "src/main.py",
        "src/transmission.py",
    ]
    config = json.loads(entries["config.json"])
    assert config["credential_class"] == "azure_iot_hub_device_identity"
    assert config["payload_path"] == "payloads.json"


def test_builds_aws_archive_with_device_scoped_certificate_material(tmp_path):
    project, _ = _project(
        tmp_path,
        "aws",
        {
            "device_id": "device-1",
            "endpoint": "example-ats.iot.eu-central-1.amazonaws.com",
            "topic": "dt/factory-twin/device-1/telemetry",
            "credential_class": "aws_iot_device_certificate",
            "credential_contract_version": 1,
            "permission_scope": "exact_client_and_telemetry_topic",
        },
    )
    auth = project / "iot_devices_auth" / "device-1"
    auth.mkdir(parents=True)
    (auth / "certificate.pem.crt").write_text(
        "-----BEGIN CERTIFICATE-----\nDEVICE\n-----END CERTIFICATE-----\n",
        encoding="utf-8",
    )
    (auth / "private.pem.key").write_text(
        "-----BEGIN PRIVATE KEY-----\nKEY\n-----END PRIVATE KEY-----\n",
        encoding="utf-8",
    )
    (auth / "private.pem.key").chmod(0o600)
    (auth / "public.pem.key").write_text("public", encoding="utf-8")
    package = SimulatorPackageService(
        project_path=project,
        source_root=_source_root(tmp_path, "aws"),
    ).build(project_name="factory-twin", provider="aws")

    entries = _entries(package.content)

    assert package.credential_class == "aws_iot_device_certificate"
    assert "configs/device-1/certificate.pem.crt" in entries
    assert "configs/device-1/private.pem.key" in entries
    assert "public.pem.key" not in " ".join(entries)


def test_gcp_archive_uses_only_dedicated_topic_publisher_key(tmp_path):
    email = "factory-simulator@example.iam.gserviceaccount.com"
    project, _ = _project(
        tmp_path,
        "google",
        {
            "device_id": "device-1",
            "project_id": "example",
            "topic_name": "factory-telemetry",
            "service_account_key_path": "/tmp/admin-credentials.json",
            "simulator_service_account_email": email,
            "credential_class": "gcp_pubsub_topic_publisher",
            "credential_contract_version": 1,
        },
    )
    runtime = project / "iot_device_simulator" / "google" / "_runtime"
    runtime.mkdir()
    runtime_key = {
        "type": "service_account",
        "project_id": "example",
        "client_email": email,
        "private_key": "-----BEGIN PRIVATE KEY-----\nRUNTIME\n-----END PRIVATE KEY-----\n",
    }
    (runtime / "service_account.json").write_text(json.dumps(runtime_key), encoding="utf-8")
    (runtime / "service_account.json").chmod(0o600)
    (project / "service_account.json").write_text("ADMIN-KEY-MUST-NOT-BE-READ", encoding="utf-8")
    package = SimulatorPackageService(
        project_path=project,
        source_root=_source_root(tmp_path, "google"),
    ).build(project_name="factory-twin", provider="gcp")

    entries = _entries(package.content)

    assert package.provider == "gcp"
    assert package.credential_class == "gcp_pubsub_topic_publisher"
    assert json.loads(entries["service_account.json"])["private_key"].find("RUNTIME") >= 0
    assert b"ADMIN-KEY" not in b"".join(entries.values())


@pytest.mark.parametrize(
    ("provider", "config"),
    [
        (
            "azure",
            {
                "device_id": "device-1",
                "connection_string": "HostName=x.azure-devices.net;DeviceId=other;SharedAccessKey=eA==",
            },
        ),
        (
            "aws",
            {
                "device_id": "device-1",
                "endpoint": "x.iot.eu-central-1.amazonaws.com",
                "topic": "dt/factory-twin/other/telemetry",
                "credential_class": "aws_iot_device_certificate",
                "credential_contract_version": 1,
                "permission_scope": "exact_client_and_telemetry_topic",
            },
        ),
    ],
)
def test_rejects_provider_identity_mismatch(tmp_path, provider, config):
    project, _ = _project(tmp_path, provider, config)
    with pytest.raises(SimulatorPackageInvalid):
        SimulatorPackageService(
            project_path=project,
            source_root=_source_root(tmp_path, provider),
        ).build(project_name="factory-twin", provider=provider)


def test_rejects_symbolic_links_in_provider_directory(tmp_path):
    project, _ = _project(
        tmp_path,
        "azure",
        {
            "device_id": "device-1",
            "connection_string": "HostName=x.azure-devices.net;DeviceId=device-1;SharedAccessKey=eA==",
        },
    )
    provider_dir = project / "iot_device_simulator" / "azure"
    (provider_dir / "linked-device").symlink_to(provider_dir / "device-1", target_is_directory=True)

    with pytest.raises(SimulatorPackageInvalid, match="symbolic links"):
        SimulatorPackageService(
            project_path=project,
            source_root=_source_root(tmp_path, "azure"),
        ).build(project_name="factory-twin", provider="azure")


def test_rejects_unexpected_gcp_runtime_credential_file(tmp_path):
    email = "factory-simulator@example.iam.gserviceaccount.com"
    project, _ = _project(
        tmp_path,
        "google",
        {
            "device_id": "device-1",
            "project_id": "example",
            "topic_name": "factory-telemetry",
            "simulator_service_account_email": email,
            "credential_class": "gcp_pubsub_topic_publisher",
            "credential_contract_version": 1,
        },
    )
    runtime = project / "iot_device_simulator" / "google" / "_runtime"
    runtime.mkdir()
    (runtime / "service_account.json").write_text("{}", encoding="utf-8")
    (runtime / "admin.json").write_text("{}", encoding="utf-8")

    with pytest.raises(SimulatorPackageInvalid, match="unexpected files"):
        SimulatorPackageService(
            project_path=project,
            source_root=_source_root(tmp_path, "google"),
        ).build(project_name="factory-twin", provider="gcp")


def test_missing_payload_fails_closed(tmp_path):
    project, _ = _project(
        tmp_path,
        "azure",
        {
            "device_id": "device-1",
            "connection_string": "HostName=x.azure-devices.net;DeviceId=device-1;SharedAccessKey=eA==",
        },
    )
    (project / "iot_device_simulator" / "payloads.json").unlink()

    with pytest.raises(SimulatorPackageNotFound, match="payloads"):
        SimulatorPackageService(
            project_path=project,
            source_root=_source_root(tmp_path, "azure"),
        ).build(project_name="factory-twin", provider="azure")


def test_rejects_unsafe_project_name_before_build(tmp_path):
    service = SimulatorPackageService(project_path=tmp_path, source_root=tmp_path)
    with pytest.raises(SimulatorPackageInvalid, match="project name"):
        service.build(project_name="../admin", provider="aws")


def test_supports_empty_payloads_and_multiple_device_configs(tmp_path):
    key = base64.b64encode(b"device-secret").decode()
    project, _ = _project(
        tmp_path,
        "azure",
        {
            "device_id": "device-1",
            "connection_string": (
                "HostName=factory.azure-devices.net;DeviceId=device-1;"
                f"SharedAccessKey={key}"
            ),
        },
    )
    provider_dir = project / "iot_device_simulator" / "azure"
    second_device = provider_dir / "device-2"
    second_device.mkdir()
    second_config = second_device / "config_generated.json"
    second_config.write_text(
        json.dumps(
            {
                "device_id": "device-2",
                "connection_string": (
                    "HostName=factory.azure-devices.net;DeviceId=device-2;"
                    f"SharedAccessKey={key}"
                ),
                "credential_class": "azure_iot_hub_device_identity",
                "credential_contract_version": 1,
            }
        ),
        encoding="utf-8",
    )
    second_config.chmod(0o600)
    (project / "iot_device_simulator" / "payloads.json").write_text("[]", encoding="utf-8")

    package = SimulatorPackageService(
        project_path=project,
        source_root=_source_root(tmp_path, "azure"),
    ).build(project_name="factory-twin", provider="azure")
    entries = _entries(package.content)

    assert json.loads(entries["payloads.json"]) == []
    assert "configs/device-1/config.json" in entries
    assert "configs/device-2/config.json" in entries


def test_rejects_payload_above_explicit_size_limit(tmp_path):
    project, _ = _project(
        tmp_path,
        "azure",
        {
            "device_id": "device-1",
            "connection_string": (
                "HostName=factory.azure-devices.net;DeviceId=device-1;"
                "SharedAccessKey=eA=="
            ),
        },
    )
    (project / "iot_device_simulator" / "payloads.json").write_bytes(
        b"[" + (b" " * MAX_PAYLOAD_FILE_BYTES) + b"]"
    )

    with pytest.raises(SimulatorPackageInvalid, match="size limit"):
        SimulatorPackageService(
            project_path=project,
            source_root=_source_root(tmp_path, "azure"),
        ).build(project_name="factory-twin", provider="azure")


def test_rejects_gcp_runtime_key_with_group_or_world_permissions(tmp_path):
    email = "factory-simulator@example.iam.gserviceaccount.com"
    project, _ = _project(
        tmp_path,
        "google",
        {
            "device_id": "device-1",
            "project_id": "example",
            "topic_name": "factory-telemetry",
            "simulator_service_account_email": email,
        },
    )
    runtime = project / "iot_device_simulator" / "google" / "_runtime"
    runtime.mkdir()
    key_path = runtime / "service_account.json"
    key_path.write_text(
        json.dumps(
            {
                "type": "service_account",
                "project_id": "example",
                "client_email": email,
                "private_key": "-----BEGIN PRIVATE KEY-----\nRUNTIME\n-----END PRIVATE KEY-----",
            }
        ),
        encoding="utf-8",
    )
    key_path.chmod(0o640)

    with pytest.raises(SimulatorPackageInvalid, match="permissions"):
        SimulatorPackageService(
            project_path=project,
            source_root=_source_root(tmp_path, "google"),
        ).build(project_name="factory-twin", provider="gcp")


def test_rejects_unsafe_device_directory_name(tmp_path):
    project, _ = _project(
        tmp_path,
        "azure",
        {
            "device_id": "device-1",
            "connection_string": (
                "HostName=factory.azure-devices.net;DeviceId=device-1;"
                "SharedAccessKey=eA=="
            ),
        },
    )
    unsafe_device = project / "iot_device_simulator" / "azure" / "device name"
    unsafe_device.mkdir()

    with pytest.raises(SimulatorPackageInvalid, match="device ID"):
        SimulatorPackageService(
            project_path=project,
            source_root=_source_root(tmp_path, "azure"),
        ).build(project_name="factory-twin", provider="azure")


def test_archive_writer_rejects_traversal_and_duplicate_entries(tmp_path):
    service = SimulatorPackageService(project_path=tmp_path, source_root=tmp_path)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        with pytest.raises(SimulatorPackageInvalid, match="Unsafe or duplicate"):
            service._write_bytes(archive, "../secret.json", b"secret")
        service._write_bytes(archive, "config.json", b"{}")
        with pytest.raises(SimulatorPackageInvalid, match="Unsafe or duplicate"):
            service._write_bytes(archive, "config.json", b"{}")


def test_service_resets_per_archive_accounting_between_builds(tmp_path):
    key = base64.b64encode(b"device-secret").decode()
    project, _ = _project(
        tmp_path,
        "azure",
        {
            "device_id": "device-1",
            "connection_string": (
                "HostName=factory.azure-devices.net;DeviceId=device-1;"
                f"SharedAccessKey={key}"
            ),
        },
    )
    service = SimulatorPackageService(
        project_path=project,
        source_root=_source_root(tmp_path, "azure"),
    )

    first = service.build(project_name="factory-twin", provider="azure")
    second = service.build(project_name="factory-twin", provider="azure")

    assert set(_entries(first.content)) == set(_entries(second.content))
