"""Provider-neutral validation and canonicalization for user-function v1."""

from __future__ import annotations

import ast
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
from io import BytesIO
import json
from pathlib import Path, PurePosixPath
import re
import signal
import stat
import sys
import threading
import time
from types import MappingProxyType
from typing import Any, Callable, Mapping
import unicodedata
import uuid
import zipfile

from jsonschema import Draft202012Validator, FormatChecker


CONTRACT_VERSION = "user-function-artifact.v1"
SLOT_VERSION = "user-function-extension-slot.v1"
ENVELOPE_VERSION = "user-function-runtime-envelope.v1"
REGISTRY_VERSION = "user-function-extension-registry.v1"
VALIDATOR_VERSION = "user-function-validator.v1"
RUNTIME_ID = "python311"
MAX_ARCHIVE_BYTES = 10 * 1024 * 1024
MAX_EXPANDED_BYTES = 20 * 1024 * 1024
MAX_FILE_BYTES = 2 * 1024 * 1024
MAX_SOURCE_BYTES = 2 * 1024 * 1024
MAX_FILE_COUNT = 64
MAX_PATH_DEPTH = 8
MAX_DEPENDENCIES = 64
MAX_JSON_BYTES = 2 * 1024 * 1024
MAX_JSON_DEPTH = 32
VALIDATION_TIMEOUT_SECONDS = 5.0
PACKAGE_TIMESTAMP = (1980, 1, 1, 0, 0, 0)
ERROR_CODES = frozenset(
    {
        "EXTENSION_ARCHIVE_UNSAFE",
        "EXTENSION_SCHEMA_INVALID",
        "EXTENSION_VERSION_UNSUPPORTED",
        "EXTENSION_ENTRYPOINT_INVALID",
        "EXTENSION_DEPENDENCY_UNPINNED",
        "EXTENSION_DEPENDENCY_FORBIDDEN",
        "EXTENSION_SECRET_MATERIAL_DETECTED",
        "EXTENSION_CONFIG_INVALID",
        "EXTENSION_RUNTIME_UNSUPPORTED",
        "EXTENSION_CAPABILITY_UNAUTHORIZED",
        "EXTENSION_BINDING_UNRESOLVED",
        "EXTENSION_PACKAGE_NONDETERMINISTIC",
        "EXTENSION_VALIDATION_TIMEOUT",
        "EXTENSION_BUILD_TIMEOUT",
    }
)
VALIDATION_CHECKS = (
    "archive_safe",
    "schema_valid",
    "entrypoint_valid",
    "dependencies_valid",
    "secret_scan_passed",
    "configuration_valid",
    "runtime_compatible",
    "capabilities_authorized",
    "package_deterministic",
    "binding_compatible",
)
_STABLE_ID = re.compile(r"^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*$")
_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
_SAFE_RUNTIME_ID = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
_LOCK_LINE = re.compile(
    r"^(?P<name>[A-Za-z0-9][A-Za-z0-9._-]{0,127})"
    r"==(?P<version>[0-9][A-Za-z0-9._-]{0,63})"
    r"(?P<hashes>(?:[ \t]+--hash=sha256:[0-9a-f]{64})+)$"
)
_HASH_OPTION = re.compile(r"--hash=(sha256:[0-9a-f]{64})")
_SECRET_KEY = re.compile(
    r"(?:^|[_-])(?:secret|password|passwd|token|credential|private[_-]?key|"
    r"access[_-]?key|api[_-]?key|client[_-]?secret|connection[_-]?string)(?:$|[_-])",
    re.IGNORECASE,
)
_SECRET_VALUE = (
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\bASIA[0-9A-Z]{16}\b"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{24,}\b"),
    re.compile(r"\beyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{10,}\."),
    re.compile(r"(?i)\bsecret://[A-Za-z0-9._~:/?#\[\]@!$&'()*+,;=%-]+"),
    re.compile(r"(?i)\barn:aws:secretsmanager:[A-Za-z0-9_:/+=.@-]+"),
    re.compile(r"(?i)\bhttps://[A-Za-z0-9.-]+\.vault\.azure\.net/secrets/"),
    re.compile(r"(?i)\bprojects/[A-Za-z0-9._-]+/(?:locations/[^/]+/)?secrets/"),
    re.compile(r"(?i)\b(?:password|token|secret|api[_-]?key)\s*[:=]\s*['\"][^'\"]{4,}"),
)
_FORBIDDEN_DEPENDENCIES = frozenset(
    {"awscli", "azure-cli", "google-cloud-sdk", "pip", "setuptools"}
)
_FORBIDDEN_IMPORT_PREFIXES = (
    "boto3",
    "botocore",
    "azure",
    "google.cloud",
    "google.auth",
    "terraform",
)
_FORBIDDEN_IMPORTS = frozenset(
    {
        "ctypes",
        "importlib",
        "multiprocessing",
        "os",
        "pathlib",
        "socket",
        "subprocess",
        "sys",
    }
)
_FORBIDDEN_CALLS = frozenset(
    {"eval", "exec", "open", "compile", "__import__", "input"}
)


class ExtensionContractError(ValueError):
    """Stable, redacted validation failure safe for API boundaries."""

    def __init__(
        self,
        code: str,
        field: str,
        message: str,
        *,
        correlation_id: str | None = None,
    ) -> None:
        if code not in ERROR_CODES:
            raise RuntimeError("Unknown extension error code")
        self.code = code
        self.field = _safe_field(field)
        self.safe_message = _safe_message(message)
        self.correlation_id = (
            correlation_id if correlation_id and _SAFE_RUNTIME_ID.fullmatch(correlation_id) else None
        )
        super().__init__(self.safe_message)

    def as_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "error_code": self.code,
            "field": self.field,
            "message": self.safe_message,
        }
        if self.correlation_id:
            payload["correlation_id"] = self.correlation_id
        return payload


