"""Immutable architecture-profile contract reader for the Deployer.

Phase 8.2 validates only. Terraform and package execution remain unchanged.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType
from typing import Any, Iterable, Mapping


CONTRACT_ROOT = (
    Path(__file__).resolve().parents[1]
    / "contracts"
    / "generated"
    / "architecture-profiles"
    / "v1"
)


def _load_runtime() -> ModuleType:
    path = CONTRACT_ROOT / "runtime.py"
    module_name = "_deployer_architecture_profile_contract_runtime"
    existing = sys.modules.get(module_name)
    if existing is not None:
        return existing
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load generated architecture contract: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


_runtime = _load_runtime()
ContractError = _runtime.ContractError
ValidatedContract = _runtime.ValidatedContract
calculate_digest = _runtime.calculate_digest
canonical_json = _runtime.canonical_json


def read_contract(
    document: Mapping[str, Any],
    *,
    linked_documents: Iterable[Mapping[str, Any]] = (),
    logger: Any | None = None,
    correlation_id: str | None = None,
) -> Any:
    """Validate a document and return the generated immutable read model."""
    return _runtime.validate_document(
        document,
        bundle_root=CONTRACT_ROOT,
        linked_documents=linked_documents,
        logger=logger,
        correlation_id=correlation_id,
    )


def read_contract_file(
    path: Path,
    *,
    linked_documents: Iterable[Mapping[str, Any]] = (),
    logger: Any | None = None,
    correlation_id: str | None = None,
) -> Any:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ContractError(
            "ARCH_SCHEMA_INVALID",
            "$",
            "Architecture contract must contain an object",
        )
    return read_contract(
        payload,
        linked_documents=linked_documents,
        logger=logger,
        correlation_id=correlation_id,
    )


def read_contract_bundle(
    documents: Iterable[Mapping[str, Any]],
) -> tuple[Any, ...]:
    return _runtime.validate_bundle(documents, bundle_root=CONTRACT_ROOT)
