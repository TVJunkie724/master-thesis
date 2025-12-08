"""
Layer 4 (TwinMaker) Deployment for AWS.

This module handles deployment and destruction of Layer 4 components:
- TwinMaker S3 Bucket (for scene assets)
- TwinMaker IAM Role
- TwinMaker Workspace

All functions accept provider parameters instead of using globals.
"""

import json
import time
from typing import TYPE_CHECKING
from logger import logger
import src.aws.util_aws as util_aws
from botocore.exceptions import ClientError

if TYPE_CHECKING:
    from src.providers.aws.provider import AWSProvider


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
# TwinMaker S3 Bucket
# ==========================================

def create_twinmaker_s3_bucket(provider: 'AWSProvider') -> None:
    """Creates the S3 Bucket for IoT TwinMaker assets."""
    bucket_name = provider.naming.twinmaker_s3_bucket()
    s3_client = provider.clients["s3"]
    region = s3_client.meta.region_name

    create_args = {"Bucket": bucket_name}
    if region != "us-east-1":
        create_args["CreateBucketConfiguration"] = {"LocationConstraint": region}

    s3_client.create_bucket(**create_args)
    logger.info(f"Created S3 Bucket: {bucket_name}")


def destroy_twinmaker_s3_bucket(provider: 'AWSProvider') -> None:
    """Destroys the TwinMaker S3 bucket."""
    util_aws.destroy_s3_bucket(provider.naming.twinmaker_s3_bucket(), provider.clients["s3"])


# ==========================================
# TwinMaker IAM Role
# ==========================================

def create_twinmaker_iam_role(provider: 'AWSProvider') -> None:
    """Creates the IAM Role for the IoT TwinMaker Workspace."""
    role_name = provider.naming.twinmaker_iam_role()
    iam_client = provider.clients["iam"]

    iam_client.create_role(
        RoleName=role_name,
        AssumeRolePolicyDocument=json.dumps({
            "Version": "2012-10-17",
            "Statement": [{
                "Effect": "Allow",
                "Principal": {"Service": "iottwinmaker.amazonaws.com"},
                "Action": "sts:AssumeRole"
            }]
        })
    )
    logger.info(f"Created IAM role: {role_name}")

    iam_client.put_role_policy(
        RoleName=role_name,
        PolicyName="TwinMakerExecutionPolicy",
        PolicyDocument=json.dumps({
            "Version": "2012-10-17",
            "Statement": [{
                "Effect": "Allow",
                "Action": ["s3:*", "dynamodb:*", "lambda:*"],
                "Resource": "*"
            }]
        })
    )
    logger.info("Attached inline IAM policy: TwinMakerExecutionPolicy")
    logger.info("Waiting for propagation...")
    time.sleep(20)


def destroy_twinmaker_iam_role(provider: 'AWSProvider') -> None:
    """Destroys the TwinMaker IAM Role."""
    _destroy_iam_role(provider, provider.naming.twinmaker_iam_role())


# ==========================================
# TwinMaker Workspace
# ==========================================

def create_twinmaker_workspace(provider: 'AWSProvider') -> None:
    """Creates the IoT TwinMaker Workspace."""
    workspace_name = provider.naming.twinmaker_workspace()
    role_name = provider.naming.twinmaker_iam_role()
    bucket_name = provider.naming.twinmaker_s3_bucket()
    twinmaker_client = provider.clients["twinmaker"]
    sts_client = provider.clients["sts"]

    account_id = sts_client.get_caller_identity()['Account']

    twinmaker_client.create_workspace(
        workspaceId=workspace_name,
        role=f"arn:aws:iam::{account_id}:role/{role_name}",
        s3Location=f"arn:aws:s3:::{bucket_name}",
        description=""
    )
    logger.info(f"Created IoT TwinMaker workspace: {workspace_name}")


def destroy_twinmaker_workspace(provider: 'AWSProvider') -> None:
    """Destroys the IoT TwinMaker Workspace (recursively deletes entities, scenes, etc.)."""
    workspace_name = provider.naming.twinmaker_workspace()
    twinmaker_client = provider.clients["twinmaker"]

    # Delete entities
    try:
        response = twinmaker_client.list_entities(workspaceId=workspace_name)
        deleted = False
        for entity in response.get("entitySummaries", []):
            try:
                twinmaker_client.delete_entity(
                    workspaceId=workspace_name,
                    entityId=entity["entityId"],
                    isRecursive=True
                )
                deleted = True
                logger.info(f"Deleted IoT TwinMaker entity: {entity['entityId']}")
            except ClientError as e:
                if e.response["Error"]["Code"] != "ResourceNotFoundException":
                    raise
        if deleted:
            time.sleep(20)
    except ClientError as e:
        if e.response["Error"]["Code"] != "ValidationException":
            raise

    # Delete scenes
    try:
        response = twinmaker_client.list_scenes(workspaceId=workspace_name)
        for scene in response.get("sceneSummaries", []):
            try:
                twinmaker_client.delete_scene(workspaceId=workspace_name, sceneId=scene["sceneId"])
                logger.info(f"Deleted IoT TwinMaker scene: {scene['sceneId']}")
            except ClientError as e:
                if e.response["Error"]["Code"] != "ResourceNotFoundException":
                    raise
    except ClientError as e:
        if e.response["Error"]["Code"] != "ValidationException":
            raise

    # Delete component types (except built-in)
    try:
        response = twinmaker_client.list_component_types(workspaceId=workspace_name)
        for ct in response.get("componentTypeSummaries", []):
            if ct["componentTypeId"].startswith("com.amazon"):
                continue
            try:
                twinmaker_client.delete_component_type(
                    workspaceId=workspace_name,
                    componentTypeId=ct["componentTypeId"]
                )
                logger.info(f"Deleted IoT TwinMaker component type: {ct['componentTypeId']}")
            except ClientError as e:
                if e.response["Error"]["Code"] != "ResourceNotFoundException":
                    raise
    except ClientError as e:
        if e.response["Error"]["Code"] != "ValidationException":
            raise

    # Delete workspace
    try:
        twinmaker_client.delete_workspace(workspaceId=workspace_name)
    except ClientError as e:
        if e.response["Error"]["Code"] == "ResourceNotFoundException":
            return
        raise

    logger.info(f"Deletion of IoT TwinMaker workspace initiated: {workspace_name}")

    while True:
        try:
            twinmaker_client.get_workspace(workspaceId=workspace_name)
            time.sleep(2)
        except ClientError as e:
            if e.response["Error"]["Code"] == "ResourceNotFoundException":
                break
            raise

    logger.info(f"Deleted IoT TwinMaker workspace: {workspace_name}")
