from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from scripts import core_live_azure_to_aws as directed
from scripts.prepare_core_runtime import prepare
from src.providers.terraform.aws_six_layer_image_publisher import image_requests


def test_fixed_case_reuses_real_aws_and_azure_packages(tmp_path):
    root = tmp_path / "runtime"
    values = prepare("aws", root)
    directed.configure(values, root)
    assert values["layer_1_provider"] == "azure"
    assert values["layer_2_provider"] == values["event_layer_provider"] == "aws"
    assert values["layer_3_hot_provider"] == "aws"
    assert values["evaluation_scope"] == "core"
    assert values["layer_4_provider"] == values["layer_5_provider"] == ""
    assert (root / ".build/aws/core-processor.zip").is_file()
    assert list((root / ".build/azure").glob("*.zip"))
    assert {request.name for request in image_requests(root, values)} == {"storage-mover", "bridge"}
    pairs = {(r["source_provider"], r["destination_provider"])
             for r in values["resolved_cross_cloud_routes"]}
    assert pairs == {("azure", "aws"), ("aws", "azure")}


def test_directed_smoke_sends_only_through_azure_and_reads_aws(monkeypatch):
    now = datetime.now(timezone.utc)
    calls = []
    monkeypatch.setattr(directed.azure, "send_telemetry", lambda v, o: (now, 123.0))
    def readback(values, outputs, sent_at, clock_start):
        calls.append((sent_at, clock_start))
        return {"sent": 10, "read_back": 10}
    monkeypatch.setattr(directed.aws, "readback", readback)
    monkeypatch.setattr(directed.aws, "smoke", lambda *_: pytest.fail("No AWS ingress shortcut"))
    result = directed.smoke({}, {})
    assert calls == [(now, 123.0)]
    assert result == {"sent": 10, "read_back": 10,
                      "source_provider": "azure", "destination_provider": "aws"}


def test_readiness_never_enables_shared_identity_or_adopts_existing_oidc(monkeypatch):
    info = {"JwtVendingEnabled": False}
    providers = []
    iam = SimpleNamespace(
        get_outbound_web_identity_federation_info=lambda: info,
        list_open_id_connect_providers=lambda: {"OpenIDConnectProviderList": providers},
        get_open_id_connect_provider=lambda **_: {"Url": "sts.windows.net/test-tenant/"},
    )
    monkeypatch.setattr(directed.aws, "session", lambda _: SimpleNamespace(client=lambda _: iam))
    values = {"azure_tenant_id": "test-tenant"}
    with pytest.raises(RuntimeError, match="NOT_READY"):
        directed.readiness(values)
    info.update(JwtVendingEnabled=True, IssuerIdentifier="https://issuer.example/")
    assert directed.readiness(values)["aws_outbound_identity_issuer"] == "https://issuer.example"
    providers.append({"Arn": "existing"})
    with pytest.raises(RuntimeError, match="SHARED_AZURE_OIDC_PROVIDER_EXISTS"):
        directed.readiness(values)