@dataclass(frozen=True)
class ValidatedArtifact:
    """Immutable validation result used by persistence and packaging."""

    manifest: Mapping[str, Any]
    files: Mapping[str, str]


@dataclass(frozen=True)
class ValidationDeadline:
    """Monotonic validation budget independent of wall-clock changes."""

    expires_at: float
    clock: Callable[[], float]

    def check(self, field: str = "validation") -> None:
        if self.clock() >= self.expires_at:
            raise ExtensionContractError(
                "EXTENSION_VALIDATION_TIMEOUT",
                field,
                "Extension validation exceeded its duration limit.",
            )


def contract_root() -> Path:
    return Path(__file__).resolve().parent


def load_registry() -> dict[str, Any]:
    registry = _load_json_file(contract_root() / "registry.json")
    if registry.get("schema_version") != REGISTRY_VERSION:
        raise ExtensionContractError(
            "EXTENSION_VERSION_UNSUPPORTED",
            "registry.schema_version",
            "The extension registry version is unsupported.",
        )
    if set(registry) != {
        "schema_version",
        "registry_version",
        "runtime",
        "dependency_policies",
        "provider_adapters",
        "error_codes",
        "slots",
    } or registry["registry_version"] != "1":
        raise ExtensionContractError(
            "EXTENSION_SCHEMA_INVALID",
            "registry",
            "The extension registry fields are invalid.",
        )
    expected_provider_runtime = {
        "aws": "python3.11",
        "azure": "3.11",
        "gcp": "python311",
    }
    if registry["runtime"] != {
        "runtime_id": RUNTIME_ID,
        "language": "python",
        "language_version": "3.11",
        "provider_values": expected_provider_runtime,
    }:
        raise ExtensionContractError(
            "EXTENSION_RUNTIME_UNSUPPORTED",
            "registry.runtime",
            "The extension runtime registry is incompatible.",
        )
    if (
        not isinstance(registry["error_codes"], list)
        or not all(
            isinstance(code, str) for code in registry["error_codes"]
        )
        or len(registry["error_codes"]) != len(ERROR_CODES)
        or set(registry["error_codes"]) != ERROR_CODES
    ):
        raise ExtensionContractError(
            "EXTENSION_SCHEMA_INVALID",
            "registry.error_codes",
            "The extension error registry is inconsistent.",
        )
    policies = registry["dependency_policies"]
    if not isinstance(policies, list) or len(policies) != 1:
        raise ExtensionContractError(
            "EXTENSION_SCHEMA_INVALID",
            "registry.dependency_policies",
            "The extension dependency policy registry is invalid.",
        )
    policy = policies[0]
    if (
        not isinstance(policy, dict)
        or set(policy) != {
            "policy_id",
            "index_url",
            "allowed_redirect_hosts",
            "forbidden_packages",
            "wheel_only",
            "hashes_required",
        }
        or policy["policy_id"] != "dependency-policy.python311.v1"
        or policy["index_url"] != "https://pypi.org/simple"
        or not isinstance(policy["allowed_redirect_hosts"], list)
        or policy["allowed_redirect_hosts"] != ["files.pythonhosted.org"]
        or not isinstance(policy["forbidden_packages"], list)
        or not all(
            isinstance(name, str)
            for name in policy["forbidden_packages"]
        )
        or set(policy["forbidden_packages"]) != _FORBIDDEN_DEPENDENCIES
        or len(policy["forbidden_packages"]) != len(_FORBIDDEN_DEPENDENCIES)
        or policy["wheel_only"] is not True
        or policy["hashes_required"] is not True
    ):
        raise ExtensionContractError(
            "EXTENSION_DEPENDENCY_FORBIDDEN",
            "registry.dependency_policies",
            "The extension dependency policy registry is inconsistent.",
        )
    adapters = registry["provider_adapters"]
    expected_adapters = {
        "aws": {
            "adapter_id": "adapter.aws.python311",
            "adapter_version": "1",
            "provider": "aws",
            "handler": "lambda_function.lambda_handler",
            "wrapper_version": "wrapper.aws.v1",
        },
        "azure": {
            "adapter_id": "adapter.azure.python311",
            "adapter_version": "1",
            "provider": "azure",
            "handler": "function_app.main",
            "wrapper_version": "wrapper.azure.v1",
        },
        "gcp": {
            "adapter_id": "adapter.gcp.python311",
            "adapter_version": "1",
            "provider": "gcp",
            "handler": "main.main",
            "wrapper_version": "wrapper.gcp.v1",
        },
    }
    if (
        not isinstance(adapters, list)
        or len(adapters) != len(expected_adapters)
        or not all(
            isinstance(adapter, dict)
            and isinstance(adapter.get("provider"), str)
            for adapter in adapters
        )
        or {
            adapter.get("provider"): adapter
            for adapter in adapters
            if isinstance(adapter, dict)
        }
        != expected_adapters
    ):
        raise ExtensionContractError(
            "EXTENSION_RUNTIME_UNSUPPORTED",
            "registry.provider_adapters",
            "The extension provider adapter registry is inconsistent.",
        )
    slots = registry.get("slots")
    if not isinstance(slots, list) or not slots:
        raise ExtensionContractError(
            "EXTENSION_SCHEMA_INVALID",
            "registry.slots",
            "The extension registry has no slots.",
        )
    seen: set[tuple[str, str]] = set()
    for index, slot in enumerate(slots):
        validate_extension_slot(slot)
        slot_adapters = {
            adapter["provider"]: adapter
            for adapter in slot["runtime_contract"]["provider_adapters"]
        }
        for provider, expected in expected_adapters.items():
            selected = slot_adapters[provider]
            if (
                selected["adapter_id"] != expected["adapter_id"]
                or selected["adapter_version"] != expected["adapter_version"]
                or selected["provider_runtime"]
                != expected_provider_runtime[provider]
            ):
                raise ExtensionContractError(
                    "EXTENSION_RUNTIME_UNSUPPORTED",
                    f"registry.slots[{index}].runtime_contract",
                    "A slot provider adapter reference is inconsistent.",
                )
        expected_compatibility = sorted(
            (
                f"{adapter['adapter_id']}.v{adapter['adapter_version']}"
                for adapter in expected_adapters.values()
            )
        )
        if (
            slot["dependency_policy_id"] != policy["policy_id"]
            or sorted(
                slot["compatibility"]["provider_adapter_versions"]
            )
            != expected_compatibility
        ):
            raise ExtensionContractError(
                "EXTENSION_VERSION_UNSUPPORTED",
                f"registry.slots[{index}].compatibility",
                "A slot compatibility reference is inconsistent.",
            )
        identity = (slot["slot_id"], slot["slot_version"])
        if identity in seen:
            raise ExtensionContractError(
                "EXTENSION_SCHEMA_INVALID",
                f"registry.slots[{index}]",
                "The extension registry contains a duplicate slot identity.",
            )
        seen.add(identity)
    return registry


