import json
import os
import time
from datetime import datetime, timezone
import globals
from logger import logger
import aws.globals_aws as globals_aws
import util
import aws.util_aws as util_aws
from botocore.exceptions import ClientError
import constants as CONSTANTS

# ==========================================
# 1. Constants & Helpers
# ==========================================

# Helper path for core lambda functions
# Location: src/aws/lambda_functions/
# These are internal functions NOT editable by the user
CORE_LAMBDA_DIR = os.path.join(globals.project_path(), CONSTANTS.AWS_CORE_LAMBDA_DIR_NAME)

# ==========================================
# 2. Hot Storage (DynamoDB)
# ==========================================

def create_hot_dynamodb_table():
  """
  Creates the DynamoDB table for Hot Storage.
  
  Infrastructure Component:
  - Table Name: Defined dynamically based on digital twin name.
  - Usage: Stores recent telemetry data for fast access (Layer 3 Hot).
  """
  table_name = globals_aws.hot_dynamodb_table_name()

  globals_aws.aws_dynamodb_client.create_table(
    TableName=table_name,
    KeySchema=[
      {'AttributeName': 'iotDeviceId', 'KeyType': 'HASH'},  # partition key
      {'AttributeName': 'id', 'KeyType': 'RANGE'}           # sort key
    ],
    AttributeDefinitions=[
      {'AttributeName': 'iotDeviceId', 'AttributeType': 'S'},
      {'AttributeName': 'id', 'AttributeType': 'S'}
    ],
    BillingMode='PAY_PER_REQUEST'
  )

  logger.info(f"Creation of DynamoDb table initiated: {table_name}")

  waiter = globals_aws.aws_dynamodb_client.get_waiter('table_exists')
  waiter.wait(TableName=table_name)

  logger.info(f"Created DynamoDb table: {table_name}")

def destroy_hot_dynamodb_table():
  table_name = globals_aws.hot_dynamodb_table_name()
  timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
  backup_name = f"{table_name}-backup-{timestamp}"

  try:
    response = globals_aws.aws_dynamodb_client.create_backup(TableName=table_name, BackupName=backup_name)
  except ClientError as e:
    if e.response["Error"]["Code"] == "ResourceNotFoundException" or e.response["Error"]["Code"] == "TableNotFoundException":
      return
    else:
      raise

  backup_arn = response["BackupDetails"]["BackupArn"]
  logger.info(f"Backup of DynamoDb table initiated: {backup_name}, {backup_arn}")

  while True:
    response_d = globals_aws.aws_dynamodb_client.describe_backup(BackupArn=backup_arn)
    status = response_d["BackupDescription"]["BackupDetails"]["BackupStatus"]

    if status == "AVAILABLE" or status == "ACTIVE":
      break

    time.sleep(5)

  logger.info("Backup creation of DynamoDb table succeeded.")

  globals_aws.aws_dynamodb_client.delete_table(TableName=table_name)
  logger.info(f"Deletion of DynamoDb table initiated: {table_name}")

  waiter = globals_aws.aws_dynamodb_client.get_waiter("table_not_exists")
  waiter.wait(TableName=table_name)

  logger.info(f"Deleted DynamoDb table: {table_name}")

# ==========================================
# 3. Mover Functions (Hot-Cold)
# ==========================================

def create_hot_cold_mover_iam_role():
  """
  Creates IAM Role for the Hot-to-Cold Data Mover.
  """
  role_name = globals_aws.hot_cold_mover_iam_role_name()

  globals_aws.aws_iam_client.create_role(
      RoleName=role_name,
      AssumeRolePolicyDocument=json.dumps(
        {
          "Version": "2012-10-17",
          "Statement": [
            {
              "Effect": "Allow",
              "Principal": {
                "Service": "lambda.amazonaws.com"
              },
              "Action": "sts:AssumeRole"
            }
          ]
        }
      )
  )

  logger.info(f"Created IAM role: {role_name}")

  policy_arns = [
    CONSTANTS.AWS_POLICY_LAMBDA_BASIC_EXECUTION,
    CONSTANTS.AWS_POLICY_DYNAMODB_FULL_ACCESS,
    CONSTANTS.AWS_POLICY_S3_FULL_ACCESS
  ]

  for policy_arn in policy_arns:
    globals_aws.aws_iam_client.attach_role_policy(
      RoleName=role_name,
      PolicyArn=policy_arn
    )

    logger.info(f"Attached IAM policy ARN: {policy_arn}")

  logger.info(f"Waiting for propagation...")

  time.sleep(20)

