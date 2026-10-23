from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from src.status import azure_six_layer, sdk


def context():
    return SimpleNamespace(
        project_name="project", project_path="/project",
        config=SimpleNamespace(digital_twin_name="factory", iot_devices=[{"id": "sensor"}], hierarchy={}),
        resolved_deployment_graph=SimpleNamespace(profile_ref={"id": "six-layer-eventing"}),
    )


def test_six_layer_dispatch_never_calls_legacy_azure_probe(monkeypatch):
    provider = Mock()
    monkeypatch.setattr(sdk, "_initialize_provider", lambda *_: provider)
    probe = Mock(return_value={"function_registered": True})
    monkeypatch.setattr(azure_six_layer, "probe", probe)
    ctx = context()
    assert sdk._probe(ctx, "azure", "info_l5")["status"] == "deployed"
    probe.assert_called_once_with(ctx, provider, "info_l5")
    provider.info_l5.assert_not_called()


def test_iot_status_uses_actual_hub_and_canonical_device(monkeypatch):
    import azure.iot.hub
    from src.providers.azure.layers import layer_1_iot

    bundle = {"iot_hub_name": "actual-hub-suffix", "hostname": "actual-hub-suffix.azure-devices.net"}
    monkeypatch.setattr(azure_six_layer, "load_terraform_outputs", lambda *_: {"azure_component_ingestion_output": bundle})
    key = Mock(return_value="test-only-connection")
    monkeypatch.setattr(layer_1_iot, "_get_iot_hub_connection_string", key)
    registry = Mock()
    registry.get_device.return_value = SimpleNamespace(device_id="sensor")
    monkeypatch.setattr(azure.iot.hub, "IoTHubRegistryManager", Mock(return_value=registry))
    provider = object()
    assert azure_six_layer.probe(context(), provider, "info_l1") == {"registered_devices": 1}
    key.assert_called_once_with(provider, hub_name=bundle["iot_hub_name"], hub_hostname=bundle["hostname"])
    registry.get_device.assert_called_once_with("sensor")


def test_adt_status_reads_seeded_models_and_twins(monkeypatch):
    import azure.digitaltwins.core
    from src.providers.azure.layers.layer_4_adt import six_layer_seed

    ctx = context()
    monkeypatch.setattr(azure_six_layer, "load_terraform_outputs", lambda *_: {"azure_component_twin_state_output": {"endpoint": "https://actual.digitaltwins.azure.net"}})
    client = Mock()
    client.get_digital_twin.side_effect = lambda name: {"$dtId": name}
    manager = Mock()
    manager.__enter__ = Mock(return_value=client)
    manager.__exit__ = Mock(return_value=False)
    monkeypatch.setattr(azure.digitaltwins.core, "DigitalTwinsClient", Mock(return_value=manager))
    assert azure_six_layer.probe(ctx, SimpleNamespace(credential=object()), "info_l4") == {"models": 1, "twins": 2}
    expected = six_layer_seed(ctx.config)
    assert [c.args[0] for c in client.get_digital_twin.call_args_list] == [x["$dtId"] for x in expected["twins"]]
    client.get_model.assert_called_once_with(expected["models"][0]["@id"])


@pytest.mark.parametrize("state,functions,success", [("Running", ["six-layer-visualization"], True), ("Stopped", ["six-layer-visualization"], False), ("Running", [], False)])
def test_l5_requires_actual_running_app_and_registration(monkeypatch, state, functions, success):
    monkeypatch.setattr(azure_six_layer, "load_terraform_outputs", lambda *_: {"azure_component_visualization_output": {"reader_function_name": "actual-visual"}})
    apps = Mock()
    apps.get.return_value = SimpleNamespace(name="actual-visual", state=state)
    apps.list_functions.return_value = [SimpleNamespace(name="actual-visual/"+x) for x in functions]
    provider = SimpleNamespace(clients={"web": SimpleNamespace(web_apps=apps)}, naming=SimpleNamespace(resource_group=lambda: "actual-rg"))
    if success:
        assert azure_six_layer.probe(context(), provider, "info_l5") == {"function_registered": True}
    else:
        with pytest.raises(RuntimeError):
            azure_six_layer.probe(context(), provider, "info_l5")
    apps.get.assert_called_once_with("actual-rg", "actual-visual")
