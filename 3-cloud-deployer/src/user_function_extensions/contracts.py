"""Load the generated canonical user-function v1 runtime."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
from types import ModuleType


CONTRACT_ROOT = (
    Path(__file__).resolve().parents[1]
    / "contracts"
    / "generated"
    / "user-function-extension"
    / "v1"
)


def load_runtime() -> ModuleType:
    module_name = "_deployer_user_function_extension_runtime"
    existing = sys.modules.get(module_name)
    if existing is not None:
        return existing
    path = CONTRACT_ROOT / "runtime.py"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load generated extension contract: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


runtime = load_runtime()
ExtensionContractError = runtime.ExtensionContractError
