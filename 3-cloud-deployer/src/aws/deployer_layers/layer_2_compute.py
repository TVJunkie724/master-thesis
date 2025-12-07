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
# These are internal functions NOT editable by the user
CORE_LAMBDA_DIR = os.path.join(globals.project_path(), CONSTANTS.AWS_CORE_LAMBDA_DIR_NAME)

# ==========================================
# 2. Persister IAM Role
# ==========================================

def create_persister_iam_role():
  """
  Creates the IAM Role for the L2 Persister Lambda.
  """
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
    CONSTANTS.AWS_POLICY_LAMBDA_BASIC_EXECUTION,
    CONSTANTS.AWS_POLICY_LAMBDA_ROLE,
    CONSTANTS.AWS_POLICY_DYNAMODB_FULL_ACCESS
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

# ==========================================
# 3. Persister Lambda Function
# ==========================================

def create_persister_lambda_function():
  """
  Creates the L2 Persister Lambda Function.
  
  Function Description:
  - Takes raw data from the Dispatcher (L1).
  - Validates and writes data to Hot Storage (DynamoDB).
  - Can optionally invoke the Event Checker.
  
  Project Structure Location:
  - Source Code: Hardcoded in `src/aws/lambda_functions/persister`
  - NOT User Editable.
  """
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
    Description="L2 Persister: Writes data to storage",
    Timeout=3, # seconds
    MemorySize=128, # MB
    Publish=True,
    Environment={
      "Variables": {
        "DIGITAL_TWIN_INFO": json.dumps(globals.digital_twin_info()),
        "DYNAMODB_TABLE_NAME": globals_aws.hot_dynamodb_table_name(),
        "EVENT_CHECKER_LAMBDA_NAME": globals_aws.event_checker_lambda_function_name(),
        "USE_EVENT_CHECKING": str(globals.is_optimization_enabled("useEventChecking")).lower()
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

# ==========================================
# 4. Event Checker IAM Role
# ==========================================

def create_event_checker_iam_role():
  """
  Creates the IAM Role for the L2 Event Checker Lambda.
  """
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
    CONSTANTS.AWS_POLICY_LAMBDA_BASIC_EXECUTION,
    CONSTANTS.AWS_POLICY_LAMBDA_ROLE,
    CONSTANTS.AWS_POLICY_DYNAMODB_FULL_ACCESS,
    CONSTANTS.AWS_POLICY_LAMBDA_READ_ONLY,
    CONSTANTS.AWS_POLICY_STEP_FUNCTIONS_FULL_ACCESS
  ]

  for policy_arn in policy_arns:
    globals_aws.aws_iam_client.attach_role_policy(
      RoleName=role_name,
      PolicyArn=policy_arn
    )

    logger.info(f"Attached IAM policy ARN: {policy_arn}")

  # Inline Policy for TwinMaker Access
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

# ==========================================
# 5. Event Checker Lambda Function
# ==========================================

def create_event_checker_lambda_function():
  """
  Creates the L2 Event Checker Lambda Function.
  
  Function Description:
  - Analyzes data against rules defined in `config_events.json`.
  - Triggers the Step Function workflow if conditions are met.
  
  Project Structure Location:
  - Source Code: Hardcoded in `src/aws/lambda_functions/event-checker`
  - NOT User Editable.
  """
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
    # Source Code Location: src/aws/lambda_functions/event-checker
    Code={"ZipFile": util.compile_lambda_function(os.path.join(CORE_LAMBDA_DIR, "event-checker"))},
    Description="L2 Event Checker: Evaluates data against rules",
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

# ==========================================
# 6. Lambda Chain (Step Function) Role
# ==========================================

def create_lambda_chain_iam_role():
  """
  Creates the IAM Role for the Step Function State Machine.
  """
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

# ==========================================
# 7. Lambda Chain (Step Function)
# ==========================================

def create_lambda_chain_step_function():
  """
  Creates the Step Function State Machine.
  
  User Editable: 
  - Yes, the definition is located in the user's upload directory.
  - Path: upload/state_machines/aws_step_function.json (via CONSTANTS)
  """
  sf_name = globals_aws.lambda_chain_step_function_name()
  role_name = globals_aws.lambda_chain_iam_role_name()

  response = globals_aws.aws_iam_client.get_role(RoleName=role_name)
  role_arn = response["Role"]["Arn"]

  # Read definition from file in upload folder
  # Logic: globals.project_path() / CONSTANTS.STATE_MACHINES_DIR_NAME / CONSTANTS.AWS_STATE_MACHINE_FILE
  # Note: util.get_path_in_project expects a name relative to project root, not absolute.
  # But CONSTANTS.STATE_MACHINES_DIR_NAME is just "state_machines".
  # If the directory is in upload, we need to correct this. 
  # Let's check where STATE_MACHINES_DIR_NAME is conceptually.
  # Based on current util.py it seems it might be in root. 
  # The original code used util.get_project_upload_path(), so it was in /upload.
  # Let's use get_project_upload_path() to be safe and consistent with original logic, 
  # or ensure STATE_MACHINES_DIR_NAME implies the full relative path "upload/state_machines".
  # CONSTANTS.py says STATE_MACHINES_DIR_NAME = "state_machines"
  # and CONSTANTS.PROJECT_UPLOAD_DIR_NAME = "upload"
  # So we should construct it properly.
  
  sf_dir = os.path.join(globals.get_project_upload_path(), CONSTANTS.STATE_MACHINES_DIR_NAME)
  sf_def_path = os.path.join(sf_dir, CONSTANTS.AWS_STATE_MACHINE_FILE)
  
  # Fallback if specific subdir doesn't exist (legacy support) or if user put it in root of upload
  if not os.path.exists(sf_def_path):
       # try root upload dir
       sf_def_path = os.path.join(globals.get_project_upload_path(), CONSTANTS.AWS_STATE_MACHINE_FILE)

  if not os.path.exists(sf_def_path):
      raise FileNotFoundError(
          f"State machine definition not found. Please ensure '{CONSTANTS.AWS_STATE_MACHINE_FILE}' "
          f"exists in the '{CONSTANTS.STATE_MACHINES_DIR_NAME}/' folder or project root."
      )

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

# ==========================================
# 8. Event Feedback IAM Role
# ==========================================

def create_event_feedback_iam_role():
  """
  Creates the IAM Role for the Event Feedback Lambda.
  """
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
    CONSTANTS.AWS_POLICY_LAMBDA_BASIC_EXECUTION,
    CONSTANTS.AWS_POLICY_IOT_DATA_ACCESS
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

# ==========================================
# 9. Event Feedback Lambda Function
# ==========================================

def create_event_feedback_lambda_function():
  """
  Creates the Event Feedback Lambda Function.
  
  Function Description:
  - This function is meant to close the feedback loop by sending commands back to the device via MQTT.
  - It is triggered by the Step Function or other logic.
  
  Project Structure Location:
  - Source Code: User Editable.
  - Path: upload/lambda_functions/event-feedback
  """
  function_name = globals_aws.event_feedback_lambda_function_name()
  role_name = globals_aws.event_feedback_iam_role_name()

  response = globals_aws.aws_iam_client.get_role(RoleName=role_name)
  role_arn = response["Role"]["Arn"]

  # Source Code Location: User Upload Directory
  # Expects folder: upload/lambda_functions/event-feedback
  lambda_dir = os.path.join(globals.get_project_upload_path(), CONSTANTS.LAMBDA_FUNCTIONS_DIR_NAME, "event-feedback")

  globals_aws.aws_lambda_client.create_function(
    FunctionName=function_name,
    Runtime="python3.13",
    Role=role_arn,
    Handler="lambda_function.lambda_handler", #  file.function
    # User Code from: upload/lambda_functions/event-feedback
    Code={"ZipFile": util.compile_lambda_function(lambda_dir)},
    Description="User Defined Event Feedback Function",
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