def get_slot(slot_id: str, slot_version: str) -> dict[str, Any]:
    if not _STABLE_ID.fullmatch(slot_id) or not re.fullmatch(r"[1-9][0-9]*", slot_version):
        raise ExtensionContractError(
            "EXTENSION_BINDING_UNRESOLVED",
            "slot",
            "The extension slot reference is invalid.",
        )
    for slot in load_registry()["slots"]:
        if slot["slot_id"] == slot_id and slot["slot_version"] == slot_version:
            return slot
    raise ExtensionContractError(
        "EXTENSION_BINDING_UNRESOLVED",
        "slot",
        "The extension slot reference could not be resolved.",
    )


def validate_extension_slot(document: Mapping[str, Any]) -> None:
    _validate_schema("extension-slot.schema.json", document)
    adapters = document["runtime_contract"]["provider_adapters"]
    providers = [adapter["provider"] for adapter in adapters]
    if set(providers) != {"aws", "azure", "gcp"} or len(providers) != 3:
        raise ExtensionContractError(
            "EXTENSION_SCHEMA_INVALID",
            "runtime_contract.provider_adapters",
            "The slot must define exactly one adapter for each provider.",
        )
    expected_runtime = {
        "aws": "python3.11",
        "azure": "3.11",
        "gcp": "python311",
    }
    for adapter in adapters:
        if adapter["provider_runtime"] != expected_runtime[adapter["provider"]]:
            raise ExtensionContractError(
                "EXTENSION_RUNTIME_UNSUPPORTED",
                "runtime_contract.provider_adapters",
                "A provider runtime mapping is incompatible with Python 3.11.",
            )
    for schema_name in ("input_schema", "output_schema", "configuration_schema"):
        schema = document[schema_name]
        required = set(schema["required"])
        properties = set(schema["properties"])
        if not required.issubset(properties):
            raise ExtensionContractError(
                "EXTENSION_SCHEMA_INVALID",
                f"{schema_name}.required",
                "A required field is not defined by the embedded schema.",
            )
        Draft202012Validator.check_schema(_jsonschema_projection(schema))
    for name, field_schema in document["configuration_schema"]["properties"].items():
        if field_schema.get("user_editable") is not True or field_schema.get("secret") is not False:
            raise ExtensionContractError(
                "EXTENSION_SCHEMA_INVALID",
                f"configuration_schema.properties.{name}",
                "Every v1 configuration field must be user editable and non-secret.",
            )
        if _SECRET_KEY.search(name):
            raise ExtensionContractError(
                "EXTENSION_SECRET_MATERIAL_DETECTED",
                f"configuration_schema.properties.{name}",
                "Secret-like configuration fields are forbidden in v1.",
            )
    allowed = set(document["permission_capabilities"])
    if len(allowed) != len(document["permission_capabilities"]):
        raise ExtensionContractError(
            "EXTENSION_SCHEMA_INVALID",
            "permission_capabilities",
            "Permission capability identifiers must be unique.",
        )


