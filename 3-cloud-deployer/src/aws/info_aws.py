from globals import logger_proxy as logger
import aws.globals_aws as globals_aws
from botocore.exceptions import ClientError
import util

def check_dispatcher_iam_role():
  role_name = globals_aws.dispatcher_iam_role_name()

  try:
    globals_aws.aws_iam_client.get_role(RoleName=role_name)
    logger.info(f"✅ Dispatcher IAM Role exists: {util.link_to_iam_role(role_name)}")
  except ClientError as e:
    if e.response["Error"]["Code"] == "NoSuchEntity":
      logger.error(f"❌ Dispatcher IAM Role missing: {role_name}")
    else:
      raise

def check_dispatcher_lambda_function():
  function_name = globals_aws.dispatcher_lambda_function_name()

  try:
    globals_aws.aws_lambda_client.get_function(FunctionName=function_name)
    logger.info(f"✅ Dispatcher Lambda Function exists: {util.link_to_lambda_function(function_name)}")
  except ClientError as e:
    if e.response["Error"]["Code"] == "ResourceNotFoundException":
      logger.error(f"❌ Dispatcher Lambda Function missing: {function_name}")
    else:
      raise

def check_dispatcher_iot_rule():
  rule_name = globals_aws.dispatcher_iot_rule_name()

  try:
    globals_aws.aws_iot_client.get_topic_rule(ruleName=rule_name)
    logger.info(f"✅ Dispatcher Iot Rule exists: {util.link_to_iot_rule(rule_name)}")
  except ClientError as e:
    if e.response["Error"]["Code"] == "UnauthorizedException":
      logger.error(f"❌ Dispatcher IoT Rule missing: {rule_name}")
    else:
      raise

def check_iot_thing(iot_device):
  thing_name = globals_aws.iot_thing_name(iot_device)

  try:
    globals_aws.aws_iot_client.describe_thing(thingName=thing_name)
    logger.info(f"✅ Iot Thing {thing_name} exists: {util.link_to_iot_thing(thing_name)}")
  except ClientError as e:
    if e.response["Error"]["Code"] == "ResourceNotFoundException":
      logger.error(f"❌ IoT Thing {thing_name} missing: {thing_name}")
    else:
      raise

def check_persister_iam_role():
  role_name = globals_aws.persister_iam_role_name()

  try:
    globals_aws.aws_iam_client.get_role(RoleName=role_name)
    logger.info(f"✅ Persister IAM Role exists: {util.link_to_iam_role(role_name)}")
  except ClientError as e:
    if e.response["Error"]["Code"] == "NoSuchEntity":
      logger.error(f"❌ Persister IAM Role missing: {role_name}")
    else:
      raise

def check_persister_lambda_function():
  function_name = globals_aws.persister_lambda_function_name()

  try:
    globals_aws.aws_lambda_client.get_function(FunctionName=function_name)
    logger.info(f"✅ Persister Lambda Function exists: {util.link_to_lambda_function(function_name)}")
  except ClientError as e:
    if e.response["Error"]["Code"] == "ResourceNotFoundException":
      logger.error(f"❌ Persister Lambda Function missing: {function_name}")
    else:
      raise

def check_event_checker_iam_role():
  role_name = globals_aws.event_checker_iam_role_name()

  try:
    globals_aws.aws_iam_client.get_role(RoleName=role_name)
    logger.info(f"✅ Event Checker IAM Role exists: {util.link_to_iam_role(role_name)}")
  except ClientError as e:
    if e.response["Error"]["Code"] == "NoSuchEntity":
      logger.error(f"❌ Event Checker IAM Role missing: {role_name}")
    else:
      raise

def check_event_checker_lambda_function():
  function_name = globals_aws.event_checker_lambda_function_name()

  try:
    globals_aws.aws_lambda_client.get_function(FunctionName=function_name)
    logger.info(f"✅ Event Checker Lambda Function exists: {util.link_to_lambda_function(function_name)}")
  except ClientError as e:
    if e.response["Error"]["Code"] == "ResourceNotFoundException":
      logger.error(f"❌ Event Checker Lambda Function missing: {function_name}")
    else:
      raise

