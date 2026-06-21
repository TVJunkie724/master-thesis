import json

from src.api.models.deployment import (
    DeploymentOperation,
    DeploymentResult,
    DeploymentStreamEvent,
    DestroyResult,
)


def test_deployment_result_serializes_stable_shape():
    result = DeploymentResult(
        project_name="factory-twin",
        provider="aws",
        terraform_outputs={"endpoint": {"value": "https://example.test"}},
    )

    assert result.model_dump(mode="json") == {
        "message": "Core and IoT services deployed successfully",
        "status": "success",
        "operation": "deploy",
        "project_name": "factory-twin",
        "provider": "aws",
        "terraform_outputs": {"endpoint": {"value": "https://example.test"}},
    }


def test_destroy_result_serializes_stable_shape():
    result = DestroyResult(project_name="factory-twin", provider="gcp")

    assert result.model_dump(mode="json") == {
        "message": "Core and IoT services destroyed successfully",
        "status": "success",
        "operation": "destroy",
        "project_name": "factory-twin",
        "provider": "gcp",
    }


def test_log_stream_event_serializes_as_sse_data_event():
    event = DeploymentStreamEvent.log(DeploymentOperation.deploy, "terraform init")

    assert event.to_sse() == (
        'data: {"event":"log","operation":"deploy","message":"terraform init"}\n\n'
    )


def test_complete_stream_event_preserves_named_sse_event_and_outputs():
    event = DeploymentStreamEvent.complete(
        DeploymentOperation.deploy,
        outputs={"endpoint": {"value": "ok"}},
    )

    prefix, data = event.to_sse().split("data: ", maxsplit=1)
    assert prefix == "event: complete\n"
    assert json.loads(data) == {
        "event": "complete",
        "operation": "deploy",
        "success": True,
        "outputs": {"endpoint": {"value": "ok"}},
    }


def test_error_stream_event_preserves_named_sse_event_and_error():
    event = DeploymentStreamEvent.failure(DeploymentOperation.destroy, "boom")

    prefix, data = event.to_sse().split("data: ", maxsplit=1)
    assert prefix == "event: error\n"
    assert json.loads(data) == {
        "event": "error",
        "operation": "destroy",
        "success": False,
        "error": "boom",
        "error_category": "internal",
    }


def test_log_stream_event_redacts_secret_like_messages():
    event = DeploymentStreamEvent.log(
        DeploymentOperation.deploy,
        "azure_client_secret=super-secret-value",
    )

    assert "super-secret-value" not in event.to_sse()
    assert "Sensitive deployment detail redacted" in event.to_sse()


def test_error_stream_event_redacts_secret_like_messages():
    event = DeploymentStreamEvent.failure(
        DeploymentOperation.deploy,
        "Terraform failed with token abc123",
    )

    assert "abc123" not in event.to_sse()
    assert "Sensitive deployment detail redacted" in event.to_sse()


def test_error_stream_event_classifies_error_category():
    cases = {
        "Terraform apply failed": "terraform",
        "Permission denied while creating role": "permission",
        "Task timed out after 300s": "timeout",
        "ZIP package build failed": "packaging",
        "Validation failed: missing config": "validation",
        "Azure SDK call failed": "provider_sdk",
        "SDK cleanup failed": "cleanup",
    }

    for message, expected_category in cases.items():
        event = DeploymentStreamEvent.failure(DeploymentOperation.deploy, message)
        payload = json.loads(event.to_sse().split("data: ", maxsplit=1)[1])
        assert payload["error_category"] == expected_category


def test_complete_stream_event_redacts_secret_outputs():
    event = DeploymentStreamEvent.complete(
        DeploymentOperation.deploy,
        outputs={
            "aws_grafana_endpoint": "https://grafana.example.test",
            "aws_grafana_api_key": "secret-api-key",
            "inter_cloud_token": "cross-cloud-token",
        },
    )

    _, data = event.to_sse().split("data: ", maxsplit=1)
    payload = json.loads(data)

    assert payload["outputs"]["aws_grafana_endpoint"] == "https://grafana.example.test"
    assert payload["outputs"]["aws_grafana_api_key"] == "[REDACTED]"
    assert payload["outputs"]["inter_cloud_token"] == "[REDACTED]"
    assert "secret-api-key" not in data
    assert "cross-cloud-token" not in data
