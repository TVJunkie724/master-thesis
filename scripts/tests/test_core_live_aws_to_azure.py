from datetime import datetime, timezone

import pytest

from scripts import core_live_aws_to_azure as directed
from scripts.prepare_core_runtime import prepare
from src.providers.terraform.aws_six_layer_image_publisher import image_requests as aws_image_requests
from src.providers.terraform.azure_six_layer_image_publisher import image_requests as azure_image_requests


def test_fixed_case_prepares_both_provider_packages_and_images(tmp_path):
    root = tmp_path / "runtime"
    values = prepare("azure", root)
    directed.configure(values, root)
    assert values["layer_1_provider"] == "aws"
    assert values["layer_2_provider"] == values["event_layer_provider"] == "azure"
    assert values["layer_3_hot_provider"] == "azure"
    assert values["evaluation_scope"] == "core"
    assert values["layer_4_provider"] == values["layer_5_provider"] == ""
    assert list((root / ".build/azure").glob("*.zip"))
    assert list((root / ".build/aws").glob("*.zip"))
    assert {request.name for request in aws_image_requests(root, values)} == {"bridge"}
    assert {request.name for request in azure_image_requests(root, values)} == {"storage-mover"}
    assert {(r["source_provider"], r["destination_provider"])
            for r in values["resolved_cross_cloud_routes"]} == {("aws", "azure"), ("azure", "aws")}


def test_directed_smoke_uses_aws_ingress_and_azure_readback(monkeypatch):
    now = datetime.now(timezone.utc)
    monkeypatch.setattr(directed.aws, "send_telemetry", lambda _: (now, 42.0))
    monkeypatch.setattr(directed.azure, "readback", lambda *args: {"sent": 10, "read_back": 10,
                                                                    "input_args": args[2:]})
    monkeypatch.setattr(directed.aws, "smoke", lambda *_: pytest.fail("local AWS shortcut"))
    result = directed.smoke({}, {})
    assert result["input_args"] == (now, 42.0)
    assert result["source_provider"] == "aws"
    assert result["destination_provider"] == "azure"