def validate_source_archive(
    *,
    metadata: Mapping[str, Any],
    archive_bytes: bytes,
    created_by: str,
    artifact_id: str | None = None,
    created_at: str | None = None,
    validation_timeout_seconds: float = VALIDATION_TIMEOUT_SECONDS,
    monotonic_clock: Callable[[], float] = time.monotonic,
) -> ValidatedArtifact:
    """Validate one multipart client payload without executing its source."""

    if validation_timeout_seconds <= 0:
        raise ValueError("validation_timeout_seconds must be positive")
    deadline = ValidationDeadline(
        expires_at=monotonic_clock() + validation_timeout_seconds,
        clock=monotonic_clock,
    )
    deadline.check()
    _reject_client_platform_fields(metadata)
    slot_id = _required_string(metadata, "slot_id")
    slot_version = _required_string(metadata, "slot_version")
    runtime_id = _required_string(metadata, "runtime_id")
    slot = get_slot(slot_id, slot_version)
    if runtime_id != RUNTIME_ID or runtime_id not in slot["runtime_contract"]["runtime_ids"]:
        raise ExtensionContractError(
            "EXTENSION_RUNTIME_UNSUPPORTED",
            "runtime_id",
            "The requested extension runtime is unsupported.",
        )
    configuration = metadata.get("configuration")
    if not isinstance(configuration, dict):
        raise ExtensionContractError(
            "EXTENSION_CONFIG_INVALID",
            "configuration",
            "Extension configuration must be an object.",
        )
    declared_capabilities = metadata.get("declared_capabilities")
    if not isinstance(declared_capabilities, list) or not all(
        isinstance(item, str) for item in declared_capabilities
    ):
        raise ExtensionContractError(
            "EXTENSION_CAPABILITY_UNAUTHORIZED",
            "declared_capabilities",
            "Declared capabilities must be an array of identifiers.",
        )
    if len(declared_capabilities) != len(set(declared_capabilities)):
        raise ExtensionContractError(
            "EXTENSION_CAPABILITY_UNAUTHORIZED",
            "declared_capabilities",
            "Declared capabilities must be unique.",
        )
    allowed_capabilities = set(slot["permission_capabilities"])
    if not set(declared_capabilities).issubset(allowed_capabilities):
        raise ExtensionContractError(
            "EXTENSION_CAPABILITY_UNAUTHORIZED",
            "declared_capabilities",
            "The artifact declares a capability that the slot does not allow.",
        )
    _scan_value(configuration, "configuration")
    _validate_configuration(slot, configuration)
    deadline.check("configuration")
    files = _read_source_archive(
        archive_bytes,
        slot["resource_limits"],
        deadline=deadline,
    )
    _validate_source(files, deadline=deadline)
    dependencies = _parse_requirements_lock(
        files["requirements.lock"],
        deadline=deadline,
    )
    if len(dependencies) > slot["resource_limits"]["dependency_count"]:
        raise ExtensionContractError(
            "EXTENSION_DEPENDENCY_FORBIDDEN",
            "requirements.lock",
            "The dependency count exceeds the slot limit.",
        )
    file_records = [
        {
            "relative_path": path,
            "content_digest": digest_text(content),
            "size_bytes": len(content.encode("utf-8")),
        }
        for path, content in sorted(files.items())
    ]
    payload_digest = digest_file_payload(files)
    reproducibility = {
        "schema_version": CONTRACT_VERSION,
        "slot_id": slot_id,
        "slot_version": slot_version,
        "runtime_id": runtime_id,
        "source": {
            "module_path": "process.py",
            "entrypoint": "process",
            "files": file_records,
            "payload_digest": payload_digest,
        },
        "dependencies": dependencies,
        "configuration": configuration,
        "declared_capabilities": sorted(declared_capabilities),
        "validator_version": VALIDATOR_VERSION,
    }
    manifest = {
        "schema_version": CONTRACT_VERSION,
        "artifact_id": artifact_id or str(uuid.uuid4()),
        "artifact_digest": digest_json(reproducibility),
        "slot_id": slot_id,
        "slot_version": slot_version,
        "runtime_id": runtime_id,
        "source": reproducibility["source"],
        "dependencies": dependencies,
        "configuration": configuration,
        "declared_capabilities": reproducibility["declared_capabilities"],
        "created_by": created_by,
        "created_at": created_at or _utc_now(),
        "validation": {
            "validator_version": VALIDATOR_VERSION,
            "checks": list(VALIDATION_CHECKS),
        },
    }
    deadline.check("manifest")
    validate_artifact_manifest(manifest)
    deadline.check("manifest")
    immutable_manifest = MappingProxyType(json.loads(canonical_json(manifest)))
    immutable_files = MappingProxyType(dict(sorted(files.items())))
    return ValidatedArtifact(manifest=immutable_manifest, files=immutable_files)


def validate_artifact_manifest(
    manifest: Mapping[str, Any],
    *,
    files: Mapping[str, str] | None = None,
) -> None:
    _validate_schema("artifact-manifest.schema.json", manifest)
    if manifest["schema_version"] != CONTRACT_VERSION:
        raise ExtensionContractError(
            "EXTENSION_VERSION_UNSUPPORTED",
            "schema_version",
            "The artifact schema version is unsupported.",
        )
    slot = get_slot(manifest["slot_id"], manifest["slot_version"])
    if manifest["runtime_id"] not in slot["runtime_contract"]["runtime_ids"]:
        raise ExtensionContractError(
            "EXTENSION_RUNTIME_UNSUPPORTED",
            "runtime_id",
            "The artifact runtime is incompatible with its slot.",
        )
    if not set(manifest["declared_capabilities"]).issubset(
        set(slot["permission_capabilities"])
    ):
        raise ExtensionContractError(
            "EXTENSION_CAPABILITY_UNAUTHORIZED",
            "declared_capabilities",
            "The artifact declares an unauthorized capability.",
        )
    _validate_configuration(slot, manifest["configuration"])
    _scan_value(manifest["configuration"], "configuration")
    paths = [item["relative_path"] for item in manifest["source"]["files"]]
    if len(paths) != len(set(paths)) or paths != sorted(paths):
        raise ExtensionContractError(
            "EXTENSION_SCHEMA_INVALID",
            "source.files",
            "Source file metadata must be unique and deterministically ordered.",
        )
    dependency_names = [item["name"] for item in manifest["dependencies"]]
    if len(dependency_names) != len(set(dependency_names)) or dependency_names != sorted(
        dependency_names
    ):
        raise ExtensionContractError(
            "EXTENSION_SCHEMA_INVALID",
            "dependencies",
            "Dependencies must be unique and deterministically ordered.",
        )
    reproducibility = _manifest_reproducibility(manifest)
    if digest_json(reproducibility) != manifest["artifact_digest"]:
        raise ExtensionContractError(
            "EXTENSION_SCHEMA_INVALID",
            "artifact_digest",
            "The artifact digest does not match the canonical manifest.",
        )
    if files is not None:
        normalized = {path: _normalize_text(content) for path, content in files.items()}
        expected = {
            item["relative_path"]: (item["content_digest"], item["size_bytes"])
            for item in manifest["source"]["files"]
        }
        actual = {
            path: (digest_text(content), len(content.encode("utf-8")))
            for path, content in sorted(normalized.items())
        }
        if actual != expected or digest_file_payload(normalized) != manifest["source"][
            "payload_digest"
        ]:
            raise ExtensionContractError(
                "EXTENSION_SCHEMA_INVALID",
                "source",
                "The stored source payload does not match the artifact manifest.",
            )


