import json

import pytest

from src.models.cloud_connection import CloudConnection
from src.models.deployer_config import DeployerConfiguration
from src.models.optimizer_config import OptimizerConfiguration
from src.models.twin import DigitalTwin
from src.models.twin_config import TwinConfiguration
from src.services.configuration_validation_service import ConfigurationValidationService
from src.services.errors import (
    ConfigurationValidationFailed,
    ExternalServiceError,
    ExternalServiceUnavailable,
)
from src.utils.crypto import encrypt_scoped


class FakeOptimizerClient:
    def __init__(self, result):
        self.result = result
        self.payload = None

    async def validate_optimizer_config(self, payload):
        self.payload = payload
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


class FakeDeployerClient:
    def __init__(self, result):
        self.result = result
        self.payload = None

    async def validate_deployer_complete(self, payload):
        self.payload = payload
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def _configured_twin() -> DigitalTwin:
    twin = DigitalTwin(id="twin-1", name="Factory Twin", user_id="user-1")
    twin.configuration = TwinConfiguration(
        twin_id=twin.id,
        aws_cloud_connection_id="connection-aws",
        aws_region="eu-central-1",
    )
    payload = {
        "aws_access_key_id": "AKIAIOSFODNN7EXAMPLE",
        "aws_secret_access_key": "secret-key",
        "aws_region": "eu-central-1",
    }
    twin.configuration.aws_cloud_connection = CloudConnection(
        id="connection-aws",
        user_id="user-1",
        provider="aws",
        display_name="AWS Dev",
        cloud_scope="{}",
        auth_type="access_key",
        encrypted_payload=encrypt_scoped(
            json.dumps(payload), "user-1", "connection-aws"
        ),
        payload_fingerprint="fingerprint",
    )
    twin.optimizer_config = OptimizerConfiguration(
        twin_id=twin.id,
        params=json.dumps({"devices": 10}),
        result_json=json.dumps({"calculationResult": {"L1": "aws"}}),
    )
    twin.deployer_config = DeployerConfiguration(
        twin_id=twin.id,
        deployer_digital_twin_name="factory",
        processor_contents=json.dumps({"device-1": "print('ok')"}),
        event_action_contents=json.dumps({"action-1": "print('ok')"}),
    )
    return twin


def _cloud_connection_configured_twin() -> DigitalTwin:
    return _configured_twin()


@pytest.mark.asyncio
async def test_validate_configured_transition_sends_exact_optimizer_and_deployer_payloads():
    optimizer = FakeOptimizerClient({"valid": True})
    deployer = FakeDeployerClient({"valid": True})
    service = ConfigurationValidationService(optimizer, deployer)

    await service.validate_configured_transition(_configured_twin())

    assert optimizer.payload == {
        "params": {"devices": 10},
        "result": {"calculationResult": {"L1": "aws"}},
    }
    assert deployer.payload["deployer_digital_twin_name"] == "factory"
    assert deployer.payload["processors"] == {"device-1": "print('ok')"}
    assert deployer.payload["event_actions"] == {"action-1": "print('ok')"}
    assert deployer.payload["optimizer_params"] == {"devices": 10}
    assert deployer.payload["cheapest_path"] == {"L1": "aws"}


@pytest.mark.asyncio
async def test_validate_configured_transition_accepts_cloud_connection_only_credentials():
    optimizer = FakeOptimizerClient({"valid": True})
    deployer = FakeDeployerClient({"valid": True})
    service = ConfigurationValidationService(optimizer, deployer)

    await service.validate_configured_transition(_cloud_connection_configured_twin())

    assert optimizer.payload["params"] == {"devices": 10}
    assert deployer.payload["deployer_digital_twin_name"] == "factory"


@pytest.mark.asyncio
async def test_validate_configured_transition_reports_dangling_cloud_connection_without_client_calls():
    twin = _configured_twin()
    twin.configuration.aws_access_key_id = None
    twin.configuration.aws_secret_access_key = None
    twin.configuration.aws_cloud_connection_id = "missing-connection"
    twin.configuration.aws_cloud_connection = None
    optimizer = FakeOptimizerClient({"valid": True})
    deployer = FakeDeployerClient({"valid": True})
    service = ConfigurationValidationService(optimizer, deployer)

    with pytest.raises(ConfigurationValidationFailed) as exc_info:
        await service.validate_configured_transition(twin)

    assert exc_info.value.errors == [
        {
            "step": 1,
            "provider": "aws",
            "code": "DANGLING_CLOUD_CONNECTION",
            "field": "credentials",
            "message": "Configured Cloud Connection is no longer available",
            "source_id": "missing-connection",
        }
    ]
    assert optimizer.payload is None
    assert deployer.payload is None


@pytest.mark.asyncio
async def test_validate_configured_transition_requires_optimizer_selected_providers():
    twin = _configured_twin()
    twin.optimizer_config.cheapest_l2 = "azure"
    optimizer = FakeOptimizerClient({"valid": True})
    deployer = FakeDeployerClient({"valid": True})
    service = ConfigurationValidationService(optimizer, deployer)

    with pytest.raises(ConfigurationValidationFailed) as exc_info:
        await service.validate_configured_transition(twin)

    assert {
        "step": 1,
        "provider": "azure",
        "code": "MISSING_CLOUD_CONNECTION",
        "field": "credentials",
        "message": "Provider requires a bound Cloud Connection",
    } in exc_info.value.errors
    assert optimizer.payload is None
    assert deployer.payload is None


