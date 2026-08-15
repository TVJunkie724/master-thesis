"""Offline validator, package, adapter, and Terraform-reference tests for #113."""

from __future__ import annotations

import copy
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
import importlib.util
import io
import json
from pathlib import Path
import shutil
import sys
from types import ModuleType, SimpleNamespace
import zipfile

import pytest

from src.tfvars_generator import (
    ConfigurationError,
    _load_validated_extension_packages,
)
from src.providers.terraform import package_builder as terraform_package_builder
from src.user_function_extensions import package_builder as package_builder_module
from src.user_function_extensions.contracts import ExtensionContractError, runtime
from src.user_function_extensions.package_builder import (
    build_bound_extension_packages,
    build_provider_package,
)


CONTRACT_ROOT = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "contracts"
    / "generated"
    / "user-function-extension"
    / "v1"
)
SOURCE_ROOT = CONTRACT_ROOT / "examples" / "source" / "valid"


def _manifest() -> dict:
    return json.loads(
        (CONTRACT_ROOT / "examples" / "valid-artifact.json").read_text(encoding="utf-8")
    )


def _files() -> dict[str, str]:
    return {
        path.relative_to(SOURCE_ROOT).as_posix(): path.read_text(encoding="utf-8")
        for path in SOURCE_ROOT.iterdir()
        if path.is_file()
    }


def _metadata() -> dict:
    manifest = _manifest()
    return {
        "slot_id": manifest["slot_id"],
        "slot_version": manifest["slot_version"],
        "runtime_id": manifest["runtime_id"],
        "configuration": manifest["configuration"],
        "declared_capabilities": manifest["declared_capabilities"],
    }


def _zip(files: dict[str, str]) -> bytes:
    return runtime.deterministic_source_zip(files)


@pytest.mark.parametrize("provider", ["aws", "azure", "gcp"])
def test_provider_packages_are_deterministic_and_preserve_source(provider):
    first, evidence = build_provider_package(
        manifest=_manifest(),
        files=_files(),
        provider=provider,
    )
    second, repeated = build_provider_package(
        manifest=_manifest(),
        files=_files(),
        provider=provider,
    )
    assert first == second
    assert evidence.package_digest == repeated.package_digest
    with zipfile.ZipFile(io.BytesIO(first)) as archive:
        assert archive.read("process.py").decode("utf-8") == _files()["process.py"]
        assert "_platform_runtime.py" in archive.namelist()
    evidence_json = json.dumps(asdict(evidence), sort_keys=True)
    assert "def process" not in evidence_json
    assert "configuration" not in evidence_json


@pytest.mark.parametrize(
    ("filename", "error_code"),
    [
        ("unknown-version.json", "EXTENSION_RUNTIME_UNSUPPORTED"),
        ("platform-field.json", "EXTENSION_SCHEMA_INVALID"),
        ("secret-configuration.json", "EXTENSION_SECRET_MATERIAL_DETECTED"),
        ("unauthorized-capability.json", "EXTENSION_CAPABILITY_UNAUTHORIZED"),
    ],
)
def test_required_invalid_metadata_fixtures_are_rejected(filename, error_code):
    metadata = json.loads(
        (CONTRACT_ROOT / "examples" / "invalid" / filename).read_text(encoding="utf-8")
    )
    with pytest.raises(ExtensionContractError) as exc:
        runtime.validate_source_archive(
            metadata=metadata,
            archive_bytes=_zip(_files()),
            created_by="00000000-0000-4000-8000-000000000001",
        )
    assert exc.value.code == error_code


def test_secret_scan_checks_every_bounded_collection_item():
    values = ["safe"] * 32 + ['token = "secret-value"']
    with pytest.raises(ExtensionContractError) as exc:
        runtime._scan_value(values, "payload")
    assert exc.value.code == "EXTENSION_SECRET_MATERIAL_DETECTED"
    assert exc.value.field == "payload[32]"


