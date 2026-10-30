import json
import signal
import ssl
import time
from urllib.parse import urlparse

import pytest

from scripts.run_core_evaluation import (
    CoreDeadlineExceeded,
    GCP_MQTT_KUBERNETES_ADDRESSES,
    Terraform,
    azure_flex_kudu_restart,
    azure_iothub_concurrent_write,
    deadline,
    functional_seconds,
    reserve,
    retry_create_count,
    safe_failure_metrics,
    terraform_resource_timings,
)
from scripts import core_live_aws, core_live_azure, core_live_gcp


@pytest.mark.parametrize("denied", [False, True])
def test_aws_inventory_includes_scoped_grafana_reader_users(monkeypatch, denied):
    class Client:
        def can_paginate(self, operation):
            return False

        def __getattr__(self, operation):
            def call(**kwargs):
                if operation == "list_users":
                    assert kwargs == {"PathPrefix": "/twin2multicloud/grafana/"}
                    if denied:
                        raise RuntimeError("inventory denied")
                    return {"Users": [{"UserName": "test-grafana-reader-abcd"}, {"UserName": "other-grafana-reader-abcd"}]}
                return {"Vpcs": []} if operation == "describe_vpcs" else {}
            return call

    class Session:
        def client(self, *_args, **_kwargs):
            return Client()

    monkeypatch.setattr(core_live_aws, "session", lambda _: Session())
    if denied:
        with pytest.raises(RuntimeError, match="inventory denied"):
            core_live_aws.inventory({}, "test")
    else:
        assert core_live_aws.inventory({}, "test")["iam:list_users"] == 1


