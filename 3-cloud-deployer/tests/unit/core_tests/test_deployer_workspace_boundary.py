"""Tests for the deployer facade's ephemeral workspace boundary."""

import asyncio
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from src.core.observability import OperationContext
from src.providers import deployer


def _context(project_path: Path = Path("/source/project")) -> SimpleNamespace:
    return SimpleNamespace(
        project_name="factory",
        project_path=project_path,
        config=SimpleNamespace(digital_twin_name="factory"),
        credentials={},
        providers={},
    )


@contextmanager
def _workspace_context(runtime_context):
    yield runtime_context, SimpleNamespace(workspace_path=runtime_context.project_path)


def test_deploy_all_runs_strategy_against_runtime_workspace_context():
    source_context = _context()
    runtime_context = _context(Path("/tmp/workspace/factory"))
    strategy = MagicMock()
    strategy.deploy_all.return_value = {"ok": {"value": True}}

    with (
        patch.object(deployer, "deployment_workspace", return_value=_workspace_context(runtime_context)) as mock_workspace,
        patch.object(deployer, "create_terraform_strategy", return_value=strategy) as mock_strategy,
    ):
        result = deployer.deploy_all(source_context, "aws")

    assert result == {"ok": {"value": True}}
    mock_workspace.assert_called_once_with(source_context, operation_context=None)
    mock_strategy.assert_called_once_with(runtime_context)
    strategy.deploy_all.assert_called_once_with(runtime_context)


def test_destroy_all_runs_canonical_strategy_once_against_runtime_workspace_context():
    source_context = _context()
    runtime_context = _context(Path("/tmp/workspace/factory"))
    strategy = MagicMock()

    with (
        patch.object(deployer, "deployment_workspace", return_value=_workspace_context(runtime_context)) as mock_workspace,
        patch.object(deployer, "create_terraform_strategy", return_value=strategy),
    ):
        deployer.destroy_all(source_context, "aws")

    mock_workspace.assert_called_once_with(source_context, operation_context=None)
    strategy.destroy_all.assert_called_once_with(runtime_context)


def test_deploy_all_terraform_uses_workspace_with_explicit_terraform_dir():
    source_context = _context()
    runtime_context = _context(Path("/tmp/workspace/factory"))
    strategy = MagicMock()
    strategy.deploy_all.return_value = {"ok": {"value": True}}

    with (
        patch.object(deployer, "deployment_workspace", return_value=_workspace_context(runtime_context)),
        patch.object(deployer, "create_terraform_strategy", return_value=strategy) as mock_strategy,
    ):
        result = deployer.deploy_all_terraform(source_context, terraform_dir="/app/src/terraform")

    assert result == {"ok": {"value": True}}
    mock_strategy.assert_called_once_with(
        runtime_context,
        terraform_dir="/app/src/terraform",
        project_path="/tmp/workspace/factory",
    )
    strategy.deploy_all.assert_called_once_with(runtime_context)


def test_destroy_all_terraform_uses_workspace_with_explicit_terraform_dir():
    source_context = _context()
    runtime_context = _context(Path("/tmp/workspace/factory"))
    strategy = MagicMock()

    with (
        patch.object(deployer, "deployment_workspace", return_value=_workspace_context(runtime_context)),
        patch.object(deployer, "create_terraform_strategy", return_value=strategy) as mock_strategy,
    ):
        deployer.destroy_all_terraform(source_context, terraform_dir="/app/src/terraform")

    mock_strategy.assert_called_once_with(
        runtime_context,
        terraform_dir="/app/src/terraform",
        project_path="/tmp/workspace/factory",
    )
    strategy.destroy_all.assert_called_once_with(runtime_context)


def test_deploy_all_passes_operation_context_to_workspace_boundary():
    source_context = _context()
    runtime_context = _context(Path("/tmp/workspace/factory"))
    operation_context = OperationContext.create(
        operation="deploy",
        project_name="factory",
        provider="aws",
        operation_id="op-123",
    )
    strategy = MagicMock()
    strategy.deploy_all.return_value = {"ok": {"value": True}}

    with (
        patch.object(deployer, "deployment_workspace", return_value=_workspace_context(runtime_context)) as mock_workspace,
        patch.object(deployer, "create_terraform_strategy", return_value=strategy),
    ):
        deployer.deploy_all(source_context, "aws", operation_context=operation_context)

    mock_workspace.assert_called_once_with(source_context, operation_context=operation_context)


def test_destroy_all_passes_operation_context_to_workspace_boundary():
    source_context = _context()
    runtime_context = _context(Path("/tmp/workspace/factory"))
    operation_context = OperationContext.create(
        operation="destroy",
        project_name="factory",
        provider="aws",
        operation_id="op-123",
    )
    strategy = MagicMock()

    with (
        patch.object(deployer, "deployment_workspace", return_value=_workspace_context(runtime_context)),
        patch.object(deployer, "create_terraform_strategy", return_value=strategy),
    ):
        deployer.destroy_all(source_context, "aws", operation_context=operation_context)

    strategy.destroy_all.assert_called_once_with(runtime_context)


def test_deploy_all_stream_sets_outputs_from_runtime_workspace_strategy():
    source_context = _context()
    runtime_context = _context(Path("/tmp/workspace/factory"))
    strategy = MagicMock()
    strategy.get_outputs.return_value = {"output": {"value": "ok"}}

    async def deploy_all_async(context):
        assert context is runtime_context
        yield "terraform init"
        yield "terraform apply"

    strategy.deploy_all_async = deploy_all_async
    output_sink = {}

    async def collect():
        return [
            line
            async for line in deployer.deploy_all_stream(source_context, output_sink=output_sink)
        ]

    with (
        patch.object(deployer, "deployment_workspace", return_value=_workspace_context(runtime_context)),
        patch.object(deployer, "create_terraform_strategy", return_value=strategy) as mock_strategy,
    ):
        lines = asyncio.run(collect())

    assert lines == ["terraform init", "terraform apply"]
    assert output_sink == {"outputs": {"output": {"value": "ok"}}}
    mock_strategy.assert_called_once_with(
        runtime_context,
        terraform_dir=None,
        project_path="/tmp/workspace/factory",
    )


def test_destroy_all_stream_runs_against_runtime_workspace_context():
    source_context = _context()
    runtime_context = _context(Path("/tmp/workspace/factory"))
    strategy = MagicMock()

    async def destroy_all_async(context):
        assert context is runtime_context
        yield "terraform destroy"

    strategy.destroy_all_async = destroy_all_async

    async def collect():
        return [line async for line in deployer.destroy_all_stream(source_context)]

    with (
        patch.object(deployer, "deployment_workspace", return_value=_workspace_context(runtime_context)),
        patch.object(deployer, "create_terraform_strategy", return_value=strategy) as mock_strategy,
    ):
        lines = asyncio.run(collect())

    assert lines == ["terraform destroy"]
    mock_strategy.assert_called_once_with(
        runtime_context,
        terraform_dir=None,
        project_path="/tmp/workspace/factory",
    )
