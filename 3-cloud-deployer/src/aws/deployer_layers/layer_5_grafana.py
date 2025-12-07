import json
import time
import globals
from logger import logger
import aws.globals_aws as globals_aws
import aws.util_aws as util_aws
from botocore.exceptions import ClientError
import constants as CONSTANTS

# ==========================================
# 1. Grafana Resources (L5)
# ==========================================

def create_grafana_iam_role():
  """
  Creates the IAM Role for Amazon Managed Grafana.
  
  Logic:
  - Creates basic role trusting 'grafana.amazonaws.com'.
  - Updates trust policy to also trust itself (weird AWS requirement or artifact of prior logic, keeping as is).
  - Attaches permission policies for TwinMaker, DynamoDB, and S3 access.
  """
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

def create_grafana_workspace():
  """
  Creates the Amazon Managed Grafana Workspace.
  
  Configuration:
  - Version: 10.4
  - Authentication: AWS SSO (required for Managed Grafana).
  - Permission Type: Customer Managed (via the role we created).
  """
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
  """
  Adds CORS configuration to the TwinMaker S3 bucket to allow access from Grafana.
  """
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
