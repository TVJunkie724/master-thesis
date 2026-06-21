#!/usr/bin/env python3
"""Export deterministic OpenAPI snapshots for service quality gates."""

from __future__ import annotations

import argparse
import importlib
import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping


REPO_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class ServiceSpec:
    project_dir: Path
    app_import: str
    env: Mapping[str, str] = field(default_factory=dict)


SERVICES: dict[str, ServiceSpec] = {
    "management-api": ServiceSpec(
        project_dir=REPO_ROOT / "twin2multicloud_backend",
        app_import="src.main:app",
        env={
            "DATABASE_URL": "sqlite:////tmp/twin2multicloud_contract_gate.db",
            "ENABLE_TEST_ENDPOINTS": "false",
            "SEED_DATA": "false",
            "DEBUG": "false",
        },
    ),
    "optimizer": ServiceSpec(
        project_dir=REPO_ROOT / "2-twin2clouds",
        app_import="rest_api:app",
    ),
    "deployer": ServiceSpec(
        project_dir=REPO_ROOT / "3-cloud-deployer",
        app_import="rest_api:app",
    ),
}


def ensure_contract_runtime_files() -> None:
    """Create non-secret runtime files required only to import legacy apps."""
    config_path = Path("/config/config.json")
    if not config_path.exists():
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(json.dumps({"mode": "INFO"}) + "\n", encoding="utf-8")


def parse_app_import(import_path: str) -> tuple[str, str]:
    if ":" not in import_path:
        raise ValueError(f"Invalid app import '{import_path}'. Expected '<module>:<attribute>'.")
    module_name, app_name = import_path.split(":", 1)
    if not module_name or not app_name:
        raise ValueError(f"Invalid app import '{import_path}'. Expected '<module>:<attribute>'.")
    return module_name, app_name


def load_openapi(spec: ServiceSpec) -> dict:
    for key, value in spec.env.items():
        os.environ.setdefault(key, value)

    ensure_contract_runtime_files()
    os.chdir(spec.project_dir)
    src_dir = spec.project_dir / "src"
    for path in (src_dir, spec.project_dir):
        if path.exists():
            sys.path.insert(0, str(path))

    module_name, app_name = parse_app_import(spec.app_import)
    module = importlib.import_module(module_name)
    app = getattr(module, app_name)
    schema = app.openapi()
    if not isinstance(schema, dict):
        raise TypeError(f"{spec.app_import} returned a non-object OpenAPI schema")
    return schema


def export_schema(service: str, output: Path) -> None:
    if service not in SERVICES:
        valid = ", ".join(sorted(SERVICES))
        raise ValueError(f"Unknown service '{service}'. Valid services: {valid}")

    output = output if output.is_absolute() else Path.cwd() / output
    schema = load_openapi(SERVICES[service])
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(schema, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Export a service OpenAPI schema.")
    parser.add_argument("--service", required=True, choices=sorted(SERVICES))
    parser.add_argument("--output", required=True, type=Path)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    export_schema(args.service, args.output)
    print(f"Exported {args.service} OpenAPI schema to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
