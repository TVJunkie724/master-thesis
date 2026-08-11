"""Stable facade for provider-specific Terraform function package builders."""

import hashlib
import json
import logging
from pathlib import Path
from typing import Any, Dict, Mapping

from src.function_registry import (
    get_functions_for_provider_build as get_functions_for_provider_build,
)
from src.providers.terraform.package_builders.aws import (
    _create_lambda_zip,
    build_aws_lambda_packages,
    get_lambda_zip_path,
)
from src.providers.terraform.package_builders.aws_v2 import (
    BRIDGE_PACKAGE_ID as AWS_V2_BRIDGE_PACKAGE_ID,
    STORAGE_MOVER_PACKAGE_ID as AWS_V2_STORAGE_MOVER_PACKAGE_ID,
    build_aws_v2_bridge_context,
    build_aws_v2_graph_app,
    build_aws_v2_storage_mover_context,
)
from src.providers.terraform.package_builders.aws_eventing import (
    build_aws_eventing_app,
)
from src.providers.terraform.package_builders.azure import (
    _add_azure_function_app_directly,
    _create_azure_function_zip,
    _discover_azure_user_functions,
    _generate_main_function_app,
    _rewrite_azure_function_names,
    azure_graph_package_ids,
    build_azure_function_packages,
    build_azure_graph_bundles,
    build_azure_l0_bundle,
    build_azure_l1_bundle,
    build_azure_l2_bundle,
    build_azure_l3_bundle,
    build_azure_user_bundle,
    get_azure_zip_path,
)
from src.providers.terraform.package_builders.azure_v2 import (
    AZURE_V2_GRAPH_APPS,
    azure_v2_graph_package_ids,
    build_azure_v2_graph_apps,
)
from src.providers.terraform.package_builders.azure_v2_container import (
    PACKAGE_ID as AZURE_V2_STORAGE_MOVER_PACKAGE_ID,
    build_azure_v2_storage_mover_context,
)
from src.providers.terraform.package_builders.common import (
    _clean_old_versioned_zips,
    _compute_content_hash,
    _merge_requirements,
    _should_include_file,
)
from src.providers.terraform.package_builders.gcp import (
    _create_gcp_function_zip,
    _create_gcp_processor_zip,
    _rewrite_gcp_function_names,
    build_gcp_cloud_function_packages,
    get_gcp_zip_path,
)
from src.providers.terraform.package_builders.gcp_v2 import (
    build_gcp_v2_container_contexts,
    build_gcp_v2_extension_container_context,
)
from src.providers.terraform.package_builders.user import (
    _compute_source_hash,
    _reconcile_user_hash_metadata,
    _save_user_hash_metadata,
    build_user_packages,
    get_user_package_path,
)
from src.provider_capabilities import validate_terraform_provider_capabilities
from src.providers.terraform.cross_cloud_routes import resolve_cross_cloud_routes
from src.user_function_extensions.package_builder import (
    build_bound_extension_packages,
    load_package_evidence,
)
from src.user_function_extensions.contracts import ExtensionContractError
from src.architecture_profiles import ResolvedDeploymentGraph
from src.core.secure_files import atomic_write_private_bytes
from src.deployment_specification.errors import DeploymentSpecificationError
from src.terraform_inputs.compatibility_projection import provider_projection

logger = logging.getLogger(__name__)
BUILD_DIR = ".build"
DEPLOYER_ROOT = Path(__file__).resolve().parents[3]
FUNCTION_SOURCE_PARTS = {
    "aws": ("src", "providers", "aws", "lambda_functions"),
    "azure": ("src", "providers", "azure", "azure_functions"),
    "gcp": ("src", "providers", "gcp", "cloud_functions"),
}
GCP_CONTAINER_SOURCE_PARTS = ("src", "providers", "gcp", "containers")


