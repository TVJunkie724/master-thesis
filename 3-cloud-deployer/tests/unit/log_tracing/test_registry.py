from datetime import datetime, timedelta, timezone

import pytest

from src.log_tracing.registry import (
    TraceExpired,
    TraceNotFound,
    TraceOwnershipError,
    TraceRateLimited,
    TraceRegistry,
)


def _registry(max_traces=1024):
    return TraceRegistry(
        cooldown=timedelta(seconds=30),
        lifetime=timedelta(seconds=120),
        max_traces=max_traces,
    )


def test_failed_start_can_rollback_without_consuming_cooldown():
    registry = _registry()
    now = datetime.now(timezone.utc)
    registry.reserve("factory", now)
    registry.rollback("factory", now)

    registry.reserve("factory", now)


def test_successful_start_enforces_cooldown():
    registry = _registry()
    now = datetime.now(timezone.utc)
    registry.reserve("factory", now)
    registry.issue("factory", "TRACE-1234ABCD", now)

    with pytest.raises(TraceRateLimited) as exc_info:
        registry.reserve("factory", now + timedelta(seconds=1))

    assert exc_info.value.retry_after == 29


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"cooldown": timedelta(0)}, "cooldown"),
        ({"lifetime": timedelta(0)}, "lifetime"),
        ({"max_traces": 0}, "capacity"),
    ],
)
def test_registry_rejects_unbounded_lifecycle_configuration(kwargs, message):
    values = {
        "cooldown": timedelta(seconds=30),
        "lifetime": timedelta(seconds=120),
        "max_traces": 1024,
    }
    values.update(kwargs)

    with pytest.raises(ValueError, match=message):
        TraceRegistry(**values)


def test_trace_ownership_and_expiration_are_enforced():
    registry = _registry()
    now = datetime.now(timezone.utc)
    registry.reserve("factory", now)
    registry.issue("factory", "TRACE-1234ABCD", now)

    with pytest.raises(TraceOwnershipError):
        registry.validate("TRACE-1234ABCD", "other", now)
    with pytest.raises(TraceExpired):
        registry.validate(
            "TRACE-1234ABCD",
            "factory",
            now + timedelta(seconds=121),
        )


def test_registry_evicts_oldest_trace_at_capacity():
    registry = _registry(max_traces=1)
    now = datetime.now(timezone.utc)
    registry.reserve("one", now)
    registry.issue("one", "TRACE-11111111", now)
    later = now + timedelta(seconds=31)
    registry.reserve("two", later)
    registry.issue("two", "TRACE-22222222", later)

    with pytest.raises(TraceNotFound):
        registry.validate("TRACE-11111111", "one", later)
    assert registry.validate("TRACE-22222222", "two", later).project_name == "two"
