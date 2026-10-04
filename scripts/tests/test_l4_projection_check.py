from copy import deepcopy
from types import SimpleNamespace
from pathlib import Path
import json

import pytest
from botocore.session import Session
from botocore.validate import validate_parameters

from scripts import l4_projection_check as projection
from scripts import run_l4_evaluation as runner


def test_isolated_aws_output_handles_absent_human_bindings():
    source = (Path(__file__).resolve().parents[2] / "3-cloud-deployer/src/terraform/aws_six_layer.tf").read_text()
    output = source.split('output "aws_component_twin_state_output"', 1)[1].split('\nlocals {', 1)[0]
    assert "access_binding_refs = try([" in output
    assert "aws_ssoadmin_permission_set.aws_aws_iam_identity_center_layer_access[0].arn" in output
    assert "aws_ssoadmin_account_assignment.aws_aws_iam_identity_center_layer_access[0].id" in output
    assert "], [])" in output


def test_azure_runner_initializes_with_installed_sdk_without_network(tmp_path, monkeypatch):
    monkeypatch.setenv("L4_SOURCE_REVISION", "a" * 40)
    (tmp_path / "private.tfvars.json").write_text(json.dumps({"digital_twin_name": "l4-azure-12345678"}))
    (tmp_path / "review.plan").write_bytes(b"offline fixture")
    (tmp_path / "plan.json").write_text(json.dumps({"resource_changes": [{
        "address": "azurerm_resource_group.main[0]",
        "change": {"after": {"name": "l4-azure-12345678-rg"}},
    }]}))
    experiment = runner.Experiment("azure", {"azure": {
        "azure_subscription_id": "00000000-0000-0000-0000-000000000001",
        "azure_tenant_id": "00000000-0000-0000-0000-000000000002",
        "azure_client_id": "00000000-0000-0000-0000-000000000003",
        "azure_client_secret": "offline-fixture-not-a-credential",
    }}, tmp_path, tmp_path)
    assert experiment.apply_started is False
    assert experiment.arm is not None and experiment.auth is not None
    experiment.arm.close()
    experiment.auth.close()
    experiment.credential.close()


class FakeAWS:
    exceptions = SimpleNamespace(ConflictException=type("Conflict", (Exception,), {}))

    def __init__(self):
        self.entities, self.types, self.writes = {}, {}, 0

    @staticmethod
    def validate(operation, args):
        model = Session().get_service_model("iottwinmaker").operation_model(operation)
        validate_parameters(args, model.input_shape)

    def create_entity(self, **args):
        self.validate("CreateEntity", args)
        self.entities[args["entityId"]] = {
            "entityId": args["entityId"], "parentEntityId": args.get("parentEntityId"),
            "status": {"state": "ACTIVE"}, "components": {},
        }

    def get_entity(self, **args):
        self.validate("GetEntity", args)
        return deepcopy(self.entities[args["entityId"]])

    def create_component_type(self, **args):
        self.validate("CreateComponentType", args)
        assert "functions" not in args
        self.types[args["componentTypeId"]] = {"propertyDefinitions": args["propertyDefinitions"],
                                               "status": {"state": "ACTIVE"}}

    def get_component_type(self, **args):
        self.validate("GetComponentType", args)
        return self.types[args["componentTypeId"]]

    def update_entity(self, **args):
        self.validate("UpdateEntity", args)
        update = args["componentUpdates"]["telemetry"]
        components = self.entities[args["entityId"]]["components"]
        if "propertyUpdates" in update:
            self.writes += 1
            components["telemetry"]["properties"] = update["propertyUpdates"]
        else:
            components["telemetry"] = update
        return {"state": "ACTIVE"}


class FakeAzure:
    def __init__(self):
        self.twins, self.models, self.relationships, self.writes = {}, [], {}, 0

    def create_models(self, models):
        self.models = models

    def upsert_digital_twin(self, twin_id, model):
        self.twins[twin_id] = deepcopy(model)

    def upsert_relationship(self, source, relation_id, body):
        self.relationships[(source, relation_id)] = body

    def get_digital_twin(self, twin_id):
        return deepcopy(self.twins[twin_id])

    def update_digital_twin(self, twin_id, patch):
        self.writes += 1
        for field in patch:
            self.twins[twin_id][field["path"].removeprefix("/")] = field["value"]


@pytest.mark.parametrize("provider", ["aws", "azure"])
def test_real_adapter_and_model_project_and_replay_offline(provider):
    client = FakeAWS() if provider == "aws" else FakeAzure()
    result = projection.check(provider, client, "l4-" + provider + "-12345678",
                              workspace_id="l4-aws-12345678-suffix")
    assert result["functional_pass"] is True
    assert result["projection_readback_attempts"] == result["replay_readback_attempts"] == 1
    assert result["sdk_calls"] < 30
    assert len(result["model_sha256"]) == len(result["adapter_sha256"]) == 64
    assert client.writes == (2 if provider == "aws" else 1)
    assert len(client.entities if provider == "aws" else client.twins) == 2