def test_unknown_artifact_schema_version_is_rejected():
    manifest = {**_manifest(), "schema_version": "user-function-artifact.v2"}
    with pytest.raises(ExtensionContractError) as exc:
        runtime.validate_artifact_manifest(manifest, files=_files())
    assert exc.value.code == "EXTENSION_VERSION_UNSUPPORTED"


@pytest.mark.parametrize(
    "requirements",
    [
        "requests>=2\n",
        "requests==2.0\n",
        "requests @ https://example.invalid/pkg.whl\n",
        "--index-url https://user:token@example.invalid/simple\n",
        "pip==24.0 --hash=sha256:" + "0" * 64 + "\n",
    ],
)
def test_dependency_lock_rejects_unpinned_unhashed_and_forbidden(requirements):
    files = {**_files(), "requirements.lock": requirements}
    with pytest.raises(ExtensionContractError) as exc:
        runtime.validate_source_archive(
            metadata=_metadata(),
            archive_bytes=_zip(files),
            created_by="00000000-0000-4000-8000-000000000001",
        )
    assert exc.value.code in {
        "EXTENSION_DEPENDENCY_UNPINNED",
        "EXTENSION_DEPENDENCY_FORBIDDEN",
        "EXTENSION_SECRET_MATERIAL_DETECTED",
    }


def test_valid_hashed_pure_python_wheel_is_packaged_at_importable_root(tmp_path):
    wheel = tmp_path / "demo_pkg-1.0-py3-none-any.whl"
    wheel.write_bytes(
        _binary_zip(
            {
                "demo_pkg/__init__.py": b"VALUE = 1\n",
                "demo_pkg-1.0.dist-info/METADATA": b"Name: demo-pkg\nVersion: 1.0\n",
            }
        )
    )
    files = {
        **_files(),
        "requirements.lock": (
            "demo-pkg==1.0 --hash=" + runtime.digest_bytes(wheel.read_bytes()) + "\n"
        ),
    }
    validated = runtime.validate_source_archive(
        metadata=_metadata(),
        archive_bytes=_zip(files),
        created_by="00000000-0000-4000-8000-000000000001",
    )
    package, _evidence = build_provider_package(
        manifest=dict(validated.manifest),
        files=dict(validated.files),
        provider="aws",
        wheelhouse=tmp_path,
    )
    with zipfile.ZipFile(io.BytesIO(package)) as archive:
        assert "demo_pkg/__init__.py" in archive.namelist()
        assert "requirements.txt" not in archive.namelist()


def test_all_schema_required_fields_and_additional_properties_fail_closed():
    envelope_schema = json.loads(
        (CONTRACT_ROOT / "runtime-envelope.schema.json").read_text(encoding="utf-8")
    )
    runtime_input = json.loads(
        (CONTRACT_ROOT / "examples" / "valid-runtime-input.json").read_text(
            encoding="utf-8"
        )
    )
    runtime_success = json.loads(
        (CONTRACT_ROOT / "examples" / "valid-runtime-success.json").read_text(
            encoding="utf-8"
        )
    )
    runtime_base = {
        key: runtime_success[key]
        for key in (
            "schema_version",
            "invocation_id",
            "correlation_id",
            "slot_id",
        )
    }
    cases = (
        (
            "extension-slot.schema.json",
            json.loads(
                (CONTRACT_ROOT / "extension-slot.schema.json").read_text(
                    encoding="utf-8"
                )
            ),
            runtime.load_registry()["slots"][0],
            runtime.validate_extension_slot,
        ),
        (
            "artifact-manifest.schema.json",
            json.loads(
                (CONTRACT_ROOT / "artifact-manifest.schema.json").read_text(
                    encoding="utf-8"
                )
            ),
            _manifest(),
            runtime.validate_artifact_manifest,
        ),
        (
            "runtime-envelope.input",
            envelope_schema["$defs"]["input"]["allOf"][1],
            runtime_input,
            runtime.validate_runtime_envelope,
        ),
        (
            "runtime-envelope.success",
            envelope_schema["$defs"]["success"]["allOf"][1],
            runtime_success,
            runtime.validate_runtime_envelope,
        ),
        (
            "runtime-envelope.rejected",
            envelope_schema["$defs"]["rejected"]["allOf"][1],
            {
                **runtime_base,
                "status": "rejected",
                "code": "DOMAIN_OUTPUT_INVALID",
                "message": "The extension result is invalid.",
            },
            runtime.validate_runtime_envelope,
        ),
        (
            "runtime-envelope.failed",
            envelope_schema["$defs"]["failed"]["allOf"][1],
            {
                **runtime_base,
                "status": "failed",
                "code": "PLATFORM_EXTENSION_FAILED",
                "message": "The extension failed.",
                "retryable": False,
            },
            runtime.validate_runtime_envelope,
        ),
    )
    for schema_name, schema, document, validator in cases:
        variants = list(_missing_required_variants(schema, document))
        assert variants, schema_name
        for field, variant in variants:
            with pytest.raises(ExtensionContractError):
                validator(variant)
        unexpected = {**document, "platform_handler": "forbidden"}
        with pytest.raises(ExtensionContractError):
            validator(unexpected)


