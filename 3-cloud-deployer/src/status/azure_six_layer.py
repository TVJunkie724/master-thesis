"""Read-only Azure status against the deployed Six-layer output contract.

No legacy naming guesses, Grafana lookup, data mutation or data-flow claim.
"""
from src.runtime_outputs import load_terraform_outputs


def probe(context, provider, method_name):
    outputs = load_terraform_outputs(context.project_name, context.project_path)
    if method_name == "info_l1":
        from azure.iot.hub import IoTHubRegistryManager
        from src.providers.azure.layers.layer_1_iot import _get_iot_hub_connection_string

        bundle = outputs["azure_component_ingestion_output"]
        connection = _get_iot_hub_connection_string(
            provider, hub_name=bundle["iot_hub_name"], hub_hostname=bundle["hostname"]
        )
        registry = IoTHubRegistryManager(connection)
        devices = [device["id"] for device in context.config.iot_devices]
        for device_id in devices:
            device = registry.get_device(device_id)
            if device is None or device.device_id != device_id:
                raise RuntimeError("Azure registered device was not confirmed")
        return {"registered_devices": len(devices)}

    if method_name == "info_l4":
        from azure.digitaltwins.core import DigitalTwinsClient
        from src.providers.azure.layers.layer_4_adt import _merge_v2_seed

        bundle = outputs["azure_component_twin_state_output"]
        expected = _merge_v2_seed(context.config.hierarchy or {}, context.config)
        with DigitalTwinsClient(bundle["endpoint"], provider.credential) as client:
            for model in expected["models"]:
                client.get_model(model["@id"])
            for twin in expected["twins"]:
                actual = client.get_digital_twin(twin["$dtId"])
                if actual.get("$dtId") != twin["$dtId"]:
                    raise RuntimeError("Azure twin identity was not confirmed")
        return {"models": len(expected["models"]), "twins": len(expected["twins"])}

    if method_name == "info_l5":
        bundle = outputs["azure_component_visualization_output"]
        name = bundle["reader_function_name"]
        app = provider.clients["web"].web_apps.get(provider.naming.resource_group(), name)
        if app.name != name or app.state != "Running":
            raise RuntimeError("Azure L5 Function App is not running")
        functions = provider.clients["web"].web_apps.list_functions(
            provider.naming.resource_group(), name
        )
        if not any(item.name.rsplit("/", 1)[-1] == "six-layer-visualization" for item in functions):
            raise RuntimeError("Azure L5 function is not registered")
        return {"function_registered": True}

    raise ValueError("Unsupported Azure Six-layer status probe")
