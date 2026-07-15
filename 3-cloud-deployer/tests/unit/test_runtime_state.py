"""Tests for durable runtime state outside Deployer project definitions."""

from pathlib import Path
import stat

from src.core.project_storage import ProjectStorage
from src.runtime_state import RuntimeStateStore


def _store(tmp_path: Path) -> tuple[RuntimeStateStore, Path]:
    storage = ProjectStorage(project_root=tmp_path)
    durable = storage.deployment_project_path("factory")
    durable.mkdir(parents=True)
    return (
        RuntimeStateStore(
            root=tmp_path / "runtime-state",
            project_storage=storage,
        ),
        durable,
    )


def test_migrate_legacy_outputs_removes_secrets_from_upload_project(tmp_path):
    store, durable = _store(tmp_path)
    state = durable / "terraform" / "terraform.tfstate"
    key = durable / "iot_devices_auth" / "device" / "private.key"
    simulator = (
        durable / "iot_device_simulator" / "aws" / "device" / "config_generated.json"
    )
    metadata = durable / ".build" / "metadata" / "functions.json"
    for path, content in (
        (state, "state"),
        (key, "key"),
        (simulator, "simulator"),
        (metadata, "{}"),
    ):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)

    store.migrate_legacy_project_outputs("factory", durable)

    runtime = store.project_path("factory")
    assert (runtime / "terraform" / "terraform.tfstate").read_text() == "state"
    assert (
        runtime / "iot_devices_auth" / "device" / "private.key"
    ).read_text() == "key"
    assert (
        runtime / "iot_device_simulator" / "aws" / "device" / "config_generated.json"
    ).read_text() == "simulator"
    assert (runtime / ".build" / "metadata" / "functions.json").read_text() == "{}"
    assert not state.exists()
    assert not (durable / "iot_devices_auth").exists()
    assert not simulator.exists()
    assert not metadata.exists()
    assert stat.S_IMODE(runtime.stat().st_mode) == 0o700
    assert (
        stat.S_IMODE(
            (runtime / "iot_devices_auth" / "device" / "private.key").stat().st_mode
        )
        == 0o600
    )


def test_restore_and_delete_are_project_scoped(tmp_path):
    store, _durable = _store(tmp_path)
    runtime = store.project_path("factory", create=True)
    state = runtime / "terraform" / "terraform.tfstate"
    state.parent.mkdir()
    state.write_text("state")
    destination = tmp_path / "operation"
    destination.mkdir()

    store.restore_into("factory", destination)

    assert (destination / "terraform" / "terraform.tfstate").read_text() == "state"
    store.delete("factory")
    assert not runtime.exists()
