import json
import signal
import time

import pytest

from scripts.run_core_evaluation import (
    CoreDeadlineExceeded,
    Terraform,
    apply_smoke_bounds,
    deadline,
    functional_seconds,
    reserve,
    safe_failure_metrics,
    terraform_resource_timings,
)
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
    with pytest.raises(CoreDeadlineExceeded, match="CORE_DEADLINE"):
        with deadline(0.01):
            time.sleep(0.1)
    assert signal.getsignal(signal.SIGALRM) == previous
    assert signal.getitimer(signal.ITIMER_REAL)[0] == 0


def test_global_deadline_is_not_retried_as_an_http_timeout(monkeypatch):
    def slow_request(*_args, **_kwargs):
        # Socket libraries translate OSError (including built-in TimeoutError)
        # into request timeouts. The whole-run deadline must escape that path.
        try:
            time.sleep(0.1)
        except OSError as exc:
            raise core_live_azure.requests.ReadTimeout() from exc

    monkeypatch.setattr(core_live_azure.requests, "get", slow_request)
    with pytest.raises(CoreDeadlineExceeded, match="CORE_DEADLINE"):
        with deadline(0.01):
            core_live_azure.poll_points({"access_url": "https://example.test"}, "key", {}, attempts=2)


def test_provider_deadlines_are_bounded_and_give_slow_clouds_more_time():
    assert functional_seconds("aws", None) == 600
    assert functional_seconds("azure", None) == 1200
    assert functional_seconds("gcp", None) == 1800
    assert functional_seconds("gcp", 900) == 900
    with pytest.raises(ValueError, match="DEADLINE_OUT_OF_RANGE"):
        functional_seconds("gcp", 3601)


def test_terraform_resource_timings_are_secret_free_and_structured(tmp_path):
    log = tmp_path / "terraform.log"
    log.write_text(
        'azurerm_resource_group.core: Creation complete after 1m33s [id=/secret/id]\n'
        'module.core.google_cloud_run_v2_service.reader[0]: Modifications complete after 4.5s [id=x]\n'
        'aws_s3_bucket.core: Destruction complete after 2s [id=secret]\n'
    )

    assert terraform_resource_timings(log) == [
        {"resource": "azurerm_resource_group.core", "operation": "create", "duration_seconds": 93.0},
        {"resource": "module.core.google_cloud_run_v2_service.reader[0]", "operation": "update", "duration_seconds": 4.5},
        {"resource": "aws_s3_bucket.core", "operation": "destroy", "duration_seconds": 2.0},
    ]
    assert "/secret/id" not in json.dumps(terraform_resource_timings(log))


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

    observation = {}
    assert core_live_azure.poll_points(
        {"access_url": "https://example.test"}, "key", {}, attempts=2, pause_seconds=0,
        observation=observation,
    ) == points
    assert observation["attempts"] == 2
    assert observation["timeout_count"] == 1
    assert observation["wait_seconds"] >= 0


def test_azure_failed_readback_retains_only_safe_wait_metrics(monkeypatch):
    monkeypatch.setattr(
        core_live_azure.requests,
        "get",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(core_live_azure.requests.ReadTimeout()),
    )
    monkeypatch.setattr(core_live_azure.time, "sleep", lambda _seconds: None)

    with pytest.raises(RuntimeError, match="CORE_READBACK_TIMEOUT") as caught:
        core_live_azure.poll_points(
            {"access_url": "https://example.test"}, "key", {}, attempts=2, pause_seconds=0,
        )

    assert safe_failure_metrics(caught.value) == {
        "readback_poll_attempts": 2,
        "readback_timeout_count": 2,
        "readback_wait_seconds": pytest.approx(0, abs=1),
    }
    caught.value.safe_metrics["secret"] = "must-not-be-copied"
    assert "secret" not in safe_failure_metrics(caught.value)
