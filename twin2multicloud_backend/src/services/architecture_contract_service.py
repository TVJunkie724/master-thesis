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


CONTRACT_BUNDLE_ROOT = (
    Path(__file__).resolve().parents[1]
    / "contracts"
    / "generated"
    / "architecture-profiles"
)
CONTRACT_ROOT = CONTRACT_BUNDLE_ROOT / "v1"


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


_runtimes = {version: _load_runtime(version) for version in ("v1", "v2")}
ValidatedContract = _runtimes["v1"].ValidatedContract
calculate_digest = _runtimes["v1"].calculate_digest
calculate_resolution_id = _runtimes["v1"].calculate_resolution_id
canonical_json = _runtimes["v1"].canonical_json


class ContractError(ValueError):
    """Version-neutral architecture-contract validation failure."""

    def __init__(self, code: str, path: str, message: str) -> None:
        super().__init__(message.replace("\n", " ")[:400])
        self.code = code
        self.path = path[:240]


def _version(document: Mapping[str, Any]) -> str:
    schema_version = str(document.get("schema_version", ""))
    if (
        schema_version == "architecture-profile.v2"
        and str(document.get("profile_version", "")) != "2"
    ):
        return "v1"
    if schema_version.endswith(".v2"):
        return "v2"
    return "v1"


def _translate(exc: Exception) -> ContractError:
    return ContractError(
        str(getattr(exc, "code", "ARCH_SCHEMA_INVALID")),
        str(getattr(exc, "path", "$")),
        str(exc),
    )


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
        version = _version(typed.root)
        runtime = _runtimes[version]
        linked = tuple(item for item in linked_documents if _version(item) == version)
        try:
            return runtime.validate_document(
                typed.root,
                bundle_root=CONTRACT_BUNDLE_ROOT / version,
                linked_documents=linked,
                logger=logger,
                correlation_id=correlation_id,
            )
        except runtime.ContractError as exc:
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
        validated: list[Any] = []
        for version in ("v1", "v2"):
            selected = tuple(item for item in typed if _version(item) == version)
            if not selected:
                continue
            runtime = _runtimes[version]
            try:
                validated.extend(
                    runtime.validate_bundle(
                        selected,
                        bundle_root=CONTRACT_BUNDLE_ROOT / version,
                    )
                )
            except runtime.ContractError as exc:
                raise _translate(exc) from exc
        return tuple(validated)