def validate_runtime_envelope(
    envelope: Mapping[str, Any],
    *,
    slot: Mapping[str, Any] | None = None,
) -> None:
    _validate_schema("runtime-envelope.schema.json", envelope)
    if envelope.get("schema_version") != ENVELOPE_VERSION:
        raise ExtensionContractError(
            "EXTENSION_VERSION_UNSUPPORTED",
            "schema_version",
            "The runtime envelope version is unsupported.",
        )
    _scan_value(envelope, "envelope")
    resolved_slot = slot or get_slot(str(envelope["slot_id"]), "1")
    if envelope.get("status") is None:
        _validate_embedded_schema(
            resolved_slot["input_schema"],
            envelope["payload"],
            "payload",
        )
    elif envelope["status"] == "success":
        _validate_embedded_schema(
            resolved_slot["output_schema"],
            envelope["payload"],
            "payload",
        )


def build_runtime_result(
    envelope: Mapping[str, Any],
    process: Callable[[dict[str, Any], dict[str, Any], dict[str, Any]], Any],
    configuration: Mapping[str, Any],
) -> dict[str, Any]:
    """Invoke approved domain code behind one sanitized runtime boundary."""

    validate_runtime_envelope(envelope)
    base = {
        "schema_version": ENVELOPE_VERSION,
        "invocation_id": envelope["invocation_id"],
        "correlation_id": envelope["correlation_id"],
        "slot_id": envelope["slot_id"],
    }
    timeout_seconds = float(
        get_slot(str(envelope["slot_id"]), "1")["resource_limits"][
            "timeout_seconds"
        ]
    )
    try:
        result = _invoke_with_timeout(
            process,
            dict(envelope["payload"]),
            dict(configuration),
            dict(envelope["context"]),
            timeout_seconds=timeout_seconds,
        )
        if not isinstance(result, dict):
            return {
                **base,
                "status": "rejected",
                "code": "DOMAIN_OUTPUT_INVALID",
                "message": "The extension returned an invalid result.",
            }
        response = {**base, "status": "success", "payload": result}
        validate_runtime_envelope(response)
        if len(canonical_json(response).encode("utf-8")) > get_slot(
            str(envelope["slot_id"]), "1"
        )["resource_limits"]["response_bytes"]:
            return {
                **base,
                "status": "failed",
                "code": "PLATFORM_RESPONSE_LIMIT",
                "message": "The extension response exceeded its limit.",
                "retryable": false_value(),
            }
        return response
    except ExtensionContractError:
        return {
            **base,
            "status": "rejected",
            "code": "DOMAIN_OUTPUT_INVALID",
            "message": "The extension returned an invalid result.",
        }
    except _InvocationTimedOut:
        return {
            **base,
            "status": "failed",
            "code": "PLATFORM_EXTENSION_TIMEOUT",
            "message": "The extension exceeded its duration limit.",
            "retryable": false_value(),
        }
    except Exception:
        return {
            **base,
            "status": "failed",
            "code": "PLATFORM_EXTENSION_FAILED",
            "message": "The extension could not be completed.",
            "retryable": false_value(),
        }


def binding_digest(
    *,
    twin_id: str,
    slot_id: str,
    slot_version: str,
    artifact_id: str,
    artifact_digest: str,
) -> str:
    return digest_json(
        {
            "schema_version": "twin-extension-binding.v1",
            "twin_id": twin_id,
            "slot_id": slot_id,
            "slot_version": slot_version,
            "artifact_id": artifact_id,
            "artifact_digest": artifact_digest,
        }
    )


def canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def digest_json(value: Any) -> str:
    return digest_bytes(canonical_json(value).encode("utf-8"))


def digest_text(value: str) -> str:
    return digest_bytes(value.encode("utf-8"))


def digest_bytes(value: bytes) -> str:
    return f"sha256:{hashlib.sha256(value).hexdigest()}"


def digest_file_payload(files: Mapping[str, str]) -> str:
    hasher = hashlib.sha256()
    for path, content in sorted(files.items()):
        path_bytes = path.encode("utf-8")
        content_bytes = content.encode("utf-8")
        hasher.update(len(path_bytes).to_bytes(4, "big"))
        hasher.update(path_bytes)
        hasher.update(len(content_bytes).to_bytes(8, "big"))
        hasher.update(content_bytes)
    return f"sha256:{hasher.hexdigest()}"


def safe_runtime_id(value: object) -> bool:
    """Return whether an opaque runtime/correlation identity is log-safe."""

    return isinstance(value, str) and _SAFE_RUNTIME_ID.fullmatch(value) is not None


def deterministic_source_zip(files: Mapping[str, str]) -> bytes:
    output = BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path, content in sorted(files.items()):
            info = zipfile.ZipInfo(path, date_time=PACKAGE_TIMESTAMP)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            archive.writestr(info, _normalize_text(content).encode("utf-8"))
    return output.getvalue()


