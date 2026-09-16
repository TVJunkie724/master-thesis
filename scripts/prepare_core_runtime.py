"""Prepare real packages for one local Core smoke test; never deploy or publish.

Uses the existing validated, provider-independent processor example, not the
synthetic package references used by Terraform mock plans. Account bindings,
published image digests, approval and execution remain separate prerequisites.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path

from scripts.prepare_core_evaluation import ROOT, materialize
from src.core.secure_files import atomic_write_private_bytes
from src.providers.terraform.package_builders.aws_eventing import build_aws_eventing_app
from src.providers.terraform.package_builders.aws_six_layer import (
    build_aws_six_layer_domain_app,
    build_aws_six_layer_storage_mover_context,
)
from src.providers.terraform.package_builders.azure_six_layer import (
    build_azure_six_layer_graph_apps,
)
from src.providers.terraform.package_builders.azure_six_layer_container import (
    build_azure_six_layer_storage_mover_context,
)
from src.providers.terraform.package_builders.gcp_six_layer import (
    build_gcp_six_layer_container_contexts,
    build_gcp_six_layer_extension_container_context,
)
from src.user_function_extensions.package_builder import build_provider_package


def prepare(provider: str, output: Path) -> dict:
    if provider not in ("aws", "azure", "gcp"):
        raise ValueError("Only the three local Core baselines are supported")
    output.mkdir(parents=True, exist_ok=False)
    values = materialize(f"core-small-local-{provider}")["tfvars"]
    example = ROOT / "contracts/user-function-extension/v1/examples"
    manifest = json.loads((example / "valid-artifact.json").read_text())
    files = {
        path.name: path.read_text()
        for path in (example / "source/valid").iterdir()
        if path.is_file()
    }
    package, evidence = build_provider_package(
        manifest=manifest, files=files, provider=provider
    )
    extension = output / ".build" / provider / "core-processor.zip"
    atomic_write_private_bytes(extension, package)
    atomic_write_private_bytes(
        output / "processor-package-evidence.json",
        (json.dumps(asdict(evidence), indent=2) + "\n").encode(),
    )
    config = {
        "config.json": {"digital_twin_name": values["digital_twin_name"]},
        "config_events.json": [],
        "config_iot_devices.json": [],
        "config_optimization.json": {"inputParamsUsed": {}},
    }
    for name, value in config.items():
        atomic_write_private_bytes(
            output / name, (json.dumps(value, indent=2) + "\n").encode()
        )
    if provider == "aws":
        build_aws_six_layer_domain_app(output)
        build_aws_eventing_app(output)
        build_aws_six_layer_storage_mover_context(output)
    elif provider == "azure":
        build_azure_six_layer_graph_apps(output, ("six-layer-domain", "six-layer-eventing"))
        build_azure_six_layer_storage_mover_context(output)
    else:
        build_gcp_six_layer_container_contexts(
            output, ("six-layer-domain", "six-layer-eventing")
        )
        build_gcp_six_layer_extension_container_context(output, extension)
    values["project_path"] = str(output.resolve())
    values["validated_extension_packages"] = [{
        key: getattr(evidence, key)
        for key in (
            "slot_id", "slot_version", "artifact_id", "artifact_digest",
            "package_digest", "adapter_id", "adapter_version",
        )
    } | {"package_path": str(extension.resolve())}]
    atomic_write_private_bytes(
        output / "runtime.tfvars.json", (json.dumps(values, indent=2) + "\n").encode()
    )
    return values


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("provider", choices=("aws", "azure", "gcp"))
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    prepare(args.provider, args.output_dir)
    print("Core runtime packages prepared locally; no device, image publication or deployment created.")


if __name__ == "__main__":
    main()
