"""Shared contracts for provider layer calculators."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from math import isfinite
from types import MappingProxyType
from typing import Any, ClassVar, Protocol, runtime_checkable


SUPPORTED_LAYER_KEYS = frozenset(
    {"L1", "L2", "L3_hot", "L3_cool", "L3_archive", "L4", "L5"}
)
SUPPORTED_PROVIDER_KEYS = frozenset({"AWS", "Azure", "GCP"})


def _validate_non_negative_number(name: str, value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"Layer result value {name!r} must be numeric")
    normalized = float(value)
    if not isfinite(normalized):
        raise ValueError(f"Layer result value {name!r} must be finite")
    if normalized < 0:
        raise ValueError(f"Layer result value {name!r} must be non-negative")
    return normalized


def _freeze_detail_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        frozen: dict[str, Any] = {}
        for key, nested in value.items():
            if not isinstance(key, str) or not key.strip():
                raise ValueError(
                    "Layer result detail names must be non-empty strings"
                )
            frozen[key] = _freeze_detail_value(nested)
        return MappingProxyType(frozen)
    if isinstance(value, (list, tuple)):
        return tuple(_freeze_detail_value(item) for item in value)
    return value


def _plain_detail_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): _plain_detail_value(nested)
            for key, nested in value.items()
        }
    if isinstance(value, tuple):
        return [_plain_detail_value(item) for item in value]
    return value


DeploymentScalar = str | int | bool


@dataclass(frozen=True, slots=True)
class ComponentDeploymentSelection:
    """Immutable deployment dimensions emitted by one costed component bundle."""

    component_id: str
    dimensions: Mapping[str, DeploymentScalar]

    def __post_init__(self) -> None:
        if not isinstance(self.component_id, str) or not self.component_id.strip():
            raise ValueError("Deployment selection component_id must be non-empty")
        if not isinstance(self.dimensions, Mapping) or not self.dimensions:
            raise ValueError("Deployment selection dimensions must be a non-empty mapping")

        normalized: dict[str, DeploymentScalar] = {}
        for dimension_id, value in self.dimensions.items():
            if not isinstance(dimension_id, str) or not dimension_id.strip():
                raise ValueError("Deployment dimension IDs must be non-empty strings")
            if type(value) not in {str, int, bool}:
                raise ValueError(
                    f"Deployment dimension {dimension_id!r} must be a scalar"
                )
            if isinstance(value, str) and not value:
                raise ValueError(
                    f"Deployment dimension {dimension_id!r} must be non-empty"
                )
            normalized[dimension_id] = value
        object.__setattr__(self, "dimensions", MappingProxyType(normalized))

    def as_dict(self) -> dict[str, Any]:
        return {
            "componentId": self.component_id,
            "dimensions": dict(self.dimensions),
        }


@dataclass(frozen=True, slots=True)
class LayerResult:
    """Canonical result returned by every provider layer calculator."""

    provider: str
    layer: str
    total_cost: float
    data_size_gb: float = 0.0
    messages: float = 0.0
    components: Mapping[str, float] = field(default_factory=dict)
    deployment_selections: tuple[ComponentDeploymentSelection, ...] = ()
    details: Mapping[str, Any] = field(default_factory=dict)
    supported: bool = True
    unsupported_reason: str | None = None

    def __post_init__(self) -> None:
        if self.provider not in SUPPORTED_PROVIDER_KEYS:
            raise ValueError(f"Unsupported layer result provider: {self.provider!r}")
        if self.layer not in SUPPORTED_LAYER_KEYS:
            raise ValueError(f"Unsupported layer result key: {self.layer}")
        values = {
            "total_cost": self.total_cost,
            "data_size_gb": self.data_size_gb,
            "messages": self.messages,
        }
        for name, value in values.items():
            _validate_non_negative_number(name, value)

        if not isinstance(self.components, Mapping):
            raise ValueError("Layer result components must be a mapping")
        normalized_components: dict[str, float] = {}
        for name, value in self.components.items():
            if not isinstance(name, str) or not name.strip():
                raise ValueError("Layer result component names must be non-empty strings")
            normalized_components[name] = _validate_non_negative_number(name, value)
        object.__setattr__(
            self,
            "components",
            MappingProxyType(normalized_components),
        )
        if not isinstance(self.deployment_selections, tuple):
            raise ValueError("Layer deployment selections must be a tuple")
        component_ids: list[str] = []
        for selection in self.deployment_selections:
            if not isinstance(selection, ComponentDeploymentSelection):
                raise ValueError(
                    "Layer deployment selections must use "
                    "ComponentDeploymentSelection"
                )
            component_ids.append(selection.component_id)
        if len(component_ids) != len(set(component_ids)):
            raise ValueError("Layer deployment selection component IDs must be unique")
        if not isinstance(self.details, Mapping):
            raise ValueError("Layer result details must be a mapping")
        object.__setattr__(
            self,
            "details",
            _freeze_detail_value(self.details),
        )

        if not isinstance(self.supported, bool):
            raise ValueError("Layer result supported state must be boolean")
        if self.unsupported_reason is not None and not isinstance(
            self.unsupported_reason, str
        ):
            raise ValueError("Layer result unsupported reason must be a string")
        normalized_reason = (self.unsupported_reason or "").strip() or None
        object.__setattr__(self, "unsupported_reason", normalized_reason)

        if self.supported and normalized_reason:
            raise ValueError("Supported layer results cannot declare an unsupported reason")
        if not self.supported and not normalized_reason:
            raise ValueError("Unsupported layer results require an explicit reason")

    def details_as_dict(self) -> dict[str, Any]:
        """Return a detached JSON-compatible details projection."""

        return _plain_detail_value(self.details)


class BaseLayerCalculatorSet:
    """Shared provider identity, capability, and result-construction invariants."""

    provider: ClassVar[str]
    supported_layers: ClassVar[frozenset[str]]

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        provider = getattr(cls, "provider", None)
        if provider not in SUPPORTED_PROVIDER_KEYS:
            raise TypeError(f"Unknown layer calculator provider: {provider!r}")
        supported_layers = frozenset(getattr(cls, "supported_layers", ()))
        unknown_layers = supported_layers - SUPPORTED_LAYER_KEYS
        if unknown_layers:
            raise TypeError(
                "Layer calculator declares unknown layers: "
                f"{sorted(unknown_layers)}"
            )
        cls.supported_layers = supported_layers

    def supports(self, layer: str) -> bool:
        if layer not in SUPPORTED_LAYER_KEYS:
            raise ValueError(f"Unknown architecture layer: {layer!r}")
        return layer in self.supported_layers

    def _result(
        self,
        *,
        layer: str,
        total_cost: float,
        data_size_gb: float = 0.0,
        messages: float = 0.0,
        components: Mapping[str, float] | None = None,
        deployment_selections: tuple[ComponentDeploymentSelection, ...] = (),
        details: Mapping[str, Any] | None = None,
        unsupported_reason: str | None = None,
    ) -> LayerResult:
        return LayerResult(
            provider=self.provider,
            layer=layer,
            total_cost=total_cost,
            data_size_gb=data_size_gb,
            messages=messages,
            components=components or {},
            deployment_selections=deployment_selections,
            details=details or {},
            supported=self.supports(layer) and unsupported_reason is None,
            unsupported_reason=unsupported_reason,
        )


@runtime_checkable
class LayerCalculatorSet(Protocol):
    """Structural contract implemented by every provider calculator set.

    Provider methods intentionally accept different domain parameters. The protocol
    standardizes their operation names and result type while preserving those
    provider-specific input contracts.
    """

    provider: ClassVar[str]
    supported_layers: ClassVar[frozenset[str]]

    def supports(self, layer: str) -> bool: ...

    def calculate_l1_cost(self, *args: Any, **kwargs: Any) -> LayerResult: ...

    def calculate_l2_cost(self, *args: Any, **kwargs: Any) -> LayerResult: ...

    def calculate_l3_hot_cost(self, *args: Any, **kwargs: Any) -> LayerResult: ...

    def calculate_l3_cool_cost(self, *args: Any, **kwargs: Any) -> LayerResult: ...

    def calculate_l3_archive_cost(self, *args: Any, **kwargs: Any) -> LayerResult: ...

    def calculate_l4_cost(self, *args: Any, **kwargs: Any) -> LayerResult: ...

    def calculate_l5_cost(self, *args: Any, **kwargs: Any) -> LayerResult: ...

    def calculate_glue_cost(self, messages: float, pricing: dict) -> float:
        """Calculate the provider's cross-cloud glue function cost."""

    def glue_deployment_selection(self) -> ComponentDeploymentSelection:
        """Return the exact runtime profile used for glue-function pricing."""
