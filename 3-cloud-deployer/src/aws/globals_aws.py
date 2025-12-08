"""
DEPRECATED: This module is deprecated and will be removed in a future version.

Use the new pattern-based approach instead:
- For AWS clients: src/providers/aws/clients.py
- For resource naming: src/providers/aws/naming.py
- For provider: src/providers/aws/provider.py

Migration Guide:
    OLD: globals_aws.aws_iam_client
    NEW: provider.clients["iam"]
    
    OLD: globals_aws.dispatcher_iam_role_name()
    NEW: provider.naming.dispatcher_iam_role()

This file remains for backward compatibility during the migration period.
"""
import warnings
warnings.warn(
    "globals_aws module is deprecated. Use src/providers/aws/ instead.",
    DeprecationWarning,
    stacklevel=2
)

import boto3
import globals 
import util 

import constants as CONSTANTS

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
aws_iot_data_client = {}
aws_apigateway_client = {}
aws_sf_client = {}

def initialize_aws_clients():
  initialize_aws_iam_client()
  initialize_aws_lambda_client()
  initialize_aws_iot_client()
  initialize_aws_sts_client()
  initialize_aws_events_client()
  initialize_aws_dynamodb_client()
  initialize_aws_s3_client()
  initialize_aws_twinmaker_client()
  initialize_aws_grafana_client()
  initialize_aws_logs_client()
  initialize_aws_iot_data_client()
  initialize_aws_apigateway_client()
  initialize_aws_sf_client()

def initialize_aws_iam_client():
  global config
  global aws_iam_client
  aws_iam_client = boto3.client("iam",
    aws_access_key_id=globals.config_credentials_aws["aws_access_key_id"],
    aws_secret_access_key=globals.config_credentials_aws["aws_secret_access_key"],
    region_name=globals.config_credentials_aws["aws_region"])

def initialize_aws_lambda_client():
  global config
  global aws_lambda_client
  aws_lambda_client = boto3.client("lambda",
    aws_access_key_id=globals.config_credentials_aws["aws_access_key_id"],
    aws_secret_access_key=globals.config_credentials_aws["aws_secret_access_key"],
    region_name=globals.config_credentials_aws["aws_region"])

def initialize_aws_iot_client():
  global config
  global aws_iot_client
  aws_iot_client = boto3.client("iot",
    aws_access_key_id=globals.config_credentials_aws["aws_access_key_id"],
    aws_secret_access_key=globals.config_credentials_aws["aws_secret_access_key"],
    region_name=globals.config_credentials_aws["aws_region"])

def initialize_aws_sts_client():
  global config
  global aws_sts_client
  aws_sts_client = boto3.client("sts",
    aws_access_key_id=globals.config_credentials_aws["aws_access_key_id"],
    aws_secret_access_key=globals.config_credentials_aws["aws_secret_access_key"],
    region_name=globals.config_credentials_aws["aws_region"])

def initialize_aws_events_client():
  global config
  global aws_events_client
  aws_events_client = boto3.client("events",
    aws_access_key_id=globals.config_credentials_aws["aws_access_key_id"],
    aws_secret_access_key=globals.config_credentials_aws["aws_secret_access_key"],
    region_name=globals.config_credentials_aws["aws_region"])

def initialize_aws_dynamodb_client():
  global config
  global aws_dynamodb_client
  aws_dynamodb_client = boto3.client("dynamodb",
    aws_access_key_id=globals.config_credentials_aws["aws_access_key_id"],
    aws_secret_access_key=globals.config_credentials_aws["aws_secret_access_key"],
    region_name=globals.config_credentials_aws["aws_region"])

def initialize_aws_s3_client():
  global config
  global aws_s3_client
  aws_s3_client = boto3.client("s3",
    aws_access_key_id=globals.config_credentials_aws["aws_access_key_id"],
    aws_secret_access_key=globals.config_credentials_aws["aws_secret_access_key"],
    region_name=globals.config_credentials_aws["aws_region"])

def initialize_aws_twinmaker_client():
  global config
  global aws_twinmaker_client
  aws_twinmaker_client = boto3.client("iottwinmaker",
    aws_access_key_id=globals.config_credentials_aws["aws_access_key_id"],
    aws_secret_access_key=globals.config_credentials_aws["aws_secret_access_key"],
    region_name=globals.config_credentials_aws["aws_region"])

def initialize_aws_grafana_client():
  global config
  global aws_grafana_client
  aws_grafana_client = boto3.client("grafana",
    aws_access_key_id=globals.config_credentials_aws["aws_access_key_id"],
    aws_secret_access_key=globals.config_credentials_aws["aws_secret_access_key"],
    region_name=globals.config_credentials_aws["aws_region"])

def initialize_aws_logs_client():
  global config
  global aws_logs_client
  aws_logs_client = boto3.client("logs",
    aws_access_key_id=globals.config_credentials_aws["aws_access_key_id"],
    aws_secret_access_key=globals.config_credentials_aws["aws_secret_access_key"],
    region_name=globals.config_credentials_aws["aws_region"])

