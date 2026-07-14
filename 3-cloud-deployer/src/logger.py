"""Process-wide, redacting logging configuration for the Deployer."""

import json
import logging
from pathlib import Path
import sys
import traceback

from colorlog import ColoredFormatter

from src.core.observability import redact_sensitive


class RedactingColoredFormatter(ColoredFormatter):
    """Apply defense-in-depth redaction to every Deployer console log."""

    def format(self, record: logging.LogRecord) -> str:
        return redact_sensitive(super().format(record))


_MANAGED_HANDLER_ATTRIBUTE = "_twin2multicloud_console_handler"
DEBUG_MODE = False


def setup_logger(debug_mode: bool = False) -> logging.Logger:
    """Create or reconfigure the one process-wide Deployer logger."""
    configured_logger = logging.getLogger("digital_twin")
    level = logging.DEBUG if debug_mode else logging.INFO
    configured_logger.setLevel(level)

    handler = next(
        (
            existing
            for existing in configured_logger.handlers
            if getattr(existing, _MANAGED_HANDLER_ATTRIBUTE, False)
        ),
        None,
    )
    if handler is None:
        handler = logging.StreamHandler(sys.stdout)
        setattr(handler, _MANAGED_HANDLER_ATTRIBUTE, True)
        configured_logger.addHandler(handler)
    handler.setLevel(level)
    handler.setFormatter(
        RedactingColoredFormatter(
            "%(log_color)s[%(levelname)s] %(message)s",
            log_colors={
                "DEBUG": "cyan",
                "INFO": "green",
                "WARNING": "yellow",
                "ERROR": "red",
                "CRITICAL": "red,bg_white",
            },
        )
    )
    return configured_logger


def get_debug_mode() -> bool:
    return DEBUG_MODE


def print_stack_trace() -> None:
    """Log the active exception stack only when explicit debug mode is enabled."""
    if get_debug_mode():
        logger.error("Unhandled exception:\n%s", traceback.format_exc())


logger = setup_logger(debug_mode=DEBUG_MODE)


def configure_logger_from_file(config_path: str | Path) -> None:
    """Configure INFO/DEBUG logging from a project config file."""
    global logger, DEBUG_MODE
    try:
        with Path(config_path).open(encoding="utf-8") as config_file:
            config = json.load(config_file)
        mode = config.get("mode", "") if isinstance(config, dict) else ""
        DEBUG_MODE = isinstance(mode, str) and mode.upper() == "DEBUG"
        logger = setup_logger(debug_mode=DEBUG_MODE)
        if DEBUG_MODE:
            logger.debug("Debug mode is active.")
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        DEBUG_MODE = False
        logger = setup_logger(debug_mode=False)
        logger.warning(
            "Failed to configure logger from file: %s. Using INFO logging.",
            exc,
        )
