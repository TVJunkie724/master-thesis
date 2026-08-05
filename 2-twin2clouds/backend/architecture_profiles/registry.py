"""Immutable Phase 8.3 architecture definition registry."""

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
        return MappingProxyType(
            {key: _freeze(item) for key, item in value.items()}
        )
    if isinstance(value, list):
        return tuple(_freeze(item) for item in value)
    return value


class ArchitectureProfileRegistry:
    """Load and expose one immutable, validated profile/catalog bundle."""

    def __init__(
        self,
        *,
        profile: Mapping[str, Any] | None = None,
        catalog: Mapping[str, Any] | None = None,
        providers: Mapping[str, Mapping[str, Any]] | None = None,
        profile_version: str = "1",
    ) -> None:
        if profile_version not in {"1", "2"}:
            raise ValueError("Unsupported five-layer profile version")
        catalog_id = "baseline" if profile_version == "1" else "complete-service"
        profile = dict(profile) if profile is not None else _read(
            DEFINITIONS_ROOT
            / "profiles"
            / "five-layer-baseline"
            / profile_version
            / "profile.json"
        )
        catalog = dict(catalog) if catalog is not None else _read(
            DEFINITIONS_ROOT
            / "component-catalogs"
            / catalog_id
            / "1"
            / "catalog.json"
        )
        providers = (
            {
                provider: dict(document)
                for provider, document in providers.items()
            }
            if providers is not None
            else {
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
        )
        if set(providers) != {
            document["provider"] for document in providers.values()
        }:
            raise contracts.ContractError(
                "ARCH_REFERENCE_UNRESOLVED",
                "providers",
                "Provider registry keys must match provider profile identities",
            )
        documents = (profile, *providers.values(), catalog)
        contracts.read_contract_bundle(documents)
        self._profile = _freeze(
            contracts.read_contract(
                profile, linked_documents=documents
            ).document
        )
        self._catalog = _freeze(
            contracts.read_contract(
                catalog, linked_documents=documents
            ).document
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

    def provider(self, provider: str) -> Mapping[str, Any]:
        try:
            return self._providers[provider]
        except KeyError as exc:
            raise contracts.ContractError(
                "ARCH_COMPONENT_UNAVAILABLE",
                "provider",
                "Unknown architecture provider",
            ) from exc

    def require_profile(
        self,
        *,
        profile_id: str,
        profile_version: str,
        content_digest: str,
    ) -> Mapping[str, Any]:
        """Resolve the sole profile by an exact immutable reference."""

        if (
            profile_id != self._profile["profile_id"]
            or profile_version != self._profile["profile_version"]
        ):
            raise contracts.ContractError(
                "ARCH_PROFILE_NOT_FOUND",
                "architectureProfile",
                "Unknown architecture profile reference",
            )
        if content_digest != self._profile["content_digest"]:
            raise contracts.ContractError(
                "ARCH_PROFILE_DIGEST_MISMATCH",
                "architectureProfile.contentDigest",
                "Architecture profile digest differs from the repository definition",
            )
        return self._profile
