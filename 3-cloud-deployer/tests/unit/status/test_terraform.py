from types import SimpleNamespace
import json
import pytest

from src.status import terraform as terraform_status


@pytest.mark.parametrize("enabled,storage_class,prefix,expected", [
    ("Enabled", "DEEP_ARCHIVE", "history/", True),
    ("Disabled", "DEEP_ARCHIVE", "history/", False),
    ("Enabled", "STANDARD_IA", "history/", False),
    ("Enabled", "DEEP_ARCHIVE", "other/", False),
])
def test_shared_archive_requires_actual_enabled_transition(tmp_path, enabled, storage_class, prefix, expected):
    directory = tmp_path / "terraform"
    directory.mkdir()
    address = "aws_s3_bucket_lifecycle_configuration.aws_aws_s3_standard_ia[0]"
    state = {"resources": [{"type": "aws_s3_bucket_lifecycle_configuration", "name": "aws_aws_s3_standard_ia", "instances": [{"attributes": {"rule": [{"status": enabled, "filter": [{"prefix": prefix}], "transition": [{"storage_class": storage_class}]}]}}]}]}
    (directory / "terraform.tfstate").write_text(json.dumps(state))
    result = terraform_status._shared_aws_archive(tmp_path, [address])
    assert result == ([address] if expected else [])


def test_missing_shared_archive_state_is_not_a_pass(tmp_path):
    assert terraform_status._shared_aws_archive(tmp_path, ["aws_s3_bucket_lifecycle_configuration.aws_aws_s3_standard_ia[0]"]) == []


def test_state_classification_exposes_the_independent_event_layer(monkeypatch):
    monkeypatch.setattr(
        terraform_status,
        "run_terraform_status_command",
        lambda *args: SimpleNamespace(
            returncode=0,
            stderr="",
            stdout="\n".join(
                [
                    "aws_iot_thing.aws_aws_iot_core[0]",
                    "aws_lambda_function.event_runtime[0]",
                    "aws_kinesis_stream.domain_telemetry[\"received\"]",
                    "aws_sfn_state_machine.aws_aws_step_functions_standard[0]",
                ]
            ),
        ),
    )

    result = terraform_status.check_terraform_state("factory")

    assert result["l1"]["deployed"] is True
    assert result["eventing"]["deployed"] is True
    assert result["eventing"]["resources"] == [
        "aws_lambda_function.event_runtime[0]",
        'aws_kinesis_stream.domain_telemetry["received"]',
    ]
    assert result["l2"]["deployed"] is True
