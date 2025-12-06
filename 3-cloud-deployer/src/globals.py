import json
import os
import boto3
import logging
import sys
from colorlog import ColoredFormatter
import traceback

from logger import logger

import constants as CONSTANTS

def contains_provider(config_providers, provider_name):
    """Check if any value in the provider config matches provider_name."""
    return any(provider_name in str(v).lower() for v in config_providers.values())

def validate_credentials(provider_name, credentials):
    """Check if credentials exist and all required fields are present."""
    provider_creds = credentials.get(provider_name, {})
    if not provider_creds:
        raise ValueError(f"{provider_name.upper()} credentials are required but not found.")
    
    missing_fields = [field for field in CONSTANTS.REQUIRED_CREDENTIALS_FIELDS[provider_name] if field not in provider_creds]
    if missing_fields:
        raise ValueError(f"{provider_name.upper()} credentials are missing fields: {missing_fields}")
    return provider_creds

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
  with open(f"{project_path()}/upload/config.json", "r") as file:
    config = json.load(file)

def initialize_config_iot_devices():
  global config_iot_devices
  with open(f"{project_path()}/upload/config_iot_devices.json", "r") as file:
    config_iot_devices = json.load(file)

def initialize_config_events():
  global config_events
  with open(f"{project_path()}/upload/config_events.json", "r") as file:
    config_events = json.load(file)

def initialize_config_hierarchy():
  global config_hierarchy
  with open(f"{project_path()}/upload/config_hierarchy.json", "r") as file:
    config_hierarchy = json.load(file)

def initialize_config_credentials():
  global config_credentials
  with open(f"{project_path()}/upload/config_credentials.json", "r") as file:
    config_credentials = json.load(file)

def initialize_config_providers():
  global config_providers
  with open(f"{project_path()}/upload/config_providers.json", "r") as file:
    config_providers = json.load(file)
    
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
