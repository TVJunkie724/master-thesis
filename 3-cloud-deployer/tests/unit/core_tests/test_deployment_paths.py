from pathlib import Path
import json

import pytest

import core.factory as factory
from core.factory import get_upload_path
from src.core.paths import (
    resolve_deployment_paths,
    resolve_project_context_path,
    resolve_template_paths,
    resolve_template_project_path,
)


def test_resolve_deployment_paths_uses_single_project_root():
    paths = resolve_deployment_paths("factory-twin", project_root=Path("/app"))

    assert paths.project_root == Path("/app")
    assert paths.upload_root == Path("/app/upload")
    assert paths.project_path == Path("/app/upload/factory-twin")
    assert paths.terraform_dir == Path("/app/upload/factory-twin/terraform")
    assert paths.tfvars_path == Path("/app/upload/factory-twin/terraform/generated.tfvars.json")
    assert paths.state_path == Path("/app/upload/factory-twin/terraform/terraform.tfstate")


def test_factory_upload_path_uses_deployment_path_resolver():
    paths = resolve_deployment_paths("template")

    assert get_upload_path("template") == paths.project_path


def test_template_paths_prefer_canonical_template_root(tmp_path):
    canonical = tmp_path / "templates" / "digital-twin"
    legacy = tmp_path / "upload" / "template"
    canonical.mkdir(parents=True)
    legacy.mkdir(parents=True)

    paths = resolve_template_paths(tmp_path)

    assert paths.templates_root == tmp_path / "templates"
    assert paths.template_path == canonical
    assert paths.legacy_template_path == legacy
    assert paths.active_template_path == canonical
    assert resolve_template_project_path(tmp_path) == canonical
    assert resolve_project_context_path("template", tmp_path) == canonical


def test_template_paths_fall_back_to_legacy_upload_template(tmp_path):
    legacy = tmp_path / "upload" / "template"
    legacy.mkdir(parents=True)

    assert resolve_template_project_path(tmp_path) == legacy
    assert resolve_project_context_path("template", tmp_path) == legacy


def test_runtime_project_context_stays_under_upload_root(tmp_path):
    project_path = resolve_project_context_path("factory-twin", tmp_path)

    assert project_path == tmp_path / "upload" / "factory-twin"


def test_create_context_uses_project_context_resolver_for_template(tmp_path, monkeypatch):
    template_path = tmp_path / "templates" / "digital-twin"
    template_path.mkdir(parents=True)
    (template_path / "config.json").write_text(json.dumps({
        "digital_twin_name": "template-twin",
        "hot_storage_size_in_days": 30,
        "cold_storage_size_in_days": 90,
        "mode": "DEBUG",
    }))
    (template_path / "config_iot_devices.json").write_text("[]")
    (template_path / "config_providers.json").write_text(json.dumps({
        "layer_1_provider": "aws",
        "layer_2_provider": "aws",
        "layer_3_hot_provider": "aws",
        "layer_4_provider": "none",
    }))

    monkeypatch.setattr(factory, "resolve_project_context_path", lambda project_name: template_path)

    context = factory.create_context("template")

    assert context.project_name == "template"
    assert context.project_path == template_path
    assert context.config.digital_twin_name == "template-twin"


def test_create_context_loads_deployment_manifest(tmp_path, monkeypatch):
    project_path = tmp_path / "upload" / "factory"
    project_path.mkdir(parents=True)
    (project_path / "config.json").write_text(json.dumps({
        "digital_twin_name": "factory",
        "hot_storage_size_in_days": 30,
        "cold_storage_size_in_days": 90,
        "mode": "DEBUG",
    }))
    (project_path / "config_iot_devices.json").write_text("[]")
    (project_path / "config_providers.json").write_text(json.dumps({
        "layer_1_provider": "aws",
        "layer_2_provider": "aws",
        "layer_3_hot_provider": "aws",
        "layer_4_provider": "none",
    }))
    (project_path / "deployment_manifest.json").write_text(json.dumps({
        "manifest_version": "1.0",
        "twin": {"resource_name": "factory"},
    }))

    monkeypatch.setattr(factory, "resolve_project_context_path", lambda project_name: project_path)

    context = factory.create_context("factory")

    assert context.is_manifest_backed is True
    assert context.manifest_resource_name == "factory"


def test_create_context_carries_request_metadata(tmp_path, monkeypatch):
    project_path = tmp_path / "upload" / "factory"
    project_path.mkdir(parents=True)
    (project_path / "config.json").write_text(json.dumps({
        "digital_twin_name": "factory",
        "hot_storage_size_in_days": 30,
        "cold_storage_size_in_days": 90,
        "mode": "DEBUG",
    }))
    (project_path / "config_iot_devices.json").write_text("[]")
    (project_path / "config_providers.json").write_text(json.dumps({
        "layer_1_provider": "aws",
        "layer_2_provider": "aws",
        "layer_3_hot_provider": "aws",
        "layer_4_provider": "none",
    }))

    monkeypatch.setattr(factory, "resolve_project_context_path", lambda project_name: project_path)

    context = factory.create_context("factory", "aws", operation_id="op-123")

    assert context.operation_id == "op-123"
    assert context.requested_provider == "aws"


def test_create_context_rejects_manifest_project_name_drift(tmp_path, monkeypatch):
    project_path = tmp_path / "upload" / "factory"
    project_path.mkdir(parents=True)
    (project_path / "config.json").write_text(json.dumps({
        "digital_twin_name": "factory",
        "hot_storage_size_in_days": 30,
        "cold_storage_size_in_days": 90,
        "mode": "DEBUG",
    }))
    (project_path / "config_iot_devices.json").write_text("[]")
    (project_path / "config_providers.json").write_text(json.dumps({
        "layer_1_provider": "aws",
        "layer_2_provider": "aws",
        "layer_3_hot_provider": "aws",
        "layer_4_provider": "none",
    }))
    (project_path / "deployment_manifest.json").write_text(json.dumps({
        "manifest_version": "1.0",
        "twin": {"resource_name": "other"},
    }))

    monkeypatch.setattr(factory, "resolve_project_context_path", lambda project_name: project_path)

    with pytest.raises(ValueError, match="resource_name does not match"):
        factory.create_context("factory")
