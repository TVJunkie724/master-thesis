"""
Unit tests for build_all_packages function.

Verifies that build_all_packages calls all required builder functions,
including build_user_packages (which was previously missing).
"""

import json
from pathlib import Path
import tarfile
from types import MappingProxyType
from unittest.mock import patch
import zipfile

import pytest

from src.architecture_profiles import resolve_deployment_graph
from src.deployment_specification import (
    ValidatedDeploymentManifest,
    validate_resolved_deployment_specification,
)
from src.providers.terraform.package_builders.azure import (
    build_azure_graph_bundles,
)
from src.providers.terraform.package_builders.azure_six_layer import (
    build_azure_six_layer_graph_apps,
)
from src.providers.terraform.package_builders.azure_six_layer_container import (
    PACKAGE_ID as AZURE_SIX_LAYER_STORAGE_MOVER_PACKAGE_ID,
    build_azure_six_layer_storage_mover_context,
)
from src.providers.terraform.package_builders.aws_eventing import (
    build_aws_eventing_app,
)
from src.providers.terraform.package_builder import (
    _aws_six_layer_bridge_selected,
    _selected_static_function_packages,
    _validate_graph_package_selection,
)


MANIFEST_ROOT = (
    Path(__file__).resolve().parents[3]
    / "src"
    / "contracts"
    / "generated"
    / "deployment-manifest"
    / "v3"
    / "fixtures"
    / "valid"
)
SIX_LAYER_MANIFEST_ROOT = (
    MANIFEST_ROOT.parent.parent.parent / "v4" / "fixtures" / "valid"
)
SIX_LAYER_LOGICAL_TO_SLOT = {
    "component.ingestion": "l1_ingestion",
    "component.processing": "l2_processing",
    "component.hot-storage": "l3_hot_storage",
    "component.cool-storage": "l3_cool_storage",
    "component.archive-storage": "l3_archive_storage",
    "component.twin-state": "l4_twin_state",
    "component.visualization": "l5_visualization",
}


def _resolve_offline_v4(name: str):
    manifest = json.loads((SIX_LAYER_MANIFEST_ROOT / name).read_text("utf-8"))
    specification = validate_resolved_deployment_specification(
        manifest["resolved_deployment_specification"]
    )
    provider_by_slot = {
        SIX_LAYER_LOGICAL_TO_SLOT[item["logical_component_id"]]: item["provider"]
        for item in manifest["resolved_twin_architecture"]["component_assignments"]
        if item["logical_component_id"] in SIX_LAYER_LOGICAL_TO_SLOT
    }
    validated = ValidatedDeploymentManifest(
        manifest=MappingProxyType(manifest),
        specification=specification,
        provider_by_slot=MappingProxyType(provider_by_slot),
        manifest_version="4.0",
        architecture=MappingProxyType(manifest["resolved_twin_architecture"]),
    )
    return resolve_deployment_graph(validated)


def test_azure_graph_bundles_are_selected_and_deterministic(tmp_path):
    selected = ("ingestion", "persister")

    first = build_azure_graph_bundles(tmp_path, selected)
    first_bytes = {package_id: path.read_bytes() for package_id, path in first.items()}
    second = build_azure_graph_bundles(tmp_path, selected)

    assert set(second) == {"azure_bundle_l0", "azure_bundle_l2"}
    assert {
        package_id: path.read_bytes() for package_id, path in second.items()
    } == first_bytes
    with zipfile.ZipFile(second["azure_bundle_l0"]) as archive:
        names = set(archive.namelist())
        main = archive.read("function_app.py").decode("utf-8")
    assert "ingestion/function_app.py" in names
    assert "hot_writer/function_app.py" not in names
    assert "ingestion_bp" in main


def test_azure_six_layer_graph_app_is_a_standalone_deterministic_package(tmp_path):
    first = build_azure_six_layer_graph_apps(tmp_path, ("six-layer-domain",))
    first_bytes = first["azure_six-layer-domain"].read_bytes()
    second = build_azure_six_layer_graph_apps(tmp_path, ("six-layer-domain",))

    assert second["azure_six-layer-domain"].read_bytes() == first_bytes
    with zipfile.ZipFile(second["azure_six-layer-domain"]) as archive:
        assert {
            "bridge_core.py",
            "core.py",
            "function_app.py",
            "host.json",
            "phase8_eventing/aws/bridge.py",
            "phase8_eventing/aws/runtime.py",
            "phase8_eventing/azure/bridge.py",
            "phase8_eventing/azure/runtime.py",
            "phase8_eventing/bridge_application.py",
            "phase8_eventing/destination_identity.py",
            "phase8_eventing/destination_publishers.py",
            "phase8_eventing/gcp/bridge.py",
            "phase8_eventing/gcp/runtime.py",
            "requirements.txt",
        } <= set(archive.namelist())
        function_app = archive.read("function_app.py").decode("utf-8")
        requirements = archive.read("requirements.txt").decode("utf-8")
        assert "cross_cloud_telemetry_bridge" in function_app
        assert "cross_cloud_control_bridge" in function_app
        assert 'max_retry_count="5"' in function_app
        assert "_event_hub_delivery_attempt(context)" in function_app
        assert "google-cloud-pubsub==2.39.0" in requirements
        assert "boto3==1.43.47" in requirements