def test_duplicate_registry_identity_and_manifest_references_are_rejected(
    monkeypatch,
):
    registry = runtime.load_registry()
    duplicate = copy.deepcopy(registry)
    duplicate["slots"].append(copy.deepcopy(duplicate["slots"][0]))
    original_loader = runtime._load_json_file
    monkeypatch.setattr(
        runtime,
        "_load_json_file",
        lambda path: (
            duplicate if path.name == "registry.json" else original_loader(path)
        ),
    )
    with pytest.raises(ExtensionContractError) as exc:
        runtime.load_registry()
    assert exc.value.code == "EXTENSION_SCHEMA_INVALID"

    adapter_drift = copy.deepcopy(registry)
    adapter_drift["slots"][0]["runtime_contract"]["provider_adapters"][0][
        "adapter_id"
    ] = "adapter.aws.unreviewed"
    monkeypatch.setattr(
        runtime,
        "_load_json_file",
        lambda path: (
            adapter_drift if path.name == "registry.json" else original_loader(path)
        ),
    )
    with pytest.raises(ExtensionContractError) as exc:
        runtime.load_registry()
    assert exc.value.code == "EXTENSION_RUNTIME_UNSUPPORTED"

    policy_drift = copy.deepcopy(registry)
    policy_drift["dependency_policies"][0]["forbidden_packages"].remove("pip")
    monkeypatch.setattr(
        runtime,
        "_load_json_file",
        lambda path: (
            policy_drift if path.name == "registry.json" else original_loader(path)
        ),
    )
    with pytest.raises(ExtensionContractError) as exc:
        runtime.load_registry()
    assert exc.value.code == "EXTENSION_DEPENDENCY_FORBIDDEN"

    monkeypatch.setattr(runtime, "_load_json_file", original_loader)
    manifest = _manifest()
    manifest["source"]["files"].append(copy.deepcopy(manifest["source"]["files"][0]))
    with pytest.raises(ExtensionContractError) as exc:
        runtime.validate_artifact_manifest(manifest)
    assert exc.value.code == "EXTENSION_SCHEMA_INVALID"


def test_digest_mutation_secret_reference_and_secret_path_are_rejected():
    mutated = {**_files(), "process.py": _files()["process.py"] + "\nVALUE = 2\n"}
    with pytest.raises(ExtensionContractError) as exc:
        runtime.validate_artifact_manifest(_manifest(), files=mutated)
    assert exc.value.code == "EXTENSION_SCHEMA_INVALID"

    referenced = {
        **_files(),
        "process.py": (
            "REFERENCE = 'secret://runtime/value'\n"
            "def process(payload, configuration, context):\n"
            "    return {'processed_value': payload['value']}\n"
        ),
    }
    with pytest.raises(ExtensionContractError) as exc:
        runtime.validate_source_archive(
            metadata=_metadata(),
            archive_bytes=_zip(referenced),
            created_by="00000000-0000-4000-8000-000000000001",
        )
    assert exc.value.code == "EXTENSION_SECRET_MATERIAL_DETECTED"

    with pytest.raises(ExtensionContractError) as exc:
        runtime.validate_source_archive(
            metadata=_metadata(),
            archive_bytes=_zip({**_files(), "api_key.py": "VALUE = 1\n"}),
            created_by="00000000-0000-4000-8000-000000000001",
        )
    assert exc.value.code == "EXTENSION_SECRET_MATERIAL_DETECTED"


