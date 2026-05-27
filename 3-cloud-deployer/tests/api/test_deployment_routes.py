"""
Deployment route boundary tests.

The route layer must remain a thin HTTP adapter. Deployment orchestration must
enter the canonical facade in src.providers.deployer.
"""

import asyncio
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from src.api import deployment
from src.api.dependencies import validate_provider


def _project_storage_for(project_path: str | Path):
    storage = MagicMock(name="project_storage")
    storage.context.return_value.project_path = Path(project_path)
    return storage


def test_deploy_route_invokes_canonical_facade_with_hard_response_shape():
    context = MagicMock(name="deployment_context")
    outputs = {"aws_lambda_dispatcher_name": {"value": "test-dispatcher"}}

    with (
        patch.object(deployment, "check_template_protection") as mock_template_guard,
        patch.object(deployment, "validate_provider", return_value="aws") as mock_validate_provider,
        patch.object(deployment, "get_project_storage", return_value=_project_storage_for("/projects/test_api_project")) as mock_storage,
        patch.object(deployment, "validate_project_directory") as mock_validate_directory,
        patch.object(deployment, "create_context", return_value=context) as mock_create_context,
        patch.object(deployment.core_deployer, "deploy_all", return_value=outputs) as mock_deploy_all,
    ):
        response = deployment.deploy_all(provider="aws", project_name="test_api_project")

    mock_template_guard.assert_called_once_with("test_api_project", "deploy")
    mock_validate_provider.assert_called_once_with("aws")
    mock_storage.return_value.context.assert_called_once_with("test_api_project")
    mock_validate_directory.assert_called_once_with(Path("/projects/test_api_project"))
    assert mock_deploy_all.call_args.args == (context, "aws")
    operation_context = mock_deploy_all.call_args.kwargs["operation_context"]
    mock_create_context.assert_called_once_with(
        "test_api_project",
        "aws",
        operation_id=operation_context.operation_id,
    )
    assert operation_context.operation == "deploy"
    assert operation_context.project_name == "test_api_project"
    assert operation_context.provider == "aws"

    operation_id = response.pop("operation_id")
    assert operation_id == operation_context.operation_id
    assert response == {
        "message": "Core and IoT services deployed successfully",
        "status": "success",
        "operation": "deploy",
        "project_name": "test_api_project",
        "provider": "aws",
        "terraform_outputs": outputs,
    }


def test_destroy_route_invokes_canonical_facade_with_hard_response_shape():
    context = MagicMock(name="deployment_context")

    with (
        patch.object(deployment, "check_template_protection") as mock_template_guard,
        patch.object(deployment, "validate_provider", return_value="aws") as mock_validate_provider,
        patch.object(deployment, "get_project_storage", return_value=_project_storage_for("/projects/test_api_project")) as mock_storage,
        patch.object(deployment, "validate_project_directory") as mock_validate_directory,
        patch.object(deployment, "create_context", return_value=context) as mock_create_context,
        patch.object(deployment.core_deployer, "destroy_all") as mock_destroy_all,
    ):
        response = deployment.destroy_all(provider="aws", project_name="test_api_project")

    mock_template_guard.assert_called_once_with("test_api_project", "destroy")
    mock_validate_provider.assert_called_once_with("aws")
    mock_storage.return_value.context.assert_called_once_with("test_api_project")
    mock_validate_directory.assert_called_once_with(Path("/projects/test_api_project"))
    assert mock_destroy_all.call_args.args == (context, "aws")
    operation_context = mock_destroy_all.call_args.kwargs["operation_context"]
    mock_create_context.assert_called_once_with(
        "test_api_project",
        "aws",
        operation_id=operation_context.operation_id,
    )
    assert operation_context.operation == "destroy"
    assert operation_context.project_name == "test_api_project"
    assert operation_context.provider == "aws"

    operation_id = response.pop("operation_id")
    assert operation_id == operation_context.operation_id
    assert response == {
        "message": "Core and IoT services destroyed successfully",
        "status": "success",
        "operation": "destroy",
        "project_name": "test_api_project",
        "provider": "aws",
    }


