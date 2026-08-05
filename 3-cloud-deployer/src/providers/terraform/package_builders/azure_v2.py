"""Additive Five-layer v2 Azure Function-App package construction."""

from __future__ import annotations

from pathlib import Path
from typing import Collection, Dict

from src.providers.terraform.package_builders.azure import _create_azure_function_zip


PROVIDERS_ROOT = Path(__file__).resolve().parents[2]
AZURE_V2_GRAPH_APPS = frozenset({"five-layer-v2"})


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
        _create_azure_function_zip(source, output)
        packages[f"azure_{name}"] = output
    return packages


__all__ = [
    "AZURE_V2_GRAPH_APPS",
    "azure_v2_graph_package_ids",
    "build_azure_v2_graph_apps",
]