def destroy_hot_cold_mover_iam_role():
  role_name = globals_aws.hot_cold_mover_iam_role_name()

  try:
    # detach managed policies
    response = globals_aws.aws_iam_client.list_attached_role_policies(RoleName=role_name)
    for policy in response["AttachedPolicies"]:
        globals_aws.aws_iam_client.detach_role_policy(RoleName=role_name, PolicyArn=policy["PolicyArn"])

    # delete inline policies
    response = globals_aws.aws_iam_client.list_role_policies(RoleName=role_name)
    for policy_name in response["PolicyNames"]:
        globals_aws.aws_iam_client.delete_role_policy(RoleName=role_name, PolicyName=policy_name)

    # remove from instance profiles
    response = globals_aws.aws_iam_client.list_instance_profiles_for_role(RoleName=role_name)
    for profile in response["InstanceProfiles"]:
      globals_aws.aws_iam_client.remove_role_from_instance_profile(
        InstanceProfileName=profile["InstanceProfileName"],
        RoleName=role_name
      )

    # delete the role
    globals_aws.aws_iam_client.delete_role(RoleName=role_name)
    logger.info(f"Deleted IAM role: {role_name}")
  except ClientError as e:
    if e.response["Error"]["Code"] != "NoSuchEntity":
      raise

def create_hot_cold_mover_lambda_function():
  """
  Creates the Hot-to-Cold Data Mover Lambda.
  
  Function Description:
  - Runs on a schedule.
  - Moves data older than `hot_storage_size_in_days` from DynamoDB to S3 (Cold Storage).
  
  Project Structure Location:
  - Source Code: Hardcoded in `src/aws/lambda_functions/hot-to-cold-mover`
  - NOT User Editable.
  """
  function_name = globals_aws.hot_cold_mover_lambda_function_name()
  role_name = globals_aws.hot_cold_mover_iam_role_name()

  response = globals_aws.aws_iam_client.get_role(RoleName=role_name)
  role_arn = response['Role']['Arn']

  globals_aws.aws_lambda_client.create_function(
    FunctionName=function_name,
    Runtime="python3.13",
    Role=role_arn,
    Handler="lambda_function.lambda_handler", #  file.function
    # Source Code Location: src/aws/lambda_functions/hot-to-cold-mover
    Code={"ZipFile": util.compile_lambda_function(os.path.join(CORE_LAMBDA_DIR, "hot-to-cold-mover"))},
    Description="Moves expired hot data to cold storage (S3)",
    Timeout=3, # seconds
    MemorySize=128, # MB
    Publish=True,
    Environment={
      "Variables": {
        "DIGITAL_TWIN_INFO": json.dumps(globals.digital_twin_info()),
        "DYNAMODB_TABLE_NAME": globals_aws.hot_dynamodb_table_name(),
        "S3_BUCKET_NAME": globals_aws.cold_s3_bucket_name()
      }
    }
  )

  logger.info(f"Created Lambda function: {function_name}")

def destroy_hot_cold_mover_lambda_function():
  function_name = globals_aws.hot_cold_mover_lambda_function_name()

  try:
    globals_aws.aws_lambda_client.delete_function(FunctionName=function_name)
    logger.info(f"Deleted Lambda function: {function_name}")
  except ClientError as e:
    if e.response["Error"]["Code"] != "ResourceNotFoundException":
      raise

def create_hot_cold_mover_event_rule():
  """
  Creates the EventBridge Rule to schedule the Hot-to-Cold Mover.
  
  Schedule: Daily at 12:00 UTC (defined in constants.py).
  """
  rule_name = globals_aws.hot_cold_mover_event_rule_name()
  schedule_expression = CONSTANTS.AWS_CRON_HOT_TO_COLD

  function_name = globals_aws.hot_cold_mover_lambda_function_name()

  rule_response = globals_aws.aws_events_client.put_rule(
    Name=rule_name,
    ScheduleExpression=schedule_expression,
    State="ENABLED",
    Description="Daily trigger for hot-to-cold data movement",
  )
  rule_arn = rule_response["RuleArn"]

  logger.info(f"Created EventBridge rule: {rule_name}")

  lambda_arn = globals_aws.aws_lambda_client.get_function(FunctionName=function_name)["Configuration"]["FunctionArn"]

  globals_aws.aws_events_client.put_targets(
    Rule=rule_name,
    Targets=[
        {
            "Id": "1",
            "Arn": lambda_arn,
        }
    ]
  )

  logger.info(f"Added Lambda function as target.")

  globals_aws.aws_lambda_client.add_permission(
    FunctionName=function_name,
    StatementId="events-invoke",
    Action="lambda:InvokeFunction",
    Principal="events.amazonaws.com",
    SourceArn=rule_arn,
  )

  logger.info(f"Added permission to Lambda function so the rule can invoke the function.")

