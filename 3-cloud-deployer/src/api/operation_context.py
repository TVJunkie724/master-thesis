"""HTTP adapter boundary for operation package acquisition."""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from fastapi import HTTPException

from src.operation_packages import (
    InvalidOperationPackageError,
    OperationPackageInUseError,
    get_operation_package_store,
)


@contextmanager
def operation_project_path(
    project_name: str,
    operation_token: str,
) -> Iterator[Path]:
    """Acquire the required one-shot runtime package for an API operation."""
    try:
        with get_operation_package_store().acquire(
            project_name, operation_token
        ) as path:
            yield path
    except OperationPackageInUseError as exc:
        raise HTTPException(
            status_code=409,
            detail="Operation package is already in use.",
        ) from exc
    except InvalidOperationPackageError as exc:
        raise HTTPException(
            status_code=400,
            detail="Operation package is invalid or expired.",
        ) from exc
