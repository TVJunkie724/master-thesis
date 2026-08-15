"""Code-backed extractors for Phase 8.0 inventory reconciliation."""

from __future__ import annotations

import ast
import importlib
import json
import os
from pathlib import Path
import re
import subprocess
from typing import Any


PROVIDERS = ("aws", "azure", "gcp")
PROVIDER_HANDLER = {
    "aws": "lambda_function.py",
    "azure": "function_app.py",
    "gcp": "main.py",
}
PROVIDER_FUNCTION_ROOT = {
    "aws": "src/providers/aws/lambda_functions",
    "azure": "src/providers/azure/azure_functions",
    "gcp": "src/providers/gcp/cloud_functions",
}
OPTIMIZER_SLOT_ORDER = (
    "l1_ingestion",
    "l2_processing",
    "l3_hot_storage",
    "l3_cool_storage",
    "l3_archive_storage",
    "l4_twin_state",
    "l5_visualization",
)
BASELINE_EDGES = (
    ("l1-to-l2", "l1_ingestion", "l2_processing"),
    ("l2-to-l3-hot", "l2_processing", "l3_hot_storage"),
    ("l3-hot-to-l3-cool", "l3_hot_storage", "l3_cool_storage"),
    ("l3-cool-to-l3-archive", "l3_cool_storage", "l3_archive_storage"),
    ("l3-hot-to-l4", "l3_hot_storage", "l4_twin_state"),
    ("l4-to-l5", "l4_twin_state", "l5_visualization"),
)
MANAGEMENT_CHEAPEST_CONSUMERS = {
    "twin2multicloud_backend/src/api/routes/twin_operations.py": (
        "cheapest_l1",
        "cheapest_l2",
        "cheapest_l3_hot",
    ),
    "twin2multicloud_backend/src/models/optimizer_config.py": (
        "cheapest_l1",
        "cheapest_l2",
        "cheapest_l3_archive",
        "cheapest_l3_cool",
        "cheapest_l3_hot",
        "cheapest_l4",
        "cheapest_l5",
    ),
    "twin2multicloud_backend/src/services/cost_calculation_run_service.py": (
        "cheapest_l1",
        "cheapest_l2",
        "cheapest_l3_archive",
        "cheapest_l3_cool",
        "cheapest_l3_hot",
        "cheapest_l4",
        "cheapest_l5",
    ),
    "twin2multicloud_backend/src/services/credential_resolution_service.py": (
        "cheapest_l1",
        "cheapest_l2",
        "cheapest_l3_archive",
        "cheapest_l3_cool",
        "cheapest_l3_hot",
        "cheapest_l4",
        "cheapest_l5",
    ),
    "twin2multicloud_backend/src/services/optimizer_config_projection.py": (
        "cheapest_l1",
        "cheapest_l2",
        "cheapest_l3_archive",
        "cheapest_l3_cool",
        "cheapest_l3_hot",
        "cheapest_l4",
        "cheapest_l5",
    ),
    "twin2multicloud_backend/src/services/resolved_architecture_service.py": (
        "cheapest_l1",
        "cheapest_l2",
        "cheapest_l3_archive",
        "cheapest_l3_cool",
        "cheapest_l3_hot",
        "cheapest_l4",
        "cheapest_l5",
    ),
}
MANAGEMENT_CHEAPEST_EXPIRY = {
    "twin2multicloud_backend/src/models/optimizer_config.py": "retained-history",
    "twin2multicloud_backend/src/services/resolved_architecture_service.py": (
        "retained-history"
    ),
    "twin2multicloud_backend/src/services/cost_calculation_run_service.py": (
        "retained-history"
    ),
    "twin2multicloud_backend/src/services/credential_resolution_service.py": "8.7",
    "twin2multicloud_backend/src/api/routes/twin_operations.py": "8.7",
    "twin2multicloud_backend/src/services/optimizer_config_projection.py": "8.7",
}
PROVIDER_KEY_CONSUMERS = {
    "twin2multicloud_backend/src/services/deployer_config_validation_service.py": (
        "layer_4_provider",
        "layer_5_provider",
    ),
    "twin2multicloud_backend/src/services/deployment_service.py": (
        "layer_1_provider",
        "layer_2_provider",
        "layer_3_archive_provider",
        "layer_3_cold_provider",
        "layer_3_hot_provider",
        "layer_4_provider",
        "layer_5_provider",
    ),
    "twin2multicloud_backend/src/services/twin_export_service.py": (
        "layer_1_provider",
        "layer_2_provider",
        "layer_3_archive_provider",
        "layer_3_cold_provider",
        "layer_3_hot_provider",
        "layer_4_provider",
        "layer_5_provider",
    ),
    (
        "twin2multicloud_flutter/lib/features/configuration_workspace/"
        "presentation/deployment/deployment_config_section.dart"
    ): (
        "layer_1_provider",
        "layer_2_provider",
        "layer_3_archive_provider",
        "layer_3_cold_provider",
        "layer_3_hot_provider",
        "layer_4_provider",
        "layer_5_provider",
    ),
    (
        "twin2multicloud_flutter/lib/widgets/file_inputs/"
        "config_visualization_block.dart"
    ): (
        "layer_1_provider",
        "layer_2_provider",
        "layer_3_archive_provider",
        "layer_3_cold_provider",
        "layer_3_hot_provider",
        "layer_4_provider",
        "layer_5_provider",
    ),
}
FIXED_SLOT_CONSUMERS = {
    "twin2multicloud_flutter/lib/models/architecture_path.dart": (
        "providerForSegment",
        "storageTierForSegment",
        "layerProviders",
    ),
    (
        "twin2multicloud_flutter/lib/widgets/architecture/architecture_service_map.dart"
    ): (
        "L1",
        "L2",
        "L3_hot",
        "L3_cool",
        "L3_archive",
        "L4",
        "L5",
    ),
    "twin2multicloud_flutter/lib/widgets/architecture_graph.dart": (
        "L1",
        "L2",
        "L3_hot",
        "L3_cool",
        "L3_archive",
        "L4",
        "L5",
    ),
    (
        "twin2multicloud_flutter/lib/features/configuration_workspace/"
        "presentation/deployment/deployment_layer_overview.dart"
    ): (
        "buildL1Layer",
        "buildL2Layer",
        "buildL3Layer",
        "buildL4Layer",
        "buildL5Layer",
    ),
}


