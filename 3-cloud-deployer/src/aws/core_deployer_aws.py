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

def create_dispatcher_iam_role():
  role_name = globals_aws.dispatcher_iam_role_name()

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
    "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole",
    "arn:aws:iam::aws:policy/service-role/AWSLambdaRole"
  ]

  for policy_arn in policy_arns:
    globals_aws.aws_iam_client.attach_role_policy(
      RoleName=role_name,
      PolicyArn=policy_arn
    )

    logger.info(f"Attached IAM policy ARN: {policy_arn}")

  logger.info(f"Waiting for propagation...")

  time.sleep(20)

def destroy_dispatcher_iam_role():
  role_name = globals_aws.dispatcher_iam_role_name()

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



# Helper path for core lambda functions
CORE_LAMBDA_DIR = os.path.join(globals.project_path(), "src", "aws", "lambda_functions")

def create_dispatcher_lambda_function():
  function_name = globals_aws.dispatcher_lambda_function_name()
  role_name = globals_aws.dispatcher_iam_role_name()

  response = globals_aws.aws_iam_client.get_role(RoleName=role_name)
  role_arn = response['Role']['Arn']

  globals_aws.aws_lambda_client.create_function(
    FunctionName=function_name,
    Runtime="python3.13",
    Role=role_arn,
    Handler="lambda_function.lambda_handler", #  file.function
    Code={"ZipFile": util.compile_lambda_function(os.path.join(CORE_LAMBDA_DIR, "dispatcher"))},
    Description="",
    Timeout=3, # seconds
    MemorySize=128, # MB
    Publish=True,
    Environment={
      "Variables": {
        "DIGITAL_TWIN_INFO": json.dumps(globals.digital_twin_info()),
        "TARGET_FUNCTION_SUFFIX": "-connector" if globals.config_providers.get("layer_2_provider", "aws") != "aws" else "-processor"
      }
    }
  )

  logger.info(f"Created Lambda function: {function_name}")

def destroy_dispatcher_lambda_function():
  function_name = globals_aws.dispatcher_lambda_function_name()

  try:
    globals_aws.aws_lambda_client.delete_function(FunctionName=function_name)
    logger.info(f"Deleted Lambda function: {function_name}")
  except ClientError as e:
    if e.response["Error"]["Code"] != "ResourceNotFoundException":
      raise


def create_dispatcher_iot_rule():
  rule_name = globals_aws.dispatcher_iot_rule_name()
  sql = f"SELECT * FROM '{globals.config['digital_twin_name']}/iot-data'"

  function_name = globals_aws.dispatcher_lambda_function_name()

  response = globals_aws.aws_lambda_client.get_function(FunctionName=function_name)
  function_arn = response['Configuration']['FunctionArn']

  globals_aws.aws_iot_client.create_topic_rule(
    ruleName=rule_name,
    topicRulePayload={
      "sql": sql,
      "description": "",
      "actions": [
        {
          "lambda": {
            "functionArn": function_arn
          }
        }
      ],
      "ruleDisabled": False
    }
  )

  logger.info(f"Created IoT rule: {rule_name}")

  region = globals_aws.aws_iot_client.meta.region_name
  account_id = globals_aws.aws_sts_client.get_caller_identity()['Account']

  globals_aws.aws_lambda_client.add_permission(
    FunctionName=function_name,
    StatementId="iot-invoke",
    Action="lambda:InvokeFunction",
    Principal="iot.amazonaws.com",
    SourceArn=f"arn:aws:iot:{region}:{account_id}:rule/{rule_name}"
  )

  logger.info(f"Added permission to Lambda function so the rule can invoke the function.")

def destroy_dispatcher_iot_rule():
  function_name = globals_aws.dispatcher_lambda_function_name()
  rule_name = globals_aws.dispatcher_iot_rule_name()

  try:
    globals_aws.aws_lambda_client.remove_permission(
        FunctionName=function_name,
        StatementId="iot-invoke"
    )
    logger.info(f"Removed permission from Lambda function: {rule_name}, {function_name}")
  except globals_aws.aws_lambda_client.exceptions.ResourceNotFoundException:
    pass

  if util.iot_rule_exists(rule_name):
    try:
      globals_aws.aws_iot_client.delete_topic_rule(ruleName=rule_name)
      logger.info(f"Deleted IoT Rule: {rule_name}")
    except globals_aws.aws_iot_client.exceptions.ResourceNotFoundException:
      pass


