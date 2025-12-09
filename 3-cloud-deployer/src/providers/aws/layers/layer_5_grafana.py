"""
Layer 5 (Grafana) Deployment for AWS.

This module handles deployment and destruction of Layer 5 components:
- Grafana IAM Role
- Amazon Managed Grafana Workspace
- CORS configuration for TwinMaker S3 bucket

All functions accept provider parameters explicitly.
"""

import json
import time
from typing import TYPE_CHECKING
from logger import logger
import src.providers.aws.util_aws as util_aws
from botocore.exceptions import ClientError

if TYPE_CHECKING:
    from providers.aws.provider import AWSProvider
    from src.core.context import DeploymentContext


def _destroy_iam_role(provider: 'AWSProvider', role_name: str) -> None:
    """Generic IAM role destruction with policy cleanup."""
    iam_client = provider.clients["iam"]
    try:
        response = iam_client.list_attached_role_policies(RoleName=role_name)
        for policy in response["AttachedPolicies"]:
            iam_client.detach_role_policy(RoleName=role_name, PolicyArn=policy["PolicyArn"])

        response = iam_client.list_role_policies(RoleName=role_name)
        for policy_name in response["PolicyNames"]:
            iam_client.delete_role_policy(RoleName=role_name, PolicyName=policy_name)

        response = iam_client.list_instance_profiles_for_role(RoleName=role_name)
        for profile in response["InstanceProfiles"]:
            iam_client.remove_role_from_instance_profile(
                InstanceProfileName=profile["InstanceProfileName"],
                RoleName=role_name
            )

        iam_client.delete_role(RoleName=role_name)
        logger.info(f"Deleted IAM role: {role_name}")
    except ClientError as e:
        if e.response["Error"]["Code"] != "NoSuchEntity":
            raise


# ==========================================
# Grafana IAM Role
# ==========================================

def create_grafana_iam_role(provider: 'AWSProvider') -> None:
    """Creates the IAM Role for Amazon Managed Grafana."""
    role_name = provider.naming.grafana_iam_role()
    iam_client = provider.clients["iam"]

    response = iam_client.create_role(
        RoleName=role_name,
        AssumeRolePolicyDocument=json.dumps({
            "Version": "2012-10-17",
            "Statement": [{
                "Effect": "Allow",
                "Principal": {"Service": "grafana.amazonaws.com"},
                "Action": "sts:AssumeRole"
            }]
        })
    )
    role_arn = response["Role"]["Arn"]
    logger.info(f"Created IAM role: {role_name}")
    logger.info("Waiting for propagation...")
    time.sleep(20)

    # Update trust policy to also trust itself
    trust_policy = iam_client.get_role(RoleName=role_name)['Role']['AssumeRolePolicyDocument']
    if isinstance(trust_policy['Statement'], dict):
        trust_policy['Statement'] = [trust_policy['Statement']]

    trust_policy['Statement'].append({
        "Effect": "Allow",
        "Principal": {"AWS": role_arn},
        "Action": "sts:AssumeRole"
    })

    iam_client.update_assume_role_policy(
        RoleName=role_name,
        PolicyDocument=json.dumps(trust_policy)
    )
    logger.info(f"Updated IAM role trust policy: {role_name}")

    # Attach inline policy
    iam_client.put_role_policy(
        RoleName=role_name,
        PolicyName="GrafanaExecutionPolicy",
        PolicyDocument=json.dumps({
            "Version": "2012-10-17",
            "Statement": [
                {"Effect": "Allow", "Action": "iottwinmaker:ListWorkspaces", "Resource": "*"},
                {"Effect": "Allow", "Action": ["iottwinmaker:*"], "Resource": "*"},
                {"Effect": "Allow", "Action": ["dynamodb:*"], "Resource": "*"},
                {"Effect": "Allow", "Action": ["s3:*"], "Resource": "*"}
            ]
        })
    )
    logger.info("Attached inline IAM policy: GrafanaExecutionPolicy")
    time.sleep(20)


def destroy_grafana_iam_role(provider: 'AWSProvider') -> None:
    """Destroys the Grafana IAM Role."""
    _destroy_iam_role(provider, provider.naming.grafana_iam_role())


# ==========================================
# Grafana Workspace
# ==========================================

def create_grafana_workspace(provider: 'AWSProvider') -> None:
    """Creates the Amazon Managed Grafana Workspace."""
    workspace_name = provider.naming.grafana_workspace()
    role_name = provider.naming.grafana_iam_role()
    iam_client = provider.clients["iam"]
    grafana_client = provider.clients["grafana"]

    response = iam_client.get_role(RoleName=role_name)
    role_arn = response["Role"]["Arn"]

    response = grafana_client.create_workspace(
        workspaceName=workspace_name,
        workspaceDescription="",
        grafanaVersion="10.4",
        accountAccessType="CURRENT_ACCOUNT",
        authenticationProviders=["AWS_SSO"],
        permissionType="CUSTOMER_MANAGED",
        workspaceRoleArn=role_arn,
        configuration=json.dumps({"plugins": {"pluginAdminEnabled": True}}),
        tags={"Environment": "Dev"}
    )
    workspace_id = response["workspace"]["id"]
    logger.info(f"Creation of Grafana workspace initiated: {workspace_name}")

    while True:
        response = grafana_client.describe_workspace(workspaceId=workspace_id)
        if response['workspace']['status'] == "ACTIVE":
            break
        time.sleep(2)

    logger.info(f"Created Grafana workspace: {workspace_name}")


