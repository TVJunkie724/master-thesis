"""Tests for bounded Twin deployment-workspace materialization."""

import io
import json
from pathlib import Path
import zipfile

import pytest

import constants as CONSTANTS
import file_manager
from tests.utils.deployment_specification import (
    deployment_manifest,
    load_specification,
    provider_config_for_specification,
)


@pytest.fixture
def temp_project_path(tmp_path):
    (tmp_path / CONSTANTS.PROJECT_UPLOAD_DIR_NAME).mkdir()
    return str(tmp_path)


@pytest.fixture
def valid_zip_bytes():
    bio = io.BytesIO()
    with zipfile.ZipFile(bio, "w") as archive:
        archive.writestr(
            CONSTANTS.CONFIG_FILE,
            json.dumps(
                {
                    "digital_twin_name": "test-twin",
                    "hot_storage_size_in_days": 30,
                    "cold_storage_size_in_days": 90,
                    "mode": "DEBUG",
                }
            ),
        )
        archive.writestr(CONSTANTS.CONFIG_IOT_DEVICES_FILE, "[]")
        archive.writestr(CONSTANTS.CONFIG_EVENTS_FILE, "[]")
        archive.writestr(CONSTANTS.CONFIG_HIERARCHY_FILE, "[]")
        archive.writestr(
            CONSTANTS.CONFIG_CREDENTIALS_FILE,
            json.dumps(
                {
                    "aws": {
                        "aws_access_key_id": "AKIATEST",
                        "aws_secret_access_key": "secret",
                        "aws_region": "us-east-1",
                    }
                }
            ),
        )
        archive.writestr(
            CONSTANTS.CONFIG_PROVIDERS_FILE,
            json.dumps(
                {
                    "layer_1_provider": "aws",
                    "layer_2_provider": "aws",
                    "layer_3_hot_provider": "aws",
                    "layer_4_provider": "aws",
                }
            ),
        )
        archive.writestr(CONSTANTS.CONFIG_OPTIMIZATION_FILE, '{"result": {}}')
        archive.writestr("twin_hierarchy/aws_hierarchy.json", "[]")
        archive.writestr("lambda_functions/placeholder.txt", "placeholder")
    return bio.getvalue()


def _valid_zip_with_manifest(resource_name: str) -> bytes:
    specification = load_specification()
    providers = provider_config_for_specification(specification)
    files = {
        CONSTANTS.CONFIG_FILE: json.dumps(
            {
                "digital_twin_name": resource_name,
                "hot_storage_size_in_days": 30,
                "cold_storage_size_in_days": 90,
                "mode": "DEBUG",
            }
        ),
        CONSTANTS.CONFIG_IOT_DEVICES_FILE: "[]",
        CONSTANTS.CONFIG_EVENTS_FILE: "[]",
        CONSTANTS.CONFIG_CREDENTIALS_FILE: json.dumps(
            {
                "aws": {
                    "aws_access_key_id": "AKIATEST",
                    "aws_secret_access_key": "secret",
                    "aws_region": "eu-central-1",
                },
                "azure": {
                    "azure_subscription_id": "subscription",
                    "azure_client_id": "client",
                    "azure_client_secret": "secret",
                    "azure_tenant_id": "tenant",
                    "azure_region": "westeurope",
                    "azure_region_iothub": "westeurope",
                    "azure_region_digital_twin": "westeurope",
                },
            }
        ),
        CONSTANTS.CONFIG_PROVIDERS_FILE: json.dumps(providers),
        CONSTANTS.CONFIG_OPTIMIZATION_FILE: '{"result": {}}',
        "config_user.json": json.dumps(
            {
                "admin_email": "admin@example.com",
                "admin_first_name": "Platform",
                "admin_last_name": "Admin",
                "aws_layer_access_principal_intent": "existing",
                "azure_principal_object_id": "11111111-1111-1111-1111-111111111111",
                "azure_principal_label": "admin@example.com",
            }
        ),
    }
    manifest = deployment_manifest(
        specification=specification,
        providers=providers,
        package_files=sorted(files),
        resource_name=resource_name,
    )
    bio = io.BytesIO()
    with zipfile.ZipFile(bio, "w") as archive:
        for path, content in files.items():
            archive.writestr(path, content)
        archive.writestr(CONSTANTS.DEPLOYMENT_MANIFEST_FILE, json.dumps(manifest))
    return bio.getvalue()


def _wrap_archive(content: bytes, *, extra_root_file: bool = False) -> bytes:
    target = io.BytesIO()
    with (
        zipfile.ZipFile(io.BytesIO(content), "r") as source,
        zipfile.ZipFile(target, "w") as archive,
    ):
        for member in source.infolist():
            archive.writestr(f"wrapped/{member.filename}", source.read(member))
        if extra_root_file:
            archive.writestr("outside.txt", "ambiguous")
    return target.getvalue()


def _project_dir(root: str, name: str) -> Path:
    return Path(root) / CONSTANTS.PROJECT_UPLOAD_DIR_NAME / name


def test_create_and_delete_workspace(temp_project_path, valid_zip_bytes):
    result = file_manager.create_project_from_zip(
        "test-project", valid_zip_bytes, project_path=temp_project_path
    )
    assert result["message"] == "Project 'test-project' created."
    assert _project_dir(temp_project_path, "test-project").is_dir()

    file_manager.delete_project("test-project", project_path=temp_project_path)
    assert not _project_dir(temp_project_path, "test-project").exists()


def test_delete_missing_workspace_rejected(temp_project_path):
    with pytest.raises(ValueError, match="does not exist"):
        file_manager.delete_project("missing", project_path=temp_project_path)