def test_validation_and_package_duration_limits_fail_closed(monkeypatch):
    validation_tick = 0

    def validation_clock():
        nonlocal validation_tick
        validation_tick += 1
        return float(validation_tick)

    with pytest.raises(ExtensionContractError) as exc:
        runtime.validate_source_archive(
            metadata=_metadata(),
            archive_bytes=_zip(_files()),
            created_by="00000000-0000-4000-8000-000000000001",
            validation_timeout_seconds=0.5,
            monotonic_clock=validation_clock,
        )
    assert exc.value.code == "EXTENSION_VALIDATION_TIMEOUT"

    build_tick = 0

    def build_clock():
        nonlocal build_tick
        build_tick += 1
        return float(build_tick)

    with pytest.raises(ExtensionContractError) as exc:
        build_provider_package(
            manifest=_manifest(),
            files=_files(),
            provider="aws",
            build_timeout_seconds=0.5,
            monotonic_clock=build_clock,
        )
    assert exc.value.code == "EXTENSION_BUILD_TIMEOUT"

    slot = copy.deepcopy(runtime.get_slot("processor.telemetry", "1"))
    slot["resource_limits"]["artifact_bytes"] = 256
    monkeypatch.setattr(runtime, "get_slot", lambda *_args: slot)
    with pytest.raises(ExtensionContractError) as exc:
        build_provider_package(
            manifest=_manifest(),
            files=_files(),
            provider="aws",
        )
    assert exc.value.code == "EXTENSION_DEPENDENCY_FORBIDDEN"


def test_dependency_wheels_require_complete_closure_and_safe_paths(tmp_path):
    requiring = tmp_path / "demo_pkg-1.0-py3-none-any.whl"
    requiring.write_bytes(
        _binary_zip(
            {
                "demo_pkg/__init__.py": b"VALUE = 1\n",
                "demo_pkg-1.0.dist-info/METADATA": (
                    b"Name: demo-pkg\nVersion: 1.0\nRequires-Dist: transitive==2.0\n"
                ),
            }
        )
    )
    validated = _validated_with_wheels([requiring])
    with pytest.raises(ExtensionContractError) as exc:
        build_provider_package(
            manifest=dict(validated.manifest),
            files=dict(validated.files),
            provider="aws",
            wheelhouse=tmp_path,
        )
    assert exc.value.code == "EXTENSION_DEPENDENCY_FORBIDDEN"

    requiring.write_bytes(
        _binary_zip(
            {
                "../escaped.py": b"VALUE = 1\n",
                "demo_pkg-1.0.dist-info/METADATA": b"Name: demo-pkg\nVersion: 1.0\n",
            }
        )
    )
    validated = _validated_with_wheels([requiring])
    with pytest.raises(ExtensionContractError) as exc:
        build_provider_package(
            manifest=dict(validated.manifest),
            files=dict(validated.files),
            provider="aws",
            wheelhouse=tmp_path,
        )
    assert exc.value.code == "EXTENSION_DEPENDENCY_FORBIDDEN"


