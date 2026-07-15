"""Bounded single-process registry for issued log traces."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import math
from threading import RLock


class TraceRegistryError(Exception):
    """Base error for trace lifecycle validation."""


class TraceRateLimited(TraceRegistryError):
    def __init__(self, retry_after: int) -> None:
        self.retry_after = retry_after
        super().__init__(f"Trace rate limit active for {retry_after} seconds")


class TraceNotFound(TraceRegistryError):
    pass


class TraceOwnershipError(TraceRegistryError):
    pass


class TraceExpired(TraceRegistryError):
    pass


@dataclass(frozen=True)
class TraceRecord:
    project_name: str
    issued_at: datetime


class TraceRegistry:
    """Coordinate trace rate limits and ownership for one service replica."""

    def __init__(
        self,
        *,
        cooldown: timedelta,
        lifetime: timedelta,
        max_traces: int = 1024,
    ) -> None:
        if cooldown <= timedelta(0):
            raise ValueError("Trace cooldown must be positive")
        if lifetime <= timedelta(0):
            raise ValueError("Trace lifetime must be positive")
        if max_traces <= 0:
            raise ValueError("Trace registry capacity must be positive")
        self.cooldown = cooldown
        self.lifetime = lifetime
        self.max_traces = max_traces
        self._last_started: dict[str, datetime] = {}
        self._reservations: dict[str, datetime] = {}
        self._traces: dict[str, TraceRecord] = {}
        self._lock = RLock()

    def reserve(self, project_name: str, now: datetime) -> None:
        with self._lock:
            self._purge(now)
            previous = self._reservations.get(project_name) or self._last_started.get(
                project_name
            )
            if previous is not None:
                remaining = self.cooldown - (now - previous)
                if remaining.total_seconds() > 0:
                    raise TraceRateLimited(
                        max(1, math.ceil(remaining.total_seconds()))
                    )
            self._reservations[project_name] = now

    def issue(self, project_name: str, trace_id: str, now: datetime) -> None:
        with self._lock:
            if self._reservations.get(project_name) != now:
                raise TraceRegistryError("Trace reservation is no longer active")
            self._reservations.pop(project_name, None)
            self._last_started[project_name] = now
            self._traces[trace_id] = TraceRecord(project_name, now)
            self._enforce_bound()

    def rollback(self, project_name: str, reserved_at: datetime) -> None:
        with self._lock:
            if self._reservations.get(project_name) == reserved_at:
                self._reservations.pop(project_name, None)

    def validate(self, trace_id: str, project_name: str, now: datetime) -> TraceRecord:
        with self._lock:
            record = self._traces.get(trace_id)
            if record is None:
                raise TraceNotFound(trace_id)
            if record.project_name != project_name:
                raise TraceOwnershipError(trace_id)
            if now - record.issued_at > self.lifetime:
                self._traces.pop(trace_id, None)
                raise TraceExpired(trace_id)
            return record

    def complete(self, trace_id: str) -> None:
        with self._lock:
            self._traces.pop(trace_id, None)

    def clear(self) -> None:
        with self._lock:
            self._last_started.clear()
            self._reservations.clear()
            self._traces.clear()

    def _purge(self, now: datetime) -> None:
        expired = [
            trace_id
            for trace_id, record in self._traces.items()
            if now - record.issued_at > self.lifetime
        ]
        for trace_id in expired:
            self._traces.pop(trace_id, None)
        stale_projects = [
            project
            for project, started_at in self._last_started.items()
            if now - started_at > self.cooldown
        ]
        for project in stale_projects:
            self._last_started.pop(project, None)

    def _enforce_bound(self) -> None:
        overflow = len(self._traces) - self.max_traces
        if overflow <= 0:
            return
        oldest = sorted(
            self._traces,
            key=lambda trace_id: self._traces[trace_id].issued_at,
        )[:overflow]
        for trace_id in oldest:
            self._traces.pop(trace_id, None)
