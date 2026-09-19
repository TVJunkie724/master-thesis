"""One fixed directed Core smoke; reuse the local sender, reader and lifecycle."""

import json

import requests

from scripts import core_live_aws as aws, core_live_azure as azure
from scripts.prepare_core_evaluation import materialize
from src.core.secure_files import atomic_write_private_bytes
from src.providers.terraform.package_builders.azure_six_layer import build_azure_six_layer_graph_apps
from src.providers.terraform.package_builders.aws_six_layer import build_aws_six_layer_bridge_context


def configure(values, runtime):
    values.update(materialize("core-small-azure-to-aws")["tfvars"])
    build_azure_six_layer_graph_apps(runtime, ("six-layer-domain", "six-layer-eventing"))
    build_aws_six_layer_bridge_context(runtime)
    atomic_write_private_bytes(runtime / "runtime.tfvars.json", json.dumps(values).encode())


def readiness(values):
    # Account preparation is outside this run: read, never enable or modify it.
    iam = aws.session(values).client("iam")
    info = iam.get_outbound_web_identity_federation_info()
    issuer = info.get("IssuerIdentifier", "")
    if info.get("JwtVendingEnabled") is not True or not issuer.startswith("https://"):
        raise RuntimeError("CORE_AWS_OUTBOUND_IDENTITY_NOT_READY")
    expected = f"sts.windows.net/{values['azure_tenant_id']}/"
    for item in iam.list_open_id_connect_providers()["OpenIDConnectProviderList"]:
        existing = iam.get_open_id_connect_provider(OpenIDConnectProviderArn=item["Arn"])
        if existing.get("Url", "").rstrip("/") == expected.rstrip("/"):
            raise RuntimeError("CORE_SHARED_AZURE_OIDC_PROVIDER_EXISTS")
    return {"aws_outbound_identity_required": True,
            "aws_outbound_identity_destinations": ["azure"],
            "aws_outbound_identity_issuer": issuer.rstrip("/")}


def inventory(values, prefix):
    result = {("pending_deletion:aws:" + key.split(":", 1)[1]
               if key.startswith("pending_deletion:") else "aws:" + key): value
              for key, value in aws.inventory(values, prefix).items()}
    result.update({"azure:" + key: value for key, value in azure.inventory(values, prefix).items()})
    iam = aws.session(values).client("iam")
    oidc_count = 0
    for item in iam.list_open_id_connect_providers()["OpenIDConnectProviderList"]:
        data = iam.get_open_id_connect_provider(OpenIDConnectProviderArn=item["Arn"])
        oidc_count += any(tag.get("Key") == "DigitalTwin" and tag.get("Value") == prefix
                          for tag in data.get("Tags", []))
    result["aws:oidc_providers"] = oidc_count
    token = azure.credential(values).get_token("https://graph.microsoft.com/.default").token
    for kind in ("applications", "servicePrincipals"):
        url = "https://graph.microsoft.com/v1.0/" + kind
        params = {"$filter": f"startswith(displayName,'{prefix} ')", "$select": "id"}
        count = 0
        while url:
            response = requests.get(url, params=params,
                                    headers={"Authorization": "Bearer " + token}, timeout=30)
            if response.status_code != 200:
                raise RuntimeError("CORE_ENTRA_INVENTORY_HTTP_" + str(response.status_code))
            data = response.json()
            count += len(data.get("value", []))
            url, params = data.get("@odata.nextLink"), None
        result["entra:" + kind] = count
    return result


def smoke(values, outputs):
    now, started = azure.send_telemetry(values, outputs)
    return {**aws.readback(values, outputs, now, started),
            "source_provider": "azure", "destination_provider": "aws"}


def diagnostics(values, outputs):
    return {"aws": aws.diagnostics(values, outputs), "azure": azure.diagnostics(values, outputs)}


stop_builds = aws.stop_builds
before_destroy = aws.before_destroy
session = aws.session