async def _collect_stream(streaming_response) -> str:
    chunks = []
    async for chunk in streaming_response.body_iterator:
        chunks.append(chunk.decode("utf-8") if isinstance(chunk, bytes) else chunk)
    return "".join(chunks)


async def _fake_deploy_stream(context, strategy=None, output_sink=None, operation_context=None):
    assert context is not None
    assert strategy is None
    assert operation_context is not None
    yield "terraform init"
    yield "terraform apply"
    if output_sink is not None:
        output_sink["outputs"] = {"output": {"value": "ok"}}


async def _fake_destroy_stream(context, strategy=None, operation_context=None):
    assert context is not None
    assert strategy is None
    assert operation_context is not None
    yield "terraform destroy"


async def _fake_failing_deploy_stream(context, strategy=None, output_sink=None, operation_context=None):
    yield "terraform init"
    raise RuntimeError("failed in /tmp/twin2multicloud-deployer-workspaces/test-api-abc/terraform")


async def _fake_failing_destroy_stream(context, strategy=None, operation_context=None):
    yield "terraform destroy"
    raise RuntimeError("client_secret=super-secret")


def test_deploy_stream_uses_canonical_facade_and_preserves_event_shape():
    context = MagicMock(name="deployment_context")
    context.project_path = Path("/projects/test_api_project")

    with (
        patch.object(deployment, "check_template_protection"),
        patch.object(deployment, "validate_provider", return_value="aws"),
        patch.object(deployment, "get_project_storage", return_value=_project_storage_for("/projects/test_api_project")),
        patch.object(deployment, "validate_project_directory"),
        patch.object(deployment, "create_context", return_value=context),
        patch.object(deployment.core_deployer, "deploy_all_stream", new=_fake_deploy_stream),
    ):
        response = asyncio.run(deployment.deploy_stream(provider="aws", project_name="test_api_project"))
        body = asyncio.run(_collect_stream(response))

    assert response.media_type == "text/event-stream"
    assert '"operation_id":"' in body
    assert 'data: {"event":"log","operation":"deploy","message":"terraform init","operation_id":"' in body
    assert 'data: {"event":"log","operation":"deploy","message":"terraform apply","operation_id":"' in body
    assert 'event: complete\ndata: {"event":"complete","operation":"deploy","success":true,"outputs":{"output":{"value":"ok"}},"operation_id":"' in body


def test_deploy_stream_redacts_workspace_paths_in_failure_event():
    context = MagicMock(name="deployment_context")
    context.project_path = Path("/projects/test_api_project")

    with (
        patch.object(deployment, "check_template_protection"),
        patch.object(deployment, "validate_provider", return_value="aws"),
        patch.object(deployment, "get_project_storage", return_value=_project_storage_for("/projects/test_api_project")),
        patch.object(deployment, "validate_project_directory"),
        patch.object(deployment, "create_context", return_value=context),
        patch.object(deployment.core_deployer, "deploy_all_stream", new=_fake_failing_deploy_stream),
    ):
        response = asyncio.run(deployment.deploy_stream(provider="aws", project_name="test_api_project"))
        body = asyncio.run(_collect_stream(response))

    assert '"error_code":"DEPLOYMENT_ERROR"' in body
    assert '"operation_id":"' in body
    assert "/tmp/twin2multicloud-deployer-workspaces" not in body


def test_destroy_stream_uses_canonical_facade_and_preserves_event_shape():
    context = MagicMock(name="deployment_context")
    context.project_path = Path("/projects/test_api_project")

    with (
        patch.object(deployment, "check_template_protection"),
        patch.object(deployment, "validate_provider", return_value="aws"),
        patch.object(deployment, "get_project_storage", return_value=_project_storage_for("/projects/test_api_project")),
        patch.object(deployment, "validate_project_directory"),
        patch.object(deployment, "create_context", return_value=context),
        patch.object(deployment.core_deployer, "destroy_all_stream", new=_fake_destroy_stream),
    ):
        response = asyncio.run(deployment.destroy_stream(provider="aws", project_name="test_api_project"))
        body = asyncio.run(_collect_stream(response))

    assert response.media_type == "text/event-stream"
    assert '"operation_id":"' in body
    assert 'data: {"event":"log","operation":"destroy","message":"terraform destroy","operation_id":"' in body
    assert 'event: complete\ndata: {"event":"complete","operation":"destroy","success":true,"operation_id":"' in body


