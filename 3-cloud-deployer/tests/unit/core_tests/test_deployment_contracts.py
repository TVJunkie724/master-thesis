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
        operation_id="op-123",
        terraform_outputs={"endpoint": {"value": "https://example.test"}},
    )

    assert result.model_dump(mode="json") == {
        "message": "Core and IoT services deployed successfully",
        "status": "success",
        "operation": "deploy",
        "project_name": "factory-twin",
        "provider": "aws",
        "operation_id": "op-123",
        "terraform_outputs": {"endpoint": {"value": "https://example.test"}},
    }


def test_destroy_result_serializes_stable_shape():
    result = DestroyResult(project_name="factory-twin", provider="gcp", operation_id="op-123")

    assert result.model_dump(mode="json") == {
        "message": "Core and IoT services destroyed successfully",
        "status": "success",
        "operation": "destroy",
        "project_name": "factory-twin",
        "provider": "gcp",
        "operation_id": "op-123",
    }


def test_log_stream_event_serializes_as_sse_data_event():
    event = DeploymentStreamEvent.log(DeploymentOperation.deploy, "terraform init", operation_id="op-123")

    assert event.to_sse() == (
        'data: {"event":"log","operation":"deploy","message":"terraform init","operation_id":"op-123"}\n\n'
    )


def test_complete_stream_event_preserves_named_sse_event_and_outputs():
    event = DeploymentStreamEvent.complete(
        DeploymentOperation.deploy,
        outputs={"endpoint": {"value": "ok"}},
        operation_id="op-123",
    )

    prefix, data = event.to_sse().split("data: ", maxsplit=1)
    assert prefix == "event: complete\n"
    assert json.loads(data) == {
        "event": "complete",
        "operation": "deploy",
        "success": True,
        "outputs": {"endpoint": {"value": "ok"}},
        "operation_id": "op-123",
    }


def test_error_stream_event_preserves_named_sse_event_and_error():
    event = DeploymentStreamEvent.failure(
        DeploymentOperation.destroy,
        "boom",
        error_code="DESTRUCTION_ERROR",
        operation_id="op-123",
    )

    prefix, data = event.to_sse().split("data: ", maxsplit=1)
    assert prefix == "event: error\n"
    assert json.loads(data) == {
        "event": "error",
        "operation": "destroy",
        "success": False,
        "error": "boom",
        "error_code": "DESTRUCTION_ERROR",
        "operation_id": "op-123",
    }