def initialize_aws_apigateway_client():
  global config
  global aws_apigateway_client
  aws_apigateway_client = boto3.client("apigatewayv2",
    aws_access_key_id=globals.config_credentials_aws["aws_access_key_id"],
    aws_secret_access_key=globals.config_credentials_aws["aws_secret_access_key"],
    region_name=globals.config_credentials_aws["aws_region"])


def dispatcher_iam_role_name():
  return globals.config["digital_twin_name"] + "-dispatcher"

def dispatcher_lambda_function_name():
  return globals.config["digital_twin_name"] + "-dispatcher"

def dispatcher_iot_rule_name():
  rule_name = globals.config["digital_twin_name"] + "-trigger-dispatcher"
  return rule_name.replace("-", "_")

def persister_iam_role_name():
  return globals.config["digital_twin_name"] + "-persister"

def persister_lambda_function_name():
  return globals.config["digital_twin_name"] + "-persister"

def event_checker_iam_role_name():
  return globals.config["digital_twin_name"] + "-event-checker"

def event_checker_lambda_function_name():
  return globals.config["digital_twin_name"] + "-event-checker"

def hot_dynamodb_table_name():
  return globals.config["digital_twin_name"] + "-hot-iot-data"

def hot_cold_mover_iam_role_name():
  return globals.config["digital_twin_name"] + "-hot-to-cold-mover"

def hot_cold_mover_lambda_function_name():
  return globals.config["digital_twin_name"] + "-hot-to-cold-mover"

def hot_cold_mover_event_rule_name():
  return globals.config["digital_twin_name"] + "-hot-to-cold-mover"

def cold_archive_mover_iam_role_name():
  return globals.config["digital_twin_name"] + "-cold-to-archive-mover"

def cold_archive_mover_lambda_function_name():
  return globals.config["digital_twin_name"] + "-cold-to-archive-mover"

def cold_archive_mover_event_rule_name():
  return globals.config["digital_twin_name"] + "-cold-to-archive-mover"

def cold_s3_bucket_name():
  return globals.config["digital_twin_name"] + "-cold-iot-data"

def archive_s3_bucket_name():
  return globals.config["digital_twin_name"] + "-archive-iot-data"

def hot_reader_iam_role_name():
  return globals.config["digital_twin_name"] + "-hot-reader"

def hot_reader_lambda_function_name():
  return globals.config["digital_twin_name"] + "-hot-reader"

def hot_reader_last_entry_iam_role_name():
  return globals.config["digital_twin_name"] + "-hot-reader-last-entry"

def hot_reader_last_entry_lambda_function_name():
  return globals.config["digital_twin_name"] + "-hot-reader-last-entry"

def twinmaker_s3_bucket_name():
  return globals.config["digital_twin_name"] + "-twinmaker"

def twinmaker_iam_role_name():
  return globals.config["digital_twin_name"] + "-twinmaker"

def twinmaker_workspace_name():
  return globals.config["digital_twin_name"] + "-twinmaker"

def grafana_workspace_name():
  return globals.config["digital_twin_name"] + "-grafana"

def grafana_iam_role_name():
  return globals.config["digital_twin_name"] + "-grafana"

def iot_thing_name(iot_device):
  return globals.config["digital_twin_name"] + "-" + iot_device["id"]

def iot_thing_policy_name(iot_device):
  return globals.config["digital_twin_name"] + "-" + iot_device["id"]

def processor_iam_role_name(iot_device):
  return globals.config["digital_twin_name"] + "-" + iot_device["id"] + "-processor"

def processor_lambda_function_name(iot_device):
  return globals.config["digital_twin_name"] + "-" + iot_device["id"] + "-processor"

def twinmaker_component_type_id(iot_device):
  return globals.config["digital_twin_name"] + "-" + iot_device["id"]

def initialize_aws_iot_data_client():
  global config
  global aws_iot_data_client
  aws_iot_data_client = boto3.client("iot-data",
    aws_access_key_id=globals.config_credentials_aws["aws_access_key_id"],
    aws_secret_access_key=globals.config_credentials_aws["aws_secret_access_key"],
    region_name=globals.config_credentials_aws["aws_region"])

def initialize_aws_sf_client():
  global config
  global aws_sf_client
  aws_sf_client = boto3.client("stepfunctions",
    aws_access_key_id=globals.config_credentials_aws["aws_access_key_id"],
    aws_secret_access_key=globals.config_credentials_aws["aws_secret_access_key"],
    region_name=globals.config_credentials_aws["aws_region"])

def lambda_chain_iam_role_name():
  return globals.config["digital_twin_name"] + "-lambda-chain"

def lambda_chain_step_function_name():
  return globals.config["digital_twin_name"] + "-lambda-chain"

def event_feedback_iam_role_name():
  return globals.config["digital_twin_name"] + "-event-feedback"

def event_feedback_lambda_function_name():
  return globals.config["digital_twin_name"] + "-event-feedback"
def connector_lambda_function_name(iot_device):
    return f"{globals.config['digital_twin_name']}-{iot_device['iotDeviceId']}-connector"

def ingestion_lambda_function_name():
    return f"{globals.config['digital_twin_name']}-ingestion"

def writer_lambda_function_name():
    return f"{globals.config['digital_twin_name']}-writer"
