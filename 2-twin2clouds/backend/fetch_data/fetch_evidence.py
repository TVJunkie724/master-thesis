"""
Evidence models for pricing fetchers.

Provider fetchers keep their public dictionary return shape for compatibility,
but matching decisions must be inspectable and deterministic. These dataclasses
capture selected and rejected candidates without depending on provider SDK
objects in API-facing layers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Iterable, Mapping, Optional, Tuple


class MatchStatus(str, Enum):
    """Outcome of a field-level pricing match."""

    SELECTED = "selected"
    NO_MATCH = "no_match"
    AMBIGUOUS = "ambiguous"


@dataclass(frozen=True)
class RejectedCandidate:
    """Candidate row that was inspected but not selected."""

    reason: str
    row: Mapping[str, Any]


@dataclass(frozen=True)
class FieldMatchEvidence:
    """Evidence for one provider pricing field."""

    provider: str
    service_name: str
    field_key: str
    status: MatchStatus
    selected_row: Optional[Mapping[str, Any]] = None
    selected_price: Optional[float] = None
    normalized_price: Optional[float] = None
    source_unit: Optional[str] = None
    rejected_candidates: Tuple[RejectedCandidate, ...] = field(default_factory=tuple)
    reason: Optional[str] = None

    @property
    def requires_review(self) -> bool:
        return self.status in {MatchStatus.NO_MATCH, MatchStatus.AMBIGUOUS}

    def as_dict(self) -> Dict[str, Any]:
        return {
            "provider": self.provider,
            "service_name": self.service_name,
            "field_key": self.field_key,
            "status": self.status.value,
            "selected_row": dict(self.selected_row) if self.selected_row else None,
            "selected_price": self.selected_price,
            "normalized_price": self.normalized_price,
            "source_unit": self.source_unit,
            "rejected_candidates": [
                {"reason": item.reason, "row": dict(item.row)}
                for item in self.rejected_candidates
            ],
            "reason": self.reason,
            "requires_review": self.requires_review,
        }


def distinct_prices(rows: Iterable[Mapping[str, Any]], price_key: str = "unitPrice") -> Tuple[float, ...]:
    """Return sorted unique non-zero prices from candidate rows."""

    prices = set()
    for row in rows:
        try:
            price = float(row.get(price_key, 0))
        except (TypeError, ValueError):
            continue
        if price > 0:
            prices.add(price)
    return tuple(sorted(prices))