def destroy_hot_cold_mover_event_rule():
  rule_name = globals_aws.hot_cold_mover_event_rule_name()
  function_name = globals_aws.hot_cold_mover_lambda_function_name()

  try:
    globals_aws.aws_lambda_client.remove_permission(FunctionName=function_name, StatementId="events-invoke")
    logger.info(f"Removed permission from Lambda function: {rule_name}, {function_name}")
  except globals_aws.aws_lambda_client.exceptions.ResourceNotFoundException:
    pass

  try:
    response = globals_aws.aws_events_client.list_targets_by_rule(Rule=rule_name, EventBusName="default")
    target_ids = [t["Id"] for t in response.get("Targets", [])]

    if target_ids:
      globals_aws.aws_events_client.remove_targets(Rule=rule_name, EventBusName="default", Ids=target_ids, Force=True)
      logger.info(f"Removed targets from EventBridge Rule: {target_ids}")
  except globals_aws.aws_events_client.exceptions.ResourceNotFoundException:
    pass

  try:
    globals_aws.aws_events_client.describe_rule(Name=rule_name)
    globals_aws.aws_events_client.delete_rule(Name=rule_name, Force=True)
    logger.info(f"Deleted EventBridge rule: {rule_name}")
  except globals_aws.aws_events_client.exceptions.ResourceNotFoundException:
    pass

# ==========================================
# 4. Cold Storage (S3) & Mover (Cold-Archive)
# ==========================================

def create_cold_s3_bucket():
  """
  Creates the S3 Bucket for Cold Storage.
  """
  bucket_name = globals_aws.cold_s3_bucket_name()

  globals_aws.aws_s3_client.create_bucket(
    Bucket=bucket_name,
    CreateBucketConfiguration={
        "LocationConstraint": globals_aws.aws_s3_client.meta.region_name
    }
  )

  logger.info(f"Created S3 Bucket: {bucket_name}")

def destroy_cold_s3_bucket():
  bucket_name = globals_aws.cold_s3_bucket_name()

  util_aws.destroy_s3_bucket(bucket_name)

def create_cold_archive_mover_iam_role():
  """
  Creates IAM Role for the Cold-to-Archive Data Mover.
  """
  role_name = globals_aws.cold_archive_mover_iam_role_name()

  globals_aws.aws_iam_client.create_role(
      RoleName=role_name,
      AssumeRolePolicyDocument=json.dumps(
        {
          "Version": "2012-10-17",
          "Statement": [
            {
              "Effect": "Allow",
              "Principal": {
                "Service": "lambda.amazonaws.com"
              },
              "Action": "sts:AssumeRole"
            }
          ]
        }
      )
  )

  logger.info(f"Created IAM role: {role_name}")

  policy_arns = [
    CONSTANTS.AWS_POLICY_LAMBDA_BASIC_EXECUTION,
    CONSTANTS.AWS_POLICY_S3_FULL_ACCESS
  ]

  for policy_arn in policy_arns:
    globals_aws.aws_iam_client.attach_role_policy(
      RoleName=role_name,
      PolicyArn=policy_arn
    )

    logger.info(f"Attached IAM policy ARN: {policy_arn}")

  logger.info(f"Waiting for propagation...")

  time.sleep(20)

def destroy_cold_archive_mover_iam_role():
  role_name = globals_aws.cold_archive_mover_iam_role_name()

  try:
    # detach managed policies
    response = globals_aws.aws_iam_client.list_attached_role_policies(RoleName=role_name)
    for policy in response["AttachedPolicies"]:
        globals_aws.aws_iam_client.detach_role_policy(RoleName=role_name, PolicyArn=policy["PolicyArn"])

    # delete inline policies
    response = globals_aws.aws_iam_client.list_role_policies(RoleName=role_name)
    for policy_name in response["PolicyNames"]:
        globals_aws.aws_iam_client.delete_role_policy(RoleName=role_name, PolicyName=policy_name)

    # remove from instance profiles
    response = globals_aws.aws_iam_client.list_instance_profiles_for_role(RoleName=role_name)
    for profile in response["InstanceProfiles"]:
      globals_aws.aws_iam_client.remove_role_from_instance_profile(
        InstanceProfileName=profile["InstanceProfileName"],
        RoleName=role_name
      )

    # delete the role
    globals_aws.aws_iam_client.delete_role(RoleName=role_name)
    logger.info(f"Deleted IAM role: {role_name}")
  except ClientError as e:
    if e.response["Error"]["Code"] != "NoSuchEntity":
      raise

