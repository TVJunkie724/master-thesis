"""Fixed AWS-ingress/Azure-Core telemetry smoke, using existing provider operations."""

import json

from scripts import core_live_aws as aws, core_live_azure as azure
from scripts import core_live_azure_to_aws as cross_cloud
from scripts.prepare_core_evaluation import materialize
from src.core.secure_files import atomic_write_private_bytes
from src.providers.terraform.package_builders.aws_eventing import build_aws_eventing_app
from src.providers.terraform.package_builders.aws_six_layer import (
    build_aws_six_layer_bridge_context,
    build_aws_six_layer_domain_app,
)


image_providers = ("aws", "azure")


def configure(values, runtime):
    values.update(materialize("core-small-aws-to-azure")["tfvars"])
    build_aws_six_layer_domain_app(runtime)
    build_aws_eventing_app(runtime)
    build_aws_six_layer_bridge_context(runtime)
    atomic_write_private_bytes(runtime / "runtime.tfvars.json", json.dumps(values).encode())


def smoke(values, outputs):
    now, started = aws.send_telemetry(values)
    return {**azure.readback(values, outputs, now, started),
            "source_provider": "aws", "destination_provider": "azure"}


def stop_builds(values, outputs):
    aws.stop_builds(values, outputs)
    azure.stop_builds(values, outputs)


def diagnostics(values, outputs):
    return {"aws": aws.diagnostics(values, outputs), "azure": azure.diagnostics(values, outputs)}


readiness = cross_cloud.readiness
inventory = cross_cloud.inventory
before_destroy = aws.before_destroy
session = aws.session
