"""Tests for private, one-operation deployment packages."""

from datetime import datetime, timedelta, timezone
import io
import json
import os
from pathlib import Path
import stat
import zipfile

import pytest

from src.core.project_storage import ProjectStorage
from src.operation_packages import (
    LOCK_FILE,
    METADATA_FILE,
    OperationPackageError,
    OperationPackageStore,
)
from src.runtime_state import RuntimeStateStore


def _archive() -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("config.json", '{"digital_twin_name":"factory"}')
        archive.writestr(
            "config_credentials.json",
            '{"aws":{"aws_secret_access_key":"operation-secret"}}',
        )
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
