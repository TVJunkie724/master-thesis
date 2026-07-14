"""Canonical redaction and logging boundary for REST API failures."""

import logging

from fastapi import HTTPException

from logger import logger
from src.core.observability import redact_sensitive


def safe_error_detail(exc: object) -> str:
    """Return a client-safe representation of an expected domain error."""
    return redact_sensitive(exc)


def internal_server_error(
    operation: str,
    exc: BaseException,
    *,
    detail: str = "Internal server error. Check logs.",
) -> HTTPException:
    """Log one unexpected exception safely and return the canonical HTTP error."""
    logger.error(
        "%s failed: %s",
        operation,
        redact_sensitive(exc),
        extra={"error_type": type(exc).__name__},
        exc_info=logger.isEnabledFor(logging.DEBUG),
    )
    return HTTPException(status_code=500, detail=detail)