class ExtractionError(RuntimeError):
    """Raised when a code-backed source cannot be reconstructed."""


def repository_root() -> Path:
    return Path(__file__).resolve().parents[2]


def deployer_container(root: Path | None = None) -> str:
    """Resolve the active Deployer container without assuming a Compose prefix."""

    configured = os.environ.get("ARCHITECTURE_INVENTORY_DEPLOYER_CONTAINER")
    if configured:
        return configured
    root = root or repository_root()
    completed = subprocess.run(
        ["docker", "compose", "ps", "-q", "3cloud-deployer"],
        cwd=root,
        capture_output=True,
        check=False,
        text=True,
        timeout=30,
    )
    container = completed.stdout.strip()
    if completed.returncode or not container:
        raise ExtractionError("Active 3cloud-deployer container could not be resolved")
    return container


def _docker_json(script: str) -> Any:
    command = [
        "docker",
        "exec",
        "-i",
        deployer_container(),
        "python",
        "-c",
        script,
    ]
    completed = subprocess.run(
        command,
        input="",
        capture_output=True,
        check=False,
        text=True,
        timeout=60,
    )
    if completed.returncode:
        detail = completed.stderr.strip().splitlines()
        bounded = detail[-1][:300] if detail else "deployer extraction failed"
        raise ExtractionError(bounded)
    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise ExtractionError("Deployer extractor returned invalid JSON") from exc


def extract_static_functions() -> list[dict[str, Any]]:
    """Load the live Function Registry inside the Deployer container."""

    try:
        module = importlib.import_module("src.function_registry")
    except ImportError:
        module = None
    if module is not None:
        return [
            {
                "name": item.name,
                "layer": item.layer.name,
                "providers": sorted(item.providers),
                "dir_name": item.get_dir_name(),
                "optional": item.is_optional,
                "boundary": list(item.boundary) if item.boundary else None,
                "target_provider_key": item.target_provider_key,
                "terraform_output_suffix": item.terraform_output_suffix,
            }
            for item in module.STATIC_FUNCTIONS
        ]
    script = r"""
import json
from src.function_registry import STATIC_FUNCTIONS
print(json.dumps([
    {
        "name": item.name,
        "layer": item.layer.name,
        "providers": sorted(item.providers),
        "dir_name": item.get_dir_name(),
        "optional": item.is_optional,
        "boundary": list(item.boundary) if item.boundary else None,
        "target_provider_key": item.target_provider_key,
        "terraform_output_suffix": item.terraform_output_suffix,
    }
    for item in STATIC_FUNCTIONS
], sort_keys=True))
"""
    return _docker_json(script)


