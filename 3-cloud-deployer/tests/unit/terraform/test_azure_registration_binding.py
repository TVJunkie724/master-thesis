"""Keep SDK registration on the Terraform-owned Hub and canonical device IDs."""

import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from src.providers.azure.layers import layer_1_iot
from src.providers.terraform import azure_deployer


def test_active_registration_requires_and_forwards_actual_ingestion_output(monkeypatch, tmp_path):
    provider = object()
    context = SimpleNamespace(
        providers={"azure": provider}, config=object(),
        resolved_deployment_graph=SimpleNamespace(
            profile_ref={"id": "six-layer-eventing", "version": "1"}
        ),
    )
    register = MagicMock()
    monkeypatch.setattr(layer_1_iot, "register_iot_devices", register)
    with pytest.raises(RuntimeError, match="Azure ingestion output is required"):
        azure_deployer.register_azure_iot_devices(context, tmp_path, {})
    register.assert_not_called()
    azure_deployer.register_azure_iot_devices(context, tmp_path, {
        "azure_component_ingestion_output": {
            "iot_hub_name": "actual-six-iot-123", "hostname": "actual.azure-devices.net",
        },
    })
    register.assert_called_once_with(
        provider, context.config, str(tmp_path), hub_name="actual-six-iot-123",
        hub_hostname="actual.azure-devices.net", canonical_device_ids=True,
    )


@pytest.mark.parametrize("canonical", [False, True])
@pytest.mark.parametrize("exists", [False, True])
def test_registration_uses_selected_hub_and_preserves_legacy_default(monkeypatch, tmp_path, canonical, exists):
    import azure.iot.hub
    from azure.core.exceptions import ResourceNotFoundError

    hub_api = SimpleNamespace(
        get=MagicMock(return_value=SimpleNamespace(properties=SimpleNamespace(state="Active"))),
        list_keys=MagicMock(return_value=[SimpleNamespace(key_name="iothubowner", primary_key="synthetic-service-key")]),
    )
    provider = SimpleNamespace(
        naming=SimpleNamespace(resource_group=lambda: "example-rg", iot_hub=lambda: "legacy-hub", iot_device=lambda name: "legacy-" + name),
        clients={"iothub": SimpleNamespace(iot_hub_resource=hub_api)},
    )
    registry = MagicMock()
    registry.get_device.return_value = SimpleNamespace(authentication=SimpleNamespace(symmetric_key=SimpleNamespace(primary_key="synthetic-device-key")))
    registry.create_device_with_sas.return_value = registry.get_device.return_value
    if not exists:
        registry.get_device.side_effect = ResourceNotFoundError("DeviceNotFound")
    factory = MagicMock(return_value=registry)
    monkeypatch.setattr(azure.iot.hub, "IoTHubRegistryManager", factory)
    config = SimpleNamespace(digital_twin_name="example", iot_devices=[{"id": "sensor"}])
    options = dict(hub_name="actual-hub", hub_hostname="actual.azure-devices.net", canonical_device_ids=True) if canonical else {}
    layer_1_iot.register_iot_devices(provider, config, str(tmp_path), **options)
    hub_api.get.assert_called_once_with(resource_group_name="example-rg", resource_name="actual-hub" if canonical else "legacy-hub")
    hub_api.list_keys.assert_called_once_with(resource_group_name="example-rg", resource_name="actual-hub" if canonical else "legacy-hub")
    registry.get_device.assert_called_once_with(device_id="sensor" if canonical else "legacy-sensor")
    saved = json.loads((tmp_path / "iot_device_simulator/azure/sensor/config_generated.json").read_text())
    if canonical:
        assert saved["device_id"] == "sensor"
        assert saved["connection_string"].startswith("HostName=actual.azure-devices.net;DeviceId=sensor;")
    if exists:
        registry.create_device_with_sas.assert_not_called()
    else:
        registry.create_device_with_sas.assert_called_once_with(
            device_id="sensor" if canonical else "legacy-sensor",
            primary_key=None, secondary_key=None, status="enabled",
        )
