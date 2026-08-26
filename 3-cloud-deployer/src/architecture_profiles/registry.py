"""Fixed-path, immutable Six-layer definition registry for the Deployer."""

from __future__ import annotations

import json
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping

from . import contracts


DEFINITIONS_ROOT = contracts.CONTRACT_ROOT.parent / "definitions"
_PROFILE_DEFINITIONS = {
    ("six-layer-eventing", "1"): ("six-layer-eventing", "six-layer-eventing"),
}


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

    def __init__(
        self,
        *,
        profile_id: str = "six-layer-eventing",
        profile_version: str = "1",
    ) -> None:
        definition = _PROFILE_DEFINITIONS.get((profile_id, profile_version))
        if definition is None:
            raise contracts.ContractError(
                "ARCH_PROFILE_UNAVAILABLE",
                "architecture_profile_ref",
                "Architecture profile reference is unsupported",
            )
        catalog_family, provider_profile_family = definition
        profile = _read(
            DEFINITIONS_ROOT
            / "profiles"
            / profile_id
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
                / provider_profile_family
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