def extract_terraform_objects() -> list[dict[str, Any]]:
    """Parse all deployer Terraform files with python-hcl2."""

    try:
        hcl2 = importlib.import_module("hcl2")
    except ImportError:
        hcl2 = None
    local_root = Path("/app/src/terraform")
    if hcl2 is not None and local_root.is_dir():
        return _parse_terraform_root(local_root, hcl2)
    script = r"""
import json
from pathlib import Path
import hcl2

records = []
for path in sorted(Path("/app/src/terraform").glob("*.tf")):
    with path.open(encoding="utf-8") as handle:
        document = hcl2.load(handle)
    relative = path.relative_to("/app").as_posix()
    for kind in ("resource", "data"):
        for block in document.get(kind, []):
            for type_name, names in block.items():
                if str(type_name).startswith("__"):
                    continue
                for name, body in names.items():
                    if str(name).startswith("__"):
                        continue
                    clean_type = str(type_name).strip('"')
                    clean_name = str(name).strip('"')
                    records.append({
                        "kind": kind,
                        "address": f"{kind}.{clean_type}.{clean_name}" if kind == "data" else f"{clean_type}.{clean_name}",
                        "path": relative,
                        "sensitive": bool(body.get("sensitive", False)) if isinstance(body, dict) else False,
                    })
    for kind in ("output", "module", "variable"):
        for block in document.get(kind, []):
            for name, body in block.items():
                if str(name).startswith("__"):
                    continue
                clean_name = str(name).strip('"')
                records.append({
                    "kind": kind,
                    "address": f"{kind}.{clean_name}",
                    "path": relative,
                    "sensitive": bool(body.get("sensitive", False)) if isinstance(body, dict) else False,
                })
    for block in document.get("locals", []):
        for name in block:
            if str(name).startswith("__"):
                continue
            clean_name = str(name).strip('"')
            records.append({
                "kind": "local",
                "address": f"local.{clean_name}",
                "path": relative,
                "sensitive": False,
            })
print(json.dumps(sorted(records, key=lambda item: (item["address"], item["path"])), sort_keys=True))
"""
    return _docker_json(script)


def _parse_terraform_root(terraform_root: Path, hcl2: Any) -> list[dict[str, Any]]:
    """Local equivalent of the container extractor, used by focused tests."""

    records: list[dict[str, Any]] = []
    for path in sorted(terraform_root.glob("*.tf")):
        with path.open(encoding="utf-8") as handle:
            document = hcl2.load(handle)
        relative = f"src/terraform/{path.name}"
        for kind in ("resource", "data"):
            for block in document.get(kind, []):
                for type_name, names in block.items():
                    if str(type_name).startswith("__"):
                        continue
                    for name, body in names.items():
                        if str(name).startswith("__"):
                            continue
                        clean_type = str(type_name).strip('"')
                        clean_name = str(name).strip('"')
                        address = (
                            f"data.{clean_type}.{clean_name}"
                            if kind == "data"
                            else f"{clean_type}.{clean_name}"
                        )
                        records.append(
                            {
                                "kind": kind,
                                "address": address,
                                "path": relative,
                                "sensitive": (
                                    bool(body.get("sensitive", False))
                                    if isinstance(body, dict)
                                    else False
                                ),
                            }
                        )
        for kind in ("output", "module", "variable"):
            for block in document.get(kind, []):
                for name, body in block.items():
                    if str(name).startswith("__"):
                        continue
                    records.append(
                        {
                            "kind": kind,
                            "address": f"{kind}.{str(name).strip(chr(34))}",
                            "path": relative,
                            "sensitive": (
                                bool(body.get("sensitive", False))
                                if isinstance(body, dict)
                                else False
                            ),
                        }
                    )
        for block in document.get("locals", []):
            for name in block:
                if str(name).startswith("__"):
                    continue
                records.append(
                    {
                        "kind": "local",
                        "address": f"local.{str(name).strip(chr(34))}",
                        "path": relative,
                        "sensitive": False,
                    }
                )
    return sorted(records, key=lambda item: (item["address"], item["path"]))