def test_azure_six_layer_storage_mover_context_is_complete_and_deterministic(tmp_path):
    first = build_azure_six_layer_storage_mover_context(tmp_path)
    first_bytes = first[AZURE_SIX_LAYER_STORAGE_MOVER_PACKAGE_ID].read_bytes()
    second = build_azure_six_layer_storage_mover_context(tmp_path)

    assert second[AZURE_SIX_LAYER_STORAGE_MOVER_PACKAGE_ID].read_bytes() == first_bytes
    with tarfile.open(
        second[AZURE_SIX_LAYER_STORAGE_MOVER_PACKAGE_ID], mode="r:gz"
    ) as archive:
        assert set(archive.getnames()) == {
            "Dockerfile",
            "constraints.txt",
            "requirements.txt",
            "storage_mover.py",
        }


def test_aws_eventing_app_is_standalone_and_deterministic(tmp_path):
    first = build_aws_eventing_app(tmp_path)
    first_bytes = first["aws_six-layer-eventing"].read_bytes()
    second = build_aws_eventing_app(tmp_path)

    assert second["aws_six-layer-eventing"].read_bytes() == first_bytes
    with zipfile.ZipFile(second["aws_six-layer-eventing"]) as archive:
        names = set(archive.namelist())
        handler = archive.read("lambda_function.py").decode("utf-8")
    assert {
        "lambda_function.py",
        "phase8_eventing/bridge_core.py",
        "phase8_eventing/aws/bridge.py",
    } <= names
    assert "def lambda_handler" in handler
    assert "function_url" not in handler


def test_azure_eventing_app_is_standalone_and_deterministic(tmp_path):
    first = build_azure_six_layer_graph_apps(tmp_path, ("six-layer-eventing",))
    first_bytes = first["azure_six-layer-eventing"].read_bytes()
    second = build_azure_six_layer_graph_apps(tmp_path, ("six-layer-eventing",))

    assert second["azure_six-layer-eventing"].read_bytes() == first_bytes
    with zipfile.ZipFile(second["azure_six-layer-eventing"]) as archive:
        names = set(archive.namelist())
        function_app = archive.read("function_app.py").decode("utf-8")
    assert {
        "function_app.py",
        "host.json",
        "requirements.txt",
        "phase8_eventing/bridge_core.py",
    } <= names
    assert "event-telemetry-processor" in function_app
    assert "EVENT_DOMAIN_DELIVERY_KEY" in function_app


def test_six_layer_cross_cloud_graph_selects_event_and_bridge_packages():
    graph = _resolve_offline_v4("six-layer-aws-azure-eventing-small.json")

    selected, package_ids = _selected_static_function_packages(graph)

    assert selected["aws"] == ("six-layer-domain",)
    assert selected["azure"] == ("six-layer-domain", "six-layer-eventing")
    assert {
        "aws_six-layer-domain",
        "azure_six-layer-domain",
        "azure_six-layer-eventing",
    } <= package_ids
    assert _aws_six_layer_bridge_selected(graph)


def test_six_layer_event_owner_is_resolved_from_the_graph():
    graph = _resolve_offline_v4("six-layer-aws-azure-eventing-small.json")
    providers = {
        "layer_1_provider": "aws",
        "layer_2_provider": "aws",
        "layer_3_hot_provider": "aws",
        "layer_3_cold_provider": "azure",
        "layer_3_archive_provider": "azure",
        "layer_4_provider": "azure",
        "layer_5_provider": "aws",
    }

    with patch(
        "src.providers.terraform.package_builder._artifact_source_digest",
        side_effect=lambda artifact: artifact["source_digest"],
    ):
        _validate_graph_package_selection(graph, providers)