def create_cold_archive_mover_lambda_function():
  """
  Creates the Cold-to-Archive Data Mover Lambda.
  
  Function Description:
  - Runs on a schedule.
  - Moves data older than `cold_storage_size_in_days` from S3 Cold to S3 Archive.
  
  Project Structure Location:
  - Source Code: Hardcoded in `src/aws/lambda_functions/cold-to-archive-mover`
  - NOT User Editable.
  """
  function_name = globals_aws.cold_archive_mover_lambda_function_name()
  role_name = globals_aws.cold_archive_mover_iam_role_name()

  response = globals_aws.aws_iam_client.get_role(RoleName=role_name)
  role_arn = response['Role']['Arn']

  globals_aws.aws_lambda_client.create_function(
    FunctionName=function_name,
    Runtime="python3.13",
    Role=role_arn,
    Handler="lambda_function.lambda_handler", #  file.function
    # Source Code Location: src/aws/lambda_functions/cold-to-archive-mover
    Code={"ZipFile": util.compile_lambda_function(os.path.join(CORE_LAMBDA_DIR, "cold-to-archive-mover"))},
    Description="Moves expired cold data to archive storage (S3 Glacier)",
    Timeout=3, # seconds
    MemorySize=128, # MB
    Publish=True,
    Environment={
      "Variables": {
        "DIGITAL_TWIN_INFO": json.dumps(globals.digital_twin_info()),
        "SOURCE_S3_BUCKET_NAME": globals_aws.cold_s3_bucket_name(),
        "TARGET_S3_BUCKET_NAME": globals_aws.archive_s3_bucket_name()
      }
    }
  )

  logger.info(f"Created Lambda function: {function_name}")

def destroy_cold_archive_mover_lambda_function():
  function_name = globals_aws.cold_archive_mover_lambda_function_name()

  try:
    globals_aws.aws_lambda_client.delete_function(FunctionName=function_name)
    logger.info(f"Deleted Lambda function: {function_name}")
  except ClientError as e:
    if e.response["Error"]["Code"] != "ResourceNotFoundException":
      raise

def create_cold_archive_mover_event_rule():
  """
  Creates the EventBridge Rule to schedule the Cold-to-Archive Mover.
  
  Schedule: Daily at 18:00 UTC (defined in constants.py).
  """
  rule_name = globals_aws.cold_archive_mover_event_rule_name()
  function_name = globals_aws.cold_archive_mover_lambda_function_name()

  schedule_expression = CONSTANTS.AWS_CRON_COLD_TO_ARCHIVE

  rule_arn = globals_aws.aws_events_client.put_rule(Name=rule_name, ScheduleExpression=schedule_expression, State="ENABLED")["RuleArn"]

  logger.info(f"Created EventBridge Rule: {rule_name}")

  lambda_arn = globals_aws.aws_lambda_client.get_function(FunctionName=function_name)["Configuration"]["FunctionArn"]

  globals_aws.aws_events_client.put_targets(
    Rule=rule_name,
    Targets=[
        {
            "Id": "1",
            "Arn": lambda_arn,
        }
    ]
  )

  logger.info(f"Added Lambda Function as target.")

  globals_aws.aws_lambda_client.add_permission(
    FunctionName=function_name,
    StatementId="events-invoke",
    Action="lambda:InvokeFunction",
    Principal="events.amazonaws.com",
    SourceArn=rule_arn,
  )

  logger.info(f"Added permission to Lambda Function so the rule can invoke the function.")