def extract_artifact_sources(root: Path | None = None) -> list[dict[str, Any]]:
    """Resolve static handlers from registry metadata and user template roots."""

    root = root or repository_root()
    deployer = root / "3-cloud-deployer"
    if not deployer.is_dir() and Path("/app/src").is_dir():
        deployer = Path("/app")
    records: list[dict[str, Any]] = []
    for function in extract_static_functions():
        for provider in function["providers"]:
            deployer_relative = (
                Path(PROVIDER_FUNCTION_ROOT[provider])
                / function["dir_name"]
                / PROVIDER_HANDLER[provider]
            )
            relative = Path("3-cloud-deployer") / deployer_relative
            records.append(
                {
                    "source_key": f"static:{provider}:{function['name']}",
                    "provider": provider,
                    "function_name": function["name"],
                    "path": relative.as_posix(),
                    "handler": PROVIDER_HANDLER[provider],
                    "exists": (deployer / deployer_relative).is_file(),
                }
            )
    registered_directories = {
        (item["provider"], Path(item["path"]).parent.name)
        for item in records
        if item["source_key"].startswith("static:")
    }
    for provider in PROVIDERS:
        provider_root = deployer / PROVIDER_FUNCTION_ROOT[provider]
        for handler in sorted(provider_root.glob(f"*/{PROVIDER_HANDLER[provider]}")):
            directory_name = handler.parent.name
            if (provider, directory_name) in registered_directories:
                continue
            role = (
                "user-package-base"
                if directory_name == "default-processor"
                else "registry-excluded-source"
            )
            records.append(
                {
                    "source_key": f"{role}:{provider}:{directory_name}",
                    "provider": provider,
                    "function_name": directory_name,
                    "path": (
                        Path("3-cloud-deployer") / handler.relative_to(deployer)
                    ).as_posix(),
                    "handler": PROVIDER_HANDLER[provider],
                    "exists": True,
                }
            )
    template_root = deployer / "templates/digital-twin/cloud_functions"
    for category in ("processors", "event_actions"):
        for directory in sorted((template_root / category).iterdir()):
            if not directory.is_dir():
                continue
            relative = (
                Path("3-cloud-deployer") / directory.relative_to(deployer)
            ).as_posix()
            records.append(
                {
                    "source_key": f"user-template:{category}:{directory.name}",
                    "provider": "platform",
                    "function_name": directory.name,
                    "path": relative,
                    "handler": "provider-selected user package",
                    "exists": True,
                }
            )
    return records


def extract_deployment_contract(root: Path | None = None) -> dict[str, Any]:
    """Load the generated cross-project deployment-dimension registry."""

    root = root or repository_root()
    path = (
        root
        / "contracts/resolved-deployment-specification/v1/deployment-dimensions.json"
    )
    contract = json.loads(path.read_text(encoding="utf-8"))
    return {
        "slots": contract["slots"],
        "slot_requirements": contract["slot_requirements"],
        "components": contract["components"],
        "cross_cloud_glue_policy": contract["cross_cloud_glue_policy"],
        "transition_runtime_policy": contract["transition_runtime_policy"],
    }


def extract_optimizer_shape(root: Path | None = None) -> dict[str, Any]:
    """Prove the seven slots and six baseline edges from Python AST literals."""

    root = root or repository_root()
    path = root / "2-twin2clouds/backend/calculation_v2/path_optimizer.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    layer_order: list[str] | None = None
    segment_ids: list[str] = []
    for node in ast.walk(tree):
        assignment_name = None
        assignment_value = None
        if isinstance(node, ast.Assign):
            targets = [
                target.id for target in node.targets if isinstance(target, ast.Name)
            ]
            if "LAYER_ORDER" in targets:
                assignment_name = "LAYER_ORDER"
                assignment_value = node.value
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            assignment_name = node.target.id
            assignment_value = node.value
        if assignment_name == "LAYER_ORDER" and isinstance(
            assignment_value, (ast.Tuple, ast.List)
        ):
            layer_order = [
                str(ast.literal_eval(item.elts[0]))
                for item in assignment_value.elts
                if isinstance(item, (ast.Tuple, ast.List)) and item.elts
            ]
        if isinstance(node, ast.Call):
            for keyword in node.keywords:
                if keyword.arg == "segment_id" and isinstance(
                    keyword.value, ast.Constant
                ):
                    segment_ids.append(str(keyword.value.value))
    expected_layers = ["L1", "L2", "L3_hot", "L3_cool", "L3_archive", "L4", "L5"]
    expected_segments = [
        "L1_to_L2",
        "L2_to_L3_hot",
        "L3_hot_to_L3_cool",
        "L3_cool_to_L3_archive",
        "L3_hot_to_L4",
        "L4_to_L5",
    ]
    if layer_order != expected_layers:
        raise ExtractionError(
            "Optimizer LAYER_ORDER no longer matches seven-slot baseline"
        )
    if segment_ids[:6] != expected_segments:
        raise ExtractionError(
            "Optimizer baseline edge literals no longer match six-edge baseline"
        )
    return {"layer_order": layer_order, "segment_ids": expected_segments}


