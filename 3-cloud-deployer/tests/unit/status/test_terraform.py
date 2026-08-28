from types import SimpleNamespace

from src.status import terraform as terraform_status


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
                    "aws_kinesis_stream.domain_events[\"received\"]",
                    "aws_lambda_function.aws_six_layer_processor_extension[0]",
                ]
            ),
        ),
    )

    result = terraform_status.check_terraform_state("factory")

    assert result["l1"]["deployed"] is True
    assert result["eventing"]["deployed"] is True
    assert result["eventing"]["resources"] == [
        "aws_lambda_function.event_runtime[0]",
        'aws_kinesis_stream.domain_events["received"]',
    ]
    assert result["l2"]["deployed"] is True