def load_json_bytes(payload: bytes, *, field: str = "document") -> dict[str, Any]:
    if len(payload) > MAX_JSON_BYTES:
        raise ExtensionContractError(
            "EXTENSION_SCHEMA_INVALID",
            field,
            "The JSON document exceeds its size limit.",
        )
    try:
        value = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ExtensionContractError(
            "EXTENSION_SCHEMA_INVALID",
            field,
            "The JSON document is invalid.",
        ) from exc
    if not isinstance(value, dict) or _value_depth(value) > MAX_JSON_DEPTH:
        raise ExtensionContractError(
            "EXTENSION_SCHEMA_INVALID",
            field,
            "The JSON document has an invalid shape.",
        )
    return value


def false_value() -> bool:
    """Avoid provider template text replacement of boolean literals."""
    return False


class _InvocationTimedOut(BaseException):
    """Platform-only signal that user ``except Exception`` cannot suppress."""


def _invoke_with_timeout(
    process: Callable[[dict[str, Any], dict[str, Any], dict[str, Any]], Any],
    payload: dict[str, Any],
    configuration: dict[str, Any],
    context: dict[str, Any],
    *,
    timeout_seconds: float,
) -> Any:
    if timeout_seconds <= 0:
        raise _InvocationTimedOut
    if threading.current_thread() is not threading.main_thread():
        return _invoke_with_trace_timeout(
            process,
            payload,
            configuration,
            context,
            timeout_seconds=timeout_seconds,
        )

    def _timeout(_signum: int, _frame: Any) -> None:
        raise _InvocationTimedOut

    previous_handler = signal.getsignal(signal.SIGALRM)
    signal.signal(signal.SIGALRM, _timeout)
    previous_timer = signal.setitimer(signal.ITIMER_REAL, timeout_seconds)
    try:
        return process(payload, configuration, context)
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous_handler)
        signal.setitimer(signal.ITIMER_REAL, *previous_timer)


def _invoke_with_trace_timeout(
    process: Callable[[dict[str, Any], dict[str, Any], dict[str, Any]], Any],
    payload: dict[str, Any],
    configuration: dict[str, Any],
    context: dict[str, Any],
    *,
    timeout_seconds: float,
) -> Any:
    deadline = time.monotonic() + timeout_seconds
    previous_trace = sys.gettrace()

    def _trace(_frame: Any, _event: str, _argument: Any):
        if time.monotonic() >= deadline:
            raise _InvocationTimedOut
        return _trace

    sys.settrace(_trace)
    try:
        result = process(payload, configuration, context)
        if time.monotonic() >= deadline:
            raise _InvocationTimedOut
        return result
    finally:
        sys.settrace(previous_trace)


def _validate_schema(filename: str, document: Mapping[str, Any]) -> None:
    schema = _load_json_file(contract_root() / filename)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(
        validator.iter_errors(document),
        key=lambda item: tuple(str(part) for part in item.absolute_path),
    )
    if not errors:
        return
    first = errors[0]
    path = ".".join(str(item) for item in first.absolute_path) or "document"
    if filename == "artifact-manifest.schema.json" and document.get("schema_version") not in {
        CONTRACT_VERSION,
        None,
    }:
        code = "EXTENSION_VERSION_UNSUPPORTED"
    elif filename == "extension-slot.schema.json" and document.get("schema_version") not in {
        SLOT_VERSION,
        None,
    }:
        code = "EXTENSION_VERSION_UNSUPPORTED"
    elif filename == "runtime-envelope.schema.json" and document.get("schema_version") not in {
        ENVELOPE_VERSION,
        None,
    }:
        code = "EXTENSION_VERSION_UNSUPPORTED"
    else:
        code = "EXTENSION_SCHEMA_INVALID"
    raise ExtensionContractError(
        code,
        path,
        "The extension contract does not match its schema.",
    )


def _load_json_file(path: Path) -> dict[str, Any]:
    try:
        return load_json_bytes(path.read_bytes(), field=path.name)
    except OSError as exc:
        raise ExtensionContractError(
            "EXTENSION_SCHEMA_INVALID",
            path.name,
            "A required local extension contract is unavailable.",
        ) from exc


def _read_source_archive(
    archive_bytes: bytes,
    limits: Mapping[str, int],
    *,
    deadline: ValidationDeadline | None = None,
) -> dict[str, str]:
    if deadline is not None:
        deadline.check("source_archive")
    archive_limit = min(MAX_ARCHIVE_BYTES, int(limits["artifact_bytes"]))
    if not archive_bytes or len(archive_bytes) > archive_limit:
        raise ExtensionContractError(
            "EXTENSION_ARCHIVE_UNSAFE",
            "source_archive",
            "The source archive is empty or exceeds its size limit.",
        )
    files: dict[str, str] = {}
    expanded = 0
    try:
        archive = zipfile.ZipFile(BytesIO(archive_bytes))
    except (zipfile.BadZipFile, OSError) as exc:
        raise ExtensionContractError(
            "EXTENSION_ARCHIVE_UNSAFE",
            "source_archive",
            "The source archive is not a valid ZIP.",
        ) from exc
    with archive:
        infos = archive.infolist()
        if len(infos) > min(MAX_FILE_COUNT, int(limits["file_count"])):
            raise ExtensionContractError(
                "EXTENSION_ARCHIVE_UNSAFE",
                "source_archive",
                "The source archive contains too many entries.",
            )
        seen: set[str] = set()
        for info in infos:
            if deadline is not None:
                deadline.check("source_archive")
            if info.flag_bits & 0x1:
                _archive_error("Encrypted archive entries are forbidden.")
            path = _safe_archive_path(info.filename)
            for part in PurePosixPath(path).parts:
                if _SECRET_KEY.search(part) or _SECRET_KEY.search(
                    PurePosixPath(part).stem
                ):
                    raise ExtensionContractError(
                        "EXTENSION_SECRET_MATERIAL_DETECTED",
                        "source_archive.path",
                        "Secret-like archive paths are forbidden in extension v1.",
                    )
            if path in seen:
                _archive_error("Duplicate archive paths are forbidden.")
            seen.add(path)
            file_type = stat.S_IFMT(info.external_attr >> 16)
            if file_type not in {0, stat.S_IFREG, stat.S_IFDIR}:
                _archive_error("Links and special files are forbidden.")
            if info.is_dir():
                continue
            if info.file_size > MAX_FILE_BYTES:
                _archive_error("An archive file exceeds its size limit.")
            expanded += info.file_size
            if expanded > min(MAX_EXPANDED_BYTES, int(limits["source_bytes"])):
                _archive_error("The expanded source exceeds its size limit.")
            suffix = PurePosixPath(path).suffix.lower()
            if path != "requirements.lock" and suffix != ".py":
                _archive_error("Only Python source and requirements.lock are accepted.")
            if suffix in {".zip", ".whl", ".so", ".dll", ".dylib", ".exe", ".bin"}:
                _archive_error("Nested archives and native binaries are forbidden.")
            try:
                raw = archive.read(info)
                if b"\x00" in raw:
                    _archive_error("Binary source content is forbidden.")
                text = _normalize_text(raw.decode("utf-8"))
            except (UnicodeDecodeError, RuntimeError, zipfile.BadZipFile) as exc:
                raise ExtensionContractError(
                    "EXTENSION_ARCHIVE_UNSAFE",
                    path,
                    "A source file could not be decoded safely.",
                ) from exc
            files[path] = text
    if "process.py" not in files or "requirements.lock" not in files:
        raise ExtensionContractError(
            "EXTENSION_ARCHIVE_UNSAFE",
            "source_archive",
            "The archive must contain process.py and requirements.lock.",
        )
    return dict(sorted(files.items()))


