"""
Deployment route boundary tests.

The route layer must remain a thin HTTP adapter. Deployment orchestration must
enter the canonical facade in src.providers.deployer.
"""

import asyncio
from unittest.mock import MagicMock, patch

from src.api import deployment


def test_deploy_route_invokes_canonical_facade_with_hard_response_shape():
    context = MagicMock(name="deployment_context")
    outputs = {"aws_lambda_dispatcher_name": {"value": "test-dispatcher"}}

    with (
        patch.object(deployment, "check_template_protection") as mock_template_guard,
        patch.object(deployment, "validate_project_context") as mock_project_guard,
        patch.object(deployment, "validate_provider", return_value="aws") as mock_validate_provider,
        patch.object(deployment, "create_context", return_value=context) as mock_create_context,
        patch.object(deployment.core_deployer, "deploy_all", return_value=outputs) as mock_deploy_all,
    ):
        response = deployment.deploy_all(provider="aws", project_name="test_api_project")

    mock_template_guard.assert_called_once_with("test_api_project", "deploy")
    mock_project_guard.assert_called_once_with("test_api_project")
    mock_validate_provider.assert_called_once_with("aws")
    mock_create_context.assert_called_once_with("test_api_project", "aws")
    mock_deploy_all.assert_called_once_with(context, "aws")

    assert response == {
        "message": "Core and IoT services deployed successfully",
        "terraform_outputs": outputs,
    }


def test_destroy_route_invokes_canonical_facade_with_hard_response_shape():
    context = MagicMock(name="deployment_context")

    with (
        patch.object(deployment, "check_template_protection") as mock_template_guard,
        patch.object(deployment, "validate_project_context") as mock_project_guard,
        patch.object(deployment, "validate_provider", return_value="aws") as mock_validate_provider,
        patch.object(deployment, "create_context", return_value=context) as mock_create_context,
        patch.object(deployment.core_deployer, "destroy_all") as mock_destroy_all,
    ):
        response = deployment.destroy_all(provider="aws", project_name="test_api_project")

    mock_template_guard.assert_called_once_with("test_api_project", "destroy")
    mock_project_guard.assert_called_once_with("test_api_project")
    mock_validate_provider.assert_called_once_with("aws")
    mock_create_context.assert_called_once_with("test_api_project", "aws")
    mock_destroy_all.assert_called_once_with(context, "aws")

    assert response == {"message": "Core and IoT services destroyed successfully"}


async def _collect_stream(streaming_response) -> str:
    chunks = []
    async for chunk in streaming_response.body_iterator:
        chunks.append(chunk.decode("utf-8") if isinstance(chunk, bytes) else chunk)
    return "".join(chunks)


async def _fake_deploy_stream(context, strategy=None):
    assert context is not None
    assert strategy is not None
    yield "terraform init"
    yield "terraform apply"


async def _fake_destroy_stream(context, strategy=None):
    assert context is not None
    assert strategy is not None
    yield "terraform destroy"


def test_deploy_stream_uses_canonical_facade_and_preserves_event_shape():
    context = MagicMock(name="deployment_context")
    strategy = MagicMock(name="terraform_strategy")

    with (
        patch.object(deployment, "check_template_protection"),
        patch.object(deployment, "validate_project_context"),
        patch.object(deployment, "validate_provider", return_value="aws"),
        patch.object(deployment, "create_context", return_value=context),
        patch.object(deployment.core_deployer, "create_terraform_strategy", return_value=strategy) as mock_strategy,
        patch.object(deployment.core_deployer, "deploy_all_stream", new=_fake_deploy_stream),
        patch.object(deployment.core_deployer, "get_terraform_outputs", return_value={"output": {"value": "ok"}}),
    ):
        response = asyncio.run(deployment.deploy_stream(provider="aws", project_name="test_api_project"))
        body = asyncio.run(_collect_stream(response))

    mock_strategy.assert_called_once()
    assert response.media_type == "text/event-stream"
    assert "data: terraform init\n\n" in body
    assert "data: terraform apply\n\n" in body
    assert "event: complete\n" in body
    assert '"success": true' in body
    assert '"outputs": {"output": {"value": "ok"}}' in body


def test_destroy_stream_uses_canonical_facade_and_preserves_event_shape():
    context = MagicMock(name="deployment_context")
    strategy = MagicMock(name="terraform_strategy")

    with (
        patch.object(deployment, "check_template_protection"),
        patch.object(deployment, "validate_project_context"),
        patch.object(deployment, "validate_provider", return_value="aws"),
        patch.object(deployment, "create_context", return_value=context),
        patch.object(deployment.core_deployer, "create_terraform_strategy", return_value=strategy) as mock_strategy,
        patch.object(deployment.core_deployer, "destroy_all_stream", new=_fake_destroy_stream),
    ):
        response = asyncio.run(deployment.destroy_stream(provider="aws", project_name="test_api_project"))
        body = asyncio.run(_collect_stream(response))

    mock_strategy.assert_called_once()
    assert response.media_type == "text/event-stream"
    assert "data: terraform destroy\n\n" in body
    assert "event: complete\n" in body
    assert '"success": true' in body
