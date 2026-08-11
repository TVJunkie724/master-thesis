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
    validate_deployment_manifest,
    validate_resolved_deployment_specification,
)
from src.providers.terraform.package_builders.azure import (
    build_azure_graph_bundles,
)
from src.providers.terraform.package_builders.azure_v2 import (
    build_azure_v2_graph_apps,
)
from src.providers.terraform.package_builders.azure_v2_container import (
    PACKAGE_ID as AZURE_V2_STORAGE_MOVER_PACKAGE_ID,
    build_azure_v2_storage_mover_context,
)
from src.providers.terraform.package_builders.aws_eventing import (
    build_aws_eventing_app,
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
V2_MANIFEST_ROOT = MANIFEST_ROOT.parent.parent.parent / "v4" / "fixtures" / "valid"
V2_LOGICAL_TO_SLOT = {
    "component.ingestion": "l1_ingestion",
    "component.processing": "l2_processing",
    "component.hot-storage": "l3_hot_storage",
    "component.cool-storage": "l3_cool_storage",
    "component.archive-storage": "l3_archive_storage",
    "component.twin-state": "l4_twin_state",
    "component.visualization": "l5_visualization",
}


def _resolve_offline_v4(name: str):
    manifest = json.loads((V2_MANIFEST_ROOT / name).read_text("utf-8"))
    specification = validate_resolved_deployment_specification(
        manifest["resolved_deployment_specification"]
    )
    provider_by_slot = {
        V2_LOGICAL_TO_SLOT[item["logical_component_id"]]: item["provider"]
        for item in manifest["resolved_twin_architecture"]["component_assignments"]
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


def test_azure_v2_graph_app_is_a_standalone_deterministic_package(tmp_path):
    first = build_azure_v2_graph_apps(tmp_path, ("five-layer-v2",))
    first_bytes = first["azure_five-layer-v2"].read_bytes()
    second = build_azure_v2_graph_apps(tmp_path, ("five-layer-v2",))

    assert second["azure_five-layer-v2"].read_bytes() == first_bytes
    with zipfile.ZipFile(second["azure_five-layer-v2"]) as archive:
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


def test_azure_v2_storage_mover_context_is_complete_and_deterministic(tmp_path):
    first = build_azure_v2_storage_mover_context(tmp_path)
    first_bytes = first[AZURE_V2_STORAGE_MOVER_PACKAGE_ID].read_bytes()
    second = build_azure_v2_storage_mover_context(tmp_path)

    assert second[AZURE_V2_STORAGE_MOVER_PACKAGE_ID].read_bytes() == first_bytes
    with tarfile.open(second[AZURE_V2_STORAGE_MOVER_PACKAGE_ID], mode="r:gz") as archive:
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

    def test_graph_builds_exact_catalog_selected_packages(self, tmp_path):
        """The activated path must not consult the legacy function registry."""
        from src.providers.terraform.package_builder import build_all_packages

        manifest = json.loads(
            (MANIFEST_ROOT / "mixed-providers.json").read_text("utf-8")
        )
        graph = resolve_deployment_graph(
            validate_deployment_manifest(manifest, manifest["providers"])
        )
        terraform_dir = tmp_path / "terraform"
        terraform_dir.mkdir()
        project_path = tmp_path / "project"
        project_path.mkdir()
        extension_path = project_path / "extension.zip"
        extension_path.write_bytes(b"extension")
        extension_ref = next(
            node.extension_artifact_refs[0]
            for node in graph.nodes
            if node.extension_artifact_refs
        )

        def build_selected(
            provider: str,
            _terraform_dir: Path,
            _project_path: Path,
            _providers: dict,
            *,
            selected_function_names,
        ) -> dict[str, Path]:
            packages = {}
            for name in selected_function_names:
                path = project_path / f"{provider}-{name}.zip"
                path.write_bytes(f"{provider}:{name}".encode())
                packages[f"{provider}_{name}"] = path
            return packages

        with (
            patch(
                "src.providers.terraform.package_builder."
                "build_bound_extension_packages",
                return_value={
                    "extension:processor.telemetry": extension_path
                },
            ),
            patch(
                "src.providers.terraform.package_builder.load_package_evidence",
                return_value=[dict(extension_ref)],
            ),
            patch(
                "src.providers.terraform.package_builder.build_aws_lambda_packages",
                side_effect=lambda *args, **kwargs: build_selected(
                    "aws", *args, **kwargs
                ),
            ) as mock_aws,
            patch(
                "src.providers.terraform.package_builder.build_azure_graph_bundles",
                side_effect=lambda _project_path, names: {
                    package_id: (project_path / f"{package_id}.zip")
                    for package_id in {
                        "azure_bundle_l0",
                        "azure_bundle_l2",
                        "azure_bundle_l3",
                    }
                },
            ) as mock_azure,
            patch(
                "src.providers.terraform.package_builder."
                "build_gcp_cloud_function_packages",
                side_effect=lambda *args, **kwargs: build_selected(
                    "gcp", *args, **kwargs
                ),
            ) as mock_gcp,
            patch(
                "src.providers.terraform.package_builder.build_user_packages"
            ) as mock_user,
        ):
            for package_id in (
                "azure_bundle_l0",
                "azure_bundle_l2",
                "azure_bundle_l3",
            ):
                (project_path / f"{package_id}.zip").write_bytes(package_id.encode())
            result = build_all_packages(
                terraform_dir,
                project_path,
                manifest["providers"],
                graph=graph,
            )

        assert mock_aws.call_args.kwargs["selected_function_names"] == (
            "connector",
            "dispatcher",
        )
        assert "ingestion" in mock_azure.call_args.args[1]
        assert mock_gcp.call_args.kwargs["selected_function_names"] == ()
        mock_user.assert_not_called()
        assert set(result) == {
            *{
                f"aws_{name}"
                for name in mock_aws.call_args.kwargs["selected_function_names"]
            },
            *{
                f"gcp_{name}"
                for name in mock_gcp.call_args.kwargs["selected_function_names"]
            },
            "azure_bundle_l0",
            "azure_bundle_l2",
            "azure_bundle_l3",
            "extension:processor.telemetry",
        }
        evidence = json.loads(
            (
                project_path / ".twin2multicloud" / "graph" / "package-evidence.json"
            ).read_text("utf-8")
        )
        assert evidence["graph_digest"] == graph.content_digest
        assert {item["package_id"] for item in evidence["built_packages"]} == set(
            result
        )


def test_aws_v2_bridge_context_selection_tracks_outbound_event_routes():
    from src.providers.terraform.package_builder import _aws_v2_bridge_selected

    mixed = _resolve_offline_v4("three-cloud-mixed-large.json")
    single = _resolve_offline_v4("single-cloud-aws-small.json")

    assert _aws_v2_bridge_selected(mixed) is True
    assert _aws_v2_bridge_selected(single) is False
