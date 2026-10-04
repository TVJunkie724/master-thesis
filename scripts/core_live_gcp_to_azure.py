"""Fixed GCP MQTT-ingress/Azure-Core smoke, reusing existing lifecycle operations."""

import json

from scripts import core_live_azure as azure, core_live_gcp as gcp
from scripts import core_live_azure_to_gcp as reverse
from scripts.prepare_core_evaluation import materialize
from src.core.secure_files import atomic_write_private_bytes
from src.providers.terraform.package_builders.gcp_six_layer import build_gcp_six_layer_container_contexts


image_providers = ("azure", "gcp")


def configure(values, runtime):
    values.update(materialize("core-small-gcp-to-azure")["tfvars"])
    build_gcp_six_layer_container_contexts(runtime, ("six-layer-domain", "six-layer-eventing"))
    atomic_write_private_bytes(runtime / "runtime.tfvars.json", json.dumps(values).encode())


def smoke(values, outputs):
    now, started, readiness_metrics = gcp.send_telemetry(values, outputs)
    return {**azure.readback(values, outputs, now, started), **readiness_metrics,
            "source_provider": "gcp", "destination_provider": "azure"}


readiness = reverse.readiness
inventory = reverse.inventory
stop_builds = reverse.stop_builds
diagnostics = reverse.diagnostics
