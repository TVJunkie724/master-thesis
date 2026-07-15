"""
SSE (Server-Sent Events) utilities for streaming logs.

Provides thread-safe log capture for async SSE streaming from synchronous code.
"""

import asyncio
from contextvars import ContextVar
import logging
import json

from backend.secret_redaction import redact_secret_like_text


pricing_operation_id: ContextVar[str | None] = ContextVar(
    "pricing_operation_id", default=None
)


class PricingOperationFilter(logging.Filter):
    """Allow only records emitted by one pricing refresh operation."""

    def __init__(self, operation_id: str):
        super().__init__()
        self.operation_id = operation_id

    def filter(self, record: logging.LogRecord) -> bool:
        return pricing_operation_id.get() == self.operation_id


class ThreadSafeSseHandler(logging.Handler):
    """
    Custom log handler that bridges sync logging to async SSE queue.
    
    Uses loop.call_soon_threadsafe() to safely put messages from
    executor threads onto the asyncio event loop's queue.
    """
    
    def __init__(self, queue: asyncio.Queue, loop: asyncio.AbstractEventLoop):
        super().__init__()
        self.queue = queue
        self.loop = loop
    
    def emit(self, record: logging.LogRecord):
        try:
            msg = redact_secret_like_text(self.format(record))[:2000]
            # Thread-safe: schedule put on the event loop
            self.loop.call_soon_threadsafe(
                self._safe_put, msg
            )
        except Exception:
            # Don't crash on logging errors
            self.handleError(record)
    
    def _safe_put(self, msg: str):
        """Put message in queue, dropping if full (backpressure)."""
        try:
            self.queue.put_nowait(msg)
        except asyncio.QueueFull:
            pass  # Drop message if queue is full


def emit_sse(message: str, event_type: str = "log") -> str:
    """
    Format SSE event matching Flutter SseLogEvent expectations.
    
    Flutter expects: {"message": "...", "type": "log|complete|error|heartbeat"}
    
    Args:
        message: The log message to send
        event_type: One of "log", "complete", "error", "heartbeat"
    
    Returns:
        Properly formatted SSE event string
    """
    data = json.dumps({"message": message, "type": event_type})
    return f"event: {event_type}\ndata: {data}\n\n"
