"""Typed lookup facade over the immutable deployment component catalog."""

from __future__ import annotations

from types import MappingProxyType
from typing import Any, Mapping

from . import contracts
from .registry import ArchitectureProfileRegistry


class DeploymentComponentCatalog:
    def __init__(self, registry: ArchitectureProfileRegistry | None = None) -> None:
        document = (registry or ArchitectureProfileRegistry()).catalog
        self._components = MappingProxyType(
            {item["deployment_component_id"]: item for item in document["components"]}
        )
        self._edges = MappingProxyType(
            {
                item["edge_implementation_id"]: item
                for item in document["edge_implementations"]
            }
        )
        self._artifacts = MappingProxyType(
            {item["artifact_id"]: item for item in document["package_artifacts"]}
        )

    @property
    def components(self) -> Mapping[str, Mapping[str, Any]]:
        return self._components

    @property
    def edges(self) -> Mapping[str, Mapping[str, Any]]:
        return self._edges

    @property
    def artifacts(self) -> Mapping[str, Mapping[str, Any]]:
        return self._artifacts

    def component(self, component_id: str) -> Mapping[str, Any]:
        try:
            return self._components[component_id]
        except KeyError as exc:
            raise contracts.ContractError(
                "ARCH_COMPONENT_UNAVAILABLE",
                "deployment_component_id",
                "Unknown deployment component",
            ) from exc

    def edge(self, edge_id: str) -> Mapping[str, Any]:
        try:
            return self._edges[edge_id]
        except KeyError as exc:
            raise contracts.ContractError(
                "ARCH_EDGE_UNAVAILABLE",
                "edge_implementation_id",
                "Unknown edge implementation",
            ) from exc
