"""Configuration for the Six-layer GCP MQTT device simulator."""

from __future__ import annotations

import json
import os
import re


_SAFE_DEVICE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


class Config:
    def __init__(self) -> None:
        self.endpoint: str | None = None
        self.port: int | None = None
        self.device_id: str | None = None
        self.digital_twin_name: str = ""
        self.username: str | None = None
        self.password: str | None = None
        self.telemetry_topic: str | None = None
        self.command_topic: str | None = None
        self.server_ca_path: str | None = None
        self.payload_path: str | None = None
        self.configs_root: str | None = None
        self.config_filename: str | None = None


config = Config()


def load_config(config_path: str) -> None:
    """Load one deployment-scoped MQTT config and resolve local file paths."""
    config_dir = os.path.dirname(os.path.abspath(config_path))
    with open(config_path, encoding="utf-8") as handle:
        data = json.load(handle)

    def resolve(path: str | None, default: str) -> str:
        resolved = path or default
        if not os.path.isabs(resolved):
            resolved = os.path.normpath(os.path.join(config_dir, resolved))
        return resolved

    config.endpoint = data["endpoint"]
    config.port = int(data.get("port", 8883))
    config.device_id = data["device_id"]
    config.digital_twin_name = data.get("digital_twin_name", "")
    config.username = data["username"]
    config.password = data["password"]
    config.telemetry_topic = data["telemetry_topic"]
    config.command_topic = data["command_topic"]
    config.server_ca_path = resolve(data.get("server_ca_path"), "server-ca.pem")
    config.payload_path = resolve(data.get("payload_path"), "../payloads.json")
    if os.path.basename(config_path) == "config_generated.json":
        config.configs_root = os.path.dirname(config_dir)
        config.config_filename = "config_generated.json"
    else:
        config.configs_root = os.path.join(config_dir, "configs")
        config.config_filename = "config.json"


def get_device_config_path(device_id: str) -> str:
    if (
        not isinstance(device_id, str)
        or not _SAFE_DEVICE_ID.fullmatch(device_id)
        or ".." in device_id
    ):
        raise ValueError("Invalid simulator device ID")
    if config.configs_root is None or config.config_filename is None:
        raise ValueError("Simulator configuration has not been initialized")
    return os.path.join(config.configs_root, device_id, config.config_filename)
