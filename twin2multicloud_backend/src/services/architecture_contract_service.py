"""Read-only architecture-profile contract service.

Phase 8.2 exposes no routes and persists nothing. Pydantic first establishes a
bounded typed read boundary; the generated validator enforces the full schema
and semantic contract.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType
from typing import Any, Iterable, Mapping

from pydantic import ConfigDict, RootModel


CONTRACT_ROOT = (
    Path(__file__).resolve().parents[1]
    / "contracts"
    / "generated"
    / "architecture-profiles"
    / "v1"
)


def _load_runtime() -> ModuleType:
    path = CONTRACT_ROOT / "runtime.py"
    module_name = "_management_architecture_profile_contract_runtime"
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


class ArchitectureContractReadModel(RootModel[dict[str, Any]]):
    """Frozen Pydantic transport model before semantic validation."""

    model_config = ConfigDict(frozen=True)


class ArchitectureContractService:
    """Validate shared fixtures without authoring runtime state."""

    @staticmethod
    def read(
        document: Mapping[str, Any],
        *,
        linked_documents: Iterable[Mapping[str, Any]] = (),
        logger: Any | None = None,
        correlation_id: str | None = None,
    ) -> Any:
        typed = ArchitectureContractReadModel.model_validate(dict(document))
        return _runtime.validate_document(
            typed.root,
            bundle_root=CONTRACT_ROOT,
            linked_documents=linked_documents,
            logger=logger,
            correlation_id=correlation_id,
        )

    @staticmethod
    def read_file(
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
        return ArchitectureContractService.read(
            payload,
            linked_documents=linked_documents,
            logger=logger,
            correlation_id=correlation_id,
        )

    @staticmethod
    def read_bundle(
        documents: Iterable[Mapping[str, Any]],
    ) -> tuple[Any, ...]:
        typed = tuple(
            ArchitectureContractReadModel.model_validate(dict(document)).root
            for document in documents
        )
        return _runtime.validate_bundle(typed, bundle_root=CONTRACT_ROOT)
