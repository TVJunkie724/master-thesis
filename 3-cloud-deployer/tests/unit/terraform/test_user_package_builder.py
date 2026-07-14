"""Provider-neutral contracts for user function package discovery."""

import json

import pytest

from src.providers.terraform.package_builders.azure import build_azure_user_bundle
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
        filename = "function_app.py" if provider == "azure" else "handler.py"
        (directory / filename).write_text(
            "import azure.functions as func\napp = func.FunctionApp()\n"
            if provider == "azure"
            else "VALUE = 1\n",
            encoding="utf-8",
        )


@pytest.mark.parametrize(
    ("provider", "expected_packages", "expected_builder"),
    [
        ("aws", {"notify", "processor-device-1", "event-feedback"}, "aws"),
        ("google", {"notify", "processor-device-1", "event-feedback"}, "gcp"),
        ("gcp", {"notify", "processor-device-1", "event-feedback"}, "gcp"),
        ("azure", set(), None),
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

    def record_build(kind, source, shared, target, kwargs):
        target.write_bytes(f"{kind}-artifact".encode("ascii"))
        calls.append((kind, source, shared, target, kwargs))

    monkeypatch.setattr(
        user,
        "_create_lambda_zip",
        lambda source, shared, target, **kwargs: record_build(
            "aws", source, shared, target, kwargs
        ),
    )
    monkeypatch.setattr(
        user,
        "_create_gcp_function_zip",
        lambda source, shared, target, **kwargs: record_build(
            "gcp", source, shared, target, kwargs
        ),
    )
    monkeypatch.setattr(
        user,
        "_create_azure_function_zip",
        lambda source, target: record_build("azure", source, None, target, {}),
    )

    packages = user.build_user_packages(
        project,
        {"layer_2_provider": provider},
    )

    assert set(packages) == expected_packages
    assert {call[0] for call in calls} == (
        {expected_builder} if expected_builder else set()
    )
    assert sum(call[1].name == "notify" for call in calls) == (
        0 if provider == "azure" else 1
    )
    metadata = project / ".build" / "metadata"
    metadata_provider = "gcp" if provider == "google" else provider
    expected_metadata = set() if provider == "azure" else {
        f"notify.{metadata_provider}",
        f"processor-device-1.{metadata_provider}",
        f"event-feedback.{metadata_provider}",
    }
    assert {path.stem for path in metadata.glob("*.json")} == expected_metadata


def test_processor_build_receives_twin_and_device_identity(monkeypatch, tmp_path):
    project = _project(tmp_path)
    _source_tree(project, "aws")
    processor_kwargs = []

    def build(source, _shared, target, **kwargs):
        target.write_bytes(b"artifact")
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
        user._compute_source_hash(source)


def test_directory_hash_rejects_symlinked_source_directories(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.py").write_text("SECRET = True\n", encoding="utf-8")
    (source / "dependency").symlink_to(outside, target_is_directory=True)

    with pytest.raises(ValueError, match="Symbolic links"):
        user._compute_source_hash(source)


def test_directory_hash_ignores_files_excluded_from_package(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "handler.py").write_text("VALUE = 1\n", encoding="utf-8")
    baseline = user._compute_source_hash(source)

    (source / ".DS_Store").write_text("local metadata", encoding="utf-8")
    (source / "old.zip").write_bytes(b"old artifact")

    assert user._compute_source_hash(source) == baseline


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


def test_azure_bundle_records_one_shared_artifact_for_all_functions(tmp_path):
    project = _project(tmp_path)
    _source_tree(project, "azure")

    artifact = build_azure_user_bundle(
        project,
        {"layer_2_provider": "azure"},
        {
            "useEventChecking": True,
            "returnFeedbackToDevice": True,
        },
    )

    assert artifact is not None
    metadata_paths = sorted((project / ".build" / "metadata").glob("*.azure.json"))
    assert {path.stem for path in metadata_paths} == {
        "event-feedback.azure",
        "notify.azure",
        "processor-device-1.azure",
    }
    metadata = [json.loads(path.read_text(encoding="utf-8")) for path in metadata_paths]
    assert {entry["schema_version"] for entry in metadata} == {2}
    assert {entry["artifact_hash"] for entry in metadata} == {
        user.hash_bytes(artifact.read_bytes())
    }
    assert len({entry["source_hash"] for entry in metadata}) == 1