def build_all_packages(
    terraform_dir: Path,
    project_path: Path,
    providers_config: dict,
    *,
    operation_id: str | None = None,
    graph: ResolvedDeploymentGraph | None = None,
) -> Dict[str, Path]:
    """Build every provider and user-function package required by one deployment."""
    terraform_dir = Path(terraform_dir)
    project_path = Path(project_path)
    architecture_profile = (
        (
            str(graph.profile_ref.get("id", "")),
            str(graph.profile_ref.get("version", "")),
        )
        if graph is not None
        else None
    )
    validate_terraform_provider_capabilities(
        providers_config,
        architecture_profile=architecture_profile,
    )
    selected_functions: dict[str, tuple[str, ...]] | None = None
    expected_static_packages: set[str] = set()
    if graph is not None:
        _validate_graph_package_selection(graph, providers_config)
        selected_functions, expected_static_packages = (
            _selected_static_function_packages(graph)
        )
        gcp_container_names, expected_gcp_container_packages = (
            _selected_gcp_container_packages(graph)
        )
        aws_v2_storage_mover_selected = _aws_v2_storage_mover_selected(graph)
        aws_v2_bridge_selected = _aws_v2_bridge_selected(graph)
        azure_v2_storage_mover_selected = _azure_v2_storage_mover_selected(graph)

    packages: Dict[str, Path] = {}
    extension_packages = build_bound_extension_packages(
        project_path,
        providers_config,
        correlation_id=operation_id,
    )
    packages.update(extension_packages)
    if graph is not None:
        _validate_extension_package_selection(
            graph,
            project_path,
            extension_packages,
            correlation_id=operation_id,
        )
        aws_v2_selected = "five-layer-v2" in selected_functions["aws"]
        aws_eventing_selected = "six-layer-eventing" in selected_functions["aws"]
        aws_v1_names = tuple(
            name
            for name in selected_functions["aws"]
            if name not in {"five-layer-v2", "six-layer-eventing"}
        )
        packages.update(
            build_aws_lambda_packages(
                terraform_dir,
                project_path,
                providers_config,
                selected_function_names=aws_v1_names,
            )
        )
        if aws_v2_selected:
            packages.update(build_aws_v2_graph_app(project_path))
        if aws_eventing_selected:
            packages.update(build_aws_eventing_app(project_path))
        azure_v2_names = tuple(
            name for name in selected_functions["azure"] if name in AZURE_V2_GRAPH_APPS
        )
        azure_v1_names = tuple(
            name
            for name in selected_functions["azure"]
            if name not in AZURE_V2_GRAPH_APPS
        )
        packages.update(build_azure_graph_bundles(project_path, azure_v1_names))
        packages.update(build_azure_v2_graph_apps(project_path, azure_v2_names))
        packages.update(
            build_gcp_cloud_function_packages(
                terraform_dir,
                project_path,
                providers_config,
                selected_function_names=selected_functions["gcp"],
            )
        )
        packages.update(
            build_gcp_v2_container_contexts(project_path, gcp_container_names)
        )
        if aws_v2_storage_mover_selected:
            packages.update(build_aws_v2_storage_mover_context(project_path))
        if aws_v2_bridge_selected:
            packages.update(build_aws_v2_bridge_context(project_path))
        if azure_v2_storage_mover_selected:
            packages.update(build_azure_v2_storage_mover_context(project_path))
        if (
            providers_config.get("layer_2_provider") in {"gcp", "google"}
            and "extension:processor.telemetry" in packages
        ):
            build_gcp_v2_extension_container_context(
                project_path,
                packages["extension:processor.telemetry"],
            )
        expected_packages = (
            expected_static_packages
            | expected_gcp_container_packages
            | (
                {AWS_V2_STORAGE_MOVER_PACKAGE_ID}
                if aws_v2_storage_mover_selected
                else set()
            )
            | ({AWS_V2_BRIDGE_PACKAGE_ID} if aws_v2_bridge_selected else set())
            | (
                {AZURE_V2_STORAGE_MOVER_PACKAGE_ID}
                if azure_v2_storage_mover_selected
                else set()
            )
            | {
                f"extension:{item['slot_id']}"
                for item in _selected_extension_refs(graph)
            }
        )
        if set(packages) != expected_packages:
            raise DeploymentSpecificationError(
                "DEPLOYMENT_PACKAGE_CATALOG_MISMATCH",
                "packages",
                "Built packages differ from the graph-selected artifact set",
            )
    else:
        if extension_packages:
            raise ExtensionContractError(
                "EXTENSION_BINDING_UNRESOLVED",
                "deployment_component_catalog",
                (
                    "The validated extension has no reviewed executable "
                    "deployment-component mapping."
                ),
                correlation_id=operation_id,
            )
        packages.update(
            build_aws_lambda_packages(
                terraform_dir,
                project_path,
                providers_config,
            )
        )
        packages.update(
            build_azure_function_packages(
                terraform_dir,
                project_path,
                providers_config,
            )
        )
        packages.update(
            build_gcp_cloud_function_packages(
                terraform_dir,
                project_path,
                providers_config,
            )
        )
        packages.update(build_user_packages(project_path, providers_config))
    if graph is not None:
        _write_graph_package_evidence(project_path, graph, packages)

    logger.info("Built %s function packages", len(packages))
    return packages


