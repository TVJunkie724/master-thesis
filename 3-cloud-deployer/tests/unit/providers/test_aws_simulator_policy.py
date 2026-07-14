"""Least-privilege policy tests for AWS simulator identities."""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

from src.providers.terraform.aws_deployer import _ensure_iot_policy, _simulator_iot_policy


def test_simulator_policy_is_scoped_to_exact_client_and_telemetry_topic():
    document = _simulator_iot_policy(
        region="eu-central-1",
        account_id="123456789012",
        device_id="device-1",
        topic="dt/factory/device-1/telemetry",
    )

    assert document["Statement"] == [
        {
            "Sid": "ConnectAsDevice",
            "Effect": "Allow",
            "Action": "iot:Connect",
            "Resource": "arn:aws:iot:eu-central-1:123456789012:client/device-1",
        },
        {
            "Sid": "PublishDeviceTelemetry",
            "Effect": "Allow",
            "Action": "iot:Publish",
            "Resource": "arn:aws:iot:eu-central-1:123456789012:topic/dt/factory/device-1/telemetry",
        },
    ]


def test_existing_matching_policy_is_not_versioned():
    iot = MagicMock()
    iot.exceptions = SimpleNamespace(ResourceNotFoundException=RuntimeError)
    document = _simulator_iot_policy(
        region="eu-central-1",
        account_id="123456789012",
        device_id="device-1",
        topic="dt/factory/device-1/telemetry",
    )
    iot.get_policy.return_value = {"defaultVersionId": "1"}
    iot.get_policy_version.return_value = {"policyDocument": document}

    _ensure_iot_policy(iot, policy_name="factory-device-1-policy", policy_document=document)

    iot.create_policy_version.assert_not_called()


def test_outdated_policy_is_replaced_and_oldest_non_default_version_removed_at_limit():
    iot = MagicMock()
    iot.exceptions = SimpleNamespace(ResourceNotFoundException=RuntimeError)
    document = _simulator_iot_policy(
        region="eu-central-1",
        account_id="123456789012",
        device_id="device-1",
        topic="dt/factory/device-1/telemetry",
    )
    iot.get_policy.return_value = {"defaultVersionId": "5"}
    iot.get_policy_version.return_value = {
        "policyDocument": {"Version": "2012-10-17", "Statement": []}
    }
    now = datetime.now(timezone.utc)
    iot.list_policy_versions.return_value = {
        "policyVersions": [
            {"versionId": str(version), "isDefaultVersion": version == 5, "createDate": now}
            for version in range(1, 6)
        ]
    }

    _ensure_iot_policy(iot, policy_name="factory-device-1-policy", policy_document=document)

    iot.delete_policy_version.assert_called_once_with(
        policyName="factory-device-1-policy",
        policyVersionId="1",
    )
    call = iot.create_policy_version.call_args.kwargs
    assert call["policyName"] == "factory-device-1-policy"
    assert call["setAsDefault"] is True
    assert '"iot:*"' not in call["policyDocument"]
