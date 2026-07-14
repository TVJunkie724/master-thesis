"""Secure, provider-aware standalone simulator package assembly."""

from __future__ import annotations

import base64
import binascii
import io
import json
import re
import stat
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any


MAX_DEVICE_COUNT = 100
MAX_SOURCE_FILE_BYTES = 2 * 1024 * 1024
MAX_CREDENTIAL_FILE_BYTES = 256 * 1024
MAX_PAYLOAD_FILE_BYTES = 4 * 1024 * 1024
MAX_ARCHIVE_INPUT_BYTES = 16 * 1024 * 1024

_SAFE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_PROVIDER_ALIASES = {
    "aws": "aws",
    "azure": "azure",
    "gcp": "google",
    "google": "google",
}
_PUBLIC_PROVIDER = {"aws": "aws", "azure": "azure", "google": "gcp"}
_CREDENTIAL_CLASS = {
    "aws": "aws_iot_device_certificate",
    "azure": "azure_iot_hub_device_identity",
    "google": "gcp_pubsub_topic_publisher",
}
_SOURCE_FILES = ("main.py", "transmission.py", "globals.py")
_TEMPLATE_FILES = {
    "README.md": "README.md.template",
    "requirements.txt": "requirements.txt",
    "Dockerfile": "Dockerfile",
    "docker-compose.yml": "docker-compose.yml.template",
}


class SimulatorPackageError(RuntimeError):
    """Base error for package assembly failures."""


class SimulatorPackageNotFound(SimulatorPackageError):
    """Required deployment output is not available."""


class SimulatorPackageInvalid(SimulatorPackageError):
    """Deployment output violates the simulator package contract."""


@dataclass(frozen=True)
class SimulatorPackage:
    """Validated archive and non-sensitive response metadata."""

    content: io.BytesIO
    filename: str
    provider: str
    credential_class: str
    media_type: str = "application/zip"


def normalize_simulator_provider(provider: str) -> str:
    """Return the internal provider identifier used by simulator assets."""
    normalized = provider.strip().lower()
    try:
        return _PROVIDER_ALIASES[normalized]
    except KeyError as exc:
        raise SimulatorPackageInvalid(
            f"Provider '{provider}' not supported. Supported: aws, azure, gcp."
        ) from exc


