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


def test_deploy_route_invokes_canonical_facade_with_hard_response_shape():
    context = MagicMock(name="deployment_context")
    outputs = {"aws_lambda_dispatcher_name": {"value": "test-dispatcher"}}

    with (
        patch.object(deployment, "check_template_protection") as mock_template_guard,
        patch.object(deployment, "validate_project_context") as mock_project_guard,
        patch.object(deployment, "validate_provider", return_value="aws") as mock_validate_provider,
        patch.object(deployment, "resolve_project_context_path", return_value="/projects/test_api_project") as mock_resolve_path,
        patch.object(deployment, "validate_project_directory") as mock_validate_directory,
        patch.object(deployment, "create_context", return_value=context) as mock_create_context,
        patch.object(deployment.core_deployer, "deploy_all", return_value=outputs) as mock_deploy_all,
    ):
        response = deployment.deploy_all(provider="aws", project_name="test_api_project")

    mock_template_guard.assert_called_once_with("test_api_project", "deploy")
    mock_project_guard.assert_called_once_with("test_api_project")
    mock_validate_provider.assert_called_once_with("aws")
    mock_resolve_path.assert_called_once_with("test_api_project")
    mock_validate_directory.assert_called_once_with("/projects/test_api_project")
    mock_create_context.assert_called_once_with("test_api_project", "aws")
    mock_deploy_all.assert_called_once_with(context, "aws")

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
        patch.object(deployment, "validate_project_context") as mock_project_guard,
        patch.object(deployment, "validate_provider", return_value="aws") as mock_validate_provider,
        patch.object(deployment, "resolve_project_context_path", return_value="/projects/test_api_project") as mock_resolve_path,
        patch.object(deployment, "validate_project_directory") as mock_validate_directory,
        patch.object(deployment, "create_context", return_value=context) as mock_create_context,
        patch.object(deployment.core_deployer, "destroy_all") as mock_destroy_all,
    ):
        response = deployment.destroy_all(provider="aws", project_name="test_api_project")

    mock_template_guard.assert_called_once_with("test_api_project", "destroy")
    mock_project_guard.assert_called_once_with("test_api_project")
    mock_validate_provider.assert_called_once_with("aws")
    mock_resolve_path.assert_called_once_with("test_api_project")
    mock_validate_directory.assert_called_once_with("/projects/test_api_project")
    mock_create_context.assert_called_once_with("test_api_project", "aws")
    mock_destroy_all.assert_called_once_with(context, "aws")

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


async def _fake_deploy_stream(context, strategy=None, output_sink=None):
    assert context is not None
    assert strategy is None
    yield "terraform init"
    yield "terraform apply"
    if output_sink is not None:
        output_sink["outputs"] = {"output": {"value": "ok"}}


async def _fake_destroy_stream(context, strategy=None):
    assert context is not None
    assert strategy is None
    yield "terraform destroy"


async def _fake_failing_deploy_stream(context, strategy=None, output_sink=None):
    yield "terraform init"
    raise RuntimeError("failed in /tmp/twin2multicloud-deployer-workspaces/test-api-abc/terraform")


def test_deploy_stream_uses_canonical_facade_and_preserves_event_shape():
    context = MagicMock(name="deployment_context")
    context.project_path = Path("/projects/test_api_project")

    with (
        patch.object(deployment, "check_template_protection"),
        patch.object(deployment, "validate_project_context"),
        patch.object(deployment, "validate_provider", return_value="aws"),
        patch.object(deployment, "resolve_project_context_path", return_value="/projects/test_api_project"),
        patch.object(deployment, "validate_project_directory"),
        patch.object(deployment, "create_context", return_value=context),
        patch.object(deployment.core_deployer, "deploy_all_stream", new=_fake_deploy_stream),
    ):
        response = asyncio.run(deployment.deploy_stream(provider="aws", project_name="test_api_project"))
        body = asyncio.run(_collect_stream(response))

    assert response.media_type == "text/event-stream"
    assert 'data: {"event":"log","operation":"deploy","message":"terraform init"}\n\n' in body
    assert 'data: {"event":"log","operation":"deploy","message":"terraform apply"}\n\n' in body
    assert 'event: complete\ndata: {"event":"complete","operation":"deploy","success":true,"outputs":{"output":{"value":"ok"}}}\n\n' in body


def test_deploy_stream_redacts_workspace_paths_in_failure_event():
    context = MagicMock(name="deployment_context")
    context.project_path = Path("/projects/test_api_project")

    with (
        patch.object(deployment, "check_template_protection"),
        patch.object(deployment, "validate_project_context"),
        patch.object(deployment, "validate_provider", return_value="aws"),
        patch.object(deployment, "resolve_project_context_path", return_value="/projects/test_api_project"),
        patch.object(deployment, "validate_project_directory"),
        patch.object(deployment, "create_context", return_value=context),
        patch.object(deployment.core_deployer, "deploy_all_stream", new=_fake_failing_deploy_stream),
    ):
        response = asyncio.run(deployment.deploy_stream(provider="aws", project_name="test_api_project"))
        body = asyncio.run(_collect_stream(response))

    assert "<workspace-path>" in body
    assert "/tmp/twin2multicloud-deployer-workspaces" not in body


