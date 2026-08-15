"""Additive Five-layer v2 Azure Function-App package construction."""

from __future__ import annotations

from pathlib import Path
from typing import Collection, Dict

from src.core.deterministic_zip import atomic_zip_archive, write_zip_file
from src.providers.terraform.package_builders.common import _should_include_file


PROVIDERS_ROOT = Path(__file__).resolve().parents[2]
BRIDGE_RUNTIME_ROOT = PROVIDERS_ROOT.parent / "runtime" / "eventing"
SIX_LAYER_BRIDGE_RUNTIME_ROOT = (
    PROVIDERS_ROOT.parent / "runtime" / "six_layer_eventing"
)
AZURE_V2_GRAPH_APPS = frozenset(
    {"five-layer-v2", "six-layer-domain", "six-layer-eventing"}
)


def _create_azure_v2_function_zip(source: Path, output: Path) -> None:
    runtime_root = (
        BRIDGE_RUNTIME_ROOT
        if source.name == "five-layer-v2"
        else SIX_LAYER_BRIDGE_RUNTIME_ROOT
    )
    bridge_core_source = runtime_root / "bridge_core.py"
    if not bridge_core_source.is_file() or bridge_core_source.is_symlink():
        raise ValueError("Shared Phase 8 bridge runtime is unavailable")
    with atomic_zip_archive(output) as archive:
        for path in sorted(source.rglob("*")):
            relative = path.relative_to(source)
            if (
                path.is_file()
                and relative.parts[0] != "storage-mover"
                and _should_include_file(path)
            ):
                write_zip_file(archive, path, relative)
        write_zip_file(archive, bridge_core_source, "bridge_core.py")
        for path in sorted(runtime_root.rglob("*")):
            if path.is_file() and _should_include_file(path):
                write_zip_file(
                    archive,
                    path,
                    Path("phase8_eventing") / path.relative_to(runtime_root),
                )


def azure_v2_graph_package_ids(
    selected_function_names: Collection[str],
) -> set[str]:
    """Return v2 package IDs without changing the frozen v1 bundle builder."""

    selected = set(selected_function_names)
    return {f"azure_{name}" for name in selected.intersection(AZURE_V2_GRAPH_APPS)}


def build_azure_v2_graph_apps(
    project_path: Path,
    selected_function_names: Collection[str],
) -> Dict[str, Path]:
    """Build selected standalone v2 Function Apps deterministically."""

    selected = set(selected_function_names)
    unknown = selected - AZURE_V2_GRAPH_APPS
    if unknown:
        raise ValueError("Selected Azure v2 app has no package owner")
    packages: Dict[str, Path] = {}
    source_root = PROVIDERS_ROOT / "azure" / "azure_functions"
    for name in sorted(selected):
        source = source_root / name
        if not source.is_dir():
            raise ValueError("Selected Azure v2 app source is unavailable")
        output = project_path / ".build" / "azure" / f"{name}.zip"
        output.parent.mkdir(parents=True, exist_ok=True)
        _create_azure_v2_function_zip(source, output)
        packages[f"azure_{name}"] = output
    return packages


__all__ = [
    "AZURE_V2_GRAPH_APPS",
    "azure_v2_graph_package_ids",
    "build_azure_v2_graph_apps",
]