def test_dependency_wheels_reject_links_executable_modes_and_binary_magic(tmp_path):
    wheel = tmp_path / "demo_pkg-1.0-py3-none-any.whl"

    def write_wheel(payload: bytes, *, mode: int = 0o100644) -> None:
        output = io.BytesIO()
        with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
            package = zipfile.ZipInfo("demo_pkg/payload.dat")
            package.create_system = 3
            package.external_attr = mode << 16
            archive.writestr(package, payload)
            archive.writestr(
                "demo_pkg-1.0.dist-info/METADATA",
                b"Name: demo-pkg\nVersion: 1.0\n",
            )
        wheel.write_bytes(output.getvalue())

    write_wheel(b"safe data")
    validated = _validated_with_wheels([wheel])
    wheelhouse = tmp_path / "wheelhouse"
    wheelhouse.mkdir()
    (wheelhouse / wheel.name).symlink_to(wheel)
    with pytest.raises(ExtensionContractError) as exc:
        build_provider_package(
            manifest=dict(validated.manifest),
            files=dict(validated.files),
            provider="aws",
            wheelhouse=wheelhouse,
        )
    assert exc.value.code == "EXTENSION_DEPENDENCY_FORBIDDEN"

    (wheelhouse / wheel.name).unlink()
    for payload, mode in ((b"safe data", 0o100755), (b"\x7fELFpayload", 0o100644)):
        write_wheel(payload, mode=mode)
        validated = _validated_with_wheels([wheel])
        (wheelhouse / wheel.name).write_bytes(wheel.read_bytes())
        with pytest.raises(ExtensionContractError) as exc:
            build_provider_package(
                manifest=dict(validated.manifest),
                files=dict(validated.files),
                provider="aws",
                wheelhouse=wheelhouse,
            )
        assert exc.value.code == "EXTENSION_DEPENDENCY_FORBIDDEN"

    write_wheel(b"x" * (package_builder_module.MAX_DEPENDENCY_FILE_BYTES + 1))
    validated = _validated_with_wheels([wheel])
    (wheelhouse / wheel.name).write_bytes(wheel.read_bytes())
    with pytest.raises(ExtensionContractError) as exc:
        build_provider_package(
            manifest=dict(validated.manifest),
            files=dict(validated.files),
            provider="aws",
            wheelhouse=wheelhouse,
        )
    assert exc.value.code == "EXTENSION_DEPENDENCY_FORBIDDEN"


def test_oversized_wheel_member_is_rejected_before_read(tmp_path, monkeypatch):
    wheel = tmp_path / "oversized.whl"
    wheel.write_bytes(
        _binary_zip(
            {
                "demo_pkg/payload.dat": (
                    b"x" * (package_builder_module.MAX_DEPENDENCY_FILE_BYTES + 1)
                ),
            }
        )
    )
    original_read = zipfile.ZipFile.read

    def guarded_read(archive, name, *args, **kwargs):
        filename = name.filename if isinstance(name, zipfile.ZipInfo) else name
        if filename == "demo_pkg/payload.dat":
            raise AssertionError("oversized member was read")
        return original_read(archive, name, *args, **kwargs)

    monkeypatch.setattr(zipfile.ZipFile, "read", guarded_read)
    with pytest.raises(ExtensionContractError) as exc:
        package_builder_module._extract_wheel(wheel, {})
    assert exc.value.code == "EXTENSION_DEPENDENCY_FORBIDDEN"


def test_managed_dependency_fetch_verifies_hashes_with_offline_pip(
    tmp_path,
    monkeypatch,
):
    wheel = tmp_path / "demo_pkg-1.0-py3-none-any.whl"
    wheel.write_bytes(
        _binary_zip(
            {
                "demo_pkg/__init__.py": b"VALUE = 1\n",
                "demo_pkg-1.0.dist-info/METADATA": b"Name: demo-pkg\nVersion: 1.0\n",
            }
        )
    )
    validated = _validated_with_wheels([wheel])
    commands = []

    def prefetch(_manifest, destination, **_kwargs):
        (destination / wheel.name).write_bytes(wheel.read_bytes())

    def run(command, **_kwargs):
        commands.append(command)
        find_links = Path(command[command.index("--find-links") + 1])
        destination = Path(command[command.index("--dest") + 1])
        shutil.copy2(find_links / wheel.name, destination / wheel.name)
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(
        package_builder_module,
        "_prefetch_locked_wheels",
        prefetch,
    )
    monkeypatch.setattr(package_builder_module.subprocess, "run", run)
    package, _evidence = build_provider_package(
        manifest=dict(validated.manifest),
        files=dict(validated.files),
        provider="aws",
    )
    with zipfile.ZipFile(io.BytesIO(package)) as archive:
        assert "demo_pkg/__init__.py" in archive.namelist()
    command = commands[0]
    assert "--require-hashes" in command
    assert "--only-binary=:all:" in command
    assert "--no-deps" in command
    assert "--no-index" in command
    assert "--find-links" in command

    with pytest.raises(ExtensionContractError):
        package_builder_module._require_approved_https_url(
            "https://evil.example/demo.whl",
            frozenset({"pypi.org", "files.pythonhosted.org"}),
        )