def check_event_checker_iam_role():
  role_name = globals_aws.event_checker_iam_role_name()

  try:
    globals_aws.aws_iam_client.get_role(RoleName=role_name)
    logger.info(f"✅ Event-Checker IAM Role exists: {util.link_to_iam_role(role_name)}")
  except ClientError as e:
    if e.response["Error"]["Code"] == "NoSuchEntity":
      logger.error(f"❌ Event-Checker IAM Role missing: {role_name}")
    else:
      raise

def check_event_checker_lambda_function():
  function_name = globals_aws.event_checker_lambda_function_name()

  try:
    globals_aws.aws_lambda_client.get_function(FunctionName=function_name)
    logger.info(f"✅ Event-Checker Lambda Function exists: {util.link_to_lambda_function(function_name)}")
  except ClientError as e:
    if e.response["Error"]["Code"] == "ResourceNotFoundException":
      logger.error(f"❌ Event-Checker Lambda Function missing: {function_name}")
    else:
      raise

def check_processor_iam_role(iot_device):
  role_name = globals_aws.processor_iam_role_name(iot_device)

  try:
    globals_aws.aws_iam_client.get_role(RoleName=role_name)
    logger.info(f"✅ Processor {role_name} IAM Role exists: {util.link_to_iam_role(role_name)}")
  except ClientError as e:
    if e.response["Error"]["Code"] == "NoSuchEntity":
      logger.error(f"❌ Processor {role_name} IAM Role missing: {role_name}")
    else:
      raise

def check_processor_lambda_function(iot_device):
  function_name = globals_aws.processor_lambda_function_name(iot_device)

  try:
    globals_aws.aws_lambda_client.get_function(FunctionName=function_name)
    logger.info(f"✅ Processor {function_name} Lambda Function exists: {util.link_to_lambda_function(function_name)}")
  except ClientError as e:
    if e.response["Error"]["Code"] == "ResourceNotFoundException":
      logger.error(f"❌ Processor {function_name} Lambda Function missing: {function_name}")
    else:
      raise

def check_hot_dynamodb_table():
  table_name = globals_aws.hot_dynamodb_table_name()

  try:
    globals_aws.aws_dynamodb_client.describe_table(TableName=table_name)
    logger.info(f"✅ DynamoDb Table exists: {util.link_to_dynamodb_table(table_name)}")
  except ClientError as e:
    if e.response["Error"]["Code"] == "ResourceNotFoundException":
      logger.error(f"❌ DynamoDb Table missing: {table_name}")
    else:
      raise

def check_hot_cold_mover_iam_role():
  role_name = globals_aws.hot_cold_mover_iam_role_name()

  try:
    globals_aws.aws_iam_client.get_role(RoleName=role_name)
    logger.info(f"✅ Hot to Cold Mover IAM Role exists: {util.link_to_iam_role(role_name)}")
  except ClientError as e:
    if e.response["Error"]["Code"] == "NoSuchEntity":
      logger.error(f"❌ Hot to Cold Mover IAM Role missing: {role_name}")
    else:
      raise

def check_hot_cold_mover_lambda_function():
  function_name = globals_aws.hot_cold_mover_lambda_function_name()

  try:
    globals_aws.aws_lambda_client.get_function(FunctionName=function_name)
    logger.info(f"✅ Hot to Cold Mover Lambda Function exists: {util.link_to_lambda_function(function_name)}")
  except ClientError as e:
    if e.response["Error"]["Code"] == "ResourceNotFoundException":
      logger.error(f"❌ Hot to Cold Mover Lambda Function missing: {function_name}")
    else:
      raise

def check_hot_cold_mover_event_rule():
  rule_name = globals_aws.hot_cold_mover_event_rule_name()

  try:
    globals_aws.aws_events_client.describe_rule(Name=rule_name)
    logger.info(f"✅ Hot to Cold Mover EventBridge Rule exists: {util.link_to_event_rule(rule_name)}")
  except ClientError as e:
    if e.response["Error"]["Code"] == "ResourceNotFoundException":
      logger.error(f"❌ Hot to Cold Mover EventBridge Rule missing: {rule_name}")
    else:
      raise

