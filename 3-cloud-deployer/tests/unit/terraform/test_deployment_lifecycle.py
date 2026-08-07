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

    def state_list(self):
        return SimpleNamespace(returncode=0, stdout="")

    def apply_targets(self, var_file, targets):
        self.events.append(("apply_targets", var_file, targets))

    async def init_async(self):
        self.events.append("init_async")
        yield "init output"

    async def apply_async(self, var_file):
        self.events.append(("apply_async", var_file))
        yield "apply output"

    async def apply_targets_async(self, var_file, targets):
        self.events.append(("apply_targets_async", var_file, targets))
        yield "foundation output"


def _strategy(tmp_path, events):
    terraform_dir = tmp_path / "terraform-source"
    terraform_dir.mkdir()
    project_path = tmp_path / "project"
    project_path.mkdir()
    strategy = TerraformDeployerStrategy(str(terraform_dir), str(project_path))
    strategy._runner = _StreamingRunner(events)
    strategy._validate_credentials = MagicMock(
        side_effect=lambda: events.append("validate")
    )
    strategy._initialize_providers = MagicMock(
        side_effect=lambda context: events.append("providers")
    )
    strategy._prepare_shared_identity_capabilities = MagicMock(
        side_effect=lambda context: events.append("identity")
    )
    strategy._build_packages = MagicMock(side_effect=lambda: events.append("build"))
    strategy._validate_project = MagicMock()
    strategy._generate_tfvars = MagicMock(side_effect=lambda: events.append("tfvars"))
    strategy._prepare_gcp_v2_image_foundation = MagicMock(return_value=False)
    strategy._prepare_aws_v2_image_foundation = MagicMock(return_value=False)
    strategy._prepare_azure_v2_image_foundation = MagicMock(return_value=False)
    strategy._run_post_deployment = MagicMock(
        side_effect=lambda context: events.append("post")
    )
    strategy._record_applied_packages = MagicMock(
        side_effect=lambda: events.append("metadata") or 2
    )
    return strategy


def _context():
    return SimpleNamespace(operation_id="op-test-terraform-lifecycle")