def _safe_archive_path(value: str) -> str:
    normalized = unicodedata.normalize("NFC", value.replace("\\", "/"))
    path = PurePosixPath(normalized)
    parts = path.parts
    if (
        not normalized
        or normalized.startswith("/")
        or "\x00" in normalized
        or len(parts) > MAX_PATH_DEPTH
        or any(part in {"", ".", ".."} or part.startswith(".") for part in parts)
        or any(":" in part for part in parts)
        or len(normalized) > 240
    ):
        _archive_error("An archive path is unsafe.")
    return path.as_posix()


def _archive_error(message: str) -> None:
    raise ExtensionContractError(
        "EXTENSION_ARCHIVE_UNSAFE",
        "source_archive",
        message,
    )


def _validate_source(
    files: Mapping[str, str],
    *,
    deadline: ValidationDeadline | None = None,
) -> None:
    for path, content in files.items():
        if deadline is not None:
            deadline.check(path)
        _scan_text(content, path)
        if path.endswith(".py"):
            _validate_python_file(path, content, require_entrypoint=path == "process.py")
    module_names = {
        PurePosixPath(path).stem
        for path in files
        if path.endswith(".py") and "/" not in path
    }
    for path, content in files.items():
        if deadline is not None:
            deadline.check(path)
        if not path.endswith(".py"):
            continue
        tree = ast.parse(content, filename=path)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                imports = [node.module or ""]
                if node.level:
                    raise ExtensionContractError(
                        "EXTENSION_ENTRYPOINT_INVALID",
                        path,
                        "Relative package imports are unsupported in v1.",
                    )
            else:
                continue
            for imported in imports:
                root = imported.split(".", 1)[0]
                if imported.startswith(_FORBIDDEN_IMPORT_PREFIXES) or root in _FORBIDDEN_IMPORTS:
                    raise ExtensionContractError(
                        "EXTENSION_CAPABILITY_UNAUTHORIZED",
                        path,
                        "The source imports a platform or unsafe runtime module.",
                    )
                if root in module_names:
                    continue


def _validate_python_file(path: str, content: str, *, require_entrypoint: bool) -> None:
    try:
        tree = ast.parse(content, filename=path)
    except SyntaxError as exc:
        raise ExtensionContractError(
            "EXTENSION_ENTRYPOINT_INVALID",
            path,
            "A Python source file has invalid syntax.",
        ) from exc
    for node in ast.walk(tree):
        if isinstance(node, (ast.ClassDef, ast.AsyncFunctionDef)):
            raise ExtensionContractError(
                "EXTENSION_ENTRYPOINT_INVALID",
                path,
                "Classes and async functions are unsupported in v1 source.",
            )
        if isinstance(node, ast.ExceptHandler) and (
            node.type is None
            or (
                isinstance(node.type, ast.Name)
                and node.type.id == "BaseException"
            )
        ):
            raise ExtensionContractError(
                "EXTENSION_CAPABILITY_UNAUTHORIZED",
                path,
                "Bare and BaseException handlers are unsupported in v1 source.",
            )
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id in _FORBIDDEN_CALLS:
                raise ExtensionContractError(
                    "EXTENSION_CAPABILITY_UNAUTHORIZED",
                    path,
                    "The source calls an unsafe runtime primitive.",
                )
    if not require_entrypoint:
        return
    process_defs = [
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "process"
    ]
    if len(process_defs) != 1:
        raise ExtensionContractError(
            "EXTENSION_ENTRYPOINT_INVALID",
            "process.py",
            "process.py must define exactly one top-level process entrypoint.",
        )
    entrypoint = process_defs[0]
    if (
        len(entrypoint.args.args) != 3
        or entrypoint.args.vararg is not None
        or entrypoint.args.kwarg is not None
        or entrypoint.args.kwonlyargs
        or entrypoint.args.defaults
    ):
        raise ExtensionContractError(
            "EXTENSION_ENTRYPOINT_INVALID",
            "process.py",
            "The process entrypoint must accept payload, configuration, and context.",
        )


