"""Dedicated AWS reader keys never use bootstrap credentials or public URLs."""
from types import SimpleNamespace
from unittest.mock import MagicMock
from pathlib import Path
import re

import pytest
from src.providers.aws.layers import layer_5_grafana as g


def test_reader_policy_has_only_two_url_bound_actions_on_the_exact_reader():
    source = (Path(__file__).resolve().parents[3] / "src/terraform/six_layer_visualization.tf").read_text()
    block = source.split('resource "aws_iam_user_policy" "aws_six_layer_grafana_reader" {', 1)[1].split('\nresource ', 1)[0]
    actual = block.split("policy = ", 1)[1].rsplit("}", 1)[0].strip()
    expected = '''jsonencode({
      Version = "2012-10-17"
      Statement = [{
        Effect = "Allow", Action = "lambda:InvokeFunctionUrl"
        Resource = aws_lambda_function.aws_aws_lambda_raw_history_reader[0].arn
        Condition = { StringEquals = { "lambda:FunctionUrlAuthType" = "AWS_IAM" } }
      }, {
        Effect = "Allow", Action = "lambda:InvokeFunction"
        Resource = aws_lambda_function.aws_aws_lambda_raw_history_reader[0].arn
        Condition = { Bool = { "lambda:InvokedViaFunctionUrl" = "true" } }
      }]
    })'''
    assert re.sub(r"\s+", "", actual) == re.sub(r"\s+", "", expected)
    assert 'resource "aws_iam_access_key"' not in source


def provider():
    iam = MagicMock()
    iam.get_user.return_value = {"User": {
        "Path": "/twin2multicloud/grafana/",
        "Tags": [{"Key": "Purpose", "Value": "grafana-l3-reader"}],
    }}
    iam.list_access_keys.return_value = {"AccessKeyMetadata": [{"AccessKeyId": "old-fixture"}]}
    iam.create_access_key.return_value = {"AccessKey": {
        "AccessKeyId": "new-fixture", "SecretAccessKey": "fixture-secret",
    }}
    return SimpleNamespace(clients={"iam": iam, "lambda": SimpleNamespace(meta=SimpleNamespace(region_name="eu-central-1"))})


def test_replace_revokes_only_the_owned_users_old_keys():
    p = provider()
    assert g._replace_reader_credentials(p, "reader-user")["AccessKeyId"] == "new-fixture"
    p.clients["iam"].delete_access_key.assert_called_once_with(UserName="reader-user", AccessKeyId="old-fixture")
    p.clients["iam"].create_access_key.assert_called_once_with(UserName="reader-user")


@pytest.mark.parametrize("case", ["wrong_path", "wrong_tag", "incomplete"])
def test_unowned_or_incomplete_identity_is_not_mutated(case):
    p = provider(); iam = p.clients["iam"]
    if case == "wrong_path": iam.get_user.return_value["User"]["Path"] = "/"
    if case == "wrong_tag": iam.get_user.return_value["User"]["Tags"] = []
    if case == "incomplete": iam.list_access_keys.return_value["IsTruncated"] = True
    with pytest.raises(ValueError): g._replace_reader_credentials(p, "reader-user")
    iam.delete_access_key.assert_not_called()
    iam.create_access_key.assert_not_called()


@pytest.mark.parametrize("failure_stage", [None, "datasource", "dashboard", "query", "second-query", "pending-auth", "pending-query-path", "missing-query-path", "invalid-query", "denied"])
def test_key_is_retained_only_after_both_grafana_queries_pass(monkeypatch, failure_stage):
    p = provider()
    revoke = MagicMock()
    monkeypatch.setattr(g, "_provisioning_service_account", lambda *_: ("service-account", "fixture-token"))
    monkeypatch.setattr(g, "_ensure_exact_plugin", lambda *_: None)
    monkeypatch.setattr(g, "_revoke_provisioning_tokens", revoke)
    datasource = MagicMock(side_effect=RuntimeError("fixture failure") if failure_stage == "datasource" else None)
    monkeypatch.setattr(g, "_upsert_v2_datasource", datasource)
    monkeypatch.setattr(g, "_upsert_v2_dashboard", MagicMock(side_effect=RuntimeError("fixture failure") if failure_stage == "dashboard" else None))
    query = MagicMock(return_value=SimpleNamespace(status_code=200, json=lambda: {"results": {"A": {"frames": []}}}),
                     side_effect=RuntimeError("fixture failure") if failure_stage == "query" else None)
    if failure_stage == "second-query":
        query.side_effect = [query.return_value, RuntimeError("fixture failure")]
    if failure_stage == "pending-auth":
        query.side_effect = [SimpleNamespace(status_code=403), query.return_value, query.return_value]
    if failure_stage == "pending-query-path":
        query.side_effect = [SimpleNamespace(status_code=404), query.return_value, query.return_value]
    if failure_stage == "missing-query-path":
        query.return_value = SimpleNamespace(status_code=404, text="Datasource not found")
    if failure_stage == "invalid-query":
        query.return_value = SimpleNamespace(status_code=400, text="Invalid query")
    if failure_stage == "denied":
        query.return_value = SimpleNamespace(status_code=403, text="Forbidden")
    monkeypatch.setattr(g.time, "sleep", lambda _: None)
    monkeypatch.setattr(g.requests, "post", query)
    args = dict(workspace_id="g-fixture", grafana_url="https://grafana.example", reader_url="https://reader.example/", reader_function_name="reader", reader_user_name="reader-user", device_id="sensor-1", metric="temperature", architecture_profile="six-layer-eventing@1")
    failed = failure_stage not in (None, "pending-auth", "pending-query-path")
    if failed:
        expected_error = {"denied": "HTTP 403", "missing-query-path": "HTTP 404", "invalid-query": "HTTP 400"}.get(failure_stage, "fixture failure")
        with pytest.raises(RuntimeError, match=expected_error) as caught:
            g.configure_six_layer_grafana(p, **args)
        if failure_stage == "missing-query-path":
            assert caught.value._aws_grafana_cause == "datasource-or-plugin-unavailable"
    else:
        g.configure_six_layer_grafana(p, **args)
        assert query.call_count == (3 if failure_stage in ("pending-auth", "pending-query-path") else 2)
    if failure_stage in ("denied", "missing-query-path"): assert query.call_count == 12
    if failure_stage == "invalid-query": assert query.call_count == 1
    deleted = [c.kwargs["AccessKeyId"] for c in p.clients["iam"].delete_access_key.call_args_list]
    assert deleted == (["old-fixture", "new-fixture"] if failed else ["old-fixture"])
    revoke.assert_called_once_with(p, "g-fixture", "service-account")
    assert datasource.call_args.kwargs["reader_credentials"]["AccessKeyId"] == "new-fixture"