def test_allowance_is_cumulative_and_rejected_without_overwriting(tmp_path):
    path = tmp_path / "ledger.json"
    reserve(path, "aws", "one", 2, 1)
    reserve(path, "azure", "other", 2, 1)
    previous = path.read_bytes()
    with pytest.raises(RuntimeError, match="ALLOWANCE_EXHAUSTED"):
        reserve(path, "gcp", "three", 2, 1)
    assert path.read_bytes() == previous
    assert len(json.loads(previous)) == 2
    assert path.stat().st_mode & 0o077 == 0


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
        'terraform_data.validated_extension_package["poc-action@1.0.0"]: Creation complete after 0s [id=secret]\n'
    )

    assert terraform_resource_timings(log) == [
        {"resource": "azurerm_resource_group.core", "operation": "create", "duration_seconds": 93.0},
        {"resource": "module.core.google_cloud_run_v2_service.reader[0]", "operation": "update", "duration_seconds": 4.5},
        {"resource": "aws_s3_bucket.core", "operation": "destroy", "duration_seconds": 2.0},
        {"resource": 'terraform_data.validated_extension_package["poc-action@1.0.0"]', "operation": "create", "duration_seconds": 0.0},
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


def test_azure_kudu_retry_is_only_for_one_package_restart(tmp_path):
    log = tmp_path / "command-01.log"
    log.write_text(
        'Error: waiting for creation of Template Deployment: '
        '[KuduSpecializer] Kudu has been restarted during deployment\n'
        '  with module.azure_six_layer_processing_package[0].'
        'azurerm_resource_group_template_deployment.publish,\n'
    )
    assert azure_flex_kudu_restart(log)
    log.write_text(log.read_text() + 'Error: unrelated provider failure\n')
    assert not azure_flex_kudu_restart(log)
    log.write_text('Error: CORE_DEADLINE\n')
    assert not azure_flex_kudu_restart(log)


def test_azure_iothub_retry_is_only_for_one_policy_race(tmp_path):
    log = tmp_path / "command-01.log"
    log.write_text(
        'Error: updating Shared Access Policy: Code="ConflictingConcurrentWriteNotAllowed"\n'
        '  with azurerm_iothub_shared_access_policy.azure_six_layer_ingress[0],\n'
    )
    assert azure_iothub_concurrent_write(log)
    log.write_text(log.read_text() + 'Error: unrelated provider failure\n')
    assert not azure_iothub_concurrent_write(log)
    log.write_text('Error: Code="ConflictingConcurrentWriteNotAllowed"\n'
                   '  with azurerm_iothub.azure_azure_iot_hub[0],\n')
    assert not azure_iothub_concurrent_write(log)


def test_retry_plan_can_only_finish_original_creates():
    approved = {"module.azure_package.publish", "azurerm_resource_group.main"}
    def plan(address, actions):
        return {"resource_changes": [{"mode": "managed", "address": address,
                                      "change": {"actions": actions}}]}

    assert retry_create_count(plan("module.azure_package.publish", ["create"]), approved) == 1
    assert retry_create_count(plan("module.azure_package.publish", ["no-op"]), approved) == 0
    for address, actions in (("module.azure_package.publish", ["delete", "create"]),
                             ("module.azure_package.publish", ["update"]),
                             ("azurerm_resource_group.unreviewed", ["create"])):
        with pytest.raises(RuntimeError, match="CORE_RETRY_PLAN_CHANGED_SCOPE"):
            retry_create_count(plan(address, actions), approved)


def test_gcp_mqtt_stage_cannot_modify_cloud_resources_or_add_other_kubernetes_objects():
    def plan(address, actions):
        return {"resource_changes": [{"mode": "managed", "address": address,
                                      "change": {"actions": actions}}]}
    assert len(GCP_MQTT_KUBERNETES_ADDRESSES) == 9
    for address in GCP_MQTT_KUBERNETES_ADDRESSES:
        assert retry_create_count(plan(address, ["create"]), GCP_MQTT_KUBERNETES_ADDRESSES) == 1
    for address, actions in (("google_container_cluster.other", ["create"]),
                             ("google_container_node_pool.main", ["update"]),
                             ("kubernetes_secret_v1.other[0]", ["create"])):
        with pytest.raises(RuntimeError, match="CORE_RETRY_PLAN_CHANGED_SCOPE"):
            retry_create_count(plan(address, actions), GCP_MQTT_KUBERNETES_ADDRESSES)


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


def test_azure_diagnostics_query_both_deployment_workspaces(monkeypatch):
    def arm(_values, _method, path):
        if "/resources?" in path:
            return {"value": [
                {"type": "Microsoft.OperationalInsights/workspaces", "id": "/containers"},
                {"type": "Microsoft.OperationalInsights/workspaces", "id": "/functions"},
            ]}
        return {"properties": {"customerId": path.split("?")[0].strip("/")}}

    class Token:
        token = "test-only"

        def get_token(self, _scope):
            return self

    class Response:
        status_code = 200

        def json(self):
            return {"tables": []}

    queried = []

    def post(url, **_kwargs):
        queried.append(url)
        return Response()

    monkeypatch.setattr(core_live_azure, "arm", arm)
    monkeypatch.setattr(core_live_azure, "credential", lambda _values: Token())
    monkeypatch.setattr(core_live_azure.requests, "post", post)
    result = core_live_azure.diagnostics(
        {"azure_subscription_id": "test"}, {"azure_six_layer_resource_group_name": "core-test"},
    )
    assert len(result["workspaces"]) == 2
    assert queried == [
        "https://api.loganalytics.io/v1/workspaces/containers/query",
        "https://api.loganalytics.io/v1/workspaces/functions/query",
    ]


def test_gcp_connect_waits_for_load_balancer_but_never_ignores_tls(monkeypatch):
    class Connection:
        errors = iter([TimeoutError(), ConnectionRefusedError(), None])

        def connect(self, _host, _port, _keepalive):
            error = next(self.errors)
            if error:
                raise error

    monkeypatch.setattr(core_live_gcp.time, "sleep", lambda _: None)
    connection = Connection()
    endpoint = urlparse("mqtts://example.test:8883")
    assert core_live_gcp.connect_mqtt(connection, endpoint)["mqtt_connect_attempts"] == 3
    connection.errors = iter([ssl.SSLCertVerificationError()])
    with pytest.raises(ssl.SSLCertVerificationError):
        core_live_gcp.connect_mqtt(connection, endpoint)
    connection.errors = iter([CoreDeadlineExceeded("CORE_DEADLINE")])
    with pytest.raises(CoreDeadlineExceeded):
        core_live_gcp.connect_mqtt(connection, endpoint)


def test_gcp_connect_timeout_is_bounded_and_retains_wait_metrics(monkeypatch):
    class Connection:
        def connect(self, _host, _port, _keepalive):
            raise TimeoutError()

    monkeypatch.setattr(core_live_gcp.time, "sleep", lambda _: None)
    with pytest.raises(RuntimeError, match="CORE_MQTT_CONNECT_TIMEOUT") as caught:
        core_live_gcp.connect_mqtt(Connection(), urlparse("mqtts://example.test:8883"), attempts=2)
    assert safe_failure_metrics(caught.value) == {
        "mqtt_connect_attempts": 2,
        "mqtt_connect_wait_seconds": pytest.approx(0, abs=1),
    }


def test_gcp_inventory_distinguishes_pending_log_buckets_from_active(monkeypatch):
    monkeypatch.setattr(core_live_gcp, "pages", lambda *_args: [
        {"name": "projects/test/locations/test/buckets/coregcp-owned-active", "lifecycleState": "ACTIVE"},
        {"name": "projects/test/locations/test/buckets/coregcp-owned-old", "lifecycleState": "DELETE_REQUESTED"},
        {"name": "projects/test/locations/test/buckets/unrelated", "lifecycleState": "ACTIVE"},
    ])
    assert core_live_gcp.log_bucket_inventory(None, "test", "test", "coregcp-owned") == {
        "log_buckets": 1, "pending_deletion:log_buckets": 1,
    }