def test_archive_safety_rejects_zip_slip_symlink_nested_and_file_count():
    unsafe_archives = [
        _binary_zip({"../process.py": b"def process(a, b, c): return {}\n"}),
        _symlink_zip(),
        _socket_zip(),
        _binary_zip(
            {
                **{name: value.encode("utf-8") for name, value in _files().items()},
                "nested.zip": b"PK\x03\x04",
            }
        ),
        _binary_zip(
            {
                **{name: value.encode("utf-8") for name, value in _files().items()},
                **{f"module_{index}.py": b"VALUE = 1\n" for index in range(65)},
            }
        ),
    ]
    for archive in unsafe_archives:
        with pytest.raises(ExtensionContractError) as exc:
            runtime.validate_source_archive(
                metadata=_metadata(),
                archive_bytes=archive,
                created_by="00000000-0000-4000-8000-000000000001",
            )
        assert exc.value.code == "EXTENSION_ARCHIVE_UNSAFE"


def test_bound_package_inputs_and_generated_paths_are_bounded(tmp_path):
    extensions = tmp_path / ".twin2multicloud" / "extensions"
    extensions.mkdir(parents=True)
    (extensions / "bindings.json").write_bytes(
        b"{" + b" " * package_builder_module.MAX_BINDING_INDEX_BYTES + b"}"
    )
    with pytest.raises(ExtensionContractError) as oversized:
        build_bound_extension_packages(
            tmp_path,
            {"layer_2_provider": "aws"},
        )
    assert oversized.value.code == "EXTENSION_BINDING_UNRESOLVED"

    (extensions / "bindings.json").unlink()
    outside = tmp_path / "outside"
    outside.mkdir()
    (tmp_path / ".build").symlink_to(outside, target_is_directory=True)
    with pytest.raises(ExtensionContractError) as linked:
        package_builder_module._prepare_generated_directory(
            tmp_path,
            tmp_path / ".build" / "extensions",
        )
    assert linked.value.code == "EXTENSION_BINDING_UNRESOLVED"