def test_destroy_stream_uses_canonical_facade_and_preserves_event_shape():
    context = MagicMock(name="deployment_context")
    context.project_path = Path("/projects/test_api_project")

    with (
        patch.object(deployment, "check_template_protection"),
        patch.object(deployment, "validate_project_context"),
        patch.object(deployment, "validate_provider", return_value="aws"),
        patch.object(deployment, "resolve_project_context_path", return_value="/projects/test_api_project"),
        patch.object(deployment, "validate_project_directory"),
        patch.object(deployment, "create_context", return_value=context),
        patch.object(deployment.core_deployer, "destroy_all_stream", new=_fake_destroy_stream),
    ):
        response = asyncio.run(deployment.destroy_stream(provider="aws", project_name="test_api_project"))
        body = asyncio.run(_collect_stream(response))

    assert response.media_type == "text/event-stream"
    assert 'data: {"event":"log","operation":"destroy","message":"terraform destroy"}\n\n' in body
    assert 'event: complete\ndata: {"event":"complete","operation":"destroy","success":true}\n\n' in body


def test_google_provider_alias_is_normalized_to_gcp_in_deploy_response():
    context = MagicMock(name="deployment_context")

    with (
        patch.object(deployment, "check_template_protection"),
        patch.object(deployment, "validate_project_context"),
        patch.object(deployment, "resolve_project_context_path", return_value="/projects/test_api_project"),
        patch.object(deployment, "validate_project_directory"),
        patch.object(deployment, "create_context", return_value=context) as mock_create_context,
        patch.object(deployment.core_deployer, "deploy_all", return_value={}) as mock_deploy_all,
    ):
        response = deployment.deploy_all(provider="google", project_name="test_api_project")

    mock_create_context.assert_called_once_with("test_api_project", "gcp")
    mock_deploy_all.assert_called_once_with(context, "gcp")
    assert response["provider"] == "gcp"


def test_validate_provider_rejects_unknown_provider_with_stable_400():
    with pytest.raises(HTTPException) as exc_info:
        validate_provider("oracle")

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "Invalid provider 'oracle'. Valid providers are: aws, azure, gcp, google"


def test_active_project_mismatch_remains_conflict():
    with (
        patch.object(deployment, "check_template_protection"),
        patch.object(
            deployment,
            "validate_project_context",
            side_effect=HTTPException(status_code=409, detail="project mismatch"),
        ),
    ):
        with pytest.raises(HTTPException) as exc_info:
            deployment.deploy_all(provider="aws", project_name="test_api_project")

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail == "project mismatch"


def test_directory_validation_failure_maps_to_400_before_deploy():
    with (
        patch.object(deployment, "check_template_protection"),
        patch.object(deployment, "validate_project_context"),
        patch.object(deployment, "resolve_project_context_path", return_value="/projects/test_api_project"),
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
    assert "deployment_manifest.json package.files mismatch" in exc_info.value.detail
    mock_validate_directory.assert_called_once_with("/projects/test_api_project")
    mock_create_context.assert_not_called()
    mock_deploy_all.assert_not_called()


def test_directory_validation_error_redacts_runtime_project_paths():
    with (
        patch.object(deployment, "check_template_protection"),
        patch.object(deployment, "validate_project_context"),
        patch.object(deployment, "resolve_project_context_path", return_value="/app/upload/test_api_project"),
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
    assert exc_info.value.detail == "Validation failed: Project directory not found: <project-path>"
    assert "/app/upload/test_api_project" not in exc_info.value.detail
    mock_create_context.assert_not_called()


def test_facade_failure_maps_to_500_without_leaking_exception_detail():
    with (
        patch.object(deployment, "check_template_protection"),
        patch.object(deployment, "validate_project_context"),
        patch.object(deployment, "resolve_project_context_path", return_value="/projects/test_api_project"),
        patch.object(deployment, "validate_project_directory"),
        patch.object(deployment, "create_context", return_value=MagicMock()),
        patch.object(deployment.core_deployer, "deploy_all", side_effect=RuntimeError("secret stack detail")),
    ):
        with pytest.raises(HTTPException) as exc_info:
            deployment.deploy_all(provider="aws", project_name="test_api_project")

    assert exc_info.value.status_code == 500
    assert exc_info.value.detail == "Deployment operation failed. Check logs."
    assert "secret stack detail" not in exc_info.value.detail
