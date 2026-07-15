"""Regression tests for integrated simulator output paths and permissions."""

from __future__ import annotations

import json
import stat

from src.providers.azure.layers.layer_1_iot import _generate_azure_simulator_config
from src.providers.terraform.aws_deployer import _generate_aws_simulator_config


def test_aws_generated_config_resolves_shared_payload_and_device_credentials(tmp_path):
    _generate_aws_simulator_config(
        tmp_path,
        {"id": "sensor-1"},
        "factory",
        "endpoint.iot.eu-central-1.amazonaws.com",
    )

    config_path = (
        tmp_path
        / "iot_device_simulator"
        / "aws"
        / "sensor-1"
        / "config_generated.json"
    )
    config = json.loads(config_path.read_text(encoding="utf-8"))

    assert (config_path.parent / config["payload_path"]).resolve() == (
        tmp_path / "iot_device_simulator" / "payloads.json"
    ).resolve()
    assert (config_path.parent / config["cert_path"]).resolve() == (
        tmp_path / "iot_devices_auth" / "sensor-1" / "certificate.pem.crt"
    ).resolve()
    assert (config_path.parent / config["key_path"]).resolve() == (
        tmp_path / "iot_devices_auth" / "sensor-1" / "private.pem.key"
    ).resolve()
    assert config["root_ca_path"].endswith("iot_device_simulator/aws/AmazonRootCA1.pem")


def test_azure_generated_config_is_atomically_private_and_uses_shared_payload(tmp_path):
    _generate_azure_simulator_config(
        {"id": "sensor-1"},
        "HostName=x.azure-devices.net;DeviceId=sensor-1;SharedAccessKey=eA==",
        "factory",
        str(tmp_path),
    )

    config_path = (
        tmp_path
        / "iot_device_simulator"
        / "azure"
        / "sensor-1"
        / "config_generated.json"
    )
    config = json.loads(config_path.read_text(encoding="utf-8"))

    assert stat.S_IMODE(config_path.stat().st_mode) == 0o600
    assert (config_path.parent / config["payload_path"]).resolve() == (
        tmp_path / "iot_device_simulator" / "payloads.json"
    ).resolve()
    assert list(config_path.parent.glob("*.tmp")) == []