def test_destroy_stream_failure_uses_typed_safe_error_event():
    context = MagicMock(name="deployment_context")
    context.project_path = Path("/projects/test_api_project")

    with (
        patch.object(deployment, "check_template_protection"),
        patch.object(deployment, "validate_provider", return_value="aws"),
        patch.object(deployment, "get_project_storage", return_value=_project_storage_for("/projects/test_api_project")),
        patch.object(deployment, "validate_project_directory"),
        patch.object(deployment, "create_context", return_value=context),
        patch.object(deployment.core_deployer, "destroy_all_stream", new=_fake_failing_destroy_stream),
    ):
        response = asyncio.run(deployment.destroy_stream(provider="aws", project_name="test_api_project"))
        body = asyncio.run(_collect_stream(response))

    assert '"error_code":"DESTRUCTION_ERROR"' in body
    assert '"operation_id":"' in body
    assert "super-secret" not in body


def test_google_provider_alias_is_normalized_to_gcp_in_deploy_response():
    context = MagicMock(name="deployment_context")

    with (
        patch.object(deployment, "check_template_protection"),
        patch.object(deployment, "get_project_storage", return_value=_project_storage_for("/projects/test_api_project")),
        patch.object(deployment, "validate_project_directory"),
        patch.object(deployment, "create_context", return_value=context) as mock_create_context,
        patch.object(deployment.core_deployer, "deploy_all", return_value={}) as mock_deploy_all,
    ):
        response = deployment.deploy_all(provider="google", project_name="test_api_project")

    operation_context = mock_deploy_all.call_args.kwargs["operation_context"]
    mock_create_context.assert_called_once_with(
        "test_api_project",
        "gcp",
        operation_id=operation_context.operation_id,
    )
    assert mock_deploy_all.call_args.args == (context, "gcp")
    assert mock_deploy_all.call_args.kwargs["operation_context"].provider == "gcp"
    assert response["provider"] == "gcp"


def test_validate_provider_rejects_unknown_provider_with_stable_400():
    with pytest.raises(HTTPException) as exc_info:
        validate_provider("oracle")

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "Invalid provider 'oracle'. Valid providers are: aws, azure, gcp, google"


def test_request_scoped_project_does_not_require_active_project_match():
    context = MagicMock(name="deployment_context")
    with (
        patch.object(deployment, "check_template_protection"),
        patch.object(deployment, "validate_provider", return_value="aws"),
        patch.object(deployment, "get_project_storage", return_value=_project_storage_for("/projects/requested")),
        patch.object(deployment, "validate_project_directory"),
        patch.object(deployment, "create_context", return_value=context),
        patch.object(deployment.core_deployer, "deploy_all", return_value={}) as mock_deploy_all,
    ):
        response = deployment.deploy_all(provider="aws", project_name="requested")

    assert response["project_name"] == "requested"
    assert mock_deploy_all.call_args.args == (context, "aws")


def test_request_boundary_http_error_redacts_detail():
    with (
        patch.object(
            deployment,
            "check_template_protection",
            side_effect=HTTPException(
                status_code=400,
                detail="blocked project /app/upload/template client_secret=super-secret",
            ),
        ),
    ):
        with pytest.raises(HTTPException) as exc_info:
            deployment.deploy_all(provider="aws", project_name="template")

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail["error_code"] == "VALIDATION_ERROR"
    assert exc_info.value.detail["message"] == "blocked project <project-path> client_secret=<redacted>"
    assert "super-secret" not in exc_info.value.detail["message"]
    assert "/app/upload/template" not in exc_info.value.detail["message"]
    assert exc_info.value.detail["operation_id"]