def test_sync_deployment_records_packages_after_apply_before_post_deployment(tmp_path):
    events = []
    strategy = _strategy(tmp_path, events)
    context = _context()

    outputs = strategy.deploy_all(context)

    assert outputs == {"resource": "created"}
    assert events == [
        "validate",
        "providers",
        "identity",
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
        strategy.deploy_all(_context())

    assert "metadata" not in events
    assert "post" not in events


def test_sync_gcp_deployment_applies_foundation_images_cloud_then_kubernetes(tmp_path):
    events = []
    strategy = _strategy(tmp_path, events)
    strategy._prepare_gcp_v2_image_foundation.return_value = True
    strategy._gcp_kubernetes_state_exists = MagicMock(return_value=False)
    strategy._publish_gcp_v2_images = MagicMock(
        side_effect=lambda: events.append("publish")
    )
    strategy._merge_tfvars = MagicMock(
        side_effect=lambda value: events.append(("merge", value))
    )

    strategy.deploy_all(_context())

    foundation = (
        "apply_targets",
        str(strategy.tfvars_path),
        strategy.GCP_V2_IMAGE_FOUNDATION_TARGETS,
    )
    assert events.index(foundation) < events.index("publish")
    apply_positions = [
        index
        for index, event in enumerate(events)
        if isinstance(event, tuple) and event[0] == "apply"
    ]
    assert len(apply_positions) == 2
    assert (
        apply_positions[0]
        < events.index(("merge", {"gcp_v2_kubernetes_stage_enabled": True}))
        < apply_positions[1]
    )


def test_sync_gcp_resume_does_not_remove_existing_kubernetes_resources(tmp_path):
    events = []
    strategy = _strategy(tmp_path, events)
    strategy._prepare_gcp_v2_image_foundation.return_value = True
    strategy._gcp_kubernetes_state_exists = MagicMock(return_value=True)
    strategy._publish_gcp_v2_images = MagicMock(
        side_effect=lambda: events.append("publish")
    )
    strategy._merge_tfvars = MagicMock(
        side_effect=lambda value: events.append(("merge", value))
    )

    strategy.deploy_all(_context())

    applies = [
        event for event in events if isinstance(event, tuple) and event[0] == "apply"
    ]
    assert len(applies) == 1
    assert ("merge", {"gcp_v2_kubernetes_stage_enabled": True}) in events


def test_sync_aws_deployment_publishes_image_before_runtime_apply(tmp_path):
    events = []
    strategy = _strategy(tmp_path, events)
    strategy._prepare_aws_v2_image_foundation.return_value = True
    strategy._publish_aws_v2_images = MagicMock(
        side_effect=lambda: events.append("publish-aws")
    )

    strategy.deploy_all(_context())

    foundation = (
        "apply_targets",
        str(strategy.tfvars_path),
        strategy.AWS_V2_IMAGE_FOUNDATION_TARGETS,
    )
    runtime_apply = ("apply", str(strategy.tfvars_path))
    assert (
        events.index(foundation)
        < events.index("publish-aws")
        < events.index(runtime_apply)
    )


def test_sync_azure_deployment_publishes_image_before_runtime_apply(tmp_path):
    events = []
    strategy = _strategy(tmp_path, events)
    strategy._prepare_azure_v2_image_foundation.return_value = True
    strategy._publish_azure_v2_images = MagicMock(
        side_effect=lambda: events.append("publish-azure")
    )

    strategy.deploy_all(_context())

    foundation = (
        "apply_targets",
        str(strategy.tfvars_path),
        strategy.AZURE_V2_IMAGE_FOUNDATION_TARGETS,
    )
    runtime_apply = ("apply", str(strategy.tfvars_path))
    assert (
        events.index(foundation)
        < events.index("publish-azure")
        < events.index(runtime_apply)
    )


def test_sync_combined_foundations_publish_in_canonical_provider_order(tmp_path):
    events = []
    strategy = _strategy(tmp_path, events)
    strategy._prepare_aws_v2_image_foundation.return_value = True
    strategy._prepare_azure_v2_image_foundation.return_value = True
    strategy._publish_aws_v2_images = MagicMock(
        side_effect=lambda: events.append("publish-aws")
    )
    strategy._publish_azure_v2_images = MagicMock(
        side_effect=lambda: events.append("publish-azure")
    )

    strategy.deploy_all(_context())

    foundation = (
        "apply_targets",
        str(strategy.tfvars_path),
        (
            *strategy.AWS_V2_IMAGE_FOUNDATION_TARGETS,
            *strategy.AZURE_V2_IMAGE_FOUNDATION_TARGETS,
        ),
    )
    runtime_apply = ("apply", str(strategy.tfvars_path))
    assert (
        events.index(foundation)
        < events.index("publish-aws")
        < events.index("publish-azure")
        < events.index(runtime_apply)
    )


def test_streaming_deployment_uses_same_canonical_order(tmp_path):
    events = []
    strategy = _strategy(tmp_path, events)

    async def collect():
        return [line async for line in strategy.deploy_all_async(_context())]

    lines = asyncio.run(collect())

    assert "init output" in lines
    assert "apply output" in lines
    assert [line for line in lines if line.startswith("T2MC_STAGE_COMPLETED:")] == [
        "T2MC_STAGE_COMPLETED:package",
        "T2MC_STAGE_COMPLETED:preplan",
        "T2MC_STAGE_COMPLETED:terraform",
        "T2MC_STAGE_COMPLETED:postapply",
    ]
    assert events == [
        "validate",
        "providers",
        "identity",
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
    assert configured_runtime_providers({"layer_2_provider": "aws"}) == set()
    assert configured_runtime_providers({"layer_4_provider": "aws"}) == {"aws"}


def test_runtime_initializes_aws_for_graph_owned_azure_identity_edge():
    graph = SimpleNamespace(
        nodes=(
            SimpleNamespace(node_id="aws-hot", provider="aws"),
            SimpleNamespace(node_id="azure-twin", provider="azure"),
        ),
        edges=(
            SimpleNamespace(
                source_node_id="aws-hot",
                destination_node_id="azure-twin",
                transfer_route_class="cross_provider",
                trust_ref={"id": "trust.workload-identity-federation"},
            ),
        ),
    )

    assert configured_runtime_providers(
        {"layer_3_hot_provider": "aws", "layer_4_provider": "azure"},
        graph,
    ) == {"aws", "azure"}
