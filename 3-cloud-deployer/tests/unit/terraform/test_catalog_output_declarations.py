"""Every catalog output must exist even if a fixture selects another provider."""
import json
import re
from pathlib import Path

from src.terraform_inputs.graph_translator import OUTPUT_PATTERN


def test_aws_grafana_catalog_resources_are_declared():
    source = Path(__file__).resolve().parents[3] / "src"
    catalog = json.loads((source / "contracts/generated/architecture-profiles/definitions/component-catalogs/six-layer-eventing/1/catalog.json").read_text())
    declared = {
        f"{kind}.{name}" for path in (source / "terraform").rglob("*.tf")
        for kind, name in re.findall(r'resource\s+"([^"]+)"\s+"([^"]+)"', path.read_text())
    }

    def resources(value):
        if isinstance(value, dict):
            yield from value.get("resource_addresses", [])
            for child in value.values():
                yield from resources(child)
        elif isinstance(value, list):
            for child in value:
                yield from resources(child)

    required = {address for address in resources(catalog) if "aws_six_layer_grafana" in address or address.startswith("aws_grafana_")}
    assert required
    assert required <= declared, sorted(required - declared)


def test_all_six_layer_catalog_outputs_are_declared():
    source = Path(__file__).resolve().parents[3] / "src"
    catalog = json.loads((source / "contracts/generated/architecture-profiles/definitions/component-catalogs/six-layer-eventing/1/catalog.json").read_text())
    declared = {
        name for path in (source / "terraform").rglob("*.tf")
        for name in OUTPUT_PATTERN.findall(path.read_text())
    }

    def outputs(value):
        if isinstance(value, dict):
            if "terraform_output" in value:
                yield value["terraform_output"]
            for child in value.values():
                yield from outputs(child)
        elif isinstance(value, list):
            for child in value:
                yield from outputs(child)

    required = set(outputs(catalog))
    assert required
    assert required <= declared, sorted(required - declared)
