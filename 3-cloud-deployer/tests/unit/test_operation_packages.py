"""Tests for private, one-operation deployment packages."""

from datetime import datetime, timedelta, timezone
import io
import json
import os
from pathlib import Path
import stat
import zipfile

import pytest

from src.architecture_profiles.contracts import (
    calculate_digest,
    calculate_resolution_id,
)
from src.core.config_loader import ProjectConfigLoader
from src.core.project_storage import ProjectStorage
from src.operation_packages import (
    LOCK_FILE,
    METADATA_FILE,
    OperationPackageError,
    OperationPackageStore,
    inspect_deployment_requirements,
)
from src.providers.terraform.package_builder import build_all_packages
from src.runtime_state import RuntimeStateStore
from src.tfvars_generator import generate_tfvars
from src.user_function_extensions.contracts import runtime as extension_runtime
from tests.utils.deployment_specification import deployment_manifest


def _archive() -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("config.json", '{"digital_twin_name":"factory"}')
        archive.writestr(
            "config_credentials.json",
            '{"aws":{"aws_secret_access_key":"operation-secret"}}',
        )
    return buffer.getvalue()


def _six_layer_archive() -> bytes:
    manifest = deployment_manifest(resource_name="factory")
    manifest["twin"]["id"] = "22222222-2222-4222-8222-222222222222"
    extension_root = (
        Path(__file__).resolve().parents[2]
        / "src"
        / "contracts"
        / "generated"
        / "user-function-extension"
        / "v1"
    )
    extension_manifest = json.loads(
        (extension_root / "examples" / "valid-artifact.json").read_text("utf-8")
    )
    source_root = extension_root / "examples" / "source" / "valid"
    architecture = manifest["resolved_twin_architecture"]
    architecture_binding = architecture["extension_bindings"][0]
    architecture_binding["artifact_id"] = extension_manifest["artifact_id"]
    architecture_binding["artifact_digest"] = extension_manifest["artifact_digest"]
    architecture["resolution_id"] = calculate_resolution_id(architecture)
    architecture["content_digest"] = calculate_digest(architecture)
    manifest["resolved_twin_architecture_digest"] = architecture["content_digest"]
    artifact_root = (
        f".twin2multicloud/extensions/artifacts/{extension_manifest['artifact_id']}"
    )
    manifest_path_in_archive = f"{artifact_root}/manifest.json"
    source_path_in_archive = f"{artifact_root}/source"
    binding_digest = extension_runtime.binding_digest(
        twin_id=manifest["twin"]["id"],
        slot_id=extension_manifest["slot_id"],
        slot_version=extension_manifest["slot_version"],
        artifact_id=extension_manifest["artifact_id"],
        artifact_digest=extension_manifest["artifact_digest"],
    )
    binding = {
        "slot_id": extension_manifest["slot_id"],
        "slot_version": extension_manifest["slot_version"],
        "artifact_id": extension_manifest["artifact_id"],
        "artifact_digest": extension_manifest["artifact_digest"],
        "binding_digest": binding_digest,
        "manifest_path": manifest_path_in_archive,
        "source_root": source_path_in_archive,
    }
    binding_index_path = ".twin2multicloud/extensions/bindings.json"
    binding_index = {
        "schema_version": "twin-extension-binding-index.v1",
        "twin_id": manifest["twin"]["id"],
        "bindings": [binding],
    }
    manifest["extensions"] = {
        "binding_index": binding_index_path,
        "bindings": [
            {
                key: binding[key]
                for key in (
                    "slot_id",
                    "slot_version",
                    "artifact_id",
                    "artifact_digest",
                    "binding_digest",
                )
            }
        ],
    }
    extension_files = {
        manifest_path_in_archive: extension_runtime.canonical_json(extension_manifest),
        binding_index_path: extension_runtime.canonical_json(binding_index),
        **{
            f"{source_path_in_archive}/{path.name}": path.read_text("utf-8")
            for path in source_root.iterdir()
            if path.is_file()
        },
    }
    manifest["package"]["files"] = sorted(
        {*manifest["package"]["files"], "config_user.json", *extension_files}
    )
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr(
            "config.json",
            json.dumps(
                {
                    "digital_twin_name": "factory",
                    "hot_storage_size_in_days": 30,
                    "cold_storage_size_in_days": 90,
                    "mode": "debug",
                }
            ),
        )
        archive.writestr(
            "config_credentials.json",
            json.dumps(
                {
                    "aws": {
                        "aws_access_key_id": "test",
                        "aws_secret_access_key": "operation-secret",
                        "aws_region": "eu-central-1",
                    },
                    "azure": {
                        "azure_subscription_id": "subscription",
                        "azure_client_id": "client",
                        "azure_client_secret": "operation-secret",
                        "azure_tenant_id": "tenant",
                        "azure_region": "westeurope",
                        "azure_region_iothub": "westeurope",
                        "azure_region_digital_twin": "westeurope",
                    },
                }
            ),
        )
        archive.writestr(
            "config_providers.json",
            json.dumps(manifest["providers"]),
        )
        archive.writestr("config_iot_devices.json", "[]")
        archive.writestr("config_events.json", "[]")
        archive.writestr(
            "config_user.json",
            json.dumps(
                {
                    "admin_email": "researcher@example.test",
                    "admin_first_name": "Thesis",
                    "admin_last_name": "Researcher",
                    "aws_layer_access_principal_intent": "existing",
                    "azure_principal_object_id": (
                        "11111111-1111-1111-1111-111111111111"
                    ),
                    "azure_principal_label": "researcher@example.test",
                }
            ),
        )
        for path, content in extension_files.items():
            archive.writestr(path, content)
        archive.writestr("deployment_manifest.json", json.dumps(manifest))
    return buffer.getvalue()


