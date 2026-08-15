"""Deterministic provider packages for validated immutable extension artifacts."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from email.parser import Parser
from html.parser import HTMLParser
from io import BytesIO
import json
import logging
import os
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess  # nosec B404
import sys
import tempfile
import time
from typing import Callable
import zipfile

from packaging.requirements import InvalidRequirement, Requirement
from packaging.tags import sys_tags
from packaging.utils import (
    InvalidWheelFilename,
    canonicalize_name,
    parse_wheel_filename,
)
from urllib.error import HTTPError, URLError
from urllib.parse import quote, unquote, urljoin, urlsplit
from urllib.request import (
    HTTPRedirectHandler,
    ProxyHandler,
    Request,
    build_opener,
)

from src.core.deterministic_zip import atomic_write_bytes
from src.user_function_extensions.contracts import ExtensionContractError, runtime


ADAPTER_ROOT = Path(__file__).resolve().parent / "adapters"
logger = logging.getLogger(__name__)
BUILD_VERSION = "user-function-package-builder.v1"
BUILD_TIMEOUT_SECONDS = 120.0
MAX_SIMPLE_INDEX_BYTES = 4 * 1024 * 1024
MAX_BINDING_INDEX_BYTES = 2 * 1024 * 1024
MAX_EVIDENCE_INDEX_BYTES = 2 * 1024 * 1024
MAX_WHEELHOUSE_FILES = 256
MAX_DEPENDENCY_FILES = 1024
MAX_DEPENDENCY_FILE_BYTES = 2 * 1024 * 1024
MAX_DEPENDENCY_EXPANDED_BYTES = 20 * 1024 * 1024
PLATFORM_DEPENDENCIES = {
    "aws": (),
    "azure": ("azure-functions==1.23.0",),
    "gcp": ("functions-framework==3.8.3",),
}
PROVIDER_WRAPPERS = {
    "aws": ("aws/lambda_function.py", "lambda_function.py", "wrapper.aws.v1"),
    "azure": ("azure/function_app.py", "function_app.py", "wrapper.azure.v1"),
    "gcp": ("gcp/main.py", "main.py", "wrapper.gcp.v1"),
}
_WHEEL_NAME = re.compile(
    r"^(?P<name>[A-Za-z0-9_.]+)-(?P<version>[A-Za-z0-9_.!+]+)"
    r"(?:-[0-9][A-Za-z0-9_.]*)?-[^-]+-[^-]+-[^-]+\.whl$"
)
_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
_EVIDENCE_FIELDS = {
    "schema_version",
    "artifact_id",
    "artifact_digest",
    "slot_id",
    "slot_version",
    "runtime_id",
    "provider",
    "adapter_id",
    "adapter_version",
    "wrapper_version",
    "builder_version",
    "source_digest",
    "dependency_digest",
    "manifest_digest",
    "package_digest",
    "included_paths",
    "validation_policy_versions",
    "package_path",
}


@dataclass(frozen=True)
class PackageEvidence:
    schema_version: str
    artifact_id: str
    artifact_digest: str
    slot_id: str
    slot_version: str
    runtime_id: str
    provider: str
    adapter_id: str
    adapter_version: str
    wrapper_version: str
    builder_version: str
    source_digest: str
    dependency_digest: str
    manifest_digest: str
    package_digest: str
    included_paths: tuple[str, ...]
    validation_policy_versions: tuple[str, ...]


@dataclass(frozen=True)
class _BuildDeadline:
    expires_at: float
    clock: Callable[[], float]

    def remaining(self) -> float:
        return max(0.0, self.expires_at - self.clock())

    def check(self, field: str = "package") -> None:
        if self.remaining() <= 0:
            raise ExtensionContractError(
                "EXTENSION_BUILD_TIMEOUT",
                field,
                "Extension package construction exceeded its duration limit.",
            )


class _SimpleLinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[str] = []

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        if tag.lower() != "a":
            return
        href = next((value for key, value in attrs if key == "href"), None)
        if href:
            self.links.append(href)


class _RestrictedRedirectHandler(HTTPRedirectHandler):
    def __init__(self, allowed_hosts: frozenset[str]) -> None:
        super().__init__()
        self.allowed_hosts = allowed_hosts

    def redirect_request(
        self,
        request,
        file_pointer,
        code,
        message,
        headers,
        new_url,
    ):
        _require_approved_https_url(new_url, self.allowed_hosts)
        return super().redirect_request(
            request,
            file_pointer,
            code,
            message,
            headers,
            new_url,
        )


def build_provider_package(
    *,
    manifest: dict,
    files: dict[str, str],
    provider: str,
    wheelhouse: Path | None = None,
    build_timeout_seconds: float = BUILD_TIMEOUT_SECONDS,
    monotonic_clock: Callable[[], float] = time.monotonic,
) -> tuple[bytes, PackageEvidence]:
    """Build one provider package without executing or rewriting user source."""

    if build_timeout_seconds <= 0:
        raise ValueError("build_timeout_seconds must be positive")
    deadline = _BuildDeadline(
        expires_at=monotonic_clock() + build_timeout_seconds,
        clock=monotonic_clock,
    )
    deadline.check()
    provider = "gcp" if provider == "google" else provider
    if provider not in PROVIDER_WRAPPERS:
        raise ExtensionContractError(
            "EXTENSION_RUNTIME_UNSUPPORTED",
            "provider",
            "The provider adapter is unsupported.",
        )
    runtime.validate_artifact_manifest(manifest, files=files)
    deadline.check("manifest")
    slot = runtime.get_slot(manifest["slot_id"], manifest["slot_version"])
    adapter = next(
        (
            item
            for item in slot["runtime_contract"]["provider_adapters"]
            if item["provider"] == provider
        ),
        None,
    )
    if adapter is None:
        raise ExtensionContractError(
            "EXTENSION_RUNTIME_UNSUPPORTED",
            "provider",
            "The extension slot has no compatible provider adapter.",
        )
    package_files = dict(files)
    wrapper_source, wrapper_target, wrapper_version = PROVIDER_WRAPPERS[provider]
    package_files["_platform_runtime.py"] = (
        ADAPTER_ROOT / "runtime_support.py"
    ).read_text(encoding="utf-8")
    package_files[wrapper_target] = (ADAPTER_ROOT / wrapper_source).read_text(
        encoding="utf-8"
    )
    package_files["_extension_config.json"] = runtime.canonical_json(
        {
            "schema_version": "user-function-runtime-config.v1",
            "slot_id": manifest["slot_id"],
            "configuration": manifest["configuration"],
            "input_schema": slot["input_schema"],
            "output_schema": slot["output_schema"],
            "response_bytes": slot["resource_limits"]["response_bytes"],
            "timeout_seconds": slot["resource_limits"]["timeout_seconds"],
            "fallback_id": "00000000-0000-4000-8000-000000000000",
        }
    )
    package_files["_artifact_manifest.json"] = runtime.canonical_json(manifest)
    if PLATFORM_DEPENDENCIES[provider]:
        package_files["requirements.txt"] = (
            "\n".join(sorted(PLATFORM_DEPENDENCIES[provider])) + "\n"
        )
    wheel_files = _validated_wheels(manifest, wheelhouse, deadline=deadline)
    if set(package_files).intersection(wheel_files):
        raise ExtensionContractError(
            "EXTENSION_DEPENDENCY_FORBIDDEN",
            "wheelhouse",
            "A dependency wheel collides with extension or platform files.",
        )
    package_bytes = _package_zip(package_files, wheel_files)
    if len(package_bytes) > int(slot["resource_limits"]["artifact_bytes"]):
        raise ExtensionContractError(
            "EXTENSION_DEPENDENCY_FORBIDDEN",
            "package",
            "The provider package exceeds its size limit.",
        )
    deadline.check("package")
    second_build = _package_zip(package_files, wheel_files)
    if package_bytes != second_build:
        raise ExtensionContractError(
            "EXTENSION_PACKAGE_NONDETERMINISTIC",
            "package",
            "The provider package is not deterministic.",
        )
    included = tuple(sorted((*package_files.keys(), *wheel_files.keys())))
    evidence = PackageEvidence(
        schema_version="user-function-package-evidence.v1",
        artifact_id=manifest["artifact_id"],
        artifact_digest=manifest["artifact_digest"],
        slot_id=manifest["slot_id"],
        slot_version=manifest["slot_version"],
        runtime_id=manifest["runtime_id"],
        provider=provider,
        adapter_id=adapter["adapter_id"],
        adapter_version=adapter["adapter_version"],
        wrapper_version=wrapper_version,
        builder_version=BUILD_VERSION,
        source_digest=manifest["source"]["payload_digest"],
        dependency_digest=runtime.digest_json(manifest["dependencies"]),
        manifest_digest=runtime.digest_json(manifest),
        package_digest=runtime.digest_bytes(package_bytes),
        included_paths=included,
        validation_policy_versions=(
            runtime.VALIDATOR_VERSION,
            slot["dependency_policy_id"],
        ),
    )
    return package_bytes, evidence


def build_bound_extension_packages(
    project_path: Path,
    providers_config: dict,
    *,
    correlation_id: str | None = None,
) -> dict[str, Path]:
    """Validate every project binding and publish packages before Terraform."""

    root = project_path / ".twin2multicloud" / "extensions"
    index_path = root / "bindings.json"
    evidence_path = project_path / ".build" / "extensions" / "evidence.json"
    if not index_path.is_file():
        if evidence_path.exists() and not _contains_symlink(project_path, evidence_path):
            evidence_path.unlink()
        return {}
    try:
        index_path = _resolve_project_path(
            project_path,
            ".twin2multicloud/extensions/bindings.json",
        )
        index_bytes = _read_bounded_file(
            index_path,
            maximum_bytes=MAX_BINDING_INDEX_BYTES,
            field="bindings.json",
        )
    except ExtensionContractError:
        raise
    index = runtime.load_json_bytes(index_bytes, field="bindings.json")
    if index.get("schema_version") != "twin-extension-binding-index.v1":
        raise ExtensionContractError(
            "EXTENSION_VERSION_UNSUPPORTED",
            "bindings.schema_version",
            "The extension binding index version is unsupported.",
        )
    twin_id = index.get("twin_id")
    bindings = index.get("bindings")
    if (
        not runtime.safe_runtime_id(twin_id)
        or not isinstance(bindings, list)
        or len(bindings) > len(runtime.load_registry()["slots"])
    ):
        raise ExtensionContractError(
            "EXTENSION_BINDING_UNRESOLVED",
            "bindings",
            "The extension binding index is invalid.",
        )
    provider = providers_config.get("layer_2_provider")
    if provider not in {"aws", "azure", "gcp", "google"}:
        raise ExtensionContractError(
            "EXTENSION_RUNTIME_UNSUPPORTED",
            "layer_2_provider",
            "The L2 provider cannot execute extension packages.",
        )
    identities: set[tuple[str, str]] = set()
    packages: dict[str, Path] = {}
    evidence_items: list[dict] = []
    build_root = (
        project_path
        / ".build"
        / "extensions"
        / ("gcp" if provider == "google" else provider)
    )
    _prepare_generated_directory(project_path, build_root)
    for position, binding in enumerate(bindings):
        if not isinstance(binding, dict):
            _binding_error(position)
        required = {
            "slot_id",
            "slot_version",
            "artifact_id",
            "artifact_digest",
            "binding_digest",
            "manifest_path",
            "source_root",
        }
        if (
            set(binding) != required
            or not all(isinstance(binding[field], str) for field in required)
            or not runtime.safe_runtime_id(binding["slot_id"])
            or not re.fullmatch(r"[1-9][0-9]*", binding["slot_version"])
            or not runtime.safe_runtime_id(binding["artifact_id"])
            or _DIGEST.fullmatch(binding["artifact_digest"]) is None
            or _DIGEST.fullmatch(binding["binding_digest"]) is None
        ):
            _binding_error(position)
        identity = (binding["slot_id"], binding["slot_version"])
        if identity in identities:
            raise ExtensionContractError(
                "EXTENSION_BINDING_UNRESOLVED",
                f"bindings[{position}]",
                "The binding index contains a duplicate slot.",
            )
        identities.add(identity)
        expected_binding_digest = runtime.binding_digest(
            twin_id=twin_id,
            slot_id=binding["slot_id"],
            slot_version=binding["slot_version"],
            artifact_id=binding["artifact_id"],
            artifact_digest=binding["artifact_digest"],
        )
        if expected_binding_digest != binding["binding_digest"]:
            _binding_error(position)
        manifest_path = _resolve_project_path(project_path, binding["manifest_path"])
        source_root = _resolve_project_path(project_path, binding["source_root"])
        manifest_bytes = _read_bounded_file(
            manifest_path,
            maximum_bytes=runtime.MAX_JSON_BYTES,
            field=f"bindings[{position}].manifest",
        )
        manifest = runtime.load_json_bytes(
            manifest_bytes,
            field=f"bindings[{position}].manifest",
        )
        if (
            manifest["artifact_id"] != binding["artifact_id"]
            or manifest["artifact_digest"] != binding["artifact_digest"]
            or manifest["slot_id"] != binding["slot_id"]
            or manifest["slot_version"] != binding["slot_version"]
        ):
            _binding_error(position)
        files: dict[str, str] = {}
        for item in manifest["source"]["files"]:
            source_path = _resolve_source_path(
                source_root,
                item["relative_path"],
            )
            try:
                source_payload = _read_bounded_file(
                    source_path,
                    maximum_bytes=runtime.MAX_FILE_BYTES,
                    field=f"bindings[{position}].source",
                )
                files[item["relative_path"]] = source_payload.decode("utf-8")
            except (OSError, UnicodeDecodeError) as exc:
                raise ExtensionContractError(
                    "EXTENSION_BINDING_UNRESOLVED",
                    f"bindings[{position}].source",
                    "An extension source file is unavailable or invalid.",
                ) from exc
        try:
            package_bytes, evidence = build_provider_package(
                manifest=manifest,
                files=files,
                provider=provider,
                wheelhouse=(
                    _resolve_project_path(
                        project_path,
                        ".twin2multicloud/extensions/wheelhouse",
                    )
                    if (root / "wheelhouse").exists()
                    else root / "wheelhouse"
                ),
            )
        except ExtensionContractError as exc:
            logger.warning(
                "Validated extension package rejected",
                extra={
                    "operation_id": correlation_id,
                    "artifact_id": binding["artifact_id"],
                    "slot_id": binding["slot_id"],
                    "error_code": exc.code,
                    "error_field": exc.field,
                },
            )
            raise ExtensionContractError(
                exc.code,
                exc.field,
                exc.safe_message,
                correlation_id=correlation_id,
            ) from exc
        package_path = build_root / f"{manifest['artifact_id']}.zip"
        atomic_write_bytes(package_path, package_bytes)
        packages[f"extension:{manifest['slot_id']}"] = package_path
        evidence_item = asdict(evidence)
        evidence_item["package_path"] = package_path.relative_to(
            project_path
        ).as_posix()
        evidence_items.append(evidence_item)
        logger.info(
            "Validated extension package built",
            extra={
                "operation_id": correlation_id,
                "artifact_id": evidence.artifact_id,
                "slot_id": evidence.slot_id,
                "package_digest": evidence.package_digest,
                "provider": evidence.provider,
            },
        )
    evidence_payload = {
        "schema_version": "user-function-package-evidence-index.v1",
        "twin_id": twin_id,
        "correlation_id": (
            correlation_id
            if isinstance(correlation_id, str)
            and runtime.safe_runtime_id(correlation_id)
            else None
        ),
        "packages": sorted(evidence_items, key=lambda item: item["slot_id"]),
    }
    _prepare_generated_directory(project_path, evidence_path.parent)
    atomic_write_bytes(
        evidence_path,
        (json.dumps(evidence_payload, indent=2, sort_keys=True) + "\n").encode("utf-8"),
    )
    return packages


def load_package_evidence(project_path: Path) -> list[dict]:
    path = project_path / ".build" / "extensions" / "evidence.json"
    if not path.is_file():
        return []
    path = _resolve_project_path(
        project_path,
        ".build/extensions/evidence.json",
    )
    document = runtime.load_json_bytes(
        _read_bounded_file(
            path,
            maximum_bytes=MAX_EVIDENCE_INDEX_BYTES,
            field="extension evidence",
        ),
        field="extension evidence",
    )
    if document.get("schema_version") != "user-function-package-evidence-index.v1":
        raise ExtensionContractError(
            "EXTENSION_VERSION_UNSUPPORTED",
            "extension evidence",
            "The extension package evidence version is unsupported.",
        )
    if set(document) != {
        "schema_version",
        "twin_id",
        "correlation_id",
        "packages",
    }:
        raise ExtensionContractError(
            "EXTENSION_SCHEMA_INVALID",
            "extension evidence",
            "The extension package evidence fields are invalid.",
        )
    if not runtime.safe_runtime_id(document["twin_id"]):
        raise ExtensionContractError(
            "EXTENSION_SCHEMA_INVALID",
            "extension evidence.twin_id",
            "The extension package Twin identity is invalid.",
        )
    if document["correlation_id"] is not None and not runtime.safe_runtime_id(
        document["correlation_id"]
    ):
        raise ExtensionContractError(
            "EXTENSION_SCHEMA_INVALID",
            "extension evidence.correlation_id",
            "The extension package correlation identity is invalid.",
        )
    packages = document.get("packages")
    if not isinstance(packages, list):
        raise ExtensionContractError(
            "EXTENSION_SCHEMA_INVALID",
            "extension evidence",
            "The extension package evidence is invalid.",
        )
    identities: set[tuple[str, str]] = set()
    for position, item in enumerate(packages):
        if not isinstance(item, dict) or set(item) != _EVIDENCE_FIELDS:
            raise ExtensionContractError(
                "EXTENSION_SCHEMA_INVALID",
                f"extension evidence.packages[{position}]",
                "An extension package evidence item is invalid.",
            )
        string_fields = _EVIDENCE_FIELDS - {
            "included_paths",
            "validation_policy_versions",
        }
        if not all(isinstance(item[field], str) for field in string_fields):
            raise ExtensionContractError(
                "EXTENSION_SCHEMA_INVALID",
                f"extension evidence.packages[{position}]",
                "An extension package evidence item is invalid.",
            )
        for field in (
            "artifact_digest",
            "source_digest",
            "dependency_digest",
            "manifest_digest",
            "package_digest",
        ):
            if _DIGEST.fullmatch(item[field]) is None:
                raise ExtensionContractError(
                    "EXTENSION_SCHEMA_INVALID",
                    f"extension evidence.packages[{position}].{field}",
                    "An extension package evidence digest is invalid.",
                )
        for field in ("included_paths", "validation_policy_versions"):
            values = item[field]
            if (
                not isinstance(values, list)
                or not values
                or not all(isinstance(value, str) and value for value in values)
            ):
                raise ExtensionContractError(
                    "EXTENSION_SCHEMA_INVALID",
                    f"extension evidence.packages[{position}].{field}",
                    "An extension package evidence list is invalid.",
                )
        if not all(
            runtime.safe_runtime_id(value)
            for value in item["validation_policy_versions"]
        ):
            raise ExtensionContractError(
                "EXTENSION_SCHEMA_INVALID",
                (f"extension evidence.packages[{position}].validation_policy_versions"),
                "An extension package evidence policy identity is invalid.",
            )
        if (
            item["schema_version"] != "user-function-package-evidence.v1"
            or item["provider"] not in {"aws", "azure", "gcp"}
            or not all(
                runtime.safe_runtime_id(item[field])
                for field in (
                    "artifact_id",
                    "slot_id",
                    "runtime_id",
                    "adapter_id",
                    "adapter_version",
                    "wrapper_version",
                    "builder_version",
                )
            )
            or re.fullmatch(r"[1-9][0-9]*", item["slot_version"]) is None
        ):
            raise ExtensionContractError(
                "EXTENSION_SCHEMA_INVALID",
                f"extension evidence.packages[{position}]",
                "An extension package evidence identity is invalid.",
            )
        identity = (item["slot_id"], item["slot_version"])
        if identity in identities:
            raise ExtensionContractError(
                "EXTENSION_SCHEMA_INVALID",
                f"extension evidence.packages[{position}]",
                "The extension package evidence contains a duplicate slot.",
            )
        identities.add(identity)
        for included_path in item["included_paths"]:
            included = PurePosixPath(included_path)
            if (
                included.is_absolute()
                or ".." in included.parts
                or any(part in {"", "."} for part in included.parts)
            ):
                raise ExtensionContractError(
                    "EXTENSION_SCHEMA_INVALID",
                    f"extension evidence.packages[{position}].included_paths",
                    "An extension package evidence path is invalid.",
                )
        path = PurePosixPath(item["package_path"])
        if (
            path.is_absolute()
            or ".." in path.parts
            or any(part in {"", "."} for part in path.parts)
        ):
            raise ExtensionContractError(
                "EXTENSION_SCHEMA_INVALID",
                f"extension evidence.packages[{position}].package_path",
                "An extension package evidence path is invalid.",
            )
    return packages


def _validated_wheels(
    manifest: dict,
    wheelhouse: Path | None,
    *,
    deadline: _BuildDeadline,
) -> dict[str, bytes]:
    dependencies = manifest["dependencies"]
    if not dependencies:
        return {}
    if wheelhouse is not None and wheelhouse.exists():
        return _validated_wheels_from_directory(
            manifest,
            wheelhouse,
            deadline=deadline,
        )

    policy_id = runtime.get_slot(
        manifest["slot_id"],
        manifest["slot_version"],
    )["dependency_policy_id"]
    policy = next(
        (
            item
            for item in runtime.load_registry()["dependency_policies"]
            if item["policy_id"] == policy_id
        ),
        None,
    )
    if policy is None or policy.get("index_url") != "https://pypi.org/simple":
        raise ExtensionContractError(
            "EXTENSION_DEPENDENCY_FORBIDDEN",
            "dependency_policy",
            "The dependency download policy is unresolved.",
        )
    deadline.check("dependencies")
    with tempfile.TemporaryDirectory(prefix="extension-wheels-") as temporary:
        downloaded = Path(temporary)
        _download_locked_wheels(
            manifest,
            downloaded,
            policy=policy,
            deadline=deadline,
        )
        return _validated_wheels_from_directory(
            manifest,
            downloaded,
            deadline=deadline,
        )


def _validated_wheels_from_directory(
    manifest: dict,
    wheelhouse: Path,
    *,
    deadline: _BuildDeadline,
) -> dict[str, bytes]:
    dependencies = manifest["dependencies"]
    if not wheelhouse.is_dir() or wheelhouse.is_symlink():
        raise ExtensionContractError(
            "EXTENSION_DEPENDENCY_FORBIDDEN",
            "wheelhouse",
            "Validated dependency wheels are unavailable.",
        )
    result: dict[str, bytes] = {}
    selected: list[Path] = []
    wheel_paths = sorted(wheelhouse.glob("*.whl"))
    if len(wheel_paths) > MAX_WHEELHOUSE_FILES:
        raise ExtensionContractError(
            "EXTENSION_DEPENDENCY_FORBIDDEN",
            "wheelhouse",
            "The dependency wheelhouse contains too many files.",
        )
    for path in wheel_paths:
        try:
            unsafe = (
                not path.is_file()
                or path.is_symlink()
                or path.stat().st_size > runtime.MAX_ARCHIVE_BYTES
            )
        except OSError as exc:
            raise ExtensionContractError(
                "EXTENSION_DEPENDENCY_FORBIDDEN",
                "wheelhouse",
                "A dependency wheel path or size is unsafe.",
            ) from exc
        if unsafe:
            raise ExtensionContractError(
                "EXTENSION_DEPENDENCY_FORBIDDEN",
                "wheelhouse",
                "A dependency wheel path or size is unsafe.",
            )
    for dependency in dependencies:
        deadline.check("wheelhouse")
        candidates = []
        for path in wheel_paths:
            match = _WHEEL_NAME.fullmatch(path.name)
            if match is None:
                continue
            normalized = re.sub(r"[-_.]+", "-", match.group("name")).lower()
            version = match.group("version").replace("_", "-")
            if normalized == dependency["name"] and version == dependency["version"]:
                candidates.append(path)
        valid = [
            path
            for path in candidates
            if runtime.digest_bytes(path.read_bytes()) in dependency["hashes"]
        ]
        if len(valid) != 1:
            raise ExtensionContractError(
                "EXTENSION_DEPENDENCY_FORBIDDEN",
                f"dependency.{dependency['name']}",
                "Exactly one validated dependency wheel is required.",
            )
        selected.append(valid[0])
    _verify_transitive_dependencies(selected, manifest)
    for path in selected:
        deadline.check("wheelhouse")
        _extract_wheel(path, result)
    return result


def _download_locked_wheels(
    manifest: dict,
    destination: Path,
    *,
    policy: dict,
    deadline: _BuildDeadline,
) -> None:
    prefetched = destination / "prefetched"
    prefetched.mkdir()
    _prefetch_locked_wheels(
        manifest,
        prefetched,
        policy=policy,
        deadline=deadline,
    )
    requirements_path = destination / "requirements.lock"
    requirements_path.write_text(
        "\n".join(_locked_requirement(item) for item in manifest["dependencies"])
        + "\n",
        encoding="utf-8",
    )
    environment = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith("PIP_") and key != "PYTHONPATH"
    }
    environment.update(
        {
            "PIP_CONFIG_FILE": os.devnull,
            "PIP_DISABLE_PIP_VERSION_CHECK": "1",
            "PIP_NO_INPUT": "1",
        }
    )
    command = [
        sys.executable,
        "-m",
        "pip",
        "download",
        "--require-hashes",
        "--only-binary=:all:",
        "--no-deps",
        "--no-index",
        "--find-links",
        str(prefetched),
        "--dest",
        str(destination),
        "--requirement",
        str(requirements_path),
    ]
    try:
        result = subprocess.run(  # nosec B603
            command,
            check=False,
            capture_output=True,
            env=environment,
            timeout=deadline.remaining(),
        )
    except subprocess.TimeoutExpired as exc:
        raise ExtensionContractError(
            "EXTENSION_BUILD_TIMEOUT",
            "dependencies",
            "Dependency download exceeded its duration limit.",
        ) from exc
    if result.returncode != 0:
        raise ExtensionContractError(
            "EXTENSION_DEPENDENCY_FORBIDDEN",
            "dependencies",
            "Locked binary dependencies could not be resolved.",
        )
    requirements_path.unlink(missing_ok=True)
    deadline.check("dependencies")


def _prefetch_locked_wheels(
    manifest: dict,
    destination: Path,
    *,
    policy: dict,
    deadline: _BuildDeadline,
) -> None:
    redirect_hosts = policy.get("allowed_redirect_hosts")
    if (
        not isinstance(redirect_hosts, list)
        or not redirect_hosts
        or not all(
            isinstance(host, str)
            and host
            and host == host.lower()
            and "/" not in host
            and "@" not in host
            for host in redirect_hosts
        )
    ):
        raise ExtensionContractError(
            "EXTENSION_DEPENDENCY_FORBIDDEN",
            "dependency_policy",
            "The dependency redirect policy is unresolved.",
        )
    index_parts = urlsplit(policy["index_url"])
    if (
        index_parts.scheme != "https"
        or index_parts.hostname != "pypi.org"
        or index_parts.username is not None
        or index_parts.password is not None
    ):
        raise ExtensionContractError(
            "EXTENSION_DEPENDENCY_FORBIDDEN",
            "dependency_policy",
            "The dependency index policy is invalid.",
        )
    allowed_hosts = frozenset({index_parts.hostname, *redirect_hosts})
    compatible_tags = frozenset(sys_tags())
    for dependency in manifest["dependencies"]:
        deadline.check("dependencies")
        index_url = (
            f"{policy['index_url'].rstrip('/')}/{quote(dependency['name'], safe='')}/"
        )
        index_payload = _read_approved_https(
            index_url,
            allowed_hosts=allowed_hosts,
            deadline=deadline,
            maximum_bytes=MAX_SIMPLE_INDEX_BYTES,
        )
        try:
            index_text = index_payload.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ExtensionContractError(
                "EXTENSION_DEPENDENCY_FORBIDDEN",
                f"dependency.{dependency['name']}",
                "The dependency index response is invalid.",
            ) from exc
        parser = _SimpleLinkParser()
        parser.feed(index_text)
        candidates: list[tuple[str, str]] = []
        for href in parser.links:
            absolute = urljoin(index_url, href)
            _require_approved_https_url(absolute, allowed_hosts)
            parsed = urlsplit(absolute)
            filename = unquote(PurePosixPath(parsed.path).name)
            try:
                wheel_name, wheel_version, _build, wheel_tags = parse_wheel_filename(
                    filename
                )
            except InvalidWheelFilename:
                continue
            fragment = parsed.fragment
            if not fragment.startswith("sha256="):
                continue
            digest = f"sha256:{fragment.removeprefix('sha256=')}"
            if (
                canonicalize_name(str(wheel_name)) == dependency["name"]
                and str(wheel_version) == dependency["version"]
                and digest in dependency["hashes"]
                and any(tag in compatible_tags for tag in wheel_tags)
                and all(tag.platform == "any" for tag in wheel_tags)
            ):
                candidates.append((filename, absolute))
        if len(candidates) != 1:
            raise ExtensionContractError(
                "EXTENSION_DEPENDENCY_FORBIDDEN",
                f"dependency.{dependency['name']}",
                "Exactly one approved pure-Python dependency wheel is required.",
            )
        filename, wheel_url = candidates[0]
        wheel_payload = _read_approved_https(
            wheel_url,
            allowed_hosts=allowed_hosts,
            deadline=deadline,
            maximum_bytes=runtime.MAX_ARCHIVE_BYTES,
        )
        if runtime.digest_bytes(wheel_payload) not in dependency["hashes"]:
            raise ExtensionContractError(
                "EXTENSION_DEPENDENCY_FORBIDDEN",
                f"dependency.{dependency['name']}",
                "The dependency wheel digest is invalid.",
            )
        (destination / filename).write_bytes(wheel_payload)


def _read_approved_https(
    url: str,
    *,
    allowed_hosts: frozenset[str],
    deadline: _BuildDeadline,
    maximum_bytes: int,
) -> bytes:
    _require_approved_https_url(url, allowed_hosts)
    opener = build_opener(
        ProxyHandler({}),
        _RestrictedRedirectHandler(allowed_hosts),
    )
    request = Request(
        url,
        headers={"User-Agent": f"Twin2MultiCloud/{BUILD_VERSION}"},
    )
    try:
        with opener.open(request, timeout=deadline.remaining()) as response:
            _require_approved_https_url(response.geturl(), allowed_hosts)
            payload = response.read(maximum_bytes + 1)
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        raise ExtensionContractError(
            "EXTENSION_DEPENDENCY_FORBIDDEN",
            "dependencies",
            "An approved dependency resource could not be retrieved.",
        ) from exc
    if len(payload) > maximum_bytes:
        raise ExtensionContractError(
            "EXTENSION_DEPENDENCY_FORBIDDEN",
            "dependencies",
            "An approved dependency resource exceeds its size limit.",
        )
    deadline.check("dependencies")
    return payload


def _require_approved_https_url(
    url: str,
    allowed_hosts: frozenset[str],
) -> None:
    parsed = urlsplit(url)
    try:
        port = parsed.port
    except ValueError as exc:
        raise ExtensionContractError(
            "EXTENSION_DEPENDENCY_FORBIDDEN",
            "dependencies",
            "A dependency URL is outside the approved HTTPS hosts.",
        ) from exc
    if (
        parsed.scheme != "https"
        or parsed.hostname not in allowed_hosts
        or parsed.username is not None
        or parsed.password is not None
        or port not in {None, 443}
        or bool(parsed.query)
    ):
        raise ExtensionContractError(
            "EXTENSION_DEPENDENCY_FORBIDDEN",
            "dependencies",
            "A dependency URL is outside the approved HTTPS hosts.",
        )


def _verify_transitive_dependencies(paths: list[Path], manifest: dict) -> None:
    locked = {item["name"]: item["version"] for item in manifest["dependencies"]}
    for path in paths:
        try:
            with zipfile.ZipFile(path) as archive:
                metadata_names = sorted(
                    name
                    for name in archive.namelist()
                    if name.endswith(".dist-info/METADATA")
                )
                if len(metadata_names) != 1:
                    raise ValueError("wheel metadata is ambiguous")
                metadata_info = archive.getinfo(metadata_names[0])
                if metadata_info.file_size > MAX_DEPENDENCY_FILE_BYTES:
                    raise ValueError("wheel metadata is oversized")
                message = Parser().parsestr(archive.read(metadata_info).decode("utf-8"))
        except (KeyError, UnicodeDecodeError, ValueError, zipfile.BadZipFile) as exc:
            raise ExtensionContractError(
                "EXTENSION_DEPENDENCY_FORBIDDEN",
                "wheelhouse",
                "A dependency wheel has invalid package metadata.",
            ) from exc
        for raw_requirement in message.get_all("Requires-Dist", []):
            try:
                requirement = Requirement(raw_requirement)
            except InvalidRequirement as exc:
                raise ExtensionContractError(
                    "EXTENSION_DEPENDENCY_FORBIDDEN",
                    "wheelhouse",
                    "A dependency wheel has an invalid transitive requirement.",
                ) from exc
            if requirement.marker is not None and not requirement.marker.evaluate():
                continue
            name = canonicalize_name(requirement.name)
            version = locked.get(name)
            if (
                requirement.url is not None
                or version is None
                or (
                    requirement.specifier
                    and not requirement.specifier.contains(
                        version,
                        prereleases=True,
                    )
                )
            ):
                raise ExtensionContractError(
                    "EXTENSION_DEPENDENCY_FORBIDDEN",
                    f"dependency.{name}",
                    "The complete transitive dependency set must be locked.",
                )


def _extract_wheel(path: Path, destination: dict[str, bytes]) -> None:
    try:
        archive = zipfile.ZipFile(path)
    except zipfile.BadZipFile as exc:
        raise ExtensionContractError(
            "EXTENSION_DEPENDENCY_FORBIDDEN",
            "wheelhouse",
            "A dependency wheel is invalid.",
        ) from exc
    expanded_bytes = sum(len(value) for value in destination.values())
    with archive:
        for info in archive.infolist():
            pure = PurePosixPath(info.filename)
            if info.is_dir():
                continue
            mode = info.external_attr >> 16
            file_type = stat.S_IFMT(mode)
            if (
                pure.is_absolute()
                or ".." in pure.parts
                or any(part in {"", "."} or part.startswith(".") for part in pure.parts)
                or len(pure.parts) > runtime.MAX_PATH_DEPTH
                or file_type not in {0, stat.S_IFREG}
                or bool(mode & 0o111)
            ):
                raise ExtensionContractError(
                    "EXTENSION_DEPENDENCY_FORBIDDEN",
                    "wheelhouse",
                    "A dependency wheel contains an unsafe path.",
                )
            if (
                info.file_size > MAX_DEPENDENCY_FILE_BYTES
                or len(destination) >= MAX_DEPENDENCY_FILES
                or expanded_bytes + info.file_size > MAX_DEPENDENCY_EXPANDED_BYTES
            ):
                raise ExtensionContractError(
                    "EXTENSION_DEPENDENCY_FORBIDDEN",
                    "wheelhouse",
                    "Dependency wheel contents exceed package safety limits.",
                )
            payload = archive.read(info)
            expanded_bytes += len(payload)
            if pure.suffix.lower() in {
                ".so",
                ".dll",
                ".dylib",
                ".exe",
                ".pyc",
                ".pyo",
            } or _has_executable_binary_magic(payload):
                raise ExtensionContractError(
                    "EXTENSION_DEPENDENCY_FORBIDDEN",
                    "wheelhouse",
                    "Native dependency binaries are unsupported in v1.",
                )
            target = pure.as_posix()
            if target in {"requirements.txt", "_platform_runtime.py"}:
                raise ExtensionContractError(
                    "EXTENSION_DEPENDENCY_FORBIDDEN",
                    "wheelhouse",
                    "A dependency wheel collides with platform package files.",
                )
            if target in destination:
                raise ExtensionContractError(
                    "EXTENSION_DEPENDENCY_FORBIDDEN",
                    "wheelhouse",
                    "Dependency wheel files collide.",
                )
            destination[target] = payload


def _has_executable_binary_magic(payload: bytes) -> bool:
    return payload.startswith(
        (
            b"\x7fELF",
            b"MZ",
            b"\xca\xfe\xba\xbe",
            b"\xce\xfa\xed\xfe",
            b"\xcf\xfa\xed\xfe",
            b"\xfe\xed\xfa\xce",
            b"\xfe\xed\xfa\xcf",
        )
    )


def _locked_requirement(dependency: dict) -> str:
    hashes = " ".join(f"--hash={value}" for value in sorted(dependency["hashes"]))
    return f"{dependency['name']}=={dependency['version']} {hashes}"


def _package_zip(text_files: dict[str, str], binary_files: dict[str, bytes]) -> bytes:
    output = BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted((*text_files.keys(), *binary_files.keys())):
            info = zipfile.ZipInfo(path, date_time=runtime.PACKAGE_TIMESTAMP)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            payload = (
                text_files[path].encode("utf-8")
                if path in text_files
                else binary_files[path]
            )
            archive.writestr(info, payload)
    return output.getvalue()


def _resolve_project_path(project_path: Path, value: object) -> Path:
    if not isinstance(value, str):
        _binding_error(0)
    candidate = project_path / value
    try:
        candidate.resolve().relative_to(project_path.resolve())
    except (OSError, ValueError) as exc:
        raise ExtensionContractError(
            "EXTENSION_BINDING_UNRESOLVED",
            "binding.path",
            "An extension binding path escaped the project boundary.",
        ) from exc
    if not candidate.is_file() and not candidate.is_dir():
        raise ExtensionContractError(
            "EXTENSION_BINDING_UNRESOLVED",
            "binding.path",
            "An extension binding path is missing.",
        )
    if _contains_symlink(project_path, candidate):
        raise ExtensionContractError(
            "EXTENSION_BINDING_UNRESOLVED",
            "binding.path",
            "Symbolic extension binding paths are forbidden.",
        )
    return candidate


def _resolve_source_path(source_root: Path, relative: str) -> Path:
    candidate = source_root / relative
    try:
        candidate.resolve().relative_to(source_root.resolve())
    except (OSError, ValueError) as exc:
        raise ExtensionContractError(
            "EXTENSION_BINDING_UNRESOLVED",
            "source",
            "An extension source path escaped its artifact root.",
        ) from exc
    if not candidate.is_file() or _contains_symlink(source_root, candidate):
        raise ExtensionContractError(
            "EXTENSION_BINDING_UNRESOLVED",
            "source",
            "An extension source file is unavailable.",
        )
    return candidate


def _read_bounded_file(
    path: Path,
    *,
    maximum_bytes: int,
    field: str,
) -> bytes:
    try:
        if path.is_symlink() or not path.is_file() or path.stat().st_size > maximum_bytes:
            raise OSError("unsafe or oversized file")
        with path.open("rb") as handle:
            payload = handle.read(maximum_bytes + 1)
    except OSError as exc:
        raise ExtensionContractError(
            "EXTENSION_BINDING_UNRESOLVED",
            field,
            "A required extension file is unavailable or exceeds its size limit.",
        ) from exc
    if len(payload) > maximum_bytes:
        raise ExtensionContractError(
            "EXTENSION_BINDING_UNRESOLVED",
            field,
            "A required extension file is unavailable or exceeds its size limit.",
        )
    return payload


def _prepare_generated_directory(project_path: Path, directory: Path) -> None:
    if _contains_symlink(project_path, directory):
        raise ExtensionContractError(
            "EXTENSION_BINDING_UNRESOLVED",
            "build.path",
            "Symbolic generated extension paths are forbidden.",
        )
    try:
        directory.mkdir(parents=True, exist_ok=True)
        directory.resolve().relative_to(project_path.resolve())
    except (OSError, ValueError) as exc:
        raise ExtensionContractError(
            "EXTENSION_BINDING_UNRESOLVED",
            "build.path",
            "The generated extension path escaped the project boundary.",
        ) from exc
    if _contains_symlink(project_path, directory):
        raise ExtensionContractError(
            "EXTENSION_BINDING_UNRESOLVED",
            "build.path",
            "Symbolic generated extension paths are forbidden.",
        )


def _contains_symlink(root: Path, candidate: Path) -> bool:
    try:
        relative = candidate.relative_to(root)
    except ValueError:
        return True
    current = root
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            return True
    return False


def _binding_error(position: int) -> None:
    raise ExtensionContractError(
        "EXTENSION_BINDING_UNRESOLVED",
        f"bindings[{position}]",
        "An extension binding is unresolved or incompatible.",
    )
