from pathlib import Path

from core.factory import get_upload_path
from src.core.paths import resolve_deployment_paths


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