def _parse_requirements_lock(
    content: str,
    *,
    deadline: ValidationDeadline | None = None,
) -> list[dict[str, Any]]:
    dependencies: list[dict[str, Any]] = []
    seen: set[str] = set()
    for line_number, raw_line in enumerate(content.splitlines(), start=1):
        if deadline is not None:
            deadline.check("requirements.lock")
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if (
            "\\" in line
            or "://" in line
            or line.startswith(("-e", "--editable", "-r", "--requirement", "--"))
            or " @ " in line
            or line.startswith((".", "/"))
        ):
            raise ExtensionContractError(
                "EXTENSION_DEPENDENCY_UNPINNED",
                f"requirements.lock:{line_number}",
                "The dependency lock contains an unsupported requirement form.",
            )
        match = _LOCK_LINE.fullmatch(line)
        if match is None:
            raise ExtensionContractError(
                "EXTENSION_DEPENDENCY_UNPINNED",
                f"requirements.lock:{line_number}",
                "Every dependency must use an exact version and SHA-256 hash.",
            )
        name = re.sub(r"[-_.]+", "-", match.group("name")).lower()
        if name in seen:
            raise ExtensionContractError(
                "EXTENSION_DEPENDENCY_FORBIDDEN",
                f"requirements.lock:{line_number}",
                "The dependency lock contains a duplicate package.",
            )
        seen.add(name)
        if name in _FORBIDDEN_DEPENDENCIES:
            raise ExtensionContractError(
                "EXTENSION_DEPENDENCY_FORBIDDEN",
                f"requirements.lock:{line_number}",
                "The dependency policy forbids this package.",
            )
        hashes = sorted(set(_HASH_OPTION.findall(match.group("hashes"))))
        dependencies.append(
            {
                "name": name,
                "version": match.group("version"),
                "hashes": hashes,
                "policy_result": "allowed",
            }
        )
    if len(dependencies) > MAX_DEPENDENCIES:
        raise ExtensionContractError(
            "EXTENSION_DEPENDENCY_FORBIDDEN",
            "requirements.lock",
            "The dependency lock contains too many packages.",
        )
    return sorted(dependencies, key=lambda item: item["name"])


def _validate_configuration(slot: Mapping[str, Any], configuration: Mapping[str, Any]) -> None:
    _validate_embedded_schema(
        slot["configuration_schema"],
        configuration,
        "configuration",
    )


def _validate_embedded_schema(
    schema: Mapping[str, Any],
    document: Any,
    field: str,
) -> None:
    validator = Draft202012Validator(_jsonschema_projection(schema))
    if next(validator.iter_errors(document), None) is not None:
        raise ExtensionContractError(
            "EXTENSION_CONFIG_INVALID",
            field,
            "The value does not satisfy the registered slot schema.",
        )


def _jsonschema_projection(schema: Mapping[str, Any]) -> dict[str, Any]:
    projected = json.loads(canonical_json(schema))
    for field_schema in projected.get("properties", {}).values():
        field_schema.pop("user_editable", None)
        field_schema.pop("secret", None)
    return projected


def _scan_value(value: Any, field: str) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if _SECRET_KEY.search(str(key)):
                raise ExtensionContractError(
                    "EXTENSION_SECRET_MATERIAL_DETECTED",
                    f"{field}.{_safe_field(str(key))}",
                    "Secret-like fields are forbidden in extension v1.",
                )
            _scan_value(child, f"{field}.{_safe_field(str(key))}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _scan_value(child, f"{field}[{index}]")
    elif isinstance(value, str):
        _scan_text(value, field)


def _scan_text(value: str, field: str) -> None:
    for pattern in _SECRET_VALUE:
        if pattern.search(value):
            raise ExtensionContractError(
                "EXTENSION_SECRET_MATERIAL_DETECTED",
                field,
                "Credential-like material is forbidden in extension v1.",
            )


def _reject_client_platform_fields(metadata: Mapping[str, Any]) -> None:
    allowed = {
        "slot_id",
        "slot_version",
        "runtime_id",
        "configuration",
        "declared_capabilities",
    }
    extra = set(metadata) - allowed
    if extra:
        raise ExtensionContractError(
            "EXTENSION_SCHEMA_INVALID",
            "metadata",
            "Client metadata contains platform-owned fields.",
        )


def _manifest_reproducibility(manifest: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": manifest["schema_version"],
        "slot_id": manifest["slot_id"],
        "slot_version": manifest["slot_version"],
        "runtime_id": manifest["runtime_id"],
        "source": manifest["source"],
        "dependencies": manifest["dependencies"],
        "configuration": manifest["configuration"],
        "declared_capabilities": manifest["declared_capabilities"],
        "validator_version": manifest["validation"]["validator_version"],
    }


def _required_string(document: Mapping[str, Any], field: str) -> str:
    value = document.get(field)
    if not isinstance(value, str) or not value:
        raise ExtensionContractError(
            "EXTENSION_SCHEMA_INVALID",
            field,
            "A required metadata field is missing.",
        )
    return value


def _normalize_text(value: str) -> str:
    return unicodedata.normalize("NFC", value.replace("\r\n", "\n").replace("\r", "\n"))


def _safe_field(value: str) -> str:
    sanitized = re.sub(r"[^A-Za-z0-9_.:\-\[\]]", "_", value)
    return sanitized[:160] or "document"


def _safe_message(value: str) -> str:
    sanitized = re.sub(r"[\r\n\t]+", " ", value)
    return sanitized[:256]


def _value_depth(value: Any, depth: int = 0) -> int:
    if not isinstance(value, (dict, list)) or not value:
        return depth
    children = value.values() if isinstance(value, dict) else value
    return max(_value_depth(child, depth + 1) for child in children)


def _utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z")
    )
