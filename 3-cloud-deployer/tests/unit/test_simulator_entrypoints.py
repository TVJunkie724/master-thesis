"""Import smoke tests for provider simulator runtime entrypoints."""

import importlib

import pytest


@pytest.mark.parametrize(
    "module",
    [
        "src.iot_device_simulator.aws.main",
        "src.iot_device_simulator.azure.main",
        "src.iot_device_simulator.google.main",
    ],
)
def test_provider_entrypoint_imports_with_production_dependencies(module):
    assert importlib.import_module(module) is not None
