import json
import os
import time
import globals
from logger import logger
import aws.globals_aws as globals_aws
import util
from botocore.exceptions import ClientError
import constants as CONSTANTS

# ==========================================
# 1. Constants & Helpers
# ==========================================

# Helper path for core lambda functions
# Location: src/aws/lambda_functions/
CORE_LAMBDA_DIR = os.path.join(globals.project_path(), CONSTANTS.AWS_CORE_LAMBDA_DIR_NAME)

# ==========================================
# 2. Dispatcher IAM Role
# ==========================================

def create_dispatcher_iam_role():
  """
  Creates the IAM Role for the L1 Dispatcher Lambda.
  
  Project Structure Location:
  - This is a core infrastructure component defined in code.
  - Role Name: Defined in globals_aws.dispatcher_iam_role_name()
  """
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
    CONSTANTS.AWS_POLICY_LAMBDA_BASIC_EXECUTION,
    CONSTANTS.AWS_POLICY_LAMBDA_ROLE
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
  """
  Destroys the IAM Role for the L1 Dispatcher Lambda.
  """
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

# ==========================================
# 3. Dispatcher Lambda Function
# ==========================================

def create_dispatcher_lambda_function():
  """
  Creates the L1 Dispatcher Lambda Function.
  
  Function Description:
  - This function acts as the entry point for all IoT telemetry data.
  - It validates the incoming message and routes it to the appropriate processor.
  - For single-cloud deployments, it routes to local Layer 2 functions.
  - For multi-cloud deployments, it can route to a connector function.

  Project Structure Location:
  - Source Code: Hardcoded in `src/aws/lambda_functions/dispatcher`
  - NOT User Editable: This logic is part of the core deployer and is not meant to be modified by the user.
  """
  function_name = globals_aws.dispatcher_lambda_function_name()
  role_name = globals_aws.dispatcher_iam_role_name()

  response = globals_aws.aws_iam_client.get_role(RoleName=role_name)
  role_arn = response['Role']['Arn']

  globals_aws.aws_lambda_client.create_function(
    FunctionName=function_name,
    Runtime="python3.13",
    Role=role_arn,
    Handler="lambda_function.lambda_handler", #  file.function
    # Source Code Location: src/aws/lambda_functions/dispatcher
    Code={"ZipFile": util.compile_lambda_function(os.path.join(CORE_LAMBDA_DIR, "dispatcher"))},
    Description="Core Dispatcher Function for Layer 1 Data Acquisition",
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
  """
  Destroys the L1 Dispatcher Lambda Function.
  """
  function_name = globals_aws.dispatcher_lambda_function_name()

  try:
    globals_aws.aws_lambda_client.delete_function(FunctionName=function_name)
    logger.info(f"Deleted Lambda function: {function_name}")
  except ClientError as e:
    if e.response["Error"]["Code"] != "ResourceNotFoundException":
      raise

# ==========================================
# 4. Dispatcher IoT Rule
# ==========================================

def create_dispatcher_iot_rule():
  """
  Creates the IoT Topic Rule that triggers the Dispatcher.
  
  Function Description:
  - Subscribes to the MQTT topic '{digital_twin_name}/iot-data'.
  - Forwards all matching messages to the Dispatcher Lambda.
  """
  rule_name = globals_aws.dispatcher_iot_rule_name()
  sql = f"SELECT * FROM '{globals.config['digital_twin_name']}/iot-data'"

  function_name = globals_aws.dispatcher_lambda_function_name()

  response = globals_aws.aws_lambda_client.get_function(FunctionName=function_name)
  function_arn = response['Configuration']['FunctionArn']

  globals_aws.aws_iot_client.create_topic_rule(
    ruleName=rule_name,
    topicRulePayload={
      "sql": sql,
      "description": "Routes all Digital Twin IoT data to the Dispatcher Lambda",
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
  """
  Destroys the IoT Topic Rule for the Dispatcher.
  """
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
