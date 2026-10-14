"""Fixed GCP MQTT-ingress/AWS-Core smoke with independent two-cloud inventory."""

import json

from scripts import core_live_aws as aws, core_live_gcp as gcp
from scripts import core_live_aws_to_gcp as reverse
from scripts.prepare_core_evaluation import materialize
from src.core.secure_files import atomic_write_private_bytes
from src.providers.terraform.package_builders.aws_six_layer import build_aws_six_layer_bridge_context
from src.providers.terraform.package_builders.gcp_six_layer import build_gcp_six_layer_container_contexts


image_providers = ("aws", "gcp")


def configure(values, runtime):
    values.update(materialize("core-small-gcp-to-aws")["tfvars"])
    build_gcp_six_layer_container_contexts(runtime, ("six-layer-domain", "six-layer-eventing"))
    build_aws_six_layer_bridge_context(runtime)
    atomic_write_private_bytes(runtime / "runtime.tfvars.json", json.dumps(values).encode())


def smoke(values, outputs):
    now, started, readiness_metrics = gcp.send_telemetry(values, outputs)
    return {**aws.readback(values, outputs, now, started), **readiness_metrics,
            "source_provider": "gcp", "destination_provider": "aws"}


def inventory(values, prefix):
    result = reverse.inventory(values, prefix)
    pool = prefix[:16] + "-aws-bridge"
    url = ("https://iam.googleapis.com/v1/projects/" + values["gcp_project_id"]
           + "/locations/global/workloadIdentityPools/" + pool)
    response = gcp.client(values).get(url, timeout=45)
    if response.status_code == 404:
        result["gcp:workload_identity_pools"] = 0
    elif response.status_code == 200:
        deleted = response.json().get("state") == "DELETED"
        result["gcp:workload_identity_pools"] = 0 if deleted else 1
        if deleted:
            result["pending_deletion:gcp:workload_identity_pools"] = 1
    else:
        raise RuntimeError("CORE_GCP_POOL_INVENTORY_HTTP_" + str(response.status_code))
    return result


readiness = reverse.readiness
stop_builds = reverse.stop_builds
diagnostics = reverse.diagnostics
before_destroy = aws.before_destroy
session = aws.session