def _validate_graph_package_selection(
    graph: ResolvedDeploymentGraph,
    providers_config: dict,
) -> None:
    expected = provider_projection(graph)
    normalized_actual = {
        key: ("google" if value == "gcp" else value)
        for key, value in providers_config.items()
        if key in expected
    }
    if normalized_actual != expected:
        raise DeploymentSpecificationError(
            "DEPLOYMENT_PACKAGE_CATALOG_MISMATCH",
            "config_providers",
            "Package provider projection differs from the resolved graph",
        )
    for artifact in _selected_artifacts(graph).values():
        if (
            not str(artifact["id"]).startswith("artifact.")
            or not str(artifact["source_digest"]).startswith("sha256:")
            or not str(artifact["builder_adapter_id"]).startswith("builder.")
            or artifact["digest_policy"] != "sha256.canonical-source.v1"
        ):
            raise DeploymentSpecificationError(
                "DEPLOYMENT_PACKAGE_CATALOG_MISMATCH",
                f"graph.package_artifacts.{artifact['id']}",
                "Graph package artifact metadata is incomplete",
            )
        if _artifact_source_digest(artifact) != artifact["source_digest"]:
            raise DeploymentSpecificationError(
                "DEPLOYMENT_PACKAGE_CATALOG_MISMATCH",
                f"graph.package_artifacts.{artifact['id']}",
                "Catalog package source digest is stale",
            )


def _selected_artifacts(
    graph: ResolvedDeploymentGraph,
) -> dict[str, Mapping[str, Any]]:
    selected: dict[str, Mapping[str, Any]] = {}
    for node in graph.nodes:
        for artifact in node.package_artifacts:
            artifact_id = str(artifact["id"])
            previous = selected.setdefault(artifact_id, artifact)
            if dict(previous) != dict(artifact):
                raise DeploymentSpecificationError(
                    "DEPLOYMENT_PACKAGE_CATALOG_MISMATCH",
                    f"graph.package_artifacts.{artifact_id}",
                    "Graph contains contradictory package artifact metadata",
                )
    return selected


def _local_artifact_source(source: str) -> Path:
    parts = Path(source).parts
    if not parts or parts[0] != "3-cloud-deployer":
        raise DeploymentSpecificationError(
            "DEPLOYMENT_PACKAGE_CATALOG_MISMATCH",
            "graph.package_artifacts.repository_source_path",
            "Catalog package source is outside the Deployer repository",
        )
    path = DEPLOYER_ROOT.joinpath(*parts[1:])
    if not path.exists() or path.is_symlink():
        raise DeploymentSpecificationError(
            "DEPLOYMENT_PACKAGE_CATALOG_MISMATCH",
            "graph.package_artifacts.repository_source_path",
            "Catalog package source is unavailable or unsafe",
        )
    return path


def _artifact_source_digest(artifact: Mapping[str, Any]) -> str:
    source = str(artifact["repository_source_path"])
    source_path = _local_artifact_source(source)
    paths = [source_path] if source_path.is_file() else sorted(source_path.rglob("*"))
    digest = hashlib.sha256()
    included = 0
    for path in paths:
        if path.is_symlink():
            raise DeploymentSpecificationError(
                "DEPLOYMENT_PACKAGE_CATALOG_MISMATCH",
                f"graph.package_artifacts.{artifact['id']}",
                "Catalog package source contains a symbolic link",
            )
        if (
            not path.is_file()
            or "__pycache__" in path.parts
            or ".git" in path.parts
            or path.suffix.lower() == ".zip"
            or path.name.startswith(".git")
            or path.name == ".DS_Store"
        ):
            continue
        relative = (
            source
            if source_path.is_file()
            else f"{source}/{path.relative_to(source_path).as_posix()}"
        )
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
        included += 1
    if included == 0:
        raise DeploymentSpecificationError(
            "DEPLOYMENT_PACKAGE_CATALOG_MISMATCH",
            f"graph.package_artifacts.{artifact['id']}",
            "Catalog package source is empty",
        )
    return f"sha256:{digest.hexdigest()}"


