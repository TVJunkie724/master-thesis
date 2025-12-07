import json
import time
import globals
from logger import logger
import aws.globals_aws as globals_aws
import aws.util_aws as util_aws
from botocore.exceptions import ClientError
import constants as CONSTANTS

# ==========================================
# 1. TwinMaker Resources (L4)
# ==========================================

def create_twinmaker_s3_bucket():
  """
  Creates the S3 Bucket for IoT TwinMaker assets.
  
  Infrastructure Component:
  - Used by TwinMaker to store scene files (GLTF/GLB) and other assets.
  """
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
  """
  Creates the IAM Role for the IoT TwinMaker Workspace.
  """
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
  """
  Creates the IoT TwinMaker Workspace.
  
  Infrastructure Component:
  - This is the container for the digital twin entities, scenes, and component types.
  - Linked to the TwinMaker S3 bucket and IAM Role.
  """
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
  """
  Destroys the IoT TwinMaker Workspace.
  
  Logic:
  - Recursively deletes entities, scenes, and component types before deleting the workspace.
  """
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