def destroy_cold_archive_mover_event_rule():
  rule_name = globals_aws.cold_archive_mover_event_rule_name()
  function_name = globals_aws.cold_archive_mover_lambda_function_name()

  try:
    globals_aws.aws_lambda_client.remove_permission(FunctionName=function_name, StatementId="events-invoke")
    logger.info(f"Removed permission from Lambda Function: {rule_name}, {function_name}")
  except globals_aws.aws_lambda_client.exceptions.ResourceNotFoundException:
    pass

  try:
    response = globals_aws.aws_events_client.list_targets_by_rule(Rule=rule_name, EventBusName="default")
    target_ids = [t["Id"] for t in response.get("Targets", [])]

    if target_ids:
      globals_aws.aws_events_client.remove_targets(Rule=rule_name, EventBusName="default", Ids=target_ids, Force=True)
      logger.info(f"Removed targets from EventBridge Rule: {target_ids}")
  except globals_aws.aws_events_client.exceptions.ResourceNotFoundException:
    pass

  try:
    globals_aws.aws_events_client.describe_rule(Name=rule_name)
    globals_aws.aws_events_client.delete_rule(Name=rule_name, Force=True)
    logger.info(f"Deleted EventBridge Rule: {rule_name}")
  except globals_aws.aws_events_client.exceptions.ResourceNotFoundException:
    pass

# ==========================================
# 5. Archive Storage (S3)
# ==========================================

def create_archive_s3_bucket():
  """
  Creates the S3 Bucket for Archive Storage (Glacier Deep Archive target).
  """
  bucket_name = globals_aws.archive_s3_bucket_name()

  globals_aws.aws_s3_client.create_bucket(
    Bucket=bucket_name,
    CreateBucketConfiguration={
        "LocationConstraint": globals_aws.aws_s3_client.meta.region_name
    }
  )

  logger.info(f"Created S3 Bucket: {bucket_name}")

def destroy_archive_s3_bucket():
  bucket_name = globals_aws.archive_s3_bucket_name()

  util_aws.destroy_s3_bucket(bucket_name)

# ==========================================
# 6. Hot Readers (For TwinMaker)
# ==========================================

def create_hot_reader_iam_role():
  """
  Creates IAM Role for the Hot Reader Lambda.
  """
  role_name = globals_aws.hot_reader_iam_role_name()

  globals_aws.aws_iam_client.create_role(
      RoleName=role_name,
      AssumeRolePolicyDocument=json.dumps(
        {
          "Version": "2012-10-17",
          "Statement": [
            {
              "Effect": "Allow",
              "Principal": {
                "Service": "lambda.amazonaws.com"
              },
              "Action": "sts:AssumeRole"
            }
          ]
        }
      )
  )

  logger.info(f"Created IAM role: {role_name}")

  policy_arns = [
    CONSTANTS.AWS_POLICY_LAMBDA_BASIC_EXECUTION,
    CONSTANTS.AWS_POLICY_DYNAMODB_FULL_ACCESS
  ]

  for policy_arn in policy_arns:
    globals_aws.aws_iam_client.attach_role_policy(
      RoleName=role_name,
      PolicyArn=policy_arn
    )

    logger.info(f"Attached IAM policy ARN: {policy_arn}")

  policy_name = "TwinmakerAccess"

  globals_aws.aws_iam_client.put_role_policy(
    RoleName=role_name,
    PolicyName=policy_name,
    PolicyDocument=json.dumps(
      {
        "Version": "2012-10-17",
        "Statement": [
          {
            "Effect": "Allow",
            "Action": [
              "iottwinmaker:*",
            ],
            "Resource": "*"
          }
        ]
      }
    )
  )
  logger.info(f"Attached inline IAM policy: {policy_name}")

  logger.info(f"Waiting for propagation...")

  time.sleep(20)

def destroy_hot_reader_iam_role():
  role_name = globals_aws.hot_reader_iam_role_name()

  try:
    response = globals_aws.aws_iam_client.list_attached_role_policies(RoleName=role_name)
    for policy in response["AttachedPolicies"]:
        globals_aws.aws_iam_client.detach_role_policy(RoleName=role_name, PolicyArn=policy["PolicyArn"])

    response = globals_aws.aws_iam_client.list_role_policies(RoleName=role_name)
    for policy_name in response["PolicyNames"]:
        globals_aws.aws_iam_client.delete_role_policy(RoleName=role_name, PolicyName=policy_name)

    response = globals_aws.aws_iam_client.list_instance_profiles_for_role(RoleName=role_name)
    for profile in response["InstanceProfiles"]:
      globals_aws.aws_iam_client.remove_role_from_instance_profile(
        InstanceProfileName=profile["InstanceProfileName"],
        RoleName=role_name
      )

    globals_aws.aws_iam_client.delete_role(RoleName=role_name)
    logger.info(f"Deleted IAM role: {role_name}")
  except ClientError as e:
    if e.response["Error"]["Code"] != "NoSuchEntity":
      raise