def _selected_static_function_packages(
    graph: ResolvedDeploymentGraph,
) -> tuple[dict[str, tuple[str, ...]], set[str]]:
    selected: dict[str, set[str]] = {
        "aws": set(),
        "azure": set(),
        "gcp": set(),
    }
    package_ids: set[str] = set()
    for artifact in _selected_artifacts(graph).values():
        source_path = _local_artifact_source(str(artifact["repository_source_path"]))
        relative = source_path.relative_to(DEPLOYER_ROOT)
        provider = next(
            (
                candidate
                for candidate, prefix in FUNCTION_SOURCE_PARTS.items()
                if relative.parts[: len(prefix)] == prefix
            ),
            None,
        )
        if (
            provider is None
            or source_path.name == "_shared"
            or artifact["platform_handler"]
            in {
                "provider.shared-runtime",
                "provider-selected.user-package",
                "terraform.managed",
            }
        ):
            continue
        selected[provider].add(source_path.name)
        if provider != "azure":
            package_ids.add(f"{provider}_{source_path.name}")
    profile = (graph.profile_ref.get("id"), str(graph.profile_ref.get("version")))
    event_route_providers = (
        {
            provider
            for route in resolve_cross_cloud_routes(graph)
            if route.execution_kind == "source_event_forwarder"
            for provider in (route.source_provider, route.destination_provider)
        }
        if profile
        in {
            ("five-layer-baseline", "2"),
            ("six-layer-eventing", "1"),
        }
        else set()
    )
    for provider in event_route_providers.intersection({"aws", "azure"}):
        selected[provider].add("five-layer-v2")
        if provider == "aws":
            package_ids.add("aws_five-layer-v2")
    azure_v2_names = selected["azure"].intersection(AZURE_V2_GRAPH_APPS)
    azure_v1_names = selected["azure"] - azure_v2_names
    package_ids.update(azure_graph_package_ids(azure_v1_names))
    package_ids.update(azure_v2_graph_package_ids(azure_v2_names))
    return (
        {
            provider: tuple(sorted(functions))
            for provider, functions in selected.items()
        },
        package_ids,
    )


def _selected_gcp_container_packages(
    graph: ResolvedDeploymentGraph,
) -> tuple[tuple[str, ...], set[str]]:
    selected: set[str] = set()
    for artifact in _selected_artifacts(graph).values():
        source_path = _local_artifact_source(str(artifact["repository_source_path"]))
        relative = source_path.relative_to(DEPLOYER_ROOT)
        if (
            relative.parts[: len(GCP_CONTAINER_SOURCE_PARTS)]
            != GCP_CONTAINER_SOURCE_PARTS
        ):
            continue
        selected.add(source_path.name)
    profile = (graph.profile_ref.get("id"), str(graph.profile_ref.get("version")))
    if profile in {
        ("five-layer-baseline", "2"),
        ("six-layer-eventing", "1"),
    } and any(
        route.execution_kind == "source_event_forwarder"
        and "gcp" in {route.source_provider, route.destination_provider}
        for route in resolve_cross_cloud_routes(graph)
    ):
        selected.add("five-layer-v2")
    names = tuple(sorted(selected))
    return names, {f"gcp_{name}" for name in names}


def _aws_v2_storage_mover_selected(graph: ResolvedDeploymentGraph) -> bool:
    return any(
        "aws.ecs-fargate-storage-mover" in component_id
        for node in graph.nodes
        for component_id in node.deployment_specification_component_ids
    )


def _aws_v2_bridge_selected(graph: ResolvedDeploymentGraph) -> bool:
    profile = (
        graph.profile_ref.get("id"),
        str(graph.profile_ref.get("version")),
    )
    if profile not in {
        ("five-layer-baseline", "2"),
        ("six-layer-eventing", "1"),
    }:
        return False
    return any(
        route.source_provider == "aws"
        and route.execution_kind == "source_event_forwarder"
        for route in resolve_cross_cloud_routes(graph)
    )


def _azure_v2_storage_mover_selected(graph: ResolvedDeploymentGraph) -> bool:
    return any(
        "azure.container-apps-scheduled-storage-job" in component_id
        for node in graph.nodes
        for component_id in node.deployment_specification_component_ids
    )


