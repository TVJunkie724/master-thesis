import os
import traceback
from backend.logger import logger
from backend.config_loader import load_config_file

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

def is_file_fresh(file_path: str, max_age_days: int = 7) -> bool:
    """
    Check if a file exists and is fresher than the specified number of days.
    
    Args:
        file_path (str): Path to the file.
        max_age_days (int): Maximum allowed age in days. Defaults to 7.
        
    Returns:
        bool: True if file exists and is fresh, False otherwise.
    """
    if not os.path.isfile(file_path):
        return False
        
    try:
        import time
        file_mod_time = os.path.getmtime(file_path)
        current_time = time.time()
        file_age_days = (current_time - file_mod_time) / (24 * 3600)
        
        if file_age_days < max_age_days:
            logger.debug(f"File {file_path} is fresh ({file_age_days:.1f} days old).")
            return True
        else:
            logger.info(f"File {file_path} is stale ({file_age_days:.1f} days old).")
            return False
    except Exception as e:
        logger.warning(f"Error checking file freshness for {file_path}: {e}")
        return False

def get_file_age_string(file_path: str) -> str:
    """
    Get a human-readable string representing the age of a file.
    Returns "N days" or "N hours" (if < 1 day).
    Returns "File not found" if the file doesn't exist.
    """
    if not os.path.isfile(file_path):
        return "File not found"
        
    try:
        import time
        file_mod_time = os.path.getmtime(file_path)
        current_time = time.time()
        age_seconds = current_time - file_mod_time
        
        days = age_seconds / (24 * 3600)
        if days >= 1:
            return f"{days:.0f} days"
        else:
            hours = age_seconds / 3600
            return f"{hours:.0f} hours"
    except Exception as e:
        logger.warning(f"Error checking file age for {file_path}: {e}")
        return "Unknown"
