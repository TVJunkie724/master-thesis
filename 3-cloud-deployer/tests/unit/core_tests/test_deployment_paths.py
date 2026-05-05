from pathlib import Path

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
