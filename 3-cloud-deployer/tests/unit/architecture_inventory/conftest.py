"""Shared access to the repository-level Phase 8.0 checker."""

from __future__ import annotations

import importlib
import os
from pathlib import Path
import sys

import pytest


def _repository_root() -> Path:
    configured = os.environ.get("ARCHITECTURE_INVENTORY_REPO_ROOT")
    candidates = [
        Path(configured) if configured else None,
        Path("/workspace"),
        Path(__file__).resolve().parents[4],
    ]
    for candidate in candidates:
        if (
            candidate is not None
            and (
                candidate / "contracts/architecture-inventory/v1/current-graph.json"
            ).is_file()
        ):
            return candidate
    raise RuntimeError(
        "Phase 8.0 repository artifacts are unavailable; set "
        "ARCHITECTURE_INVENTORY_REPO_ROOT"
    )


REPOSITORY_ROOT = _repository_root()
_SCRIPTS_PATH = str(REPOSITORY_ROOT / "scripts")
sys.path.insert(0, _SCRIPTS_PATH)
try:
    importlib.import_module("architecture_inventory")
finally:
    sys.path.remove(_SCRIPTS_PATH)


@pytest.fixture(scope="session")
def repository_root() -> Path:
    return REPOSITORY_ROOT