class SimulatorPackageService:
    """Build simulator archives from an explicit, least-privilege allowlist."""

    def __init__(self, *, project_path: Path, source_root: Path):
        self.project_path = project_path
        self.source_root = source_root
        self._input_bytes = 0
        self._archive_names: set[str] = set()

    def build(self, *, project_name: str, provider: str) -> SimulatorPackage:
        self._input_bytes = 0
        self._archive_names.clear()
        internal_provider = normalize_simulator_provider(provider)
        self._validate_safe_name(project_name, "project name")
        project_root = self._validated_directory(self.project_path, "project")
        provider_dir = self._validated_directory(
            project_root / "iot_device_simulator" / internal_provider,
            "simulator provider",
        )
        source_dir = self._validated_directory(
            self.source_root / internal_provider,
            "simulator source",
        )

        device_configs = self._load_device_configs(provider_dir, internal_provider)
        payload = self._load_json_file(
            project_root / "iot_device_simulator" / "payloads.json",
            max_bytes=MAX_PAYLOAD_FILE_BYTES,
            description="simulator payloads",
        )
        if not isinstance(payload, list):
            raise SimulatorPackageInvalid("Simulator payloads must be a JSON array.")

        credentials = self._load_provider_credentials(
            internal_provider,
            project_root,
            provider_dir,
            device_configs,
            source_dir,
        )

        archive = io.BytesIO()
        with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zip_file:
            first_device = next(iter(device_configs))
            self._write_json(
                zip_file,
                "config.json",
                self._archive_config(
                    internal_provider,
                    first_device,
                    device_configs[first_device],
                    root=True,
                ),
            )
            for device_id, config in device_configs.items():
                self._write_json(
                    zip_file,
                    f"configs/{device_id}/config.json",
                    self._archive_config(
                        internal_provider,
                        device_id,
                        config,
                        root=False,
                    ),
                )

            self._write_json(zip_file, "payloads.json", payload)
            for archive_name, content in credentials:
                self._write_bytes(zip_file, archive_name, content)

            for source_name in _SOURCE_FILES:
                content = self._read_regular_file(
                    source_dir / source_name,
                    max_bytes=MAX_SOURCE_FILE_BYTES,
                    description=f"simulator source {source_name}",
                )
                self._write_bytes(zip_file, f"src/{source_name}", content)

            template_vars = self._template_variables(
                project_name,
                internal_provider,
                device_configs,
            )
            templates_dir = self._validated_directory(
                source_dir / "templates",
                "simulator templates",
            )
            for archive_name, template_name in _TEMPLATE_FILES.items():
                template = self._read_regular_file(
                    templates_dir / template_name,
                    max_bytes=MAX_SOURCE_FILE_BYTES,
                    description=f"simulator template {template_name}",
                ).decode("utf-8")
                for key, value in template_vars.items():
                    template = template.replace(f"{{{{{key}}}}}", str(value))
                self._write_bytes(zip_file, archive_name, template.encode("utf-8"))

        archive.seek(0)
        public_provider = _PUBLIC_PROVIDER[internal_provider]
        return SimulatorPackage(
            content=archive,
            filename=f"simulator_package_{project_name}_{public_provider}.zip",
            provider=public_provider,
            credential_class=_CREDENTIAL_CLASS[internal_provider],
        )

    def _load_device_configs(
        self,
        provider_dir: Path,
        provider: str,
    ) -> dict[str, dict[str, Any]]:
        symlink_entries = [child.name for child in provider_dir.iterdir() if child.is_symlink()]
        if symlink_entries:
            raise SimulatorPackageInvalid("Simulator provider directory contains symbolic links.")
        device_dirs = sorted(
            child
            for child in provider_dir.iterdir()
            if child.name != "_runtime" and child.is_dir() and not child.is_symlink()
        )
        if not device_dirs:
            raise SimulatorPackageNotFound("No simulator device configurations found. Deploy L1 first.")
        if len(device_dirs) > MAX_DEVICE_COUNT:
            raise SimulatorPackageInvalid(
                f"Simulator package exceeds the {MAX_DEVICE_COUNT}-device limit."
            )

        configs: dict[str, dict[str, Any]] = {}
        for device_dir in device_dirs:
            self._validate_safe_name(device_dir.name, "device ID")
            config_path = device_dir / "config_generated.json"
            loader = self._load_sensitive_json_file if provider == "azure" else self._load_json_file
            config = loader(
                config_path,
                max_bytes=MAX_CREDENTIAL_FILE_BYTES,
                description=f"simulator config for {device_dir.name}",
            )
            if not isinstance(config, dict):
                raise SimulatorPackageInvalid(
                    f"Simulator config for '{device_dir.name}' must be a JSON object."
                )
            self._validate_device_config(provider, device_dir.name, config)
            configs[device_dir.name] = config
        return configs

    def _validate_device_config(
        self,
        provider: str,
        device_id: str,
        config: dict[str, Any],
    ) -> None:
        if config.get("device_id") != device_id:
            raise SimulatorPackageInvalid(
                f"Simulator config identity does not match device directory '{device_id}'."
            )
        if provider == "aws":
            self._validate_credential_contract(config, provider, device_id)
            if config.get("permission_scope") != "exact_client_and_telemetry_topic":
                raise SimulatorPackageInvalid(
                    f"AWS simulator permission scope is not proven for '{device_id}'."
                )
            endpoint = self._required_string(config, "endpoint", device_id)
            topic = self._required_string(config, "topic", device_id)
            if not endpoint.endswith(".amazonaws.com"):
                raise SimulatorPackageInvalid(f"Invalid AWS IoT endpoint for '{device_id}'.")
            if not re.fullmatch(rf"dt/[A-Za-z0-9._-]+/{re.escape(device_id)}/telemetry", topic):
                raise SimulatorPackageInvalid(f"Invalid AWS telemetry topic for '{device_id}'.")
        elif provider == "azure":
            self._validate_credential_contract(config, provider, device_id)
            connection_string = self._required_string(config, "connection_string", device_id)
            self._validate_azure_connection_string(connection_string, device_id)
        else:
            self._required_string(config, "project_id", device_id)
            self._required_string(config, "topic_name", device_id)
            expected_email = self._required_string(
                config,
                "simulator_service_account_email",
                device_id,
            )
            if not expected_email.endswith(".iam.gserviceaccount.com"):
                raise SimulatorPackageInvalid(
                    f"Invalid GCP simulator service account for '{device_id}'."
                )
            self._validate_credential_contract(config, provider, device_id)

    def _load_provider_credentials(
        self,
        provider: str,
        project_root: Path,
        provider_dir: Path,
        device_configs: dict[str, dict[str, Any]],
        source_dir: Path,
    ) -> list[tuple[str, bytes]]:
        if provider == "aws":
            credentials: list[tuple[str, bytes]] = []
            auth_root = self._validated_directory(
                project_root / "iot_devices_auth",
                "AWS device credentials",
            )
            for device_id in device_configs:
                device_auth = self._validated_directory(
                    auth_root / device_id,
                    f"AWS credentials for {device_id}",
                )
                self._assert_directory_entries(
                    device_auth,
                    {"certificate.pem.crt", "private.pem.key", "public.pem.key"},
                    f"AWS credentials for {device_id}",
                )
                certificate = self._read_regular_file(
                    device_auth / "certificate.pem.crt",
                    max_bytes=MAX_CREDENTIAL_FILE_BYTES,
                    description=f"AWS certificate for {device_id}",
                )
                private_key = self._read_sensitive_file(
                    device_auth / "private.pem.key",
                    max_bytes=MAX_CREDENTIAL_FILE_BYTES,
                    description=f"AWS private key for {device_id}",
                )
                if b"BEGIN CERTIFICATE" not in certificate:
                    raise SimulatorPackageInvalid(f"Invalid AWS certificate for '{device_id}'.")
                if b"PRIVATE KEY" not in private_key:
                    raise SimulatorPackageInvalid(f"Invalid AWS private key for '{device_id}'.")
                credentials.extend(
                    [
                        (f"configs/{device_id}/certificate.pem.crt", certificate),
                        (f"configs/{device_id}/private.pem.key", private_key),
                    ]
                )
            root_ca = self._read_regular_file(
                source_dir / "AmazonRootCA1.pem",
                max_bytes=MAX_CREDENTIAL_FILE_BYTES,
                description="AWS public root CA",
            )
            if b"BEGIN CERTIFICATE" not in root_ca:
                raise SimulatorPackageInvalid("Invalid AWS public root CA.")
            credentials.append(("AmazonRootCA1.pem", root_ca))
            return credentials

        if provider == "azure":
            return []

        runtime_dir = self._validated_directory(
            provider_dir / "_runtime",
            "GCP simulator runtime credentials",
        )
        self._assert_directory_entries(
            runtime_dir,
            {"service_account.json"},
            "GCP simulator runtime credentials",
        )
        key = self._load_sensitive_json_file(
            runtime_dir / "service_account.json",
            max_bytes=MAX_CREDENTIAL_FILE_BYTES,
            description="GCP simulator service account key",
        )
        if not isinstance(key, dict):
            raise SimulatorPackageInvalid("GCP simulator service account key must be a JSON object.")
        expected_projects = {str(config["project_id"]) for config in device_configs.values()}
        expected_emails = {
            str(config["simulator_service_account_email"])
            for config in device_configs.values()
        }
        if len(expected_projects) != 1 or key.get("project_id") not in expected_projects:
            raise SimulatorPackageInvalid("GCP simulator key project does not match device configs.")
        if len(expected_emails) != 1 or key.get("client_email") not in expected_emails:
            raise SimulatorPackageInvalid("GCP simulator key identity does not match device configs.")
        if key.get("type") != "service_account" or "PRIVATE KEY" not in str(key.get("private_key", "")):
            raise SimulatorPackageInvalid("GCP simulator service account key is invalid.")
        return [("service_account.json", self._canonical_json(key))]

    def _archive_config(
        self,
        provider: str,
        device_id: str,
        config: dict[str, Any],
        *,
        root: bool,
    ) -> dict[str, Any]:
        prefix = "" if root else "../"
        if provider == "aws":
            credential_prefix = "configs/" if root else ""
            return {
                "endpoint": config["endpoint"],
                "topic": config["topic"],
                "device_id": device_id,
                "cert_path": f"{credential_prefix}{device_id + '/' if root else ''}certificate.pem.crt",
                "key_path": f"{credential_prefix}{device_id + '/' if root else ''}private.pem.key",
                "root_ca_path": "AmazonRootCA1.pem" if root else "../../AmazonRootCA1.pem",
                "payload_path": "payloads.json" if root else "../../payloads.json",
                "credential_class": _CREDENTIAL_CLASS[provider],
                "credential_contract_version": 1,
            }
        if provider == "azure":
            return {
                "connection_string": config["connection_string"],
                "device_id": device_id,
                "digital_twin_name": config.get("digital_twin_name", ""),
                "payload_path": "payloads.json" if root else "../../payloads.json",
                "credential_class": _CREDENTIAL_CLASS[provider],
                "credential_contract_version": 1,
            }
        return {
            "project_id": config["project_id"],
            "topic_name": config["topic_name"],
            "device_id": device_id,
            "digital_twin_name": config.get("digital_twin_name", ""),
            "service_account_key_path": "service_account.json"
            if root
            else "../../service_account.json",
            "payload_path": "payloads.json" if root else "../../payloads.json",
            "simulator_service_account_email": config["simulator_service_account_email"],
            "credential_class": _CREDENTIAL_CLASS[provider],
            "credential_contract_version": 1,
        }

    def _template_variables(
        self,
        project_name: str,
        provider: str,
        configs: dict[str, dict[str, Any]],
    ) -> dict[str, Any]:
        first_device = next(iter(configs))
        first_config = configs[first_device]
        return {
            "project_name": project_name,
            "provider": _PUBLIC_PROVIDER[provider],
            "device_id": first_device,
            "device_ids": ", ".join(configs),
            "device_count": len(configs),
            "endpoint": first_config.get("endpoint", ""),
            "project_id": first_config.get("project_id", ""),
            "topic_name": first_config.get("topic_name", ""),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def _validated_directory(self, path: Path, description: str) -> Path:
        if not path.exists():
            raise SimulatorPackageNotFound(f"Required {description} directory is missing.")
        if path.is_symlink() or not path.is_dir():
            raise SimulatorPackageInvalid(f"Required {description} path is not a regular directory.")
        return path.resolve()

    def _read_regular_file(self, path: Path, *, max_bytes: int, description: str) -> bytes:
        if not path.exists():
            raise SimulatorPackageNotFound(f"Required {description} file is missing.")
        if path.is_symlink() or not path.is_file():
            raise SimulatorPackageInvalid(f"Required {description} path is not a regular file.")
        size = path.stat().st_size
        if size > max_bytes:
            raise SimulatorPackageInvalid(f"Required {description} file exceeds its size limit.")
        self._input_bytes += size
        if self._input_bytes > MAX_ARCHIVE_INPUT_BYTES:
            raise SimulatorPackageInvalid("Simulator package exceeds the total input size limit.")
        return path.read_bytes()

    def _read_sensitive_file(self, path: Path, *, max_bytes: int, description: str) -> bytes:
        content = self._read_regular_file(path, max_bytes=max_bytes, description=description)
        if stat.S_IMODE(path.stat().st_mode) & 0o077:
            raise SimulatorPackageInvalid(f"Required {description} file permissions are too broad.")
        return content

    @staticmethod
    def _assert_directory_entries(path: Path, allowed: set[str], description: str) -> None:
        unexpected = sorted(
            child.name
            for child in path.iterdir()
            if child.name not in allowed or child.is_symlink() or not child.is_file()
        )
        if unexpected:
            raise SimulatorPackageInvalid(
                f"Required {description} directory contains unexpected files."
            )

    def _load_json_file(self, path: Path, *, max_bytes: int, description: str) -> Any:
        raw = self._read_regular_file(path, max_bytes=max_bytes, description=description)
        try:
            return json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise SimulatorPackageInvalid(f"Required {description} file is not valid JSON.") from exc

    def _load_sensitive_json_file(self, path: Path, *, max_bytes: int, description: str) -> Any:
        raw = self._read_sensitive_file(path, max_bytes=max_bytes, description=description)
        try:
            return json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise SimulatorPackageInvalid(f"Required {description} file is not valid JSON.") from exc

    def _write_json(self, archive: zipfile.ZipFile, name: str, value: Any) -> None:
        self._write_bytes(archive, name, self._canonical_json(value))

    def _write_bytes(self, archive: zipfile.ZipFile, name: str, content: bytes) -> None:
        archive_name = PurePosixPath(name)
        if archive_name.is_absolute() or ".." in archive_name.parts or name in self._archive_names:
            raise SimulatorPackageInvalid(f"Unsafe or duplicate archive entry: {name}")
        self._archive_names.add(name)
        archive.writestr(name, content)

    @staticmethod
    def _canonical_json(value: Any) -> bytes:
        return json.dumps(value, indent=2, sort_keys=True).encode("utf-8")

    @staticmethod
    def _validate_safe_name(value: str, description: str) -> None:
        if not _SAFE_NAME.fullmatch(value) or ".." in value:
            raise SimulatorPackageInvalid(f"Unsafe {description}.")

    @staticmethod
    def _required_string(config: dict[str, Any], key: str, device_id: str) -> str:
        value = config.get(key)
        if not isinstance(value, str) or not value or len(value) > 4096 or any(
            character in value for character in "\r\n\0"
        ):
            raise SimulatorPackageInvalid(
                f"Simulator config field '{key}' is invalid for '{device_id}'."
            )
        return value

    @staticmethod
    def _validate_azure_connection_string(connection_string: str, device_id: str) -> None:
        parts: dict[str, str] = {}
        for segment in connection_string.split(";"):
            key, separator, value = segment.partition("=")
            if not separator or key in parts or not value:
                raise SimulatorPackageInvalid(f"Invalid Azure device identity for '{device_id}'.")
            parts[key] = value
        if set(parts) != {"HostName", "DeviceId", "SharedAccessKey"}:
            raise SimulatorPackageInvalid(f"Invalid Azure device identity for '{device_id}'.")
        if not parts["HostName"].endswith(".azure-devices.net") or parts["DeviceId"] != device_id:
            raise SimulatorPackageInvalid(f"Azure device identity does not match '{device_id}'.")
        try:
            base64.b64decode(parts["SharedAccessKey"], validate=True)
        except (binascii.Error, ValueError) as exc:
            raise SimulatorPackageInvalid(f"Invalid Azure device key for '{device_id}'.") from exc

    @staticmethod
    def _validate_credential_contract(
        config: dict[str, Any],
        provider: str,
        device_id: str,
    ) -> None:
        if config.get("credential_class") != _CREDENTIAL_CLASS[provider]:
            raise SimulatorPackageInvalid(
                f"Simulator credential class is missing for '{device_id}'."
            )
        if config.get("credential_contract_version") != 1:
            raise SimulatorPackageInvalid(
                f"Unsupported simulator credential contract for '{device_id}'."
            )
