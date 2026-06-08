"""Typed inputs passed into optimization metric providers."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class OptimizationMetricContext:
    """Provider-neutral metric input for one optimization candidate."""

    candidate_id: str
    metric_inputs: dict[str, Any]
    evidence_references: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