def check_hot_reader_iam_role():
  role_name = globals_aws.hot_reader_iam_role_name()

  try:
    globals_aws.aws_iam_client.get_role(RoleName=role_name)
    logger.info(f"✅ Hot Reader IAM Role exists: {util.link_to_iam_role(role_name)}")
  except ClientError as e:
    if e.response["Error"]["Code"] == "NoSuchEntity":
      logger.error(f"❌ Hot Reader IAM Role missing: {role_name}")
    else:
      raise

def check_hot_reader_lambda_function():
  function_name = globals_aws.hot_reader_lambda_function_name()

  try:
    globals_aws.aws_lambda_client.get_function(FunctionName=function_name)
    logger.info(f"✅ Hot Reader Lambda Function exists: {util.link_to_lambda_function(function_name)}")
  except ClientError as e:
    if e.response["Error"]["Code"] == "ResourceNotFoundException":
      logger.error(f"❌ Hot Reader Lambda Function missing: {function_name}")
    else:
      raise

def check_hot_reader_last_entry_iam_role():
  role_name = globals_aws.hot_reader_last_entry_iam_role_name()

  try:
    globals_aws.aws_iam_client.get_role(RoleName=role_name)
    logger.info(f"✅ Hot Reader Last Entry IAM Role exists: {util.link_to_iam_role(role_name)}")
  except ClientError as e:
    if e.response["Error"]["Code"] == "NoSuchEntity":
      logger.error(f"❌ Hot Reader Last Entry IAM Role missing: {role_name}")
    else:
      raise

def check_hot_reader_last_entry_lambda_function():
  function_name = globals_aws.hot_reader_last_entry_lambda_function_name()

  try:
    globals_aws.aws_lambda_client.get_function(FunctionName=function_name)
    logger.info(f"✅ Hot Reader Last Entry Lambda Function exists: {util.link_to_lambda_function(function_name)}")
  except ClientError as e:
    if e.response["Error"]["Code"] == "ResourceNotFoundException":
      logger.error(f"❌ Hot Reader Last Entry Lambda Function missing: {function_name}")
    else:
      raise

def check_cold_s3_bucket():
  bucket_name = globals_aws.cold_s3_bucket_name()

  try:
    globals_aws.aws_s3_client.head_bucket(Bucket=bucket_name)
    logger.info(f"✅ Cold S3 Bucket exists: {util.link_to_s3_bucket(bucket_name)}")
  except ClientError as e:
    if int(e.response["Error"]["Code"]) == 404:
      logger.error(f"❌ Cold S3 Bucket missing: {bucket_name}")
    else:
      raise

def check_cold_archive_mover_iam_role():
  role_name = globals_aws.cold_archive_mover_iam_role_name()

  try:
    globals_aws.aws_iam_client.get_role(RoleName=role_name)
    logger.info(f"✅ Cold to Archive Mover IAM Role exists: {util.link_to_iam_role(role_name)}")
  except ClientError as e:
    if e.response["Error"]["Code"] == "NoSuchEntity":
      logger.error(f"❌ Cold to Archive Mover IAM Role missing: {role_name}")
    else:
      raise

def check_cold_archive_mover_lambda_function():
  function_name = globals_aws.cold_archive_mover_lambda_function_name()

  try:
    globals_aws.aws_lambda_client.get_function(FunctionName=function_name)
    logger.info(f"✅ Cold to Archive Mover Lambda Function exists: {util.link_to_lambda_function(function_name)}")
  except ClientError as e:
    if e.response["Error"]["Code"] == "ResourceNotFoundException":
      logger.error(f"❌ Cold to Archive Mover Lambda Function missing: {function_name}")
    else:
      raise

def check_cold_archive_mover_event_rule():
  rule_name = globals_aws.cold_archive_mover_event_rule_name()

  try:
    globals_aws.aws_events_client.describe_rule(Name=rule_name)
    logger.info(f"✅ Cold to Archive Mover EventBridge Rule exists: {util.link_to_event_rule(rule_name)}")
  except ClientError as e:
    if e.response["Error"]["Code"] == "ResourceNotFoundException":
      logger.error(f"❌ Cold to Archive Mover EventBridge Rule missing: {rule_name}")
    else:
      raise