def test_projection_failure_keeps_timing_and_call_count():
    client = FakeAWS()
    client.update_entity = lambda **_: (_ for _ in ()).throw(RuntimeError("private-value"))
    report = {}
    with pytest.raises(Exception):
        projection.check("aws", client, "l4-aws-12345678",
                         workspace_id="l4-aws-12345678-suffix", report=report)
    assert report["functional_pass"] is False
    assert report["sdk_calls"] > 0
    assert report["phases"][0]["passed"] is False
    assert "private-value" not in str(report)


def test_wrong_workspace_is_rejected_before_any_sdk_call():
    report = {}
    with pytest.raises(ValueError, match="OWNERSHIP"):
        projection.check("aws", FakeAWS(), "l4-aws-12345678", workspace_id="another", report=report)
    assert report["sdk_calls"] == 0


@pytest.mark.parametrize("field,value", [("sourceSequence", "old"), ("value", 0),
    ("value", True), ("metric", "other"), ("lastEventId", "old"), ("observedAt", "")])
def test_projection_requires_correlated_snapshot(field, value):
    event = projection.fixture("run")
    state = dict(metric="temperature", value=20.5, sourceSequence=event["source_sequence"],
                 lastEventId=event["event_id"], observedAt=event["occurred_at"])
    state[field] = value
    assert projection.matches(state, event, "aws") is False


def test_client_and_response_limits():
    client = projection.BoundedClient(SimpleNamespace(get=lambda: {}), limit=1)
    client.get()
    with pytest.raises(RuntimeError, match="CALL_LIMIT"):
        client.get()
    client = projection.BoundedClient(SimpleNamespace(get=lambda: "x" * 17000))
    with pytest.raises(RuntimeError, match="SIZE_LIMIT"):
        client.get()


@pytest.mark.parametrize("error", [RuntimeError("secret"), TimeoutError(), KeyboardInterrupt(), SystemExit(), runner.L4DeadlineExceeded()])
def test_failure_and_interrupt_always_cleanup_then_inventory(error):
    calls, report = [], {}
    def fail():
        raise error
    runner.lifecycle(fail, lambda: calls.append("cleanup") or True,
                     lambda: calls.append("inventory") or True, report)
    assert calls == ["cleanup", "inventory"]
    assert report["passed"] is False
    assert report["cleanup_pass"] is report["inventory_pass"] is True
    assert "secret" not in str(report)


def test_cleanup_failure_still_inventories_and_never_passes():
    report = {"functional_pass": True}
    def fail():
        raise RuntimeError("private")
    runner.lifecycle(lambda: None, fail, lambda: True, report)
    assert report["passed"] is False
    assert report["inventory_pass"] is True


def test_no_approval_no_preparation(monkeypatch):
    monkeypatch.setattr(runner, "prepare", lambda *_: pytest.fail("No approved run"))
    with pytest.raises(ValueError, match="APPROVAL"):
        runner.run(SimpleNamespace(approve_live=False))


def test_no_apply_no_cleanup_of_preexisting_prefix():
    experiment = runner.Experiment.__new__(runner.Experiment)
    experiment.apply_started = False
    experiment.cleanup_children = lambda: pytest.fail("pre-existing resources must survive")
    assert experiment.cleanup() is True


def test_inventory_does_not_treat_permission_errors_as_absence():
    def forbidden():
        raise PermissionError("private")
    with pytest.raises(PermissionError):
        runner.absent(forbidden, ("ResourceNotFoundException",))


@pytest.mark.parametrize("status", [403, 404])
def test_azure_http_response_is_not_a_botocore_dictionary(status):
    from azure.core.exceptions import HttpResponseError
    error = HttpResponseError(message="private")
    error.status_code = status
    error.response = SimpleNamespace(status_code=status)
    def fail():
        raise error
    if status == 404:
        assert runner.absent(fail, ()) is True
    else:
        with pytest.raises(HttpResponseError):
            runner.absent(fail, ())


def test_workspace_retry_only_allows_the_missing_workspace(tmp_path):
    plan = {"resource_changes": [{"mode": "managed", "address": address,
        "change": {"actions": ["create"] if address.startswith("awscc_") else ["no-op"]}}
        for address in runner.EXPECTED["aws"]]}
    runner.review_workspace_retry(plan)
    for resource in plan["resource_changes"]:
        if not resource["address"].startswith("awscc_"):
            resource["change"]["actions"] = ["update"]
            break
    with pytest.raises(RuntimeError, match="RETRY_SCOPE"):
        runner.review_workspace_retry(plan)
    log = tmp_path / "synthetic.log"
    log.write_text('Error: InvalidRequest: role assume permission\n with awscc_iottwinmaker_workspace.aws_aws_iot_twinmaker_standard[0]\n')
    assert runner.workspace_role_propagation_failure(log)
    log.write_text('Error: AccessDenied\n')
    assert not runner.workspace_role_propagation_failure(log)