def create_hot_reader_lambda_function():
  """
  Creates the Hot Reader Lambda.
  
  Function Description:
  - Fetches data range from Hot Storage (DynamoDB).
  - Used by TwinMaker/Grafana via API Gateway.
  
  Project Structure Location:
  - Source Code: Hardcoded in `src/aws/lambda_functions/hot-reader`
  - NOT User Editable.
  """
  function_name = globals_aws.hot_reader_lambda_function_name()
  role_name = globals_aws.hot_reader_iam_role_name()

  response = globals_aws.aws_iam_client.get_role(RoleName=role_name)
  role_arn = response['Role']['Arn']

  globals_aws.aws_lambda_client.create_function(
    FunctionName=function_name,
    Runtime="python3.13",
    Role=role_arn,
    Handler="lambda_function.lambda_handler", #  file.function
    # Source Code Location: src/aws/lambda_functions/hot-reader
    Code={"ZipFile": util.compile_lambda_function(os.path.join(CORE_LAMBDA_DIR, "hot-reader"))},
    Description="Reads data range from hot storage",
    Timeout=3, # seconds
    MemorySize=128, # MB
    Publish=True,
    Environment={
      "Variables": {
        "DIGITAL_TWIN_INFO": json.dumps(globals.digital_twin_info()),
        "DYNAMODB_TABLE_NAME": globals_aws.hot_dynamodb_table_name()
      }
    }
  )

  logger.info(f"Created Lambda function: {function_name}")

def destroy_hot_reader_lambda_function():
  function_name = globals_aws.hot_reader_lambda_function_name()

  try:
    globals_aws.aws_lambda_client.delete_function(FunctionName=function_name)
    logger.info(f"Deleted Lambda function: {function_name}")
  except ClientError as e:
    if e.response["Error"]["Code"] != "ResourceNotFoundException":
      raise

def create_hot_reader_last_entry_iam_role():
  """
  Creates IAM Role for the Hot Reader (Last Entry) Lambda.
  """
  role_name = globals_aws.hot_reader_last_entry_iam_role_name()

  globals_aws.aws_iam_client.create_role(
      RoleName=role_name,
      AssumeRolePolicyDocument=json.dumps(
        {
          "Version": "2012-10-17",
          "Statement": [
            {
              "Effect": "Allow",
              "Principal": {
                "Service": "lambda.amazonaws.com"
              },
              "Action": "sts:AssumeRole"
            }
          ]
        }
      )
  )

  logger.info(f"Created IAM role: {role_name}")

  policy_arns = [
    CONSTANTS.AWS_POLICY_LAMBDA_BASIC_EXECUTION,
    CONSTANTS.AWS_POLICY_DYNAMODB_FULL_ACCESS
  ]

  for policy_arn in policy_arns:
    globals_aws.aws_iam_client.attach_role_policy(
      RoleName=role_name,
      PolicyArn=policy_arn
    )

    logger.info(f"Attached IAM policy ARN: {policy_arn}")

  policy_name = "TwinmakerAccess"

  globals_aws.aws_iam_client.put_role_policy(
    RoleName=role_name,
    PolicyName=policy_name,
    PolicyDocument=json.dumps(
      {
        "Version": "2012-10-17",
        "Statement": [
          {
            "Effect": "Allow",
            "Action": [
              "iottwinmaker:*",
            ],
            "Resource": "*"
          }
        ]
      }
    )
  )
  logger.info(f"Attached inline IAM policy: {policy_name}")

  logger.info(f"Waiting for propagation...")

  time.sleep(20)

def destroy_hot_reader_last_entry_iam_role():
  role_name = globals_aws.hot_reader_last_entry_iam_role_name()

  try:
    response = globals_aws.aws_iam_client.list_attached_role_policies(RoleName=role_name)
    for policy in response["AttachedPolicies"]:
        globals_aws.aws_iam_client.detach_role_policy(RoleName=role_name, PolicyArn=policy["PolicyArn"])

    response = globals_aws.aws_iam_client.list_role_policies(RoleName=role_name)
    for policy_name in response["PolicyNames"]:
        globals_aws.aws_iam_client.delete_role_policy(RoleName=role_name, PolicyName=policy_name)

    response = globals_aws.aws_iam_client.list_instance_profiles_for_role(RoleName=role_name)
    for profile in response["InstanceProfiles"]:
      globals_aws.aws_iam_client.remove_role_from_instance_profile(
        InstanceProfileName=profile["InstanceProfileName"],
        RoleName=role_name
      )

    globals_aws.aws_iam_client.delete_role(RoleName=role_name)
    logger.info(f"Deleted IAM role: {role_name}")
  except ClientError as e:
    if e.response["Error"]["Code"] != "NoSuchEntity":
      raise