def _store(tmp_path: Path) -> tuple[OperationPackageStore, Path, RuntimeStateStore]:
    storage = ProjectStorage(project_root=tmp_path)
    durable = storage.deployment_project_path("factory")
    durable.mkdir(parents=True)
    (durable / "terraform").mkdir()
    (durable / "terraform" / "terraform.tfstate").write_text("before")
    runtime_state_store = RuntimeStateStore(
        root=tmp_path / "runtime-state",
        project_storage=storage,
    )
    return (
        OperationPackageStore(
            root=tmp_path / "operations",
            project_storage=storage,
            runtime_state_store=runtime_state_store,
            ttl_seconds=60,
        ),
        durable,
        runtime_state_store,
    )


def test_stage_is_private_and_acquire_is_one_shot(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "file_manager.validator.validate_project_zip", lambda _archive, **_kwargs: []
    )
    store, durable, runtime_state_store = _store(tmp_path)

    staged = store.stage("factory", _archive())
    package_path = store.root / staged.token

    assert stat.S_IMODE(package_path.stat().st_mode) == 0o700
    assert (
        stat.S_IMODE((package_path / "config_credentials.json").stat().st_mode) == 0o600
    )
    assert not (durable / "config_credentials.json").exists()
    assert not (durable / "terraform" / "terraform.tfstate").exists()

    with store.acquire("factory", staged.token) as acquired:
        assert (acquired / "terraform" / "terraform.tfstate").read_text() == "before"
        assert "operation-secret" in (acquired / "config_credentials.json").read_text()
        (acquired / "terraform" / "terraform.tfstate").write_text("after")

    assert not package_path.exists()
    assert (
        runtime_state_store.project_path("factory") / "terraform" / "terraform.tfstate"
    ).read_text() == "after"
    with pytest.raises(OperationPackageError, match="invalid or expired"):
        with store.acquire("factory", staged.token):
            pass


