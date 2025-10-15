import json
import os
import boto3
import logging
import sys
from colorlog import ColoredFormatter
import traceback
from util import contains_provider, validate_credentials

logger = None

config = {}
config_iot_devices = []
config_credentials = {}
config_credentials_aws = None
config_credentials_azure = None
config_credentials_google = None
config_providers = {}
config_hierarchy = []
config_events = []

def project_path():
  return os.path.dirname(os.path.dirname(__file__))

def initialize_config():
  global config
  with open(f"{project_path()}/config.json", "r") as file:
    config = json.load(file)

def initialize_config_iot_devices():
  global config_iot_devices
  with open(f"{project_path()}/config_iot_devices.json", "r") as file:
    config_iot_devices = json.load(file)

def initialize_config_events():
  global config_events
  with open(f"{project_path()}/config_events.json", "r") as file:
    config_events = json.load(file)

def initialize_config_hierarchy():
  global config_hierarchy
  with open(f"{project_path()}/config_hierarchy.json", "r") as file:
    config_hierarchy = json.load(file)

def initialize_config_credentials():
  global config_credentials
  with open(f"{project_path()}/config_credentials.json", "r") as file:
    config_credentials = json.load(file)

def initialize_config_providers():
  global config_providers
  with open(f"{project_path()}/config_providers.json", "r") as file:
    config_providers = json.load(file)
    
def digital_twin_info():
  return {
    "config": config,
    "config_iot_devices": config_iot_devices,
    "config_events": config_events
  }



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

def initialize_all():
  global logger
  global config_credentials_aws
  global config_credentials_azure
  global config_credentials_google
    
  initialize_config()
  initialize_config_iot_devices()
  initialize_config_events()
  initialize_config_hierarchy()
  initialize_config_credentials()
  initialize_config_providers()
  
  
  # check credentials based on providers in use
  valid_providers = ["aws", "azure", "google"]
  for provider in valid_providers:
    if contains_provider(config_providers, provider):
        valid_credentials = validate_credentials(provider, config_credentials)
        match provider:
            case "aws":
                config_credentials_aws = valid_credentials
            case "azure":
                config_credentials_azure = valid_credentials
            case "google":
                config_credentials_google = valid_credentials
            case _:
                raise ValueError(f"Unsupported provider: {provider}, valid providers are: {', '.join(valid_providers)}")

  DEBUG_MODE = config.get("mode", "").upper() == "DEBUG"
  logger = setup_logger(debug_mode=DEBUG_MODE)

  logger.debug("Debug mode is active.")