def test_directory_validation_failure_maps_to_400_before_deploy():
    with (
        patch.object(deployment, "check_template_protection"),
        patch.object(deployment, "get_project_storage", return_value=_project_storage_for("/projects/test_api_project")),
        patch.object(
            deployment,
            "validate_project_directory",
            side_effect=ValueError("deployment_manifest.json package.files mismatch"),
        ) as mock_validate_directory,
        patch.object(deployment, "create_context") as mock_create_context,
        patch.object(deployment.core_deployer, "deploy_all") as mock_deploy_all,
    ):
        with pytest.raises(HTTPException) as exc_info:
            deployment.deploy_all(provider="aws", project_name="test_api_project")

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail["error_code"] == "VALIDATION_ERROR"
    assert "deployment_manifest.json package.files mismatch" in exc_info.value.detail["message"]
    assert exc_info.value.detail["operation_id"]
    mock_validate_directory.assert_called_once_with(Path("/projects/test_api_project"))
    mock_create_context.assert_not_called()
    mock_deploy_all.assert_not_called()


def test_directory_validation_error_redacts_runtime_project_paths():
    with (
        patch.object(deployment, "check_template_protection"),
        patch.object(deployment, "get_project_storage", return_value=_project_storage_for("/app/upload/test_api_project")),
        patch.object(
            deployment,
            "validate_project_directory",
            side_effect=ValueError("Project directory not found: /app/upload/test_api_project"),
        ),
        patch.object(deployment, "create_context") as mock_create_context,
    ):
        with pytest.raises(HTTPException) as exc_info:
            deployment.deploy_all(provider="aws", project_name="test_api_project")

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail["error_code"] == "VALIDATION_ERROR"
    assert exc_info.value.detail["message"] == "Validation failed: Project directory not found: <project-path>"
    assert "/app/upload/test_api_project" not in exc_info.value.detail["message"]
    mock_create_context.assert_not_called()


def test_facade_failure_maps_to_500_without_leaking_exception_detail(caplog):
    with caplog.at_level("ERROR", logger="digital_twin"):
        with (
            patch.object(deployment, "check_template_protection"),
            patch.object(deployment, "get_project_storage", return_value=_project_storage_for("/projects/test_api_project")),
            patch.object(deployment, "validate_project_directory"),
            patch.object(deployment, "create_context", return_value=MagicMock()),
            patch.object(deployment.core_deployer, "deploy_all", side_effect=RuntimeError("secret stack detail")),
        ):
            with pytest.raises(HTTPException) as exc_info:
                deployment.deploy_all(provider="aws", project_name="test_api_project")

    assert exc_info.value.status_code == 500
    assert exc_info.value.detail["error_code"] == "DEPLOYMENT_ERROR"
    assert exc_info.value.detail["message"] == "Deployment operation failed. Check server logs."
    assert "secret stack detail" not in exc_info.value.detail["message"]
    assert exc_info.value.detail["operation_id"]
    assert "secret stack detail" not in caplog.text


def test_destroy_facade_failure_maps_to_destruction_error_without_leaking_detail(caplog):
    with caplog.at_level("ERROR", logger="digital_twin"):
        with (
            patch.object(deployment, "check_template_protection"),
            patch.object(deployment, "get_project_storage", return_value=_project_storage_for("/projects/test_api_project")),
            patch.object(deployment, "validate_project_directory"),
            patch.object(deployment, "create_context", return_value=MagicMock()),
            patch.object(deployment.core_deployer, "destroy_all", side_effect=RuntimeError("client_secret=super-secret")),
        ):
            with pytest.raises(HTTPException) as exc_info:
                deployment.destroy_all(provider="aws", project_name="test_api_project")

    assert exc_info.value.status_code == 500
    assert exc_info.value.detail["error_code"] == "DESTRUCTION_ERROR"
    assert exc_info.value.detail["message"] == "Destruction operation failed. Check server logs."
    assert "super-secret" not in exc_info.value.detail["message"]
    assert exc_info.value.detail["operation_id"]
    assert "super-secret" not in caplog.text