def test_manifest_resource_name_must_match_workspace(temp_project_path):
    file_manager.create_project_from_zip(
        "matching",
        _valid_zip_with_manifest("matching"),
        project_path=temp_project_path,
    )

    with pytest.raises(ValueError, match="resource_name does not match"):
        file_manager.create_project_from_zip(
            "requested",
            _valid_zip_with_manifest("manifest"),
            project_path=temp_project_path,
        )


def test_update_manifest_mismatch_preserves_workspace(temp_project_path):
    name = "matching"
    file_manager.create_project_from_zip(
        name, _valid_zip_with_manifest(name), project_path=temp_project_path
    )

    with pytest.raises(ValueError, match="resource_name does not match"):
        file_manager.update_project_from_zip(
            name,
            _valid_zip_with_manifest("other"),
            project_path=temp_project_path,
        )

    manifest = json.loads(
        (_project_dir(temp_project_path, name) / CONSTANTS.DEPLOYMENT_MANIFEST_FILE)
        .read_text(encoding="utf-8")
    )
    assert manifest["twin"]["resource_name"] == name


def test_create_never_persists_uploaded_credentials(
    temp_project_path, valid_zip_bytes
):
    file_manager.create_project_from_zip(
        "secret-free", valid_zip_bytes, project_path=temp_project_path
    )

    assert not (
        _project_dir(temp_project_path, "secret-free")
        / CONSTANTS.CONFIG_CREDENTIALS_FILE
    ).exists()


def test_create_failure_leaves_no_partial_workspace(
    monkeypatch, temp_project_path, valid_zip_bytes
):
    def fail_extraction(*_args, **_kwargs):
        raise OSError("simulated extraction failure")

    monkeypatch.setattr(file_manager.shutil, "copyfileobj", fail_extraction)
    with pytest.raises(OSError, match="simulated extraction failure"):
        file_manager.create_project_from_zip(
            "atomic-create", valid_zip_bytes, project_path=temp_project_path
        )

    upload_root = Path(temp_project_path) / CONSTANTS.PROJECT_UPLOAD_DIR_NAME
    assert not (upload_root / "atomic-create").exists()
    assert list(upload_root.glob(".atomic-create.staging-*")) == []


def test_update_replaces_definition_without_history(
    temp_project_path, valid_zip_bytes
):
    name = "atomic-update"
    file_manager.create_project_from_zip(
        name, valid_zip_bytes, project_path=temp_project_path
    )
    workspace = _project_dir(temp_project_path, name)
    (workspace / "stale.txt").write_text("stale", encoding="utf-8")
    (workspace / ".build").mkdir()
    (workspace / ".build" / "old.zip").write_bytes(b"stale")

    file_manager.update_project_from_zip(
        name, valid_zip_bytes, project_path=temp_project_path
    )

    assert not (workspace / "stale.txt").exists()
    assert not (workspace / ".build").exists()
    assert not (workspace / "versions").exists()
    assert not (workspace / "project_info.json").exists()


def test_update_requires_existing_workspace(temp_project_path, valid_zip_bytes):
    with pytest.raises(ValueError, match="does not exist"):
        file_manager.update_project_from_zip(
            "missing", valid_zip_bytes, project_path=temp_project_path
        )


def test_update_publication_failure_restores_previous_workspace(
    monkeypatch, temp_project_path, valid_zip_bytes
):
    name = "rollback-update"
    file_manager.create_project_from_zip(
        name, valid_zip_bytes, project_path=temp_project_path
    )
    workspace = _project_dir(temp_project_path, name)
    marker = workspace / "original.txt"
    marker.write_text("keep", encoding="utf-8")
    original_replace = Path.replace

    def fail_staging_publish(path, target):
        if path.name.startswith(f".{name}.staging-"):
            raise OSError("simulated publication failure")
        return original_replace(path, target)

    monkeypatch.setattr(Path, "replace", fail_staging_publish)
    with pytest.raises(OSError, match="simulated publication failure"):
        file_manager.update_project_from_zip(
            name, valid_zip_bytes, project_path=temp_project_path
        )

    assert marker.read_text(encoding="utf-8") == "keep"
    assert list(workspace.parent.glob(f".{name}.backup-*")) == []


def test_uploaded_runtime_and_legacy_product_state_is_discarded(
    temp_project_path, valid_zip_bytes
):
    archive = io.BytesIO(valid_zip_bytes)
    with zipfile.ZipFile(archive, "a") as package:
        package.writestr(".build/metadata.json", "secret")
        package.writestr("terraform/terraform.tfstate", "secret")
        package.writestr("versions/injected.zip", "legacy")
        package.writestr("project_info.json", '{"description": "legacy"}')

    file_manager.create_project_from_zip(
        "sanitized", archive.getvalue(), project_path=temp_project_path
    )
    workspace = _project_dir(temp_project_path, "sanitized")

    assert not (workspace / ".build").exists()
    assert not (workspace / "terraform").exists()
    assert not (workspace / "versions").exists()
    assert not (workspace / "project_info.json").exists()


def test_single_archive_wrapper_is_flattened(temp_project_path, valid_zip_bytes):
    file_manager.create_project_from_zip(
        "wrapped",
        _wrap_archive(valid_zip_bytes),
        project_path=temp_project_path,
    )
    workspace = _project_dir(temp_project_path, "wrapped")
    assert (workspace / CONSTANTS.CONFIG_FILE).is_file()
    assert not (workspace / "wrapped").exists()


def test_archive_wrapper_rejects_files_outside_root(
    temp_project_path, valid_zip_bytes
):
    with pytest.raises(ValueError, match="outside the canonical project root"):
        file_manager.create_project_from_zip(
            "ambiguous",
            _wrap_archive(valid_zip_bytes, extra_root_file=True),
            project_path=temp_project_path,
        )
    assert not _project_dir(temp_project_path, "ambiguous").exists()
