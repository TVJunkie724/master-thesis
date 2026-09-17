import json
import signal
import time

import pytest

from scripts.run_core_evaluation import Terraform, apply_smoke_bounds, deadline, reserve
from scripts import core_live_aws, core_live_azure


def test_allowance_is_cumulative_and_rejected_without_overwriting(tmp_path):
    path = tmp_path / "ledger.json"
    reserve(path, "aws", "one", 2, 1)
    reserve(path, "azure", "other", 2, 1)
    reserve(path, "aws", "two", 2, 1)
    previous = path.read_bytes()
    with pytest.raises(RuntimeError, match="ALLOWANCE_EXHAUSTED"):
        reserve(path, "aws", "three", 2, 1)
    assert path.read_bytes() == previous
    assert len(json.loads(previous)) == 3
    assert path.stat().st_mode & 0o077 == 0


def test_live_azure_core_uses_free_iot_ingress_without_changing_other_providers():
    azure = {"azure_iot_hub_sku": "S1", "azure_iot_hub_capacity": 1}
    apply_smoke_bounds("azure", azure)
    assert azure == {"azure_iot_hub_sku": "F1", "azure_iot_hub_capacity": 1}

    aws = {"azure_iot_hub_sku": "S1", "azure_iot_hub_capacity": 1}
    apply_smoke_bounds("aws", aws)
    assert aws == {"azure_iot_hub_sku": "S1", "azure_iot_hub_capacity": 1}


def test_deadline_interrupts_and_restores_handler():
    previous = signal.getsignal(signal.SIGALRM)
    with pytest.raises(TimeoutError, match="CORE_DEADLINE"):
        with deadline(0.01):
            time.sleep(0.1)
    assert signal.getsignal(signal.SIGALRM) == previous
    assert signal.getitimer(signal.ITIMER_REAL)[0] == 0


def test_terraform_failure_does_not_emit_raw_diagnostic(tmp_path, monkeypatch):
    class Process:
        def __init__(self, command, **kwargs):
            kwargs["stdout"].write(b"sensitive diagnostic")
        def wait(self):
            return 1
    monkeypatch.setattr("scripts.run_core_evaluation.subprocess.Popen", Process)
    with pytest.raises(RuntimeError, match="TERRAFORM_APPLY_FAILED_LOG_01") as error:
        Terraform(tmp_path, {}).run("apply")
    assert "sensitive" not in str(error.value)


def test_sns_archive_cleanup_only_touches_owned_state(monkeypatch):
    changes = []
    class Session:
        def client(self, _service):
            return self
        def set_topic_attributes(self, **kwargs):
            changes.append(kwargs)
    monkeypatch.setattr(core_live_aws, "session", lambda _: Session())
    owned = "arn:aws:sns:eu-central-1:123456789012:coreaws-test-domain.fifo"
    state = {"resources": [{"mode": "managed", "type": "aws_sns_topic", "instances": [
        {"attributes": {"arn": owned, "archive_policy": "configured"}}]}]}
    core_live_aws.before_destroy({"digital_twin_name": "coreaws-test"}, state)
    assert changes == [{"TopicArn": owned, "AttributeName": "ArchivePolicy", "AttributeValue": "{}"}]
    with pytest.raises(RuntimeError, match="OWNERSHIP_MISMATCH"):
        core_live_aws.before_destroy({"digital_twin_name": "unrelated"}, state)
    assert len(changes) == 1


def test_azure_readback_poll_tolerates_flex_cold_start(monkeypatch):
    points = [{"value": number} for number in range(10)]

    class Response:
        status_code = 200

        def json(self):
            return {"points": points}

    responses = iter((core_live_azure.requests.ReadTimeout(), Response()))

    def get(*_args, **_kwargs):
        response = next(responses)
        if isinstance(response, Exception):
            raise response
        return response

    monkeypatch.setattr(core_live_azure.requests, "get", get)
    monkeypatch.setattr(core_live_azure.time, "sleep", lambda _seconds: None)

    assert core_live_azure.poll_points(
        {"access_url": "https://example.test"}, "key", {}, attempts=2, pause_seconds=0
    ) == points
