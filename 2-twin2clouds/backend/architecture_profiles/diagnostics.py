"""Bounded, redacted diagnostics for architecture profile resolution."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import re
from typing import Any


ARCHITECTURE_ERROR_CODES = frozenset(
    {
        "ARCH_PROFILE_NOT_FOUND",
        "ARCH_PROFILE_DIGEST_MISMATCH",
        "ARCH_PROFILE_BUNDLE_INCOMPATIBLE",
        "ARCH_WORKLOAD_INCOMPATIBLE",
        "ARCH_EXTENSION_BINDING_INVALID",
        "ARCH_PROVIDER_IMPLEMENTATION_MISSING",
        "ARCH_COMPONENT_CANDIDATE_MISSING",
        "ARCH_EDGE_IMPLEMENTATION_MISSING",
        "ARCH_FUNCTIONAL_INCOMPLETE",
        "ARCH_PRICING_EVIDENCE_MISSING",
        "ARCH_FORMULA_MISSING",
        "ARCH_DEPLOYMENT_MAPPING_MISSING",
        "ARCH_NO_ADMISSIBLE_CANDIDATE",
        "ARCH_RESOLUTION_BUILD_FAILED",
    }
)
MAX_REPRESENTATIVE_CANDIDATES = 25
_SAFE_CANDIDATE_ID = re.compile(r"^[a-z0-9][a-z0-9._:|-]{0,159}$")


class ArchitectureResolutionError(ValueError):
    """Stable fail-closed error without unsafe payload or traceback details."""

    def __init__(self, code: str, field: str, message: str):
        if code not in ARCHITECTURE_ERROR_CODES:
            raise ValueError(f"Unknown architecture error code: {code}")
        self.code = code
        self.field = field
        self.message = message
        super().__init__(f"{code} at {field}: {message}")


@dataclass(frozen=True)
class RejectionDiagnostics:
    """Aggregate candidate rejection evidence safe for API responses and logs."""

    rejected_by_error_code: tuple[tuple[str, int], ...]
    representative_candidate_ids: tuple[str, ...]

    @property
    def rejected_candidate_count(self) -> int:
        return sum(count for _, count in self.rejected_by_error_code)

    def to_dict(self) -> dict[str, Any]:
        return {
            "rejectedCandidateCount": self.rejected_candidate_count,
            "rejectedByErrorCode": dict(self.rejected_by_error_code),
            "representativeCandidateIds": list(
                self.representative_candidate_ids
            ),
        }


class RejectionCollector:
    """Collect only stable codes and bounded canonical candidate identities."""

    def __init__(self) -> None:
        self._counts: Counter[str] = Counter()
        self._candidate_ids: list[str] = []

    def record(self, code: str, candidate_id: str) -> None:
        if code not in ARCHITECTURE_ERROR_CODES:
            raise ValueError(f"Unknown architecture error code: {code}")
        if not _SAFE_CANDIDATE_ID.fullmatch(candidate_id):
            raise ValueError("Candidate ID is not safe for bounded diagnostics")
        self._counts[code] += 1
        if (
            candidate_id not in self._candidate_ids
            and len(self._candidate_ids) < MAX_REPRESENTATIVE_CANDIDATES
        ):
            self._candidate_ids.append(candidate_id)

    def freeze(self) -> RejectionDiagnostics:
        return RejectionDiagnostics(
            rejected_by_error_code=tuple(sorted(self._counts.items())),
            representative_candidate_ids=tuple(self._candidate_ids),
        )