def check_archive_s3_bucket():
  bucket_name = globals_aws.archive_s3_bucket_name()

  try:
    globals_aws.aws_s3_client.head_bucket(Bucket=bucket_name)
    logger.info(f"✅ Archive S3 Bucket exists: {util.link_to_s3_bucket(bucket_name)}")
  except ClientError as e:
    if int(e.response["Error"]["Code"]) == 404:
      logger.error(f"❌ Archive S3 Bucket missing: {bucket_name}")
    else:
      raise

def check_twinmaker_s3_bucket():
  bucket_name = globals_aws.twinmaker_s3_bucket_name()

  try:
    globals_aws.aws_s3_client.head_bucket(Bucket=bucket_name)
    logger.info(f"✅ Twinmaker S3 Bucket exists: {util.link_to_s3_bucket(bucket_name)}")
  except ClientError as e:
    if int(e.response["Error"]["Code"]) == 404:
      logger.error(f"❌ Twinmaker S3 Bucket missing: {bucket_name}")
    if int(e.response["Error"]["Code"]) == 403:
      logger.error(f"❌ Twinmaker S3 Bucket access forbidden (check permissions or given credentials): {bucket_name}")
    else:
      raise

def check_twinmaker_iam_role():
  role_name = globals_aws.twinmaker_iam_role_name()

  try:
    globals_aws.aws_iam_client.get_role(RoleName=role_name)
    logger.info(f"✅ Twinmaker IAM Role exists: {util.link_to_iam_role(role_name)}")
  except ClientError as e:
    if e.response["Error"]["Code"] == "NoSuchEntity":
      logger.error(f"❌ Twinmaker IAM Role missing: {role_name}")
    else:
      raise

def check_twinmaker_workspace():
  workspace_name = globals_aws.twinmaker_workspace_name()

  try:
    globals_aws.aws_twinmaker_client.get_workspace(workspaceId=workspace_name)
    logger.info(f"✅ Twinmaker Workspace exists: {util.link_to_twinmaker_workspace(workspace_name)}")
  except ClientError as e:
    if e.response["Error"]["Code"] == "ResourceNotFoundException":
      logger.error(f"❌ Twinmaker Workspace missing: {workspace_name}")
    else:
      raise

def check_twinmaker_component_type(iot_device):
  workspace_name = globals_aws.twinmaker_workspace_name()
  component_type_id = globals_aws.twinmaker_component_type_id(iot_device)

  try:
    globals_aws.aws_twinmaker_client.get_component_type(workspaceId=workspace_name, componentTypeId=component_type_id)
    logger.info(f"✅ Twinmaker Component Type {component_type_id} exists: {util.link_to_twinmaker_component_type(workspace_name, component_type_id)}")
  except ClientError as e:
    if e.response["Error"]["Code"] == "ResourceNotFoundException":
      logger.error(f"❌ Twinmaker Component Type {component_type_id} missing: {component_type_id}")
    else:
      raise

def check_grafana_iam_role():
  role_name = globals_aws.grafana_iam_role_name()

  try:
    globals_aws.aws_iam_client.get_role(RoleName=role_name)
    logger.info(f"✅ Grafana IAM Role exists: {util.link_to_iam_role(role_name)}")
  except ClientError as e:
    if e.response["Error"]["Code"] == "NoSuchEntity":
      logger.error(f"❌ Grafana IAM Role missing: {role_name}")
    else:
      raise

def check_grafana_workspace():
  workspace_name = globals_aws.grafana_workspace_name()

  try:
    workspace_id = util.get_grafana_workspace_id_by_name(workspace_name)
    globals_aws.aws_grafana_client.describe_workspace(workspaceId=workspace_id)
    logger.info(f"✅ Grafana Workspace exists: {util.link_to_grafana_workspace(workspace_id)}")
  except ClientError as e:
    if e.response["Error"]["Code"] == "ResourceNotFoundException":
      logger.error(f"❌ Grafana Workspace missing: {workspace_name}")
    else:
      raise