def destroy_grafana_workspace(provider: 'AWSProvider') -> None:
    """Destroys the Grafana Workspace."""
    workspace_name = provider.naming.grafana_workspace()
    grafana_client = provider.clients["grafana"]

    try:
        workspace_id = util_aws.get_grafana_workspace_id_by_name(workspace_name, grafana_client)
        grafana_client.delete_workspace(workspaceId=workspace_id)
    except ClientError as e:
        if e.response["Error"]["Code"] == "ResourceNotFoundException":
            return
        raise

    logger.info(f"Deletion of Grafana workspace initiated: {workspace_name}")

    while True:
        try:
            grafana_client.describe_workspace(workspaceId=workspace_id)
            time.sleep(2)
        except ClientError as e:
            if e.response["Error"]["Code"] == "ResourceNotFoundException":
                break
            raise

    logger.info(f"Deleted Grafana workspace: {workspace_name}")


# ==========================================
# CORS Configuration
# ==========================================

def add_cors_to_twinmaker_s3_bucket(provider: 'AWSProvider') -> None:
    """Adds CORS configuration to the TwinMaker S3 bucket for Grafana access."""
    bucket_name = provider.naming.twinmaker_s3_bucket()
    workspace_name = provider.naming.grafana_workspace()
    s3_client = provider.clients["s3"]
    grafana_client = provider.clients["grafana"]

    workspace_id = util_aws.get_grafana_workspace_id_by_name(workspace_name, grafana_client)
    region = grafana_client.meta.region_name

    s3_client.put_bucket_cors(
        Bucket=bucket_name,
        CORSConfiguration={
            "CORSRules": [{
                "AllowedOrigins": [f"https://grafana.{region}.amazonaws.com/workspaces/{workspace_id}"],
                "AllowedMethods": ["GET"],
                "AllowedHeaders": ["*"],
                "MaxAgeSeconds": 3000
            }]
        }
    )
    logger.info(f"CORS configuration applied to bucket: {bucket_name}")
    logger.info(f"Allowed origin: https://grafana.{region}.amazonaws.com/workspaces/{workspace_id}")


def remove_cors_from_twinmaker_s3_bucket(provider: 'AWSProvider') -> None:
    """Removes CORS configuration from the TwinMaker S3 bucket."""
    bucket_name = provider.naming.twinmaker_s3_bucket()
    s3_client = provider.clients["s3"]

    try:
        s3_client.get_bucket_cors(Bucket=bucket_name)
        s3_client.delete_bucket_cors(Bucket=bucket_name)
        logger.info(f"CORS configuration removed from bucket: {bucket_name}")
    except ClientError as e:
        if e.response["Error"]["Code"] not in ("NoSuchBucket", "NoSuchCORSConfiguration"):
            raise


# ==========================================
# 10. Info / Status Checks
# ==========================================

def _links():
    return util_aws

def check_grafana_iam_role(provider: 'AWSProvider'):
    role_name = provider.naming.grafana_iam_role()
    client = provider.clients["iam"]

    try:
        client.get_role(RoleName=role_name)
        logger.info(f"✅ Grafana IAM Role exists: {_links().link_to_iam_role(role_name, region=provider.region)}")
    except ClientError as e:
        if e.response["Error"]["Code"] == "NoSuchEntity":
            logger.error(f"❌ Grafana IAM Role missing: {role_name}")
        else:
            raise

def check_grafana_workspace(provider: 'AWSProvider'):
    workspace_name = provider.naming.grafana_workspace()
    client = provider.clients["grafana"]
    # get_grafana_workspace_id_by_name uses list_workspaces, so it's a good check + gets ID
    try:
        workspace_id = _links().get_grafana_workspace_id_by_name(workspace_name, grafana_client=client) 
        client.describe_workspace(workspaceId=workspace_id)
        logger.info(f"✅ Grafana Workspace exists: {_links().link_to_grafana_workspace(workspace_id, region=provider.region)}")
    except ClientError as e:
        if e.response["Error"]["Code"] == "ResourceNotFoundException":
            logger.error(f"❌ Grafana Workspace missing: {workspace_name}")
        else:
            raise
    except ValueError: # Raised by get_grafana_workspace_id_by_name if not found
         logger.error(f"❌ Grafana Workspace missing: {workspace_name}")


def info_l5(context: 'DeploymentContext', provider: 'AWSProvider') -> None:
    """Check status of all L5 components."""
    check_grafana_iam_role(provider)
    check_grafana_workspace(provider)

