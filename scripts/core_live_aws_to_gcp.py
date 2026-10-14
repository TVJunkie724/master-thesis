"""Fixed AWS-ingress/GCP-Core telemetry smoke with both provider inventories."""

import json

from scripts import core_live_aws as aws, core_live_gcp as gcp
from scripts.prepare_core_evaluation import materialize
from src.core.secure_files import atomic_write_private_bytes
from src.providers.terraform.package_builders.aws_eventing import build_aws_eventing_app
from src.providers.terraform.package_builders.aws_six_layer import (
    build_aws_six_layer_bridge_context,
    build_aws_six_layer_domain_app,
)


image_providers = ("aws", "gcp")


def configure(values, runtime):
    values.update(materialize("core-small-aws-to-gcp")["tfvars"])
    build_aws_six_layer_domain_app(runtime)
    build_aws_eventing_app(runtime)
    build_aws_six_layer_bridge_context(runtime)
    atomic_write_private_bytes(runtime / "runtime.tfvars.json", json.dumps(values).encode())


def readiness(values):
    iam = aws.session(values).client("iam")
    info = iam.get_outbound_web_identity_federation_info()
    issuer = info.get("IssuerIdentifier", "")
    if info.get("JwtVendingEnabled") is not True or not issuer.startswith("https://"):
        raise RuntimeError("CORE_AWS_OUTBOUND_IDENTITY_NOT_READY")
    # AWS accepts Google's built-in issuer for the reverse route; no provider
    # registration or account-wide change belongs to this scenario.
    return {"aws_outbound_identity_required": True,
            "aws_outbound_identity_destinations": ["gcp"],
            "aws_outbound_identity_issuer": issuer.rstrip("/")}


def inventory(values, prefix):
    result = {("pending_deletion:aws:" + key.split(":", 1)[1]
               if key.startswith("pending_deletion:") else "aws:" + key): value
              for key, value in aws.inventory(values, prefix).items()}
    result.update({("pending_deletion:gcp:" + key.split(":", 1)[1]
                   if key.startswith("pending_deletion:") else "gcp:" + key): value
                  for key, value in gcp.inventory(values, prefix).items()})
    iam = aws.session(values).client("iam")
    oidc_count = 0
    for item in iam.list_open_id_connect_providers()["OpenIDConnectProviderList"]:
        data = iam.get_open_id_connect_provider(OpenIDConnectProviderArn=item["Arn"])
        oidc_count += any(tag.get("Key") == "DigitalTwin" and tag.get("Value") == prefix
                          for tag in data.get("Tags", []))
    result["aws:oidc_providers"] = oidc_count
    return result


def smoke(values, outputs):
    now, started = aws.send_telemetry(values)
    return {**gcp.readback(values, outputs, now, started),
            "source_provider": "aws", "destination_provider": "gcp"}


def stop_builds(values, outputs):
    aws.stop_builds(values, outputs)
    gcp.stop_builds(values, outputs)


def diagnostics(values, outputs):
    return {"aws": aws.diagnostics(values, outputs), "gcp": gcp.diagnostics(values, outputs)}


before_destroy = aws.before_destroy
session = aws.session
