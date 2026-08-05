"""Fixed-path, immutable Phase 8.3 definition registry for the Deployer."""

from __future__ import annotations

import json
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping

from . import contracts


DEFINITIONS_ROOT = contracts.CONTRACT_ROOT.parent / "definitions"


def _read(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise contracts.ContractError(
            "ARCH_SCHEMA_INVALID", "$", "Architecture definition must be an object"
        )
    return payload


def _freeze(value: Any) -> Any:
    if isinstance(value, dict):
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple(_freeze(item) for item in value)
    return value


class ArchitectureProfileRegistry:
    """Load definitions without compiling Terraform or building packages."""

    def __init__(self, *, profile_version: str = "1") -> None:
        if profile_version not in {"1", "2"}:
            raise contracts.ContractError(
                "ARCH_PROFILE_UNAVAILABLE",
                "architecture_profile_ref.version",
                "Architecture profile version is unsupported",
            )
        catalog_family = "baseline" if profile_version == "1" else "complete-service"
        profile = _read(
            DEFINITIONS_ROOT
            / "profiles"
            / "five-layer-baseline"
            / profile_version
            / "profile.json"
        )
        catalog = _read(
            DEFINITIONS_ROOT
            / "component-catalogs"
            / catalog_family
            / "1"
            / "catalog.json"
        )
        providers = {
            provider: _read(
                DEFINITIONS_ROOT
                / "provider-implementations"
                / "five-layer-baseline"
                / profile_version
                / provider
                / "1.json"
            )
            for provider in ("aws", "azure", "gcp")
        }
        documents = (profile, *providers.values(), catalog)
        contracts.read_contract_bundle(documents)
        self._profile = _freeze(
            contracts.read_contract(profile, linked_documents=documents).document
        )
        self._catalog = _freeze(
            contracts.read_contract(catalog, linked_documents=documents).document
        )
        self._providers = MappingProxyType(
            {
                provider: _freeze(
                    contracts.read_contract(
                        document, linked_documents=documents
                    ).document
                )
                for provider, document in providers.items()
            }
        )

    @property
    def profile(self) -> Mapping[str, Any]:
        return self._profile

    @property
    def catalog(self) -> Mapping[str, Any]:
        return self._catalog

    @property
    def providers(self) -> Mapping[str, Mapping[str, Any]]:
        return self._providers
