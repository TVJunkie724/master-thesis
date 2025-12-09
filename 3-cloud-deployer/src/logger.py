import logging
import sys
from colorlog import ColoredFormatter
import traceback
import json
import constants as CONSTANTS

global logger
config = {}

def setup_logger(debug_mode=False):
    logger = logging.getLogger("digital_twin")
    logger.setLevel(logging.DEBUG if debug_mode else logging.INFO)

    # Create console handler
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.DEBUG if debug_mode else logging.INFO)

    # Create colored formatter
    formatter = ColoredFormatter(
        "%(log_color)s[%(levelname)s] %(message)s",
        log_colors={
            "DEBUG":    "cyan",
            "INFO":     "green",
            "WARNING":  "yellow",
            "ERROR":    "red",
            "CRITICAL": "red,bg_white",
        }
    )
    handler.setFormatter(formatter)

    if not logger.handlers:
        logger.addHandler(handler)

    return logger

def get_debug_mode():
    return config.get("mode", "").upper() == "DEBUG"

def print_stack_trace():
    """
    Print the stack trace if debug_mode is enabled.

    Args:
        debug_mode (bool, optional): _description_. Defaults to False.
    """
    if get_debug_mode():
        error_msg = traceback.format_exc()
        logger.error(error_msg)
  
class LoggerProxy:
    def __getattr__(self, name):
        if logger is None:
            raise RuntimeError("Logger not initialized yet.")
        return getattr(logger, name)

logger_proxy = LoggerProxy()








# Logger defaults to INFO unless initialized/reconfigured later.
DEBUG_MODE = False # Default
logger = setup_logger(debug_mode=DEBUG_MODE)

def configure_logger_from_file(config_path):
    global logger, DEBUG_MODE
    try:
        with open(config_path) as f:
            config = json.load(f)
        DEBUG_MODE = config.get("mode", "").upper() == "DEBUG"
        # Re-setup logger with new mode
        logger = setup_logger(debug_mode=DEBUG_MODE)
        if DEBUG_MODE:
            logger.debug("Debug mode is active.")
    except Exception as e:
        logger.warning(f"Failed to configure logger from file: {e}. Using default settings.")
