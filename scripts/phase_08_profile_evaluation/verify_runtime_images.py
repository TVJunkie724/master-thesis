#!/usr/bin/env python3
"""Verify the locally built evaluation runtime images against frozen digests."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
from typing import Mapping


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = Path(__file__).with_name("evaluation_config.json")
COMPOSE_FILE = REPOSITORY_ROOT / "compose.yaml"
SERVICE_NAMES = {
    "optimizer": "2twin2clouds",
    "management-api": "management-api",
    "deployer": "3cloud-deployer",
    "docs": "docs",
}


def configured_digests(config_path: Path = CONFIG_PATH) -> dict[str, str]:
    config = json.loads(config_path.read_text(encoding="utf-8"))
    rows = config["runtime"]["container_images"]
    result = {row["service"]: row["digest"] for row in rows}
    if set(result) != set(SERVICE_NAMES):
        raise AssertionError(
            f"runtime image service drift: expected={sorted(SERVICE_NAMES)}, "
            f"actual={sorted(result)}"
        )
    return result


def compose_image_names(project: str) -> dict[str, str]:
    result = subprocess.run(
        [
            "docker",
            "compose",
            "-p",
            project,
            "-f",
            str(COMPOSE_FILE),
            "--profile",
            "docs",
            "config",
            "--format",
            "json",
        ],
        cwd=REPOSITORY_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    compose = json.loads(result.stdout)
    services = compose["services"]
    return {
        logical_name: services[compose_name].get("image") or f"{project}-{compose_name}"
        for logical_name, compose_name in SERVICE_NAMES.items()
    }


def local_image_digests(image_names: Mapping[str, str]) -> dict[str, str]:
    result: dict[str, str] = {}
    for service, image_name in image_names.items():
        inspected = subprocess.run(
            ["docker", "image", "inspect", image_name, "--format", "{{.Id}}"],
            cwd=REPOSITORY_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        result[service] = inspected.stdout.strip()
    return result


def compare_digests(expected: Mapping[str, str], actual: Mapping[str, str]) -> None:
    if dict(expected) != dict(actual):
        mismatches = {
            service: {"expected": expected.get(service), "actual": actual.get(service)}
            for service in sorted(set(expected) | set(actual))
            if expected.get(service) != actual.get(service)
        }
        raise AssertionError(f"runtime image digest drift: {mismatches}")


def verify(project: str) -> None:
    expected = configured_digests()
    actual = local_image_digests(compose_image_names(project))
    compare_digests(expected, actual)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    verify(args.project)
    print("Phase 8 evaluation runtime images: verified")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AssertionError, KeyError, OSError, subprocess.SubprocessError) as exc:
        print(f"Phase 8 runtime image verification failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