def create_hot_reader_last_entry_lambda_function():
  """
  Creates the Hot Reader (Last Entry) Lambda.
  
  Function Description:
  - Fetches very last value for a property from Hot Storage.
  - Optimized for current-value display.
  
  Project Structure Location:
  - Source Code: Hardcoded in `src/aws/lambda_functions/hot-reader-last-entry`
  - NOT User Editable.
  """
  function_name = globals_aws.hot_reader_last_entry_lambda_function_name()
  role_name = globals_aws.hot_reader_last_entry_iam_role_name()

  response = globals_aws.aws_iam_client.get_role(RoleName=role_name)
  role_arn = response['Role']['Arn']

  globals_aws.aws_lambda_client.create_function(
    FunctionName=function_name,
    Runtime="python3.13",
    Role=role_arn,
    Handler="lambda_function.lambda_handler", #  file.function
    # Source Code Location: src/aws/lambda_functions/hot-reader-last-entry
    Code={"ZipFile": util.compile_lambda_function(os.path.join(CORE_LAMBDA_DIR, "hot-reader-last-entry"))},
    Description="Reads last entered data from hot storage",
    Timeout=3, # seconds
    MemorySize=128, # MB
    Publish=True,
    Environment={
      "Variables": {
        "DIGITAL_TWIN_INFO": json.dumps(globals.digital_twin_info()),
        "DYNAMODB_TABLE_NAME": globals_aws.hot_dynamodb_table_name()
      }
    }
  )

  logger.info(f"Created Lambda function: {function_name}")

def destroy_hot_reader_last_entry_lambda_function():
  function_name = globals_aws.hot_reader_last_entry_lambda_function_name()

  try:
    globals_aws.aws_lambda_client.delete_function(FunctionName=function_name)
    logger.info(f"Deleted Lambda function: {function_name}")
  except ClientError as e:
    if e.response["Error"]["Code"] != "ResourceNotFoundException":
      raise

# ==========================================
# 7. Writer Function
# ==========================================

def create_writer_lambda_function():
  """
  Deploys Writer Function if L2 is Remote and L3 is Local (AWS).
  
  Function Description:
  - Receives data from a remote L2 persister.
  - Writes to local DynamoDB.
  
  Project Structure Location:
  - Source Code: User Editable (part of upload template).
  - Path: upload/lambda_functions/writer
  """
  l2_provider = globals.config_providers.get("layer_2_provider", "aws")
  l3_provider = globals.config_providers.get("layer_3_hot_provider", "aws")

  if l2_provider != "aws" and l3_provider == "aws":
      function_name = globals_aws.writer_lambda_function_name()
      # Reuse Persister role? Valid, as it has DynamoDB access.
      role_name = globals_aws.persister_iam_role_name()

      try:
          response = globals_aws.aws_iam_client.get_role(RoleName=role_name)
          role_arn = response['Role']['Arn']
      except ClientError:
          logger.error(f"Persister Role {role_name} not found. Writer deployment failed.")
          return

      # Token
      conn_id = f"{l2_provider}_l2_to_{l3_provider}_l3"
      token = globals.get_inter_cloud_token(conn_id)

      # Code location: upload/lambda_functions/writer
      writer_dir = os.path.join(globals.get_project_upload_path(), CONSTANTS.LAMBDA_FUNCTIONS_DIR_NAME, "writer")

      globals_aws.aws_lambda_client.create_function(
        FunctionName=function_name,
        Runtime="python3.13",
        Role=role_arn, # Reuse Persister Role
        Handler="lambda_function.lambda_handler", 
        Code={"ZipFile": util.compile_lambda_function(writer_dir)},
        Description="Writer from Remote L2",
        Timeout=10, 
        MemorySize=128, 
        Publish=True,
        Environment={
          "Variables": {
             "INTER_CLOUD_TOKEN": token,
             "DYNAMODB_TABLE_NAME": globals_aws.hot_dynamodb_table_name()
          }
        }
      )
      
      # Enable Function URL
      globals_aws.aws_lambda_client.create_function_url_config(
        FunctionName=function_name,
        AuthType='NONE'
      )
      # Add Permission for public access
      globals_aws.aws_lambda_client.add_permission(
        FunctionName=function_name,
        StatementId="FunctionURLAllowPublicAccess",
        Action="lambda:InvokeFunctionUrl",
        Principal="*",
        FunctionUrlAuthType="NONE"
      )

      logger.info(f"Created Writer Lambda function: {function_name}")

