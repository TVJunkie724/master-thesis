"""Concurrency and publication primitives for provider pricing caches."""

from __future__ import annotations

from contextlib import contextmanager
from functools import wraps
import json
import os
from pathlib import Path
import tempfile
import threading
from typing import Any, Callable, Iterator, TypeVar


class PricingRefreshInProgressError(RuntimeError):
    """Raised when a provider refresh is already active in this process."""


_PROVIDER_LOCKS = {
    provider: threading.Lock() for provider in ("aws", "azure", "gcp")
}
_T = TypeVar("_T")


@contextmanager
def provider_refresh_guard(provider: str) -> Iterator[None]:
    """Reject duplicate in-process refreshes for the same provider."""

    try:
        lock = _PROVIDER_LOCKS[provider]
    except KeyError as exc:
        raise ValueError(f"Unsupported pricing provider: {provider}") from exc

    if not lock.acquire(blocking=False):
        raise PricingRefreshInProgressError(
            f"A {provider.upper()} pricing refresh is already in progress"
        )
    try:
        yield
    finally:
        lock.release()


def serialized_provider_refresh(function: Callable[..., _T]) -> Callable[..., _T]:
    """Serialize a refresh function by its first provider argument."""

    @wraps(function)
    def wrapper(target_provider: str, *args: Any, **kwargs: Any) -> _T:
        with provider_refresh_guard(target_provider):
            return function(target_provider, *args, **kwargs)

    return wrapper


def write_json_atomically(target: Path, payload: dict[str, Any]) -> None:
    """Publish JSON via fsync and atomic same-directory replacement."""

    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    file_descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{target.name}.",
        suffix=".tmp",
        dir=target.parent,
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(file_descriptor, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, target)
    finally:
        temporary_path.unlink(missing_ok=True)
