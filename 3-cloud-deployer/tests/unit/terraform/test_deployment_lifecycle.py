"""Contract tests for the canonical Terraform deployment lifecycle."""

import asyncio
import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from src.providers.terraform.deployer_strategy import TerraformDeployerStrategy
from src.providers.terraform.deployment_metadata import mark_built_packages_deployed
from src.providers.terraform.provider_runtime import configured_runtime_providers


class _StreamingRunner:
    def __init__(self, events, *, fail_apply=False):
        self.events = events
        self.fail_apply = fail_apply

    def init(self):
        self.events.append("init")

    def apply(self, *, var_file):
        self.events.append(("apply", var_file))
        if self.fail_apply:
            raise RuntimeError("apply failed")

    def output(self):
        self.events.append("output")
        return {"resource": "created"}

    async def init_async(self):
        self.events.append("init_async")
        yield "init output"

    async def apply_async(self, var_file):
        self.events.append(("apply_async", var_file))
        yield "apply output"


def _strategy(tmp_path, events):
    terraform_dir = tmp_path / "terraform-source"
    terraform_dir.mkdir()
    project_path = tmp_path / "project"
    project_path.mkdir()
    strategy = TerraformDeployerStrategy(str(terraform_dir), str(project_path))
    strategy._runner = _StreamingRunner(events)
    strategy._validate_credentials = MagicMock(side_effect=lambda: events.append("validate"))
    strategy._initialize_providers = MagicMock(side_effect=lambda context: events.append("providers"))
    strategy._build_packages = MagicMock(side_effect=lambda: events.append("build"))
    strategy._validate_project = MagicMock()
    strategy._generate_tfvars = MagicMock(side_effect=lambda: events.append("tfvars"))
    strategy._run_post_deployment = MagicMock(side_effect=lambda context: events.append("post"))
    strategy._record_applied_packages = MagicMock(
        side_effect=lambda: events.append("metadata") or 2
    )
    return strategy


def test_sync_deployment_records_packages_after_apply_before_post_deployment(tmp_path):
    events = []
    strategy = _strategy(tmp_path, events)
    context = SimpleNamespace()

    outputs = strategy.deploy_all(context)

    assert outputs == {"resource": "created"}
    assert events == [
        "validate",
        "providers",
        "build",
        "tfvars",
        "init",
        ("apply", str(strategy.tfvars_path)),
        "output",
        "metadata",
        "post",
    ]


def test_sync_deployment_does_not_advance_metadata_when_apply_fails(tmp_path):
    events = []
    strategy = _strategy(tmp_path, events)
    strategy._runner.fail_apply = True

    with pytest.raises(RuntimeError, match="apply failed"):
        strategy.deploy_all(SimpleNamespace())

    assert "metadata" not in events
    assert "post" not in events


def test_streaming_deployment_uses_same_canonical_order(tmp_path):
    events = []
    strategy = _strategy(tmp_path, events)

    async def collect():
        return [line async for line in strategy.deploy_all_async(SimpleNamespace())]

    lines = asyncio.run(collect())

    assert "init output" in lines
    assert "apply output" in lines
    assert events == [
        "validate",
        "providers",
        "build",
        "tfvars",
        "init_async",
        ("apply_async", str(strategy.tfvars_path)),
        "output",
        "metadata",
        "post",
    ]


def test_metadata_marks_only_current_built_hash_as_deployed(tmp_path):
    metadata_dir = tmp_path / ".build" / "metadata"
    metadata_dir.mkdir(parents=True)
    metadata_path = metadata_dir / "processor.aws.json"
    metadata_path.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "function": "processor",
                "provider": "aws",
                "source_hash": "sha256:" + "a" * 64,
                "artifact_hash": "sha256:" + "b" * 64,
                "last_built": "2026-01-01T00:00:00Z",
            }
        )
    )

    assert mark_built_packages_deployed(tmp_path) == 1

    metadata = json.loads(metadata_path.read_text())
    assert metadata["deployed_artifact_hash"] == "sha256:" + "b" * 64
    assert metadata["last_deployed"].endswith("Z")
    assert not metadata_path.with_suffix(".json.tmp").exists()


def test_runtime_initialization_only_includes_providers_with_sdk_owned_steps():
    assert configured_runtime_providers({"layer_1_provider": "google"}) == set()
    assert configured_runtime_providers({"layer_2_provider": "azure"}) == set()
    assert configured_runtime_providers({"layer_4_provider": "aws"}) == {"aws"}
