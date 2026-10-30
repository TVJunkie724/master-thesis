import importlib.util
from datetime import datetime, timedelta
import io
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from botocore.exceptions import ClientError
import pytest

from scripts import core_live_aws_roundtrip as cut
from scripts.run_core_evaluation import run


@pytest.fixture
def values(tmp_path):
    return {"project_path": str(tmp_path), "digital_twin_name": "coreaws-test", "aws_region": "eu-central-1"}


def test_one_rule_uses_real_parser_without_new_layers(values, tmp_path):
    cut.configure(values, tmp_path)
    assert len(values["events"]) == 1
    assert json.loads((tmp_path / "config_iot_devices.json").read_text()) == [{"id": "core-sensor"}]
    path = Path(__file__).resolve().parents[2] / "3-cloud-deployer/src/providers/aws/lambda_functions/six-layer-domain/handler.py"
    spec = importlib.util.spec_from_file_location("roundtrip_domain", path)
    domain = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(domain)
    assert domain._condition_matches(values["events"][0]["condition"], {"value": 42})
    assert not domain._condition_matches(values["events"][0]["condition"], {"value": 41})
    assert "layer_4_provider" not in values


def test_directed_roundtrip_rejected_before_files(tmp_path):
    with pytest.raises(ValueError, match="only local providers"):
        run(SimpleNamespace(provider="aws", command_roundtrip=True, azure_to_aws=True, output_dir=tmp_path / "run"))
    assert not (tmp_path / "run").exists()


def test_certificate_journal_precedes_attachment_and_excludes_secrets(values):
    client = Mock()
    client.create_keys_and_certificate.return_value = {"certificateId": "cert-id", "certificateArn": "cert-arn",
                                                     "keyPair": {"PrivateKey": "do-not-store"}}
    cut.JournaledIoT(client, values).create_keys_and_certificate(setAsActive=True)
    journal = cut._journal(values)
    assert json.loads(journal.read_text()) == {"certificate_id": "cert-id", "certificate_arn": "cert-arn"}
    assert journal.stat().st_mode & 0o077 == 0
    client.attach_thing_principal.assert_not_called()


def test_journal_failure_compensates_certificate(values, monkeypatch):
    client = Mock()
    client.create_keys_and_certificate.return_value = {"certificateId": "id", "certificateArn": "arn"}
    monkeypatch.setattr(cut, "save", Mock(side_effect=OSError))
    with pytest.raises(OSError):
        cut.JournaledIoT(client, values).create_keys_and_certificate()
    client.update_certificate.assert_called_once_with(certificateId="id", newStatus="INACTIVE")
    client.delete_certificate.assert_called_once_with(certificateId="id", forceDelete=True)


def iot_for_cleanup(values, monkeypatch):
    cut.save(cut._journal(values), {"certificate_id": "id", "certificate_arn": "arn"})
    client = Mock()
    client.list_thing_principals.return_value = {"principals": ["arn"]}
    client.list_principal_things.return_value = {"things": ["coreaws-test-core-sensor"]}
    client.list_attached_policies.return_value = {"policies": [{"policyName": "coreaws-test-core-sensor-policy"}]}
    monkeypatch.setattr(cut, "session", lambda _: SimpleNamespace(client=lambda _: client))
    return client


def test_cleanup_removes_owned_certificate_policy_and_thing(values, monkeypatch):
    client = iot_for_cleanup(values, monkeypatch)
    cut.cleanup_device(values)
    client.detach_policy.assert_called_once_with(policyName="coreaws-test-core-sensor-policy", target="arn")
    client.delete_certificate.assert_called_once_with(certificateId="id", forceDelete=True)
    client.delete_thing.assert_called_once_with(thingName="coreaws-test-core-sensor")
    client.delete_policy.assert_called_once_with(policyName="coreaws-test-core-sensor-policy")


@pytest.mark.parametrize("method,result", [
    ("list_thing_principals", {"principals": ["foreign"]}),
    ("list_principal_things", {"things": ["foreign"]}),
    ("list_attached_policies", {"policies": [{"policyName": "foreign"}]}),
])
def test_cleanup_rejects_foreign_attachments(values, monkeypatch, method, result):
    client = iot_for_cleanup(values, monkeypatch)
    getattr(client, method).return_value = result
    with pytest.raises(RuntimeError, match="OWNERSHIP_MISMATCH"):
        cut.cleanup_device(values)
    client.delete_certificate.assert_not_called()
    client.delete_thing.assert_not_called()


