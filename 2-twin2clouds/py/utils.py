import os
import traceback
from py.logger import logger
from py.config_loader import load_config_file

def file_exists(file_path: str) -> bool:
    """Check if a file exists at the given path."""
    return os.path.isfile(file_path)

def get_debug_mode():
  config = load_config_file()
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