def test_bound_packages_fail_closed_before_terraform_and_publish_evidence(tmp_path):
    artifact_root = (
        tmp_path
        / ".twin2multicloud"
        / "extensions"
        / "artifacts"
        / _manifest()["artifact_id"]
    )
    source_root = artifact_root / "source"
    source_root.mkdir(parents=True)
    (artifact_root / "manifest.json").write_text(
        runtime.canonical_json(_manifest()),
        encoding="utf-8",
    )
    for name, content in _files().items():
        target = source_root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")

    twin_id = "00000000-0000-4000-8000-000000000099"
    manifest = _manifest()
    binding = {
        "slot_id": manifest["slot_id"],
        "slot_version": manifest["slot_version"],
        "artifact_id": manifest["artifact_id"],
        "artifact_digest": manifest["artifact_digest"],
        "binding_digest": runtime.binding_digest(
            twin_id=twin_id,
            slot_id=manifest["slot_id"],
            slot_version=manifest["slot_version"],
            artifact_id=manifest["artifact_id"],
            artifact_digest=manifest["artifact_digest"],
        ),
        "manifest_path": str((artifact_root / "manifest.json").relative_to(tmp_path)),
        "source_root": str(source_root.relative_to(tmp_path)),
    }
    index_path = tmp_path / ".twin2multicloud" / "extensions" / "bindings.json"
    index_path.write_text(
        runtime.canonical_json(
            {
                "schema_version": "twin-extension-binding-index.v1",
                "twin_id": twin_id,
                "bindings": [binding],
            }
        ),
        encoding="utf-8",
    )

    packages = build_bound_extension_packages(
        tmp_path,
        {"layer_2_provider": "aws"},
    )
    assert packages["extension:processor.telemetry"].is_file()
    tfvars = _load_validated_extension_packages(tmp_path)
    assert tfvars["validated_extension_packages"][0]["package_digest"].startswith(
        "sha256:"
    )
    assert Path(tfvars["validated_extension_packages"][0]["package_path"]).is_absolute()
    evidence = json.loads(
        (tmp_path / ".build" / "extensions" / "evidence.json").read_text(
            encoding="utf-8"
        )
    )
    assert not Path(evidence["packages"][0]["package_path"]).is_absolute()
    assert "def process" not in json.dumps(evidence)
    package_path = Path(tfvars["validated_extension_packages"][0]["package_path"])
    package_bytes = package_path.read_bytes()
    package_path.write_bytes(package_bytes + b"tampered")
    with pytest.raises(ConfigurationError):
        _load_validated_extension_packages(tmp_path)
    package_path.write_bytes(package_bytes)

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(
        terraform_package_builder,
        "validate_terraform_provider_capabilities",
        lambda _providers, **_kwargs: None,
    )
    try:
        with pytest.raises(ExtensionContractError) as exc:
            terraform_package_builder.build_all_packages(
                tmp_path,
                tmp_path,
                {"layer_2_provider": "aws"},
                operation_id="operation-test-1",
            )
        assert exc.value.code == "EXTENSION_BINDING_UNRESOLVED"
        assert exc.value.field == "deployment_component_catalog"
        assert exc.value.correlation_id == "operation-test-1"
    finally:
        monkeypatch.undo()

    binding["binding_digest"] = "sha256:" + "0" * 64
    index_path.write_text(
        runtime.canonical_json(
            {
                "schema_version": "twin-extension-binding-index.v1",
                "twin_id": twin_id,
                "bindings": [binding],
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ExtensionContractError) as exc:
        build_bound_extension_packages(
            tmp_path,
            {"layer_2_provider": "aws"},
        )
    assert exc.value.code == "EXTENSION_BINDING_UNRESOLVED"


def test_provider_wrappers_return_equivalent_runtime_envelopes(tmp_path):
    envelope = json.loads(
        (CONTRACT_ROOT / "examples" / "valid-runtime-input.json").read_text(
            encoding="utf-8"
        )
    )
    responses = {}
    for provider in ("aws", "azure", "gcp"):
        package, _evidence = build_provider_package(
            manifest=_manifest(),
            files=_files(),
            provider=provider,
        )
        provider_root = tmp_path / provider
        provider_root.mkdir()
        with zipfile.ZipFile(io.BytesIO(package)) as archive:
            archive.extractall(provider_root)
        responses[provider] = _invoke_wrapper(provider_root, provider, envelope)
    assert responses["aws"] == responses["azure"] == responses["gcp"]
    assert responses["aws"]["status"] == "success"


def test_provider_wrappers_return_equivalent_timeout_envelopes(tmp_path):
    envelope = json.loads(
        (CONTRACT_ROOT / "examples" / "valid-runtime-input.json").read_text(
            encoding="utf-8"
        )
    )
    responses = {}
    for provider in ("aws", "azure", "gcp"):
        package, _evidence = build_provider_package(
            manifest=_manifest(),
            files=_files(),
            provider=provider,
        )
        provider_root = tmp_path / f"{provider}-timeout"
        provider_root.mkdir()
        with zipfile.ZipFile(io.BytesIO(package)) as archive:
            archive.extractall(provider_root)
        config_path = provider_root / "_extension_config.json"
        config = json.loads(config_path.read_text(encoding="utf-8"))
        config["timeout_seconds"] = 0.01
        config_path.write_text(json.dumps(config), encoding="utf-8")
        (provider_root / "process.py").write_text(
            "def process(payload, configuration, context):\n"
            "    while True:\n"
            "        pass\n",
            encoding="utf-8",
        )
        with ThreadPoolExecutor(max_workers=1) as executor:
            responses[provider] = executor.submit(
                _invoke_wrapper,
                provider_root,
                provider,
                envelope,
                expected_status=500,
            ).result(timeout=2)
    assert responses["aws"] == responses["azure"] == responses["gcp"]
    assert responses["aws"]["code"] == "PLATFORM_EXTENSION_TIMEOUT"
    assert responses["aws"]["retryable"] is False


def _binary_zip(files: dict[str, bytes]) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in files.items():
            archive.writestr(name, content)
    return output.getvalue()


def _validated_with_wheels(paths: list[Path]):
    requirements = "\n".join(
        (
            f"{path.name.split('-', 1)[0].replace('_', '-')}=="
            f"{path.name.split('-')[1]} --hash={runtime.digest_bytes(path.read_bytes())}"
        )
        for path in paths
    )
    return runtime.validate_source_archive(
        metadata=_metadata(),
        archive_bytes=_zip({**_files(), "requirements.lock": requirements + "\n"}),
        created_by="00000000-0000-4000-8000-000000000001",
    )


def _missing_required_variants(schema: dict, document: dict):
    def visit(current_schema, current_value, path):
        if not isinstance(current_schema, dict):
            return
        if isinstance(current_value, dict):
            for field in current_schema.get("required", []):
                if field in current_value:
                    variant = copy.deepcopy(document)
                    target = variant
                    for part in path:
                        target = target[part]
                    target.pop(field)
                    yield ".".join((*map(str, path), field)), variant
            for field, field_schema in current_schema.get("properties", {}).items():
                if field in current_value:
                    yield from visit(
                        field_schema,
                        current_value[field],
                        (*path, field),
                    )
        elif (
            isinstance(current_value, list)
            and current_value
            and isinstance(current_schema.get("items"), dict)
        ):
            yield from visit(
                current_schema["items"],
                current_value[0],
                (*path, 0),
            )

    yield from visit(schema, document, ())


def _symlink_zip() -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        link = zipfile.ZipInfo("process.py")
        link.create_system = 3
        link.external_attr = 0o120777 << 16
        archive.writestr(link, "target.py")
        archive.writestr("requirements.lock", "\n")
    return output.getvalue()


def _socket_zip() -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        special = zipfile.ZipInfo("process.py")
        special.create_system = 3
        special.external_attr = 0o140777 << 16
        archive.writestr(special, "def process(a, b, c): return {}\n")
        archive.writestr("requirements.lock", "\n")
    return output.getvalue()


def _invoke_wrapper(
    root: Path,
    provider: str,
    envelope: dict,
    *,
    expected_status: int = 200,
) -> dict:
    for name in (
        "process",
        "_platform_runtime",
        "lambda_function",
        "function_app",
        "main",
        "azure",
        "azure.functions",
    ):
        sys.modules.pop(name, None)
    sys.path.insert(0, str(root))
    try:
        if provider == "azure":
            _install_azure_stub()
        module_name = {
            "aws": "lambda_function",
            "azure": "function_app",
            "gcp": "main",
        }[provider]
        module = _load_module(module_name, root / f"{module_name}.py")
        if provider == "aws":
            return module.lambda_handler(envelope, None)
        request = SimpleNamespace(get_json=lambda: envelope)
        if provider == "gcp":
            body, status, _headers = module.main(request)
            assert status == expected_status
            return json.loads(body)
        response = module.main(request)
        assert response.status_code == expected_status
        return json.loads(response.body)
    finally:
        sys.path.remove(str(root))


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _install_azure_stub() -> None:
    functions = ModuleType("azure.functions")

    class FunctionApp:
        def route(self, **_kwargs):
            return lambda function: function

    class HttpResponse:
        def __init__(self, body, *, status_code, mimetype):
            self.body = body
            self.status_code = status_code
            self.mimetype = mimetype

    functions.FunctionApp = FunctionApp
    functions.HttpRequest = object
    functions.HttpResponse = HttpResponse
    functions.AuthLevel = SimpleNamespace(FUNCTION="function")
    azure = ModuleType("azure")
    azure.functions = functions
    sys.modules["azure"] = azure
    sys.modules["azure.functions"] = functions