@pytest.mark.parametrize("method,result", [
    ("list_thing_principals", {"principals": ["arn"], "nextToken": "more"}),
    ("list_principal_things", {"things": [], "nextToken": "more"}),
    ("list_attached_policies", {"policies": [], "nextMarker": "more"}),
])
def test_cleanup_rejects_truncated_ownership_inventory(values, monkeypatch, method, result):
    client = iot_for_cleanup(values, monkeypatch)
    getattr(client, method).return_value = result
    with pytest.raises(RuntimeError, match="INVENTORY_TRUNCATED"):
        cut.cleanup_device(values)
    client.delete_certificate.assert_not_called()


def test_permission_failure_is_not_zero_inventory():
    client = Mock(side_effect=ClientError({"Error": {"Code": "AccessDeniedException"}}, "GetPolicy"))
    with pytest.raises(ClientError):
        cut._absent(client)


def test_sns_pre_destroy_still_runs_after_device_cleanup_failure(values, monkeypatch):
    monkeypatch.setattr(cut, "cleanup_device", Mock(side_effect=RuntimeError("failed")))
    original = Mock()
    monkeypatch.setattr(cut.core, "before_destroy", original)
    with pytest.raises(RuntimeError):
        cut.before_destroy(values, {})
    original.assert_called_once_with(values, {})


@pytest.mark.parametrize("case", ["pass", "no_receipt", "wrong_trace", "unrelated_history", "negative_time"])
def test_smoke_requires_actual_receipt_and_exact_history(values, monkeypatch, case):
    from src.providers.terraform import aws_deployer
    from src.iot_device_simulator.aws import globals as config, transmission
    aws = Mock()
    iot, reader, sts = Mock(), Mock(), Mock()
    aws.client.side_effect = lambda name: {"iot": iot, "lambda": reader, "sts": sts}[name]
    sts.get_caller_identity.return_value = {"Account": "test-account"}
    iot.describe_endpoint.return_value = {"endpointAddress": "test-endpoint"}
    monkeypatch.setattr(cut, "session", lambda _: aws)
    monkeypatch.setattr(cut.time, "sleep", lambda _: None)
    def register(_provider, root, *_args):
        cut.save(root / "iot_device_simulator/aws/core-sensor/config_generated.json", {
            "device_id": "core-sensor", "cert_path": "cert", "key_path": "key", "root_ca_path": "ca"})
    monkeypatch.setattr(aws_deployer, "_register_iot_device", register)
    previous = config.config
    def listen(timeout, *, telemetry_payload):
        assert timeout == 300
        assert config.config["device_id"] == "core-sensor"
        now = datetime.fromisoformat(telemetry_payload["payload"]["event_time"])
        trace = telemetry_payload["source_sequence"]
        for stage, stamp in [("simulator_sent", now), ("simulator_command_received", now + timedelta(seconds=-1 if case == "negative_time" else 1))]:
            print("T2MC_CHECKPOINT " + json.dumps({"stage": stage, "trace_id": "TRACE-OTHER123" if case == "wrong_trace" else trace,
                                                   "observed_at": stamp.isoformat()}))
        point_time = now + timedelta(seconds=1) if case == "unrelated_history" else now
        reader.invoke.side_effect = lambda **_: {"Payload": io.BytesIO(json.dumps({"statusCode": 200,
            "body": json.dumps({"points": [{"event_time": point_time.isoformat(), "value": 42}]})}).encode())}
        return case != "no_receipt"
    monkeypatch.setattr(transmission, "listen_for_command", listen)
    outputs = {"aws_component_storage_read_access_output": {"reader_function_name": "reader"}}
    if case == "pass":
        result = cut.smoke(values, outputs)
        assert result["roundtrip_seconds"] == 1
        assert result["command_received"] == result["read_back"] == 1
    else:
        with pytest.raises(RuntimeError, match="COMMAND_"):
            cut.smoke(values, outputs)
    assert config.config is previous
    assert (Path(values["project_path"]) / "simulator.log").stat().st_mode & 0o077 == 0
