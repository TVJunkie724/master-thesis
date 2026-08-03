"""Typed graph-derived Terraform input models."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping


TerraformScalar = str | int | bool


@dataclass(frozen=True, slots=True)
class TerraformInputSet:
    values: Mapping[str, TerraformScalar]
    graph_digest: str
    specification_digest: str

    @classmethod
    def create(
        cls,
        values: dict[str, TerraformScalar],
        *,
        graph_digest: str,
        specification_digest: str,
    ) -> "TerraformInputSet":
        return cls(
            values=MappingProxyType(dict(sorted(values.items()))),
            graph_digest=graph_digest,
            specification_digest=specification_digest,
        )