@pytest.mark.asyncio
async def test_validate_configured_transition_collects_local_step_errors():
    twin = DigitalTwin(id="twin-1", name=" ", user_id="user-1")
    service = ConfigurationValidationService(
        FakeOptimizerClient({"valid": True}),
        FakeDeployerClient({"valid": True}),
    )

    with pytest.raises(ConfigurationValidationFailed) as exc_info:
        await service.validate_configured_transition(twin)

    assert exc_info.value.message == "Cannot mark as configured: 2 validation errors"
    assert exc_info.value.errors == [
        {
            "step": 1,
            "code": "EMPTY_NAME",
            "field": "twin_name",
            "message": "Twin name is required",
        },
        {
            "step": 1,
            "code": "MISSING_CREDENTIALS",
            "field": "credentials",
            "message": "At least one cloud provider credentials required",
        },
    ]


@pytest.mark.asyncio
async def test_validate_configured_transition_collects_optimizer_and_deployer_validation_errors():
    optimizer = FakeOptimizerClient(
        {"valid": False, "errors": [{"code": "BAD_PARAMS", "field": "params"}]}
    )
    deployer = FakeDeployerClient(
        {"valid": False, "errors": [{"code": "BAD_DEPLOYER", "field": "config"}]}
    )
    service = ConfigurationValidationService(optimizer, deployer)

    with pytest.raises(ConfigurationValidationFailed) as exc_info:
        await service.validate_configured_transition(_configured_twin())

    assert exc_info.value.errors == [
        {"step": 2, "code": "BAD_PARAMS", "field": "params"},
        {"step": 3, "code": "BAD_DEPLOYER", "field": "config"},
    ]


@pytest.mark.asyncio
async def test_validate_configured_transition_preserves_capability_error_contract():
    optimizer = FakeOptimizerClient({"valid": True})
    deployer = FakeDeployerClient(
        {
            "valid": False,
            "errors": [
                {
                    "code": "CAPABILITY_UNAVAILABLE",
                    "field": "cheapest_path.L4",
                    "provider": "gcp",
                    "layer": "l4",
                    "message": "GCP L4 deployment is outside the implemented thesis path.",
                }
            ],
        }
    )
    service = ConfigurationValidationService(optimizer, deployer)

    with pytest.raises(ConfigurationValidationFailed) as exc_info:
        await service.validate_configured_transition(_configured_twin())

    assert exc_info.value.errors == [
        {
            "step": 3,
            "code": "CAPABILITY_UNAVAILABLE",
            "field": "cheapest_path.L4",
            "provider": "gcp",
            "layer": "l4",
            "message": "GCP L4 deployment is outside the implemented thesis path.",
        }
    ]


@pytest.mark.asyncio
async def test_validate_configured_transition_redacts_unexpected_exception_details():
    optimizer = FakeOptimizerClient(Exception("credential=must-not-leak"))
    deployer = FakeDeployerClient(Exception("private_key=must-not-leak"))
    service = ConfigurationValidationService(optimizer, deployer)

    with pytest.raises(ConfigurationValidationFailed) as exc_info:
        await service.validate_configured_transition(_configured_twin())

    assert exc_info.value.errors == [
        {
            "step": 2,
            "code": "OPTIMIZER_UNAVAILABLE",
            "field": "optimizer",
            "message": "Optimizer validation failed unexpectedly",
        },
        {
            "step": 3,
            "code": "DEPLOYER_UNAVAILABLE",
            "field": "deployer",
            "message": "Deployer validation failed unexpectedly",
        },
    ]
    assert "must-not-leak" not in str(exc_info.value.errors)


@pytest.mark.asyncio
async def test_validate_configured_transition_maps_external_client_failures():
    optimizer = FakeOptimizerClient(
        ExternalServiceUnavailable("Optimizer API unavailable")
    )
    deployer = FakeDeployerClient(
        ExternalServiceError("Deployer API returned 500: boom")
    )
    service = ConfigurationValidationService(optimizer, deployer)

    with pytest.raises(ConfigurationValidationFailed) as exc_info:
        await service.validate_configured_transition(_configured_twin())

    assert exc_info.value.errors == [
        {
            "step": 2,
            "code": "OPTIMIZER_UNAVAILABLE",
            "field": "optimizer",
            "message": "Optimizer API error: Optimizer API unavailable",
        },
        {
            "step": 3,
            "code": "DEPLOYER_ERROR",
            "field": "deployer",
            "message": "Deployer validation failed: Deployer API returned 500: boom",
        },
    ]


@pytest.mark.asyncio
async def test_validate_configured_transition_reports_malformed_stored_json_without_client_calls():
    twin = _configured_twin()
    twin.optimizer_config.params = "{bad-json"
    optimizer = FakeOptimizerClient({"valid": True})
    deployer = FakeDeployerClient({"valid": True})
    service = ConfigurationValidationService(optimizer, deployer)

    with pytest.raises(ConfigurationValidationFailed) as exc_info:
        await service.validate_configured_transition(twin)

    assert exc_info.value.errors == [
        {
            "step": 2,
            "code": "INVALID_JSON",
            "field": "optimizer.params",
            "message": "Invalid JSON: Expecting property name enclosed in double quotes",
        }
    ]
    assert optimizer.payload is None
    assert deployer.payload is None
