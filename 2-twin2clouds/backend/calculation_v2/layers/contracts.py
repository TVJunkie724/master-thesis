"""Shared contracts for provider layer calculators."""

from __future__ import annotations

from dataclasses import dataclass, field
from math import isfinite
from typing import Any, ClassVar, Mapping, Protocol, runtime_checkable


SUPPORTED_LAYER_KEYS = frozenset(
    {"L1", "L2", "L3_hot", "L3_cool", "L3_archive", "L4", "L5"}
)


@dataclass(frozen=True, slots=True)
class LayerResult:
    """Canonical result returned by every provider layer calculator."""

    provider: str
    layer: str
    total_cost: float
    data_size_gb: float = 0.0
    messages: float = 0.0
    components: Mapping[str, float] = field(default_factory=dict)
    supported: bool = True
    unsupported_reason: str | None = None

    def __post_init__(self) -> None:
        if self.layer not in SUPPORTED_LAYER_KEYS:
            raise ValueError(f"Unsupported layer result key: {self.layer}")
        for name, value in {
            "total_cost": self.total_cost,
            "data_size_gb": self.data_size_gb,
            "messages": self.messages,
            **dict(self.components),
        }.items():
            if not isinstance(value, (int, float)) or not isfinite(float(value)):
                raise ValueError(f"Layer result value {name!r} must be finite")
            if value < 0:
                raise ValueError(f"Layer result value {name!r} must be non-negative")
        if self.supported and self.unsupported_reason:
            raise ValueError("Supported layer results cannot declare an unsupported reason")
        if not self.supported and not self.unsupported_reason:
            raise ValueError("Unsupported layer results require an explicit reason")


@runtime_checkable
class LayerCalculatorSet(Protocol):
    """Structural contract implemented by every provider calculator set.

    Provider methods intentionally accept different domain parameters. The protocol
    standardizes their operation names and result type while preserving those
    provider-specific input contracts.
    """

    provider: ClassVar[str]
    supported_layers: ClassVar[frozenset[str]]

    def calculate_l1_cost(self, *args: Any, **kwargs: Any) -> LayerResult: ...

    def calculate_l2_cost(self, *args: Any, **kwargs: Any) -> LayerResult: ...

    def calculate_l3_hot_cost(self, *args: Any, **kwargs: Any) -> LayerResult: ...

    def calculate_l3_cool_cost(self, *args: Any, **kwargs: Any) -> LayerResult: ...

    def calculate_l3_archive_cost(self, *args: Any, **kwargs: Any) -> LayerResult: ...

    def calculate_l4_cost(self, *args: Any, **kwargs: Any) -> LayerResult: ...

    def calculate_l5_cost(self, *args: Any, **kwargs: Any) -> LayerResult: ...

    def calculate_glue_cost(self, messages: float, pricing: dict) -> float:
        """Calculate the provider's cross-cloud glue function cost."""