def create_persister_iam_role():
  role_name = globals_aws.persister_iam_role_name()

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
    "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole",
    "arn:aws:iam::aws:policy/service-role/AWSLambdaRole",
    "arn:aws:iam::aws:policy/AmazonDynamoDBFullAccess_v2"
  ]

  for policy_arn in policy_arns:
    globals_aws.aws_iam_client.attach_role_policy(
      RoleName=role_name,
      PolicyArn=policy_arn
    )

    logger.info(f"Attached IAM policy ARN: {policy_arn}")

  logger.info(f"Waiting for propagation...")

  time.sleep(20)

def destroy_persister_iam_role():
  role_name = globals_aws.persister_iam_role_name()

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


def create_writer_lambda_function():
  """
  Deploys Writer Function if L2 is Remote and L3 is Local (AWS).
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

      globals_aws.aws_lambda_client.create_function(
        FunctionName=function_name,
        Runtime="python3.13",
        Role=role_arn, # Reuse Persister Role
        Handler="lambda_function.lambda_handler", 
        Code={"ZipFile": util.compile_lambda_function(os.path.join(util.get_path_in_project(CONSTANTS.LAMBDA_FUNCTIONS_DIR_NAME), "writer"))},
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

def create_persister_lambda_function():
  function_name = globals_aws.persister_lambda_function_name()
  role_name = globals_aws.persister_iam_role_name()

  response = globals_aws.aws_iam_client.get_role(RoleName=role_name)
  role_arn = response['Role']['Arn']

  globals_aws.aws_lambda_client.create_function(
    FunctionName=function_name,
    Runtime="python3.13",
    Role=role_arn,
    Handler="lambda_function.lambda_handler", #  file.function
    Code={"ZipFile": util.compile_lambda_function(os.path.join(CORE_LAMBDA_DIR, "persister"))},
    Description="",
    Timeout=3, # seconds
    MemorySize=128, # MB
    Publish=True,
    Environment={
      "Variables": {
        "DIGITAL_TWIN_INFO": json.dumps(globals.digital_twin_info()),
        "DYNAMODB_TABLE_NAME": globals_aws.hot_dynamodb_table_name(),
        "EVENT_CHECKER_LAMBDA_NAME": globals_aws.event_checker_lambda_function_name()
      }
    }
  )

  logger.info(f"Created Lambda function: {function_name}")

def destroy_persister_lambda_function():
  function_name = globals_aws.persister_lambda_function_name()

  try:
    globals_aws.aws_lambda_client.delete_function(FunctionName=function_name)
    logger.info(f"Deleted Lambda function: {function_name}")
  except ClientError as e:
    if e.response["Error"]["Code"] != "ResourceNotFoundException":
      raise


def create_event_checker_iam_role():
  role_name = globals_aws.event_checker_iam_role_name()

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
    "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole",
    "arn:aws:iam::aws:policy/service-role/AWSLambdaRole",
    "arn:aws:iam::aws:policy/AmazonDynamoDBFullAccess_v2",
    "arn:aws:iam::aws:policy/AWSLambda_ReadOnlyAccess",
    "arn:aws:iam::aws:policy/AWSStepFunctionsFullAccess"
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
            "Action": "iottwinmaker:ListWorkspaces",
            "Resource": "*"
          },
          {
            "Effect": "Allow",
            "Action": [
              "iottwinmaker:*",
            ],
            "Resource": "*"
          },
          {
            "Effect": "Allow",
            "Action": [
              "dynamodb:*",
            ],
            "Resource": "*"
          },
          {
            "Effect": "Allow",
            "Action": [
              "s3:*"
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

def destroy_event_checker_iam_role():
  role_name = globals_aws.event_checker_iam_role_name()

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


def create_event_checker_lambda_function():
  function_name = globals_aws.event_checker_lambda_function_name()
  role_name = globals_aws.event_checker_iam_role_name()

  response = globals_aws.aws_iam_client.get_role(RoleName=role_name)
  role_arn = response['Role']['Arn']

  # Fetch ARNs only if features are enabled to avoid errors if resources don't exist
  lambda_chain_arn = "NONE"
  if globals.is_optimization_enabled("triggerNotificationWorkflow") and globals.is_optimization_enabled("useEventChecking"):
      region = globals_aws.aws_lambda_client.meta.region_name
      account_id = globals_aws.aws_sts_client.get_caller_identity()['Account']
      lambda_chain_name = globals_aws.lambda_chain_step_function_name()
      lambda_chain_arn = f"arn:aws:states:{region}:{account_id}:stateMachine:{lambda_chain_name}"

  event_feedback_lambda_function_arn = "NONE"
  if globals.is_optimization_enabled("returnFeedbackToDevice") and globals.is_optimization_enabled("useEventChecking"):
      event_feedback_lambda_function = globals_aws.event_feedback_lambda_function_name()
      # NOTE: Logic assumes event feedback lambda creates successfully before this or we handle it gracefully.
      # For now, we attempt to get it. If it fails, deployment might fail, which is acceptable if ordering is wrong.
      try:
          response = globals_aws.aws_lambda_client.get_function(FunctionName=event_feedback_lambda_function)
          event_feedback_lambda_function_arn = response["Configuration"]["FunctionArn"]
      except Exception as e:
          logger.warning(f"Could not retrieve Event Feedback Lambda ARN: {e}")
          event_feedback_lambda_function_arn = "UNKNOWN"

  globals_aws.aws_lambda_client.create_function(
    FunctionName=function_name,
    Runtime="python3.13",
    Role=role_arn,
    Handler="lambda_function.lambda_handler", #  file.function
    Code={"ZipFile": util.compile_lambda_function(os.path.join(CORE_LAMBDA_DIR, "event-checker"))},
    Description="",
    Timeout=3, # seconds
    MemorySize=128, # MB
    Publish=True,
    Environment={
      "Variables": {
        "DIGITAL_TWIN_INFO": json.dumps(globals.digital_twin_info()),
        "TWINMAKER_WORKSPACE_NAME": globals_aws.twinmaker_workspace_name(),
        "LAMBDA_CHAIN_STEP_FUNCTION_ARN": lambda_chain_arn,
        "EVENT_FEEDBACK_LAMBDA_FUNCTION_ARN": event_feedback_lambda_function_arn,
        "USE_STEP_FUNCTIONS": str(globals.is_optimization_enabled("triggerNotificationWorkflow")).lower(),
        "USE_FEEDBACK": str(globals.is_optimization_enabled("returnFeedbackToDevice")).lower()
      }
    }
  )

  logger.info(f"Created Lambda function: {function_name}")

def destroy_event_checker_lambda_function():
  function_name = globals_aws.event_checker_lambda_function_name()

  try:
    globals_aws.aws_lambda_client.delete_function(FunctionName=function_name)
    logger.info(f"Deleted Lambda function: {function_name}")
  except ClientError as e:
    if e.response["Error"]["Code"] != "ResourceNotFoundException":
      raise

def redeploy_event_checker_lambda_function():
  destroy_event_checker_lambda_function()
  create_event_checker_lambda_function()


def create_lambda_chain_iam_role():
  role_name = globals_aws.lambda_chain_iam_role_name()

  globals_aws.aws_iam_client.create_role(
      RoleName=role_name,
      AssumeRolePolicyDocument=json.dumps(
        {
          "Version": "2012-10-17",
          "Statement": [
            {
              "Effect": "Allow",
              "Principal": {
                "Service": "states.amazonaws.com"
              },
              "Action": "sts:AssumeRole"
            }
          ]
        }
      )
  )

  logger.info(f"Created IAM role: {role_name}")

  policy_arns = [
    "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole",
    "arn:aws:iam::aws:policy/service-role/AWSLambdaRole"
  ]

  for policy_arn in policy_arns:
    globals_aws.aws_iam_client.attach_role_policy(
      RoleName=role_name,
      PolicyArn=policy_arn
    )

    logger.info(f"Attached IAM policy ARN: {policy_arn}")

  logger.info(f"Waiting for propagation...")

  time.sleep(20)

def destroy_lambda_chain_iam_role():
  role_name = globals_aws.lambda_chain_iam_role_name()

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

def check_lambda_chain_iam_role():
  role_name = globals_aws.lambda_chain_iam_role_name()

  try:
    globals_aws.aws_iam_client.get_role(RoleName=role_name)
    logger.info(f"✅ Lambda-Chain IAM Role exists: {util.link_to_iam_role(role_name)}")
  except ClientError as e:
    if e.response["Error"]["Code"] == "NoSuchEntity":
      logger.info(f"❌ Lambda-Chain IAM Role missing: {role_name}")
    else:
      raise


def create_lambda_chain_step_function():
  sf_name = globals_aws.lambda_chain_step_function_name()
  role_name = globals_aws.lambda_chain_iam_role_name()

  response = globals_aws.aws_iam_client.get_role(RoleName=role_name)
  role_arn = response["Role"]["Arn"]

  # Read definition from file in upload folder
  # globals.py is in src/, so we can compute path relative to it
  sf_def_path = os.path.join(util.get_path_in_project(CONSTANTS.STATE_MACHINES_DIR_NAME), CONSTANTS.AWS_STATE_MACHINE_FILE)
  
  with open(sf_def_path, 'r') as f:
      definition = f.read()

  globals_aws.aws_sf_client.create_state_machine(
    name=sf_name,
    roleArn=role_arn,
    definition=definition
  )

  logger.info(f"Created Step Function: {sf_name}")

def destroy_lambda_chain_step_function():
  sf_name = globals_aws.lambda_chain_step_function_name()
  region = globals_aws.aws_lambda_client.meta.region_name
  account_id = globals_aws.aws_sts_client.get_caller_identity()['Account']
  sf_arn = f"arn:aws:states:{region}:{account_id}:stateMachine:{sf_name}"

  try:
    globals_aws.aws_sf_client.describe_state_machine(stateMachineArn=sf_arn)
  except ClientError as e:
    if e.response["Error"]["Code"] == "StateMachineDoesNotExist":
      return

  globals_aws.aws_sf_client.delete_state_machine(stateMachineArn=sf_arn)
  logger.info(f"Deletion of Step Function initiated: {sf_name}")

  while True:
    try:
      globals_aws.aws_sf_client.describe_state_machine(stateMachineArn=sf_arn)
      time.sleep(2)
    except ClientError as e:
      if e.response["Error"]["Code"] == "StateMachineDoesNotExist":
        break
      else:
        raise

  logger.info(f"Deleted Step Function: {sf_name}")

def check_lambda_chain_step_function():
  sf_name = globals_aws.lambda_chain_step_function_name()
  region = globals_aws.aws_lambda_client.meta.region_name
  account_id = globals_aws.aws_sts_client.get_caller_identity()['Account']
  sf_arn = f"arn:aws:states:{region}:{account_id}:stateMachine:{sf_name}"

  try:
    globals_aws.aws_sf_client.describe_state_machine(stateMachineArn=sf_arn)
    logger.info(f"✅ Lambda-Chain Step Function exists: {util.link_to_step_function(sf_arn)}")
  except ClientError as e:
    if e.response["Error"]["Code"] == "StateMachineDoesNotExist":
      logger.info(f"❌ Lambda-Chain Step Function missing: {sf_name}")
    else:
      raise

def redeploy_lambda_chain_step_function():
    destroy_lambda_chain_step_function()
    create_lambda_chain_step_function()


def create_event_feedback_iam_role():
  role_name = globals_aws.event_feedback_iam_role_name()

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
    "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole",
    "arn:aws:iam::aws:policy/AWSIoTDataAccess"
  ]

  for policy_arn in policy_arns:
    globals_aws.aws_iam_client.attach_role_policy(
      RoleName=role_name,
      PolicyArn=policy_arn
    )

    logger.info(f"Attached IAM policy ARN: {policy_arn}")

  logger.info(f"Waiting for propagation...")

  time.sleep(20)

def destroy_event_feedback_iam_role():
  role_name = globals_aws.event_feedback_iam_role_name()

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

def check_event_feedback_iam_role():
  role_name = globals_aws.event_feedback_iam_role_name()

  try:
    globals_aws.aws_iam_client.get_role(RoleName=role_name)
    logger.info(f"✅ Event-Feedback IAM Role exists: {util.link_to_iam_role(role_name)}")
  except ClientError as e:
    if e.response["Error"]["Code"] == "NoSuchEntity":
      logger.info(f"❌ Event-Feedback IAM Role missing: {role_name}")
    else:
      raise


def create_event_feedback_lambda_function():
  function_name = globals_aws.event_feedback_lambda_function_name()
  role_name = globals_aws.event_feedback_iam_role_name()

  response = globals_aws.aws_iam_client.get_role(RoleName=role_name)
  role_arn = response["Role"]["Arn"]

  globals_aws.aws_lambda_client.create_function(
    FunctionName=function_name,
    Runtime="python3.13",
    Role=role_arn,
    Handler="lambda_function.lambda_handler", #  file.function
    Code={"ZipFile": util.compile_lambda_function(os.path.join(util.get_path_in_project(CONSTANTS.LAMBDA_FUNCTIONS_DIR_NAME), "event-feedback"))},
    Description="",
    Timeout=3, # seconds
    MemorySize=128, # MB
    Publish=True,
    Environment={
      "Variables": {
        "DIGITAL_TWIN_INFO": json.dumps(globals.digital_twin_info())
      }
    }
  )

  logger.info(f"Created Lambda function: {function_name}")

def destroy_event_feedback_lambda_function():
  function_name = globals_aws.event_feedback_lambda_function_name()

  try:
    globals_aws.aws_lambda_client.delete_function(FunctionName=function_name)
    logger.info(f"Deleted Lambda function: {function_name}")
  except ClientError as e:
    if e.response["Error"]["Code"] != "ResourceNotFoundException":
      raise

def check_event_feedback_lambda_function():
  function_name = globals_aws.event_feedback_lambda_function_name()

  try:
    globals_aws.aws_lambda_client.get_function(FunctionName=function_name)
    logger.info(f"✅ Event-Feedback Lambda Function exists: {util.link_to_lambda_function(function_name)}")
  except ClientError as e:
    if e.response["Error"]["Code"] == "ResourceNotFoundException":
      logger.info(f"❌ Event-Feedback Lambda Function missing: {function_name}")
    else:
      raise

def redeploy_event_feedback_lambda_function():
    destroy_event_feedback_lambda_function()
    create_event_feedback_lambda_function()

def create_hot_dynamodb_table():
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


def create_hot_cold_mover_iam_role():
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
    "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole",
    "arn:aws:iam::aws:policy/AmazonDynamoDBFullAccess_v2",
    "arn:aws:iam::aws:policy/AmazonS3FullAccess"
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
  function_name = globals_aws.hot_cold_mover_lambda_function_name()
  role_name = globals_aws.hot_cold_mover_iam_role_name()

  response = globals_aws.aws_iam_client.get_role(RoleName=role_name)
  role_arn = response['Role']['Arn']

  globals_aws.aws_lambda_client.create_function(
    FunctionName=function_name,
    Runtime="python3.13",
    Role=role_arn,
    Handler="lambda_function.lambda_handler", #  file.function
    Code={"ZipFile": util.compile_lambda_function(os.path.join(CORE_LAMBDA_DIR, "hot-to-cold-mover"))},
    Description="",
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
  rule_name = globals_aws.hot_cold_mover_event_rule_name()
  schedule_expression = f"cron(0 12 * * ? *)"

  function_name = globals_aws.hot_cold_mover_lambda_function_name()

  rule_response = globals_aws.aws_events_client.put_rule(
    Name=rule_name,
    ScheduleExpression=schedule_expression,
    State="ENABLED",
    Description="",
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


def create_cold_s3_bucket():
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
    "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole",
    "arn:aws:iam::aws:policy/AmazonS3FullAccess"
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
  function_name = globals_aws.cold_archive_mover_lambda_function_name()
  role_name = globals_aws.cold_archive_mover_iam_role_name()

  response = globals_aws.aws_iam_client.get_role(RoleName=role_name)
  role_arn = response['Role']['Arn']

  globals_aws.aws_lambda_client.create_function(
    FunctionName=function_name,
    Runtime="python3.13",
    Role=role_arn,
    Handler="lambda_function.lambda_handler", #  file.function
    Code={"ZipFile": util.compile_lambda_function(os.path.join(CORE_LAMBDA_DIR, "cold-to-archive-mover"))},
    Description="",
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
  rule_name = globals_aws.cold_archive_mover_event_rule_name()
  function_name = globals_aws.cold_archive_mover_lambda_function_name()

  schedule_expression = f"cron(0 18 * * ? *)"

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


def create_archive_s3_bucket():
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


def create_hot_reader_iam_role():
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
    "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole",
    "arn:aws:iam::aws:policy/AmazonDynamoDBFullAccess_v2"
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
  function_name = globals_aws.hot_reader_lambda_function_name()
  role_name = globals_aws.hot_reader_iam_role_name()

  response = globals_aws.aws_iam_client.get_role(RoleName=role_name)
  role_arn = response['Role']['Arn']

  globals_aws.aws_lambda_client.create_function(
    FunctionName=function_name,
    Runtime="python3.13",
    Role=role_arn,
    Handler="lambda_function.lambda_handler", #  file.function
    Code={"ZipFile": util.compile_lambda_function(os.path.join(CORE_LAMBDA_DIR, "hot-reader"))},
    Description="",
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
    "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole",
    "arn:aws:iam::aws:policy/AmazonDynamoDBFullAccess_v2"
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
  function_name = globals_aws.hot_reader_last_entry_lambda_function_name()
  role_name = globals_aws.hot_reader_last_entry_iam_role_name()

  response = globals_aws.aws_iam_client.get_role(RoleName=role_name)
  role_arn = response['Role']['Arn']

  globals_aws.aws_lambda_client.create_function(
    FunctionName=function_name,
    Runtime="python3.13",
    Role=role_arn,
    Handler="lambda_function.lambda_handler", #  file.function
    Code={"ZipFile": util.compile_lambda_function(os.path.join(CORE_LAMBDA_DIR, "hot-reader-last-entry"))},
    Description="",
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

def create_twinmaker_s3_bucket():
  bucket_name = globals_aws.twinmaker_s3_bucket_name()

  globals_aws.aws_s3_client.create_bucket(
    Bucket=bucket_name,
    CreateBucketConfiguration={
        "LocationConstraint": globals_aws.aws_s3_client.meta.region_name
    }
  )

  logger.info(f"Created S3 Bucket: {bucket_name}")

def destroy_twinmaker_s3_bucket():
  bucket_name = globals_aws.twinmaker_s3_bucket_name()

  util_aws.destroy_s3_bucket(bucket_name)


def create_twinmaker_iam_role():
  role_name = globals_aws.twinmaker_iam_role_name()

  globals_aws.aws_iam_client.create_role(
      RoleName=role_name,
      AssumeRolePolicyDocument=json.dumps(
        {
          "Version": "2012-10-17",
          "Statement": [
            {
              "Effect": "Allow",
              "Principal": {
                "Service": "iottwinmaker.amazonaws.com"
              },
              "Action": "sts:AssumeRole"
            }
          ]
        }
      )
  )
  logger.info(f"Created IAM role: {role_name}")

  policy_name = "TwinMakerExecutionPolicy"

  globals_aws.aws_iam_client.put_role_policy(
    RoleName=role_name,
    PolicyName=policy_name,
    PolicyDocument=json.dumps({
      "Version": "2012-10-17",
      "Statement": [
        {
          "Effect": "Allow",
          "Action": [
            "s3:*",
            "dynamodb:*",
            "lambda:*",
          ],
          "Resource": "*"
        }
      ]
  })
  )
  logger.info(f"Attached inline IAM policy: {policy_name}")

  logger.info(f"Waiting for propagation...")
  time.sleep(20)

def destroy_twinmaker_iam_role():
  role_name = globals_aws.twinmaker_iam_role_name()

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


def create_twinmaker_workspace():
  workspace_name = globals_aws.twinmaker_workspace_name()
  role_name = globals_aws.twinmaker_iam_role_name()
  bucket_name = globals_aws.twinmaker_s3_bucket_name()

  account_id = globals_aws.aws_sts_client.get_caller_identity()['Account']

  globals_aws.aws_twinmaker_client.create_workspace(
    workspaceId=workspace_name,
    role=f"arn:aws:iam::{account_id}:role/{role_name}",
    s3Location=f"arn:aws:s3:::{bucket_name}",
    description=""
  )

  logger.info(f"Created IoT TwinMaker workspace: {workspace_name}")

def destroy_twinmaker_workspace():
  workspace_name = globals_aws.twinmaker_workspace_name()

  try:
    response = globals_aws.aws_twinmaker_client.list_entities(workspaceId=workspace_name)
    deleted_an_entity = False
    for entity in response.get("entitySummaries", []):
      try:
        globals_aws.aws_twinmaker_client.delete_entity(workspaceId=workspace_name, entityId=entity["entityId"], isRecursive=True)
        deleted_an_entity = True
        logger.info(f"Deleted IoT TwinMaker entity: {entity['entityId']}")
      except ClientError as e:
        if e.response["Error"]["Code"] != "ResourceNotFoundException":
          raise

    if deleted_an_entity:
      logger.info(f"Waiting for propagation...")
      time.sleep(20)
  except ClientError as e:
    if e.response["Error"]["Code"] != "ValidationException":
      raise

  try:
    response = globals_aws.aws_twinmaker_client.list_scenes(workspaceId=workspace_name)
    for scene in response.get("sceneSummaries", []):
      try:
        globals_aws.aws_twinmaker_client.delete_scene(workspaceId=workspace_name, sceneId=scene["sceneId"])
        logger.info(f"Deleted IoT TwinMaker scene: {scene['sceneId']}")
      except ClientError as e:
        if e.response["Error"]["Code"] != "ResourceNotFoundException":
          raise
  except ClientError as e:
    if e.response["Error"]["Code"] != "ValidationException":
      raise

  try:
    response = globals_aws.aws_twinmaker_client.list_component_types(workspaceId=workspace_name)
    for componentType in response.get("componentTypeSummaries", []):
      if componentType["componentTypeId"].startswith("com.amazon"):
        continue
      try:
        globals_aws.aws_twinmaker_client.delete_component_type(workspaceId=workspace_name, componentTypeId=componentType["componentTypeId"])
        logger.info(f"Deleted IoT TwinMaker component type: {componentType['componentTypeId']}")
      except ClientError as e:
        if e.response["Error"]["Code"] != "ResourceNotFoundException":
          raise
  except ClientError as e:
    if e.response["Error"]["Code"] != "ValidationException":
      raise

  try:
    globals_aws.aws_twinmaker_client.delete_workspace(workspaceId=workspace_name)
  except ClientError as e:
    if e.response["Error"]["Code"] == "ResourceNotFoundException":
      return
    else:
      raise

  logger.info(f"Deletion of IoT TwinMaker workspace initiated: {workspace_name}")

  while True:
    try:
      globals_aws.aws_twinmaker_client.get_workspace(workspaceId=workspace_name)
      time.sleep(2)
    except ClientError as e:
      if e.response["Error"]["Code"] == "ResourceNotFoundException":
        break
      else:
        raise

  logger.info(f"Deleted IoT TwinMaker workspace: {workspace_name}")


def create_grafana_iam_role():
  role_name = globals_aws.grafana_iam_role_name()

  response = globals_aws.aws_iam_client.create_role(
      RoleName=role_name,
      AssumeRolePolicyDocument=json.dumps(
        {
          "Version": "2012-10-17",
          "Statement": [
            {
              "Effect": "Allow",
              "Principal": {
                "Service": "grafana.amazonaws.com"
              },
              "Action": "sts:AssumeRole"
            }
          ]
        }
      )
  )
  role_arn = response["Role"]["Arn"]

  logger.info(f"Created IAM role: {role_name}")

  logger.info(f"Waiting for propagation...")
  time.sleep(20)

  trust_policy = globals_aws.aws_iam_client.get_role(RoleName=role_name)['Role']['AssumeRolePolicyDocument']

  if isinstance(trust_policy['Statement'], dict):
    trust_policy['Statement'] = [trust_policy['Statement']]

  new_statement = {
      "Effect": "Allow",
      "Principal": {
          "AWS": role_arn
      },
      "Action": "sts:AssumeRole"
  }

  trust_policy['Statement'].append(new_statement)

  globals_aws.aws_iam_client.update_assume_role_policy(
      RoleName=role_name,
      PolicyDocument=json.dumps(trust_policy)
  )

  logger.info(f"Updated IAM role trust policy: {role_name}")

  policy_name = "GrafanaExecutionPolicy"

  globals_aws.aws_iam_client.put_role_policy(
    RoleName=role_name,
    PolicyName=policy_name,
    PolicyDocument=json.dumps(
      {
        "Version": "2012-10-17",
        "Statement": [
          {
            "Effect": "Allow",
            "Action": "iottwinmaker:ListWorkspaces",
            "Resource": "*"
          },
          {
            "Effect": "Allow",
            "Action": [
              "iottwinmaker:*",
            ],
            "Resource": "*"
          },
          {
            "Effect": "Allow",
            "Action": [
              "dynamodb:*",
            ],
            "Resource": "*"
          },
          {
            "Effect": "Allow",
            "Action": [
              "s3:*"
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

def destroy_grafana_iam_role():
  role_name = globals_aws.grafana_iam_role_name()

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



def create_grafana_iam_role():
  role_name = globals_aws.grafana_iam_role_name()

  trust_policy = {
    "Version": "2012-10-17",
    "Statement": [
      {
        "Effect": "Allow",
        "Principal": {
          "Service": "grafana.amazonaws.com"
        },
        "Action": "sts:AssumeRole"
      }
    ]
  }

  try:
    globals_aws.aws_iam_client.create_role(
      RoleName=role_name,
      AssumeRolePolicyDocument=json.dumps(trust_policy)
    )
    logger.info(f"Created IAM role: {role_name}")
  except globals_aws.aws_iam_client.exceptions.EntityAlreadyExistsException:
    logger.info(f"IAM role already exists: {role_name}")

  # Attach generic administrator policy for simplicty in this scope
  # In production, this should be scoped down.
  policy_arn = "arn:aws:iam::aws:policy/AdministratorAccess"
  globals_aws.aws_iam_client.attach_role_policy(
    RoleName=role_name,
    PolicyArn=policy_arn
  )
  logger.info(f"Attached policy {policy_arn} to role {role_name}")

def destroy_grafana_iam_role():
  role_name = globals_aws.grafana_iam_role_name()

  try:
    # detach managed policies
    response = globals_aws.aws_iam_client.list_attached_role_policies(RoleName=role_name)
    for policy in response["AttachedPolicies"]:
        globals_aws.aws_iam_client.detach_role_policy(RoleName=role_name, PolicyArn=policy["PolicyArn"])

    # delete inline policies
    response = globals_aws.aws_iam_client.list_role_policies(RoleName=role_name)
    for policy_name in response["PolicyNames"]:
        globals_aws.aws_iam_client.delete_role_policy(RoleName=role_name, PolicyName=policy_name)

    # delete the role
    globals_aws.aws_iam_client.delete_role(RoleName=role_name)
    logger.info(f"Deleted IAM role: {role_name}")
  except ClientError as e:
    if e.response["Error"]["Code"] != "NoSuchEntity":
      raise


def create_grafana_workspace():
  workspace_name = globals_aws.grafana_workspace_name()
  role_name = globals_aws.grafana_iam_role_name()

  response = globals_aws.aws_iam_client.get_role(RoleName=role_name)
  role_arn = response["Role"]["Arn"]

  response = globals_aws.aws_grafana_client.create_workspace(
    workspaceName=workspace_name,
    workspaceDescription="",
    grafanaVersion="10.4",
    accountAccessType="CURRENT_ACCOUNT",
    authenticationProviders=["AWS_SSO"],
    permissionType="CUSTOMER_MANAGED",
    workspaceRoleArn=role_arn,
    configuration=json.dumps(
      {
        "plugins": {
          "pluginAdminEnabled": True
        },
        # "unifiedAlerting": {
        #   "enabled": True
        # }
      }
    ),
    tags={
        "Environment": "Dev"
    }
  )
  workspace_id = response["workspace"]["id"]

  logger.info(f"Creation of Grafana workspace initiated: {workspace_name}")

  while True:
    response = globals_aws.aws_grafana_client.describe_workspace(workspaceId=workspace_id)
    if response['workspace']['status'] == "ACTIVE":
      break
    time.sleep(2)

  logger.info(f"Created Grafana workspace: {workspace_name}")

def destroy_grafana_workspace():
  workspace_name = globals_aws.grafana_workspace_name()

  try:
    workspace_id = util_aws.get_grafana_workspace_id_by_name(workspace_name)
    globals_aws.aws_grafana_client.delete_workspace(workspaceId=workspace_id)
  except ClientError as e:
    if e.response["Error"]["Code"] == "ResourceNotFoundException":
      return
    else:
      raise

  logger.info(f"Deletion of Grafana workspace initiated: {workspace_name}")

  while True:
    try:
      globals_aws.aws_grafana_client.describe_workspace(workspaceId=workspace_id)
      time.sleep(2)
    except ClientError as e:
      if e.response["Error"]["Code"] == "ResourceNotFoundException":
        break
      else:
        raise

  logger.info(f"Deleted Grafana workspace: {workspace_name}")


def add_cors_to_twinmaker_s3_bucket():
  bucket_name = globals_aws.twinmaker_s3_bucket_name()
  grafana_workspace_id = util_aws.get_grafana_workspace_id_by_name(globals_aws.grafana_workspace_name())

  globals_aws.aws_s3_client.put_bucket_cors(
      Bucket=bucket_name,
      CORSConfiguration={
        "CORSRules": [
          {
            "AllowedOrigins": [f"https://grafana.{globals_aws.aws_grafana_client.meta.region_name}.amazonaws.com/workspaces/{grafana_workspace_id}"],
            "AllowedMethods": ["GET"],
            "AllowedHeaders": ["*"],
            "MaxAgeSeconds": 3000
          }
        ]
      }
  )

  logger.info(f"CORS configuration applied to bucket: {bucket_name}")
  grafana_link = f"https://grafana.{globals_aws.aws_grafana_client.meta.region_name}.amazonaws.com/workspaces/{grafana_workspace_id}"
  logger.info(f"------- allowed origin: {grafana_link} -------")

def remove_cors_from_twinmaker_s3_bucket():
  bucket_name = globals_aws.twinmaker_s3_bucket_name()

  try:
    globals_aws.aws_s3_client.get_bucket_cors(Bucket=bucket_name)
    globals_aws.aws_s3_client.delete_bucket_cors(Bucket=bucket_name)
  except ClientError as e:
    if e.response["Error"]["Code"] == "NoSuchBucket" or e.response["Error"]["Code"] == "NoSuchCORSConfiguration":
      return
    else:
      raise

  logger.info(f"CORS configuration removed from bucket: {bucket_name}")

def create_api():
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
