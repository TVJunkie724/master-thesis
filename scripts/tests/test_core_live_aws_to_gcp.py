from datetime import datetime, timezone
from types import SimpleNamespace

from scripts import core_live_aws_to_gcp as directed
from scripts.prepare_core_runtime import prepare
from src.providers.terraform.aws_six_layer_image_publisher import image_requests as aws_image_requests
from src.providers.terraform.gcp_six_layer_image_publisher import image_requests as gcp_image_requests


def test_fixed_case_prepares_source_and_target_images(tmp_path):
    root = tmp_path / "runtime"
    values = prepare("gcp", root)
    directed.configure(values, root)
    assert values["layer_1_provider"] == "aws"
    assert values["layer_2_provider"] == values["event_layer_provider"] == "google"
    assert values["layer_3_hot_provider"] == "google"
    assert values["evaluation_scope"] == "core"
    assert values["layer_4_provider"] == values["layer_5_provider"] == ""
    assert {request.name for request in aws_image_requests(root, values)} == {"bridge"}
    assert {request.name for request in gcp_image_requests(root, values)} == {
        "platform", "event-runtime", "processor-extension", "storage-mover",
    }


def test_directed_smoke_uses_aws_ingress_and_gcp_readback(monkeypatch):
    now = datetime.now(timezone.utc)
    monkeypatch.setattr(directed.aws, "send_telemetry", lambda _: (now, 42.0))
    monkeypatch.setattr(directed.gcp, "readback", lambda *args: {"sent": 10, "read_back": 10,
                                                                  "input_args": args[2:]})
    monkeypatch.setattr(directed.gcp, "smoke", lambda *_: (_ for _ in ()).throw(AssertionError("local GCP shortcut")))
    result = directed.smoke({}, {})
    assert result["input_args"] == (now, 42.0)
    assert result["source_provider"] == "aws"
    assert result["destination_provider"] == "gcp"


def test_readiness_uses_existing_outbound_issuer_without_changes(monkeypatch):
    iam = SimpleNamespace(
        get_outbound_web_identity_federation_info=lambda: {
            "JwtVendingEnabled": True, "IssuerIdentifier": "https://issuer.example/",
        },
    )
    monkeypatch.setattr(directed.aws, "session", lambda _: SimpleNamespace(client=lambda _: iam))
    assert directed.readiness({})["aws_outbound_identity_destinations"] == ["gcp"]
