from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from scripts import core_live_gcp_to_aws, core_live_gcp_to_azure
from scripts.prepare_core_runtime import prepare
from src.providers.terraform.aws_six_layer_image_publisher import image_requests as aws_images
from src.providers.terraform.azure_six_layer_image_publisher import image_requests as azure_images
from src.providers.terraform.gcp_six_layer_image_publisher import image_requests as gcp_images


@pytest.mark.parametrize("directed,target,images,expected", [
    (core_live_gcp_to_aws, "aws", aws_images, {"storage-mover", "bridge"}),
    (core_live_gcp_to_azure, "azure", azure_images, {"storage-mover"}),
])
def test_fixed_cases_package_only_required_source_and_destination_images(
        tmp_path, directed, target, images, expected):
    runtime = tmp_path / "runtime"
    values = prepare(target, runtime)
    directed.configure(values, runtime)
    assert values["layer_1_provider"] == "google"
    assert values["layer_2_provider"] == values["event_layer_provider"] == target
    assert values["evaluation_scope"] == "core"
    assert values["layer_4_provider"] == values["layer_5_provider"] == ""
    assert {request.name for request in gcp_images(runtime, values)} == {"platform"}
    assert {request.name for request in images(runtime, values)} == expected
    assert {(route["source_provider"], route["destination_provider"])
            for route in values["resolved_cross_cloud_routes"]} == {("gcp", target), (target, "gcp")}


@pytest.mark.parametrize("directed,target", [
    (core_live_gcp_to_aws, "aws"), (core_live_gcp_to_azure, "azure"),
])
def test_directed_smoke_uses_mqtt_source_and_authenticated_destination_reader(
        monkeypatch, directed, target):
    now = datetime.now(timezone.utc)
    outputs = {"mqtt": "source-only"}
    monkeypatch.setattr(directed.gcp, "send_telemetry", lambda values, actual:
                        (now, 42.0, {"mqtt_connect_attempts": 2}) if actual == outputs else None)
    monkeypatch.setattr(directed.gcp, "smoke", lambda *_: pytest.fail("local GCP smoke bypass"))
    reader = directed.aws if target == "aws" else directed.azure
    monkeypatch.setattr(reader, "readback", lambda *args:
                        {"sent": 10, "read_back": 10, "input_args": args[2:]})
    result = directed.smoke({}, outputs)
    assert result["input_args"] == (now, 42.0)
    assert result["source_provider"] == "gcp"
    assert result["destination_provider"] == target
    assert result["mqtt_connect_attempts"] == 2


@pytest.mark.parametrize("status,state,active,pending", [
    (404, None, 0, 0), (200, "ACTIVE", 1, 0), (200, "DELETED", 0, 1),
])
def test_aws_destination_inventory_includes_reverse_route_identity_pool(
        monkeypatch, status, state, active, pending):
    directed = core_live_gcp_to_aws
    monkeypatch.setattr(directed.reverse, "inventory", lambda *_: {"aws:resources": 0})
    requested = []
    def get(url, **_):
        requested.append(url)
        return SimpleNamespace(status_code=status, json=lambda: {"state": state})
    monkeypatch.setattr(directed.gcp, "client", lambda _: SimpleNamespace(get=get))
    result = directed.inventory({"gcp_project_id": "example-project"}, "coreg2a-12345678")
    assert result["gcp:workload_identity_pools"] == active
    assert result.get("pending_deletion:gcp:workload_identity_pools", 0) == pending
    assert requested[0].endswith("/coreg2a-12345678-aws-bridge")
