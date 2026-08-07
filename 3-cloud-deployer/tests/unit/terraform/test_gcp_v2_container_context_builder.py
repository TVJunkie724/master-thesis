"""Deterministic GCP Five-layer v2 container context tests."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tarfile
from types import MappingProxyType
import zipfile

import pytest

from src.architecture_profiles.graph_resolver import resolve_deployment_graph
from src.deployment_specification import (
    ValidatedDeploymentManifest,
    validate_resolved_deployment_specification,
)
from src.providers.terraform.package_builder import (
    _selected_gcp_container_packages,
)
from src.providers.terraform.package_builders.gcp_v2 import (
    build_gcp_v2_container_contexts,
    build_gcp_v2_extension_container_context,
)


MANIFEST_ROOT = (
    Path(__file__).resolve().parents[3]
    / "src"
    / "contracts"
    / "generated"
    / "deployment-manifest"
    / "v4"
    / "fixtures"
    / "valid"
)
LOGICAL_TO_SLOT = {
    "component.ingestion": "l1_ingestion",
    "component.processing": "l2_processing",
    "component.hot-storage": "l3_hot_storage",
    "component.cool-storage": "l3_cool_storage",
    "component.archive-storage": "l3_archive_storage",
    "component.twin-state": "l4_twin_state",
    "component.visualization": "l5_visualization",
}


def _resolve_offline_v4(name: str):
    manifest = json.loads((MANIFEST_ROOT / name).read_text("utf-8"))
    specification = validate_resolved_deployment_specification(
        manifest["resolved_deployment_specification"]
    )
    provider_by_slot = {
        LOGICAL_TO_SLOT[item["logical_component_id"]]: item["provider"]
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


def test_gcp_v2_container_context_is_deterministic_and_complete(tmp_path):
    first = build_gcp_v2_container_contexts(tmp_path, ("five-layer-v2",))
    first_bytes = first["gcp_five-layer-v2"].read_bytes()
    first_digest = hashlib.sha256(first_bytes).hexdigest()

    second = build_gcp_v2_container_contexts(tmp_path, ("five-layer-v2",))
    second_bytes = second["gcp_five-layer-v2"].read_bytes()

    assert second_bytes == first_bytes
    assert hashlib.sha256(second_bytes).hexdigest() == first_digest
    with tarfile.open(second["gcp_five-layer-v2"], "r:gz") as archive:
        members = archive.getmembers()
        names = {member.name for member in members}
        assert {
            ".dockerignore",
            "bridge_core.py",
            "Dockerfile",
            "grafana/Dockerfile",
            "grafana/dashboard.json.template",
            "grafana/entrypoint.sh",
            "grafana/provisioning/dashboards/twin2multicloud.yaml",
            "grafana/provisioning/datasources/twin2multicloud.yaml",
            "platform/app.py",
            "platform/constraints.txt",
            "platform/core.py",
            "platform/mqtt_adapter.py",
            "platform/requirements.txt",
        } <= names
        assert all(member.mtime == 0 for member in members)
        assert all(member.uid == member.gid == 0 for member in members)
        assert not any("__pycache__" in name for name in names)


def test_gcp_v2_container_context_rejects_unknown_builder_target(tmp_path):
    with pytest.raises(ValueError, match="Unknown GCP Five-layer v2 context"):
        build_gcp_v2_container_contexts(tmp_path, ("unreviewed",))


def test_gcp_v2_extension_context_is_deterministic_and_closed(tmp_path):
    package = tmp_path / "processor.zip"
    with zipfile.ZipFile(package, "w") as archive:
        archive.writestr("process.py", "def process(payload, config, context): return payload\n")
        archive.writestr("main.py", "def main(request): return ('{}', 200, {})\n")
        archive.writestr("requirements.txt", "functions-framework==3.8.3\n")

    first = build_gcp_v2_extension_container_context(tmp_path, package)
    first_bytes = first.read_bytes()
    second = build_gcp_v2_extension_container_context(tmp_path, package)

    assert second.read_bytes() == first_bytes
    with tarfile.open(second, "r:gz") as archive:
        names = {item.name for item in archive.getmembers()}
        dockerfile = archive.extractfile("Dockerfile")
        assert names == {"Dockerfile", "main.py", "process.py", "requirements.txt"}
        assert dockerfile is not None
        assert b"functions-framework" in dockerfile.read()


def test_gcp_v2_extension_context_rejects_unsafe_zip_member(tmp_path):
    package = tmp_path / "processor.zip"
    with zipfile.ZipFile(package, "w") as archive:
        archive.writestr("../main.py", "unsafe")
        archive.writestr("requirements.txt", "functions-framework==3.8.3\n")

    with pytest.raises(ValueError, match="unsafe path"):
        build_gcp_v2_extension_container_context(tmp_path, package)


def test_gcp_v2_container_context_is_selected_by_v4_graph():
    graph = _resolve_offline_v4("three-cloud-mixed-large.json")

    assert _selected_gcp_container_packages(graph) == (
        ("five-layer-v2",),
        {"gcp_five-layer-v2"},
    )
