"""
DEPRECATED: This module is deprecated and will be removed in a future version.

Use the new pattern-based approach instead:
- For configuration: src/core/config_loader.py, src/core/context.py
- For providers: src/providers/ package
- For deployment: src/providers/aws/deployer_strategy.py

Migration Guide:
    OLD: import globals; twin_name = globals.config["digital_twin_name"]
    NEW: context.config.digital_twin_name

This file remains for backward compatibility during the migration period.
"""
import warnings
warnings.warn(
    "globals module is deprecated. Use src/core/context.py instead.",
    DeprecationWarning,
    stacklevel=2
)

import json
import os
import boto3
import logging
import sys
from colorlog import ColoredFormatter
import traceback

from logger import logger, print_stack_trace, configure_logger_from_file

import constants as CONSTANTS
# Import shared utility functions from util.py to avoid duplication
from util import contains_provider, validate_credentials

config = {}
config_iot_devices = []
config_credentials = {}
config_credentials_aws = None
config_credentials_azure = None
config_credentials_google = None
config_optimization = {}
config_providers = {}
config_inter_cloud = {}
config_hierarchy = []
config_events = []
CURRENT_PROJECT = CONSTANTS.DEFAULT_PROJECT_NAME

def get_project_upload_path():
    return os.path.join(project_path(), CONSTANTS.PROJECT_UPLOAD_DIR_NAME, CURRENT_PROJECT)

def set_active_project(project_name):
    global CURRENT_PROJECT
    
    # Simple validation using os.path to prevent directory traversal
    safe_name = os.path.basename(project_name)
    if safe_name != project_name:
        raise ValueError("Invalid project name.")
        
    target_path = os.path.join(project_path(), CONSTANTS.PROJECT_UPLOAD_DIR_NAME, safe_name)
    if not os.path.exists(target_path):
         raise ValueError(f"Project '{project_name}' does not exist.")
         
    CURRENT_PROJECT = project_name
    initialize_all()

def project_path():
  return os.path.dirname(os.path.dirname(__file__))

def initialize_config():
  global config
  config_path = os.path.join(get_project_upload_path(), CONSTANTS.CONFIG_FILE)
  with open(config_path, "r") as file:
    config = json.load(file)
  
  # Re-configure logger based on new config
  configure_logger_from_file(config_path)

def initialize_config_iot_devices():
  global config_iot_devices
  with open(os.path.join(get_project_upload_path(), CONSTANTS.CONFIG_IOT_DEVICES_FILE), "r") as file:
    config_iot_devices = json.load(file)

def initialize_config_events():
  global config_events
  with open(os.path.join(get_project_upload_path(), CONSTANTS.CONFIG_EVENTS_FILE), "r") as file:
    config_events = json.load(file)

def initialize_config_hierarchy():
  global config_hierarchy
  with open(os.path.join(get_project_upload_path(), CONSTANTS.CONFIG_HIERARCHY_FILE), "r") as file:
    config_hierarchy = json.load(file)

def initialize_config_credentials():
  global config_credentials
  with open(os.path.join(get_project_upload_path(), CONSTANTS.CONFIG_CREDENTIALS_FILE), "r") as file:
    config_credentials = json.load(file)

def initialize_config_providers():
  global config_providers
  with open(os.path.join(get_project_upload_path(), CONSTANTS.CONFIG_PROVIDERS_FILE), "r") as file:
    config_providers = json.load(file)

def initialize_config_inter_cloud():
  global config_inter_cloud
  path = os.path.join(get_project_upload_path(), CONSTANTS.CONFIG_INTER_CLOUD_FILE)
  if os.path.exists(path):
    with open(path, "r") as file:
      config_inter_cloud = json.load(file)
  else:
    logger.info(f"Inter-cloud config file not found at {path}. Defaulting to empty config.")
    config_inter_cloud = {}

def get_inter_cloud_token(connection_id):
    """
    Retrieves the token for a specific connection ID.
    Raises ValueError if missing.
    """
    connections = config_inter_cloud.get("connections", {})
    connection = connections.get(connection_id)
    if not connection:
        raise ValueError(f"Connection '{connection_id}' not found in {CONSTANTS.CONFIG_INTER_CLOUD_FILE}.")
    
    token = connection.get("token")
    if not token:
        raise ValueError(f"Token missing for connection '{connection_id}'.")
    return token

def initialize_config_optimization():
    global config_optimization
    path = os.path.join(get_project_upload_path(), CONSTANTS.CONFIG_OPTIMIZATION_FILE)
    if os.path.exists(path):
        with open(path, "r") as file:
            config_optimization = json.load(file)
    else:
        logger.warning(f"Optimization config file not found at {path}. Defaulting to empty config.")
        config_optimization = {}

def is_optimization_enabled(param_key):
    """
    Checks if a specific optimization parameter is enabled in config_optimization.
    Structure: result > inputParamsUsed > [param_key]
    Defaults to False if key or file is missing.
    """
    try:
        return config_optimization.get("result", {}).get("inputParamsUsed", {}).get(param_key, False)
    except Exception:
        return False

def should_deploy_api_gateway(current_provider):
    """
    Determines if API Gateway should be deployed for the current provider.
    Logic: 
      1. Current provider MUST be the L3 Hot provider.
      2. AND (L3 Hot != L4 OR L3 Hot != L5)
    """
    l3_hot = config_providers.get("layer_3_hot_provider")
    l4 = config_providers.get("layer_4_provider")
    l5 = config_providers.get("layer_5_provider")
    
    if current_provider != l3_hot:
        return False
        
    return (l3_hot != l4) or (l3_hot != l5)
    
def digital_twin_info():
  return {
    "config": config,
    "config_iot_devices": config_iot_devices,
    "config_events": config_events
  }

def initialize_all():
  global config
  global config_credentials
  global config_credentials_aws
  global config_credentials_azure
  global config_credentials_google
    
  initialize_config()
  initialize_config_iot_devices()
  initialize_config_events()
  initialize_config_hierarchy()
  initialize_config_credentials()
  initialize_config_providers()
  initialize_config_optimization()
  initialize_config_inter_cloud()
  
  
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

def api_name():
  return config["digital_twin_name"] + "-api"
