"""Provider-neutral contracts for user function package discovery."""

import json

import pytest

from src.providers.terraform.package_builders import user


def _project(tmp_path):
    (tmp_path / "config.json").write_text(
        json.dumps({"digital_twin_name": "factory"}),
        encoding="utf-8",
    )
    (tmp_path / "config_events.json").write_text(
        json.dumps(
            [
                {"action": {"type": "function", "functionName": "notify"}},
                {"action": {"type": "function", "functionName": "notify"}},
                {"action": {"type": "workflow"}},
            ]
        ),
        encoding="utf-8",
    )
    (tmp_path / "config_iot_devices.json").write_text(
        json.dumps([{"id": "device-1"}, {"id": "device-1"}]),
        encoding="utf-8",
    )
    return tmp_path


def _source_tree(project, provider):
    root_name = {
        "aws": "lambda_functions",
        "azure": "azure_functions",
        "google": "cloud_functions",
        "gcp": "cloud_functions",
    }[provider]
    root = project / root_name
    for relative in (
        "event_actions/notify",
        "processors/device-1",
        "event-feedback",
    ):
        directory = root / relative
        directory.mkdir(parents=True)
        (directory / "handler.py").write_text("VALUE = 1\n", encoding="utf-8")


@pytest.mark.parametrize(
    ("provider", "expected_packages", "expected_builder"),
    [
        ("aws", {"notify", "processor-device-1", "event-feedback"}, "aws"),
        ("google", {"notify", "processor-device-1", "event-feedback"}, "gcp"),
        ("gcp", {"notify", "processor-device-1", "event-feedback"}, "gcp"),
        ("azure", {"notify"}, "azure"),
    ],
)
def test_user_package_discovery_preserves_provider_contracts(
    monkeypatch,
    tmp_path,
    provider,
    expected_packages,
    expected_builder,
):
    project = _project(tmp_path)
    _source_tree(project, provider)
    calls = []
    monkeypatch.setattr(
        user,
        "_create_lambda_zip",
        lambda source, shared, target, **kwargs: calls.append(
            ("aws", source, shared, target, kwargs)
        ),
    )
    monkeypatch.setattr(
        user,
        "_create_gcp_function_zip",
        lambda source, shared, target, **kwargs: calls.append(
            ("gcp", source, shared, target, kwargs)
        ),
    )
    monkeypatch.setattr(
        user,
        "_create_azure_function_zip",
        lambda source, target: calls.append(("azure", source, None, target, {})),
    )

    packages = user.build_user_packages(
        project,
        {"layer_2_provider": provider},
    )

    assert set(packages) == expected_packages
    assert {call[0] for call in calls} == {expected_builder}
    assert sum(call[1].name == "notify" for call in calls) == 1
    metadata = project / ".build" / "metadata"
    metadata_provider = "gcp" if provider == "google" else provider
    assert {path.stem for path in metadata.glob("*.json")} == {
        f"notify.{metadata_provider}",
        f"processor-device-1.{metadata_provider}",
        f"event-feedback.{metadata_provider}",
    }


def test_processor_build_receives_twin_and_device_identity(monkeypatch, tmp_path):
    project = _project(tmp_path)
    _source_tree(project, "aws")
    processor_kwargs = []

    def build(source, _shared, _target, **kwargs):
        if source.name == "device-1":
            processor_kwargs.append(kwargs)

    monkeypatch.setattr(user, "_create_lambda_zip", build)

    user.build_user_packages(project, {"layer_2_provider": "aws"})

    assert processor_kwargs == [
        {"digital_twin_name": "factory", "device_id": "device-1"}
    ]


@pytest.mark.parametrize(
    ("filename", "payload", "message"),
    [
        ("config_events.json", {}, "Event config must be an array"),
        ("config_iot_devices.json", ["device"], "Device config must be an array"),
    ],
)
def test_config_shapes_fail_before_package_mutation(tmp_path, filename, payload, message):
    project = _project(tmp_path)
    (project / filename).write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match=message):
        user.build_user_packages(project, {"layer_2_provider": "aws"})


def test_user_function_name_cannot_escape_source_boundary(tmp_path):
    project = _project(tmp_path)
    (project / "config_events.json").write_text(
        json.dumps([{"action": {"type": "function", "functionName": "../escape"}}]),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Invalid function name"):
        user.build_user_packages(project, {"layer_2_provider": "aws"})


def test_directory_hash_rejects_symlinked_source_files(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    outside = tmp_path / "outside.py"
    outside.write_text("SECRET = True\n", encoding="utf-8")
    (source / "handler.py").symlink_to(outside)

    with pytest.raises(ValueError, match="Symbolic links"):
        user._compute_directory_hash(source)


def test_directory_hash_rejects_symlinked_source_directories(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.py").write_text("SECRET = True\n", encoding="utf-8")
    (source / "dependency").symlink_to(outside, target_is_directory=True)

    with pytest.raises(ValueError, match="Symbolic links"):
        user._compute_directory_hash(source)


def test_directory_hash_ignores_files_excluded_from_package(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "handler.py").write_text("VALUE = 1\n", encoding="utf-8")
    baseline = user._compute_directory_hash(source)

    (source / ".DS_Store").write_text("local metadata", encoding="utf-8")
    (source / "old.zip").write_bytes(b"old artifact")

    assert user._compute_directory_hash(source) == baseline


def test_failed_package_build_does_not_publish_build_metadata(monkeypatch, tmp_path):
    project = _project(tmp_path)
    _source_tree(project, "aws")
    monkeypatch.setattr(
        user,
        "_create_lambda_zip",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("build failed")),
    )

    with pytest.raises(RuntimeError, match="build failed"):
        user.build_user_packages(project, {"layer_2_provider": "aws"})

    metadata_dir = project / ".build" / "metadata"
    assert not metadata_dir.exists() or list(metadata_dir.iterdir()) == []