ALLOWLISTED_ANCHORS = (
    *(
        {
            "owner": "management-api",
            "path": path,
            "anchors": anchors,
            "rationale": (
                "Read/write consumer of persisted seven-slot cheapest_l* fields."
            ),
            "expiry_phase": MANAGEMENT_CHEAPEST_EXPIRY.get(path, "8.6"),
        }
        for path, anchors in MANAGEMENT_CHEAPEST_CONSUMERS.items()
    ),
    *(
        {
            "owner": (
                "flutter"
                if path.startswith("twin2multicloud_flutter/")
                else "management-api"
            ),
            "path": path,
            "anchors": anchors,
            "rationale": (
                "Consumer of the fixed Management-to-Deployer provider-key projection."
            ),
            "expiry_phase": (
                "8.7" if path.startswith("twin2multicloud_flutter/") else "8.4"
            ),
        }
        for path, anchors in PROVIDER_KEY_CONSUMERS.items()
    ),
    *(
        {
            "owner": "flutter",
            "path": path,
            "anchors": anchors,
            "rationale": "Fixed seven-slot architecture presentation.",
            "expiry_phase": "8.7",
        }
        for path, anchors in FIXED_SLOT_CONSUMERS.items()
    ),
)


def _discover_pattern_consumers(
    root: Path,
    directories: tuple[str, ...],
    suffixes: set[str],
    pattern: str,
) -> set[str]:
    expression = re.compile(pattern)
    discovered: set[str] = set()
    for directory in directories:
        for path in (root / directory).rglob("*"):
            if path.suffix not in suffixes or not path.is_file():
                continue
            if expression.search(path.read_text(encoding="utf-8")):
                discovered.add(path.relative_to(root).as_posix())
    return discovered


def verify_allowlisted_anchors(root: Path | None = None) -> list[str]:
    """Fail closed when a declared fixed-field consumer moves or changes."""

    root = root or repository_root()
    actual_cheapest = _discover_pattern_consumers(
        root,
        ("twin2multicloud_backend/src",),
        {".py"},
        r"cheapest_l(?:1|2|3_hot|3_cool|3_archive|4|5)",
    )
    expected_cheapest = set(MANAGEMENT_CHEAPEST_CONSUMERS)
    actual_provider_keys = _discover_pattern_consumers(
        root,
        ("twin2multicloud_backend/src", "twin2multicloud_flutter/lib"),
        {".dart", ".py"},
        r"layer_(?:1|2|3_hot|3_cold|3_archive|4|5)_provider",
    )
    expected_provider_keys = set(PROVIDER_KEY_CONSUMERS)
    coverage_findings = sorted(
        {
            *(
                f"undeclared-cheapest-consumer:{path}"
                for path in actual_cheapest - expected_cheapest
            ),
            *(
                f"stale-cheapest-consumer:{path}"
                for path in expected_cheapest - actual_cheapest
            ),
            *(
                f"undeclared-provider-key-consumer:{path}"
                for path in actual_provider_keys - expected_provider_keys
            ),
            *(
                f"stale-provider-key-consumer:{path}"
                for path in expected_provider_keys - actual_provider_keys
            ),
        }
    )
    if coverage_findings:
        raise ExtractionError("; ".join(coverage_findings[:20]))

    verified: list[str] = []
    for entry in ALLOWLISTED_ANCHORS:
        text = (root / entry["path"]).read_text(encoding="utf-8")
        for anchor in entry["anchors"]:
            if anchor not in text:
                raise ExtractionError(
                    f"Allowlisted anchor missing: {entry['path']}#{anchor}"
                )
            verified.append(f"{entry['path']}#{anchor}")
    return sorted(verified)
