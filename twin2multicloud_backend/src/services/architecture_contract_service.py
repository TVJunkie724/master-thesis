"""Read-only architecture-profile contract validation service.

Pydantic first establishes a bounded typed read boundary; the generated
validator enforces the full schema and semantic contract used by the active
profile APIs and persistence services.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType
from typing import Any, Iterable, Mapping

from pydantic import ConfigDict, RootModel


CONTRACT_BUNDLE_ROOT = (
    Path(__file__).resolve().parents[1]
    / "contracts"
    / "generated"
    / "architecture-profiles"
)
CONTRACT_ROOT = CONTRACT_BUNDLE_ROOT / "v2"


def _load_runtime(version: str) -> ModuleType:
    root = CONTRACT_BUNDLE_ROOT / version
    path = root / "runtime.py"
    module_name = f"_management_architecture_profile_contract_runtime_{version}"
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


_runtime = _load_runtime("v2")
ValidatedContract = _runtime.ValidatedContract


class ContractError(ValueError):
    """Version-neutral architecture-contract validation failure."""

    def __init__(self, code: str, path: str, message: str) -> None:
        super().__init__(message.replace("\n", " ")[:400])
        self.code = code
        self.path = path[:240]


def _translate(exc: Exception) -> ContractError:
    return ContractError(
        str(getattr(exc, "code", "ARCH_SCHEMA_INVALID")),
        str(getattr(exc, "path", "$")),
        str(exc),
    )


def calculate_digest(document: Mapping[str, Any]) -> str:
    """Calculate an architecture digest with its matching runtime."""

    return str(_runtime.calculate_digest(document))


def calculate_resolution_id(document: Mapping[str, Any]) -> str:
    """Calculate a resolution ID with its matching runtime."""

    return str(_runtime.calculate_resolution_id(document))


def canonical_json(value: object) -> str:
    """Use the active v2 contract's canonical set semantics."""

    return str(_runtime.canonical_json(value))


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
        linked = tuple(linked_documents)
        try:
            return _runtime.validate_document(
                typed.root,
                bundle_root=CONTRACT_ROOT,
                linked_documents=linked,
                logger=logger,
                correlation_id=correlation_id,
            )
        except _runtime.ContractError as exc:
            raise _translate(exc) from exc

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
        try:
            return tuple(_runtime.validate_bundle(typed, bundle_root=CONTRACT_ROOT))
        except _runtime.ContractError as exc:
            raise _translate(exc) from exc
