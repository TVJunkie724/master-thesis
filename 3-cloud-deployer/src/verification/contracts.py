"""Typed contracts for data-flow verification orchestration."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal


PhaseStatus = Literal["pass", "fail", "skip", "partial"]


@dataclass(frozen=True)
class VerificationContext:
    project_name: str
    project_path: Path
    providers: dict
    terraform_outputs: dict
    optimization: dict
    credentials: dict
    events: list[dict] = field(default_factory=list)


@dataclass(frozen=True)
class ProbeResult:
    success: bool
    elapsed: float = 0.0
    error: str | None = None
    evidence: dict = field(default_factory=dict)


@dataclass(frozen=True)
class PhaseOutcome:
    status: PhaseStatus
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    failed_phase: str | None = None


@dataclass(frozen=True)
class PhaseEmission:
    event: str | None = None
    outcome: PhaseOutcome | None = None


@dataclass
class VerificationSummary:
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    failed_phase: str | None = None

    def include(self, outcome: PhaseOutcome) -> None:
        self.passed += outcome.passed
        self.failed += outcome.failed
        self.skipped += outcome.skipped
        if self.failed_phase is None and outcome.failed_phase:
            self.failed_phase = outcome.failed_phase
