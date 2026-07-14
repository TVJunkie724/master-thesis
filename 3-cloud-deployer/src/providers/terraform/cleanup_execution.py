"""Hard-timeout process isolation for destructive provider fallback cleanup."""

from __future__ import annotations

import multiprocessing
from queue import Empty

from src.api.deployment_trace import sanitize_deployment_message
from src.providers.cleanup_registry import CleanupRequest, cleanup_provider_resources


def _cleanup_worker(request: CleanupRequest, result_queue) -> None:
    try:
        cleanup_provider_resources(request)
    except BaseException as exc:  # Process boundary must report every failure.
        result_queue.put(
            (
                False,
                type(exc).__name__,
                sanitize_deployment_message(str(exc)),
            )
        )
    else:
        result_queue.put((True, "", ""))


def run_cleanup_attempt(request: CleanupRequest, timeout_seconds: int) -> None:
    """Execute one cleanup attempt and terminate it when its deadline expires."""
    context = multiprocessing.get_context("spawn")
    result_queue = context.Queue(maxsize=1)
    process = context.Process(
        target=_cleanup_worker,
        args=(request, result_queue),
        daemon=False,
    )
    try:
        process.start()
        process.join(timeout_seconds)

        if process.is_alive():
            process.terminate()
            process.join(10)
            if process.is_alive():
                process.kill()
                process.join()
            raise TimeoutError(
                f"{request.provider} cleanup exceeded {timeout_seconds} seconds"
            )

        success, error_type, message = result_queue.get(timeout=2)
        if not success:
            raise RuntimeError(f"{error_type}: {message}")
    except Empty as exc:
        raise RuntimeError(
            f"{request.provider} cleanup process exited without a result "
            f"(exit code {process.exitcode})"
        ) from exc
    finally:
        if process.is_alive():
            process.terminate()
            process.join(10)
        result_queue.close()
        result_queue.join_thread()