def destroy_writer_lambda_function():
  function_name = globals_aws.writer_lambda_function_name()
  try:
    globals_aws.aws_lambda_client.delete_function(FunctionName=function_name)
    logger.info(f"Deleted Writer Lambda function: {function_name}")
  except ClientError as e:
    if e.response["Error"]["Code"] != "ResourceNotFoundException":
      logger.warning(f"Failed to delete writer function: {e}")

# ==========================================
# 8. API Gateway & Integration
# ==========================================

def create_api():
  """
  Creates the API Gateway HTTP API.
  """
  api_name = globals.api_name()

  api = globals_aws.aws_apigateway_client.create_api(
      Name=api_name,
      ProtocolType="HTTP"
  )

  logger.info(f"Created API: {api_name}")

  stage = globals_aws.aws_apigateway_client.create_stage(
    ApiId=api["ApiId"],
    StageName="$default",
    AutoDeploy=True
  )

  logger.info(f"Created API Stage: {stage['StageName']}")

def destroy_api():
  api_name = globals.api_name()
  api_id = util_aws.get_api_id_by_name(api_name)

  if api_id is None:
    return

  try:
    globals_aws.aws_apigateway_client.delete_api(ApiId=api_id)
    logger.info(f"Deleted API: {api_name}")
  except globals_aws.aws_apigateway_client.exceptions.NotFoundException:
    pass


def create_api_hot_reader_integration():
  """
  Creates integration for Hot Reader Lambda.
  """
  api_id = util_aws.get_api_id_by_name(globals.api_name())
  function_name = globals_aws.hot_reader_lambda_function_name()
  function_arn = util_aws.get_lambda_arn_by_name(function_name)

  integration = globals_aws.aws_apigateway_client.create_integration(
    ApiId=api_id,
    IntegrationType="AWS_PROXY",
    IntegrationUri=function_arn,
    PayloadFormatVersion="2.0"
  )

  logger.info(f"Created API Integration: {function_arn}")

  route_key = f"GET /{function_name}"

  globals_aws.aws_apigateway_client.create_route(
    ApiId=api_id,
    RouteKey=route_key,
    Target=f"integrations/{integration['IntegrationId']}"
  )

  logger.info(f"Created API Route: {route_key}")

  account_id = globals_aws.aws_sts_client.get_caller_identity()['Account']
  region = globals_aws.aws_apigateway_client.meta.region_name
  source_arn = f"arn:aws:execute-api:{region}:{account_id}:{api_id}/*/*/{function_name}"
  statement_id = "api-gateway-invoke"

  globals_aws.aws_lambda_client.add_permission(
      FunctionName=function_name,
      StatementId=statement_id,
      Action="lambda:InvokeFunction",
      Principal="apigateway.amazonaws.com",
      SourceArn=source_arn
  )

  logger.info(f"Added permission to Lambda Function so API Gateway can invoke the function.")

def destroy_api_hot_reader_integration():
  function_name = globals_aws.hot_reader_lambda_function_name()
  statement_id = "api-gateway-invoke"

  try:
    globals_aws.aws_lambda_client.remove_permission(FunctionName=function_name, StatementId=statement_id)
    logger.info(f"Removed permission from Lambda function: {statement_id}, {function_name}")
  except globals_aws.aws_lambda_client.exceptions.ResourceNotFoundException:
    pass

  api_id = util_aws.get_api_id_by_name(globals.api_name())

  if api_id is None:
    return

  route_key = f"GET /{function_name}"
  route_id = util_aws.get_api_route_id_by_key(route_key)

  if route_id is not None:
    try:
      globals_aws.aws_apigateway_client.delete_route(ApiId=api_id, RouteId=route_id)
      logger.info(f"Deleted API Route: {route_key}")
    except globals_aws.aws_apigateway_client.exceptions.NotFoundException:
      pass

  function_arn = util_aws.get_lambda_arn_by_name(function_name)
  integration_id = util_aws.get_api_integration_id_by_uri(function_arn)

  if integration_id is not None:
    try:
      globals_aws.aws_apigateway_client.delete_integration(ApiId=api_id, IntegrationId=integration_id)
      logger.info(f"Deleted API Integration: {route_key}")
    except globals_aws.aws_apigateway_client.exceptions.NotFoundException:
      pass