def test_stage_rejects_invalid_contract_before_creating_package_root(
    monkeypatch,
    tmp_path,
):
    store, _durable, _runtime_state_store = _store(tmp_path)
    monkeypatch.setattr(
        "file_manager.validate_deployment_operation_archive",
        lambda _archive: (_ for _ in ()).throw(
            ValueError("DEPLOYMENT_MANIFEST_REQUIRED")
        ),
    )

    with pytest.raises(ValueError, match="DEPLOYMENT_MANIFEST_REQUIRED"):
        store.stage("factory", _archive())

    assert not store.root.exists()


def test_stage_six_layer_compiles_graph_and_returns_bounded_evidence(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setattr(
        "file_manager.validator.validate_project_zip",
        lambda _archive, **_kwargs: [],
    )
    store, _durable, _runtime_state_store = _store(tmp_path)

    staged = store.stage("factory", _six_layer_archive())

    assert staged.graph_evidence is not None
    assert staged.graph_evidence["graph_schema_version"] == (
        "resolved-deployment-graph.v1"
    )
    assert staged.graph_evidence["node_count"] == 8
    assert staged.graph_evidence["edge_count"] == 9
    assert staged.graph_evidence["binding_count"] == 18
    metadata = json.loads(
        (store.root / staged.token / METADATA_FILE).read_text("utf-8")
    )
    assert metadata["graph_evidence"] == staged.graph_evidence


def test_requirement_inspection_is_secret_free_and_leaves_no_workspace(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setattr(
        "file_manager.validator.validate_project_zip",
        lambda _archive, **_kwargs: [],
    )
    created = tmp_path / "inspection"

    def make_inspection_directory(**_kwargs):
        created.mkdir()
        return str(created)

    monkeypatch.setattr(
        "src.operation_packages.tempfile.mkdtemp",
        make_inspection_directory,
    )

    inspection = inspect_deployment_requirements(
        "factory",
        _six_layer_archive(),
        project_storage=ProjectStorage(project_root=tmp_path / "projects"),
    )

    assert inspection.graph_evidence["requirements_digest"].startswith("sha256:")
    assert inspection.graph_evidence["requirement_count"] == len(
        inspection.requirements
    )
    assert {item["provider"] for item in inspection.requirements} == {
        "aws",
        "azure",
    }
    assert "operation-secret" not in json.dumps(
        {
            "graph_evidence": inspection.graph_evidence,
            "requirements": inspection.requirements,
        }
    )
    assert not created.exists()


def test_six_layer_operation_package_drives_real_graph_packages_and_tfvars(
    monkeypatch,
    tmp_path,
):
    """Exercise the Six-layer v4 manifest through packages and tfvars."""
    monkeypatch.setattr(
        "file_manager.validator.validate_project_zip",
        lambda _archive, **_kwargs: [],
    )
    store, _durable, _runtime_state_store = _store(tmp_path)
    staged = store.stage("factory", _six_layer_archive())
    terraform_dir = Path(__file__).resolve().parents[2] / "src" / "terraform"

    with store.acquire("factory", staged.token) as acquired:
        context = ProjectConfigLoader().create_context_from_path(
            "factory",
            acquired,
            "aws",
            operation_id="phase-8.6-offline",
        )
        packages = build_all_packages(
            terraform_dir,
            acquired,
            context.config.providers,
            operation_id=context.operation_id,
            graph=context.resolved_deployment_graph,
        )
        tfvars_path = acquired / "terraform" / "generated.tfvars.json"
        generate_tfvars(str(acquired), str(tfvars_path))
        tfvars = json.loads(tfvars_path.read_text("utf-8"))

        assert set(packages) == {
            item["package_id"]
            for item in json.loads(
                (
                    acquired / ".twin2multicloud" / "graph" / "package-evidence.json"
                ).read_text("utf-8")
            )["built_packages"]
        }
        assert tfvars["layer_1_provider"] == "aws"
        assert tfvars["layer_5_provider"] == "aws"
        assert tfvars["event_layer_provider"] == "azure"
        assert tfvars["architecture_profile_id"] == "six-layer-eventing"
        assert tfvars["architecture_profile_version"] == "1"


def test_acquire_rejects_cross_project_and_concurrent_use(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "file_manager.validator.validate_project_zip", lambda _archive, **_kwargs: []
    )
    store, _durable, _runtime_state_store = _store(tmp_path)
    staged = store.stage("factory", _archive())

    with pytest.raises(OperationPackageError, match="does not belong"):
        with store.acquire("another-project", staged.token):
            pass

    with store.acquire("factory", staged.token):
        with pytest.raises(OperationPackageError, match="already in use"):
            with store.acquire("factory", staged.token):
                pass


def test_discard_project_invalidates_unused_packages(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "file_manager.validator.validate_project_zip", lambda _archive, **_kwargs: []
    )
    store, _durable, _runtime_state_store = _store(tmp_path)
    first = store.stage("factory", _archive())
    second = store.stage("factory", _archive())

    store.discard_project("factory")

    assert not (store.root / first.token).exists()
    assert not (store.root / second.token).exists()


def test_discard_project_rejects_active_operation(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "file_manager.validator.validate_project_zip", lambda _archive, **_kwargs: []
    )
    store, _durable, _runtime_state_store = _store(tmp_path)
    staged = store.stage("factory", _archive())

    with store.acquire("factory", staged.token):
        with pytest.raises(OperationPackageError, match="active deployment operation"):
            store.discard_project("factory")

    assert not (store.root / staged.token).exists()


def test_cleanup_removes_expired_packages_but_never_active_package(
    monkeypatch, tmp_path
):
    monkeypatch.setattr(
        "file_manager.validator.validate_project_zip", lambda _archive, **_kwargs: []
    )
    store, _durable, _runtime_state_store = _store(tmp_path)
    staged = store.stage("factory", _archive())
    package_path = store.root / staged.token
    metadata_path = package_path / METADATA_FILE
    metadata = json.loads(metadata_path.read_text())
    metadata["expires_at"] = (
        datetime.now(timezone.utc) - timedelta(seconds=1)
    ).isoformat()
    metadata_path.write_text(json.dumps(metadata))

    (package_path / LOCK_FILE).write_text(str(os.getpid()))
    store.cleanup_expired()
    assert package_path.exists()

    (package_path / LOCK_FILE).unlink()
    store.cleanup_expired()
    assert not package_path.exists()


def test_cleanup_removes_package_with_stale_process_lock(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "file_manager.validator.validate_project_zip", lambda _archive, **_kwargs: []
    )
    store, _durable, _runtime_state_store = _store(tmp_path)
    staged = store.stage("factory", _archive())
    package_path = store.root / staged.token
    (package_path / LOCK_FILE).write_text("999999999")

    store.cleanup_expired()

    assert not package_path.exists()


def test_acquire_preserves_original_failure_when_output_sync_also_fails(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setattr(
        "file_manager.validator.validate_project_zip", lambda _archive, **_kwargs: []
    )
    store, _durable, _runtime_state_store = _store(tmp_path)
    staged = store.stage("factory", _archive())

    def failing_sync(_workspace):
        raise OSError("sync failed")

    monkeypatch.setattr("src.operation_packages.sync_runtime_outputs", failing_sync)

    with pytest.raises(RuntimeError, match="deployment failed"):
        with store.acquire("factory", staged.token):
            raise RuntimeError("deployment failed")

    assert not (store.root / staged.token).exists()


def test_acquire_surfaces_output_sync_failure_after_success(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "file_manager.validator.validate_project_zip", lambda _archive, **_kwargs: []
    )
    store, _durable, _runtime_state_store = _store(tmp_path)
    staged = store.stage("factory", _archive())

    def failing_sync(_workspace):
        raise OSError("sync failed")

    monkeypatch.setattr("src.operation_packages.sync_runtime_outputs", failing_sync)

    with pytest.raises(OSError, match="sync failed"):
        with store.acquire("factory", staged.token):
            pass

    assert not (store.root / staged.token).exists()