class TestBuildAllPackages:
    """Tests for the build_all_packages orchestration function."""

    @pytest.fixture
    def mock_providers_all_gcp(self):
        """Provider config with all layers on GCP."""
        return {
            "layer_1_provider": "google",
            "layer_2_provider": "google",
            "layer_3_hot_provider": "google",
            "layer_3_cold_provider": "google",
            "layer_3_archive_provider": "google",
        }

    @pytest.fixture
    def mock_providers_all_aws(self):
        """Provider config with all layers on AWS."""
        return {
            "layer_1_provider": "aws",
            "layer_2_provider": "aws",
            "layer_3_hot_provider": "aws",
            "layer_3_cold_provider": "aws",
            "layer_3_archive_provider": "aws",
        }

    def test_calls_all_builder_functions(self, tmp_path, mock_providers_all_gcp):
        """Verify build_all_packages calls all expected builder functions."""
        from src.providers.terraform.package_builder import build_all_packages

        terraform_dir = tmp_path / "terraform"
        terraform_dir.mkdir()
        project_path = tmp_path / "project"
        project_path.mkdir()

        with (
            patch(
                "src.providers.terraform.package_builder.build_aws_lambda_packages"
            ) as mock_aws,
            patch(
                "src.providers.terraform.package_builder.build_azure_function_packages"
            ) as mock_azure,
            patch(
                "src.providers.terraform.package_builder.build_gcp_cloud_function_packages"
            ) as mock_gcp,
            patch(
                "src.providers.terraform.package_builder.build_user_packages"
            ) as mock_user,
        ):
            # Configure mocks to return empty dicts
            mock_aws.return_value = {"aws_pkg": Path("/tmp/aws.zip")}
            mock_azure.return_value = {"azure_pkg": Path("/tmp/azure.zip")}
            mock_gcp.return_value = {"gcp_pkg": Path("/tmp/gcp.zip")}
            mock_user.return_value = {"user_pkg": Path("/tmp/user.zip")}

            build_all_packages(terraform_dir, project_path, mock_providers_all_gcp)

            # Assert all builder functions were called
            mock_aws.assert_called_once()
            mock_azure.assert_called_once()
            mock_gcp.assert_called_once()
            mock_user.assert_called_once()

            # Verify build_user_packages was called with correct args
            mock_user.assert_called_with(project_path, mock_providers_all_gcp)

    def test_merges_all_package_results(self, tmp_path, mock_providers_all_gcp):
        """Verify build_all_packages merges results from all builders."""
        from src.providers.terraform.package_builder import build_all_packages

        terraform_dir = tmp_path / "terraform"
        terraform_dir.mkdir()
        project_path = tmp_path / "project"
        project_path.mkdir()

        with (
            patch(
                "src.providers.terraform.package_builder.build_aws_lambda_packages"
            ) as mock_aws,
            patch(
                "src.providers.terraform.package_builder.build_azure_function_packages"
            ) as mock_azure,
            patch(
                "src.providers.terraform.package_builder.build_gcp_cloud_function_packages"
            ) as mock_gcp,
            patch(
                "src.providers.terraform.package_builder.build_user_packages"
            ) as mock_user,
        ):
            mock_aws.return_value = {"aws_dispatcher": Path("/tmp/aws_dispatcher.zip")}
            mock_azure.return_value = {"azure_l0": Path("/tmp/azure_l0.zip")}
            mock_gcp.return_value = {"gcp_persister": Path("/tmp/gcp_persister.zip")}
            mock_user.return_value = {
                "processor-sensor1": Path("/tmp/processor-sensor1.zip")
            }

            result = build_all_packages(
                terraform_dir, project_path, mock_providers_all_gcp
            )

            # Verify all packages are in the result
            assert "aws_dispatcher" in result
            assert "azure_l0" in result
            assert "gcp_persister" in result
            assert "processor-sensor1" in result
            assert len(result) == 4

    def test_user_packages_called_for_gcp_l2(self, tmp_path, mock_providers_all_gcp):
        """Verify build_user_packages is called when L2 is GCP (per-device processors)."""
        from src.providers.terraform.package_builder import build_all_packages

        terraform_dir = tmp_path / "terraform"
        terraform_dir.mkdir()
        project_path = tmp_path / "project"
        project_path.mkdir()

        with (
            patch(
                "src.providers.terraform.package_builder.build_aws_lambda_packages",
                return_value={},
            ),
            patch(
                "src.providers.terraform.package_builder.build_azure_function_packages",
                return_value={},
            ),
            patch(
                "src.providers.terraform.package_builder.build_gcp_cloud_function_packages",
                return_value={},
            ),
            patch(
                "src.providers.terraform.package_builder.build_user_packages"
            ) as mock_user,
        ):
            mock_user.return_value = {
                "processor-temperature-sensor-1": Path("/tmp/proc1.zip"),
                "processor-pressure-sensor-1": Path("/tmp/proc2.zip"),
            }

            result = build_all_packages(
                terraform_dir, project_path, mock_providers_all_gcp
            )

            # build_user_packages should be called regardless of provider
            mock_user.assert_called_once()

            # User packages should be in result
            assert "processor-temperature-sensor-1" in result
            assert "processor-pressure-sensor-1" in result

    def test_user_packages_called_for_aws_l2(self, tmp_path, mock_providers_all_aws):
        """Verify build_user_packages is also called when L2 is AWS."""
        from src.providers.terraform.package_builder import build_all_packages

        terraform_dir = tmp_path / "terraform"
        terraform_dir.mkdir()
        project_path = tmp_path / "project"
        project_path.mkdir()

        with (
            patch(
                "src.providers.terraform.package_builder.build_aws_lambda_packages",
                return_value={},
            ),
            patch(
                "src.providers.terraform.package_builder.build_azure_function_packages",
                return_value={},
            ),
            patch(
                "src.providers.terraform.package_builder.build_gcp_cloud_function_packages",
                return_value={},
            ),
            patch(
                "src.providers.terraform.package_builder.build_user_packages"
            ) as mock_user,
        ):
            mock_user.return_value = {}

            build_all_packages(terraform_dir, project_path, mock_providers_all_aws)

            # build_user_packages should always be called
            mock_user.assert_called_once()
