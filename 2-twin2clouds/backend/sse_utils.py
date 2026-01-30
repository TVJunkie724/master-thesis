"""
SSE (Server-Sent Events) utilities for streaming logs.

Provides thread-safe log capture for async SSE streaming from synchronous code.
"""

import asyncio
import logging
import json
from typing import Optional


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
            msg = self.format(record)
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
