import json
import os
import boto3
<<<<<<< HEAD
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
=======


iot_data_path = "iot_devices_auth"
lambda_functions_path = "lambda_functions"

config = {}
config_iot_devices = []
config_providers = {}
config_credentials = {}

aws_iam_client = {}
aws_lambda_client = {}
aws_iot_client = {}
aws_sts_client = {}
aws_events_client = {}
aws_dynamodb_client = {}
aws_s3_client = {}
aws_twinmaker_client = {}
aws_grafana_client = {}
aws_logs_client = {}

>>>>>>> 94f88ba (add deployer init)

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

<<<<<<< HEAD
def initialize_config_events():
  global config_events
  with open(f"{project_path()}/config_events.json", "r") as file:
    config_events = json.load(file)

def initialize_config_hierarchy():
  global config_hierarchy
  with open(f"{project_path()}/config_hierarchy.json", "r") as file:
    config_hierarchy = json.load(file)
=======
def initialize_config_providers():
  global config_providers
  with open(f"{project_path()}/config_providers.json", "r") as file:
    config_providers = json.load(file)
>>>>>>> 94f88ba (add deployer init)

def initialize_config_credentials():
  global config_credentials
  with open(f"{project_path()}/config_credentials.json", "r") as file:
    config_credentials = json.load(file)

<<<<<<< HEAD
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
=======
def digital_twin_info():
  return { "name": config["digital_twin_name"] } | config_providers | { "iot_devices": config_iot_devices }


def initialize_aws_iam_client():
  global config
  global aws_iam_client
  aws_iam_client = boto3.client("iam",
    aws_access_key_id=config_credentials["aws_access_key_id"],
    aws_secret_access_key=config_credentials["aws_secret_access_key"],
    region_name=config_credentials["aws_region"])

def initialize_aws_lambda_client():
  global config
  global aws_lambda_client
  aws_lambda_client = boto3.client("lambda",
    aws_access_key_id=config_credentials["aws_access_key_id"],
    aws_secret_access_key=config_credentials["aws_secret_access_key"],
    region_name=config_credentials["aws_region"])

def initialize_aws_iot_client():
  global config
  global aws_iot_client
  aws_iot_client = boto3.client("iot",
    aws_access_key_id=config_credentials["aws_access_key_id"],
    aws_secret_access_key=config_credentials["aws_secret_access_key"],
    region_name=config_credentials["aws_region"])

def initialize_aws_sts_client():
  global config
  global aws_sts_client
  aws_sts_client = boto3.client("sts",
    aws_access_key_id=config_credentials["aws_access_key_id"],
    aws_secret_access_key=config_credentials["aws_secret_access_key"],
    region_name=config_credentials["aws_region"])

def initialize_aws_events_client():
  global config
  global aws_events_client
  aws_events_client = boto3.client("events",
    aws_access_key_id=config_credentials["aws_access_key_id"],
    aws_secret_access_key=config_credentials["aws_secret_access_key"],
    region_name=config_credentials["aws_region"])

def initialize_aws_dynamodb_client():
  global config
  global aws_dynamodb_client
  aws_dynamodb_client = boto3.client("dynamodb",
    aws_access_key_id=config_credentials["aws_access_key_id"],
    aws_secret_access_key=config_credentials["aws_secret_access_key"],
    region_name=config_credentials["aws_region"])

def initialize_aws_s3_client():
  global config
  global aws_s3_client
  aws_s3_client = boto3.client("s3",
    aws_access_key_id=config_credentials["aws_access_key_id"],
    aws_secret_access_key=config_credentials["aws_secret_access_key"],
    region_name=config_credentials["aws_region"])

def initialize_aws_twinmaker_client():
  global config
  global aws_twinmaker_client
  aws_twinmaker_client = boto3.client("iottwinmaker",
    aws_access_key_id=config_credentials["aws_access_key_id"],
    aws_secret_access_key=config_credentials["aws_secret_access_key"],
    region_name=config_credentials["aws_region"])

def initialize_aws_grafana_client():
  global config
  global aws_grafana_client
  aws_grafana_client = boto3.client("grafana",
    aws_access_key_id=config_credentials["aws_access_key_id"],
    aws_secret_access_key=config_credentials["aws_secret_access_key"],
    region_name=config_credentials["aws_region"])

def initialize_aws_logs_client():
  global config
  global aws_logs_client
  aws_logs_client = boto3.client("logs",
    aws_access_key_id=config_credentials["aws_access_key_id"],
    aws_secret_access_key=config_credentials["aws_secret_access_key"],
    region_name=config_credentials["aws_region"])


def dispatcher_iam_role_name():
  return config["digital_twin_name"] + "-dispatcher"

def dispatcher_lambda_function_name():
  return config["digital_twin_name"] + "-dispatcher"

def dispatcher_iot_rule_name():
  rule_name = config["digital_twin_name"] + "-trigger-dispatcher"
  return rule_name.replace("-", "_")

def persister_iam_role_name():
  return config["digital_twin_name"] + "-persister"

def persister_lambda_function_name():
  return config["digital_twin_name"] + "-persister"

def dynamodb_table_name():
  return config["digital_twin_name"] + "-iot-data"

def hot_cold_mover_iam_role_name():
  return config["digital_twin_name"] + "-hot-to-cold-mover"

def hot_cold_mover_lambda_function_name():
  return config["digital_twin_name"] + "-hot-to-cold-mover"

def hot_cold_mover_event_rule_name():
  return config["digital_twin_name"] + "-hot-to-cold-mover"

def cold_archive_mover_iam_role_name():
  return config["digital_twin_name"] + "-cold-to-archive-mover"

def cold_archive_mover_lambda_function_name():
  return config["digital_twin_name"] + "-cold-to-archive-mover"

def cold_archive_mover_event_rule_name():
  return config["digital_twin_name"] + "-cold-to-archive-mover"

def cold_s3_bucket_name():
  return config["digital_twin_name"] + "-cold-iot-data"

def archive_s3_bucket_name():
  return config["digital_twin_name"] + "-archive-iot-data"

def twinmaker_connector_iam_role_name():
  return config["digital_twin_name"] + "-twinmaker-connector"

def twinmaker_connector_lambda_function_name():
  return config["digital_twin_name"] + "-twinmaker-connector"

def twinmaker_s3_bucket_name():
  return config["digital_twin_name"] + "-twinmaker"

def twinmaker_iam_role_name():
  return config["digital_twin_name"] + "-twinmaker"

def twinmaker_workspace_name():
  return config["digital_twin_name"] + "-twinmaker"

def grafana_workspace_name():
  return config["digital_twin_name"] + "-grafana"

def grafana_iam_role_name():
  return config["digital_twin_name"] + "-grafana"

def iot_thing_name(iot_device):
  return config["digital_twin_name"] + "-" + iot_device["name"]

def iot_thing_policy_name(iot_device):
  return config["digital_twin_name"] + "-" + iot_device["name"]

def processor_iam_role_name(iot_device):
  return config["digital_twin_name"] + "-" + iot_device["name"] + "-processor"

def processor_lambda_function_name(iot_device):
  return config["digital_twin_name"] + "-" + iot_device["name"] + "-processor"

def twinmaker_component_type_id(iot_device):
  return config["digital_twin_name"] + "-" + iot_device["name"]
>>>>>>> 94f88ba (add deployer init)