def _selected_extension_refs(
    graph: ResolvedDeploymentGraph,
) -> list[Mapping[str, Any]]:
    refs: dict[tuple[str, str], Mapping[str, Any]] = {}
    for node in graph.nodes:
        for item in node.extension_artifact_refs:
            identity = (str(item["slot_id"]), str(item["slot_version"]))
            if identity in refs:
                raise DeploymentSpecificationError(
                    "DEPLOYMENT_GRAPH_BINDING_DUPLICATE",
                    "graph.nodes.extension_artifact_refs",
                    "Extension slot is selected more than once",
                )
            refs[identity] = item
    return [refs[key] for key in sorted(refs)]


def _validate_extension_package_selection(
    graph: ResolvedDeploymentGraph,
    project_path: Path,
    packages: Dict[str, Path],
    *,
    correlation_id: str | None,
) -> None:
    expected = {
        (
            str(item["slot_id"]),
            str(item["slot_version"]),
            str(item["artifact_id"]),
            str(item["artifact_digest"]),
        )
        for item in _selected_extension_refs(graph)
    }
    actual = {
        (
            str(item["slot_id"]),
            str(item["slot_version"]),
            str(item["artifact_id"]),
            str(item["artifact_digest"]),
        )
        for item in load_package_evidence(project_path)
    }
    if actual != expected or len(packages) != len(expected):
        raise ExtensionContractError(
            "EXTENSION_BINDING_UNRESOLVED",
            "deployment_component_catalog",
            "Built extension packages differ from graph bindings.",
            correlation_id=correlation_id,
        )


def _write_graph_package_evidence(
    project_path: Path,
    graph: ResolvedDeploymentGraph,
    packages: Dict[str, Path],
) -> None:
    package_evidence = []
    for package_id, path in sorted(packages.items()):
        package_path = Path(path)
        if not package_path.is_file() or package_path.is_symlink():
            raise DeploymentSpecificationError(
                "DEPLOYMENT_PACKAGE_CATALOG_MISMATCH",
                "packages",
                "Built package evidence references an unavailable file",
            )
        package_evidence.append(
            {
                "package_id": package_id,
                "sha256": hashlib.sha256(package_path.read_bytes()).hexdigest(),
                "size_bytes": package_path.stat().st_size,
            }
        )
    evidence = {
        "evidence_version": "graph-package-evidence.v1",
        "graph_id": graph.graph_id,
        "graph_digest": graph.content_digest,
        "selected_artifacts": [
            {
                "artifact_id": artifact["id"],
                "artifact_version": artifact["version"],
                "source_digest": artifact["source_digest"],
                "builder_adapter_id": artifact["builder_adapter_id"],
            }
            for _, artifact in sorted(_selected_artifacts(graph).items())
        ],
        "built_packages": package_evidence,
    }
    output = project_path / ".twin2multicloud" / "graph" / "package-evidence.json"
    atomic_write_private_bytes(
        output,
        (
            json.dumps(evidence, ensure_ascii=True, indent=2, sort_keys=True) + "\n"
        ).encode("utf-8"),
    )


__all__ = [
    "BUILD_DIR",
    "_add_azure_function_app_directly",
    "_clean_old_versioned_zips",
    "_compute_content_hash",
    "_compute_source_hash",
    "_create_azure_function_zip",
    "_create_gcp_function_zip",
    "_create_gcp_processor_zip",
    "_create_lambda_zip",
    "_discover_azure_user_functions",
    "_generate_main_function_app",
    "_merge_requirements",
    "_rewrite_azure_function_names",
    "_rewrite_gcp_function_names",
    "_reconcile_user_hash_metadata",
    "_save_user_hash_metadata",
    "_should_include_file",
    "build_all_packages",
    "build_aws_lambda_packages",
    "build_aws_v2_bridge_context",
    "build_aws_v2_storage_mover_context",
    "build_azure_function_packages",
    "build_azure_l0_bundle",
    "build_azure_l1_bundle",
    "build_azure_l2_bundle",
    "build_azure_l3_bundle",
    "build_azure_user_bundle",
    "build_gcp_cloud_function_packages",
    "build_gcp_v2_container_contexts",
    "build_user_packages",
    "get_azure_zip_path",
    "get_functions_for_provider_build",
    "get_gcp_zip_path",
    "get_lambda_zip_path",
    "get_user_package_path",
]
