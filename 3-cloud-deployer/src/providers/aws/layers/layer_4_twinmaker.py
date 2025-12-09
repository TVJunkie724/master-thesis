"""
Layer 4 (TwinMaker) Deployment for AWS.

This module handles deployment and destruction of Layer 4 components:
- TwinMaker S3 Bucket (for scene assets)
- TwinMaker IAM Role
- TwinMaker Workspace
- TwinMaker Hierarchy (Entities & Components)

All functions accept provider parameters instead of using globals.
"""

import json
import time
from typing import TYPE_CHECKING
from logger import logger
import src.providers.aws.util_aws as util_aws
from botocore.exceptions import ClientError

if TYPE_CHECKING:
    from providers.aws.provider import AWSProvider
    from src.core.context import ProjectConfig


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


# ==========================================
# TwinMaker Hierarchy (Entities & Components)
# ==========================================

def create_twinmaker_hierarchy(provider: 'AWSProvider', hierarchy: list, config: 'ProjectConfig') -> None:
    """Create TwinMaker entity hierarchy."""
    if provider is None:
        raise ValueError("provider is required")
    if hierarchy is None:
        raise ValueError("hierarchy is required")
    if config is None:
        raise ValueError("config is required")
    
    workspace_name = provider.naming.twinmaker_workspace()
    twinmaker_client = provider.clients["twinmaker"]
    
    config_dict = {"digital_twin_name": config.digital_twin_name}
    
    for entity in hierarchy:
        util_aws.create_twinmaker_entity(
            entity_info=entity,
            workspace_name=workspace_name,
            twinmaker_client=twinmaker_client,
            config=config_dict
        )


def destroy_twinmaker_hierarchy(provider: 'AWSProvider', hierarchy: list) -> None:
    """Destroy TwinMaker entity hierarchy."""
    if provider is None:
        raise ValueError("provider is required")
    if hierarchy is None:
        raise ValueError("hierarchy is required")
    
    twinmaker_client = provider.clients["twinmaker"]
    workspace_name = provider.naming.twinmaker_workspace()
    
    deleting_entities = []
    
    for entity in hierarchy:
        try:
            twinmaker_client.delete_entity(
                workspaceId=workspace_name,
                entityId=entity["id"],
                isRecursive=True
            )
            deleting_entities.append(entity)
        except ClientError as e:
            if e.response["Error"]["Code"] != "ResourceNotFoundException":
                raise
    
    # Wait for deletion to complete
    for entity in deleting_entities:
        while True:
            try:
                twinmaker_client.get_entity(workspaceId=workspace_name, entityId=entity["id"])
                time.sleep(2)
            except ClientError as e:
                if e.response["Error"]["Code"] == "ResourceNotFoundException":
                    break
                else:
                    raise
        
        logger.info(f"Deleted IoT TwinMaker Entity: {entity['id']}")


def info_twinmaker_hierarchy(
    provider: 'AWSProvider',
    hierarchy: list,
    config: 'ProjectConfig',
    parent: dict = None
) -> None:
    """Print status of TwinMaker entity hierarchy."""
    if provider is None:
        raise ValueError("provider is required")
    if hierarchy is None:
        raise ValueError("hierarchy is required")
    
    twinmaker_client = provider.clients["twinmaker"]
    workspace_name = provider.naming.twinmaker_workspace()
    digital_twin_name = config.digital_twin_name
    
    for entry in hierarchy:
        if entry["type"] == "entity":
            try:
                response = twinmaker_client.get_entity(workspaceId=workspace_name, entityId=entry["id"])
                logger.info(f"✅ IoT TwinMaker Entity exists: {util_aws.link_to_twinmaker_entity(workspace_name, entry['id'], region=provider.region)}")
                
                if parent is not None and parent.get("entityId") != response.get("parentEntityId"):
                    logger.info(f"❌ IoT TwinMaker Entity {entry['id']} is missing parent: {parent.get('entityId')}")
                
                if "children" in entry:
                    info_twinmaker_hierarchy(provider, entry["children"], config, response)
                    
            except ClientError as e:
                if e.response["Error"]["Code"] == "ResourceNotFoundException":
                    logger.info(f"❌ IoT TwinMaker Entity missing: {entry['id']}")
                else:
                    raise
        
        elif entry["type"] == "component":
            if parent is None:
                continue
            
            if entry["name"] not in parent.get("components", {}):
                logger.info(f"❌ IoT TwinMaker Entity {parent.get('entityId')} is missing component: {entry['name']}")
                continue
            
            logger.info(f"✅ IoT TwinMaker Component exists: {util_aws.link_to_twinmaker_component(workspace_name, parent.get('entityId'), entry['name'], region=provider.region)}")
            
            component_info = parent["components"][entry["name"]]
            
            if "componentTypeId" in entry:
                entry_component_type_id = entry["componentTypeId"]
            else:
                entry_component_type_id = f"{digital_twin_name}-{entry['iotDeviceId']}"
            
            if component_info["componentTypeId"] != entry_component_type_id:
                logger.info(f"❌ IoT TwinMaker Component {entry['name']} has the wrong component type: {component_info['componentTypeId']} (expected: {entry_component_type_id})")


# ==========================================
# TwinMaker Component Types (for IoT Devices)
# ==========================================

def create_twinmaker_component_type(iot_device, provider: 'AWSProvider') -> None:
  """Create TwinMaker Component Type for an IoT Device."""
  if provider is None:
    raise ValueError("provider is required")

  twinmaker_client = provider.clients["twinmaker"]
  lambda_client = provider.clients["lambda"]
  connector_function_name = provider.naming.hot_reader_lambda_function()
  connector_last_entry_function_name = provider.naming.hot_reader_last_entry_lambda_function()
  workspace_name = provider.naming.twinmaker_workspace()
  component_type_id = provider.naming.twinmaker_component_type_id(iot_device["id"])

  response = lambda_client.get_function(FunctionName=connector_function_name)
  connector_function_arn = response["Configuration"]["FunctionArn"]

  response = lambda_client.get_function(FunctionName=connector_last_entry_function_name)
  connector_last_entry_function_arn = response["Configuration"]["FunctionArn"]

  property_definitions = {}

  if "properties" in iot_device:
    for property in iot_device["properties"]:
      property_definitions[property["name"]] = {
        "dataType": {
          "type": property["dataType"]
        },
        "isTimeSeries": True,
        "isStoredExternally": True
      }

  if "constProperties" in iot_device:
    for const_property in iot_device["constProperties"]:
      property_definitions[const_property["name"]] = {
        "dataType": {
          "type": const_property["dataType"]
        },
        "defaultValue": {
          f"{const_property['dataType'].lower()}Value": const_property["value"]
        },
        "isTimeSeries": False,
        "isStoredExternally": False
      }

  functions = {
    "dataReader": {
      "implementedBy": {
        "lambda": {
          "arn": connector_function_arn
        }
      }
    },
    "attributePropertyValueReaderByEntity": {
      "implementedBy": {
        "lambda": {
          "arn": connector_last_entry_function_arn
        }
      }
    }
  }

  twinmaker_client.create_component_type(
    workspaceId=workspace_name,
    componentTypeId=component_type_id,
    propertyDefinitions=property_definitions,
    functions=functions
  )

  logger.info(f"Creation of IoT Twinmaker Component Type initiated: {component_type_id}")

  while True:
    response = twinmaker_client.get_component_type(workspaceId=workspace_name, componentTypeId=component_type_id)
    if response["status"]["state"] == "ACTIVE":
      break
    time.sleep(2)

  logger.info(f"Created IoT Twinmaker Component Type: {component_type_id}")


def destroy_twinmaker_component_type(iot_device, provider: 'AWSProvider') -> None:
  """Destroy TwinMaker Component Type and clean up entities using it."""
  if provider is None:
    raise ValueError("provider is required")

  twinmaker_client = provider.clients["twinmaker"]
  workspace_name = provider.naming.twinmaker_workspace()
  component_type_id = provider.naming.twinmaker_component_type_id(iot_device["id"])

  try:
    twinmaker_client.get_component_type(workspaceId=workspace_name, componentTypeId=component_type_id)
  except ClientError as e:
    if e.response['Error']['Code'] == 'ResourceNotFoundException':
      return

  try:
    response = twinmaker_client.list_entities(workspaceId=workspace_name)

    for entity in response.get("entitySummaries", []):
      entity_details = twinmaker_client.get_entity(workspaceId=workspace_name, entityId=entity["entityId"])
      components = entity_details.get("components", {})
      component_updates = {}

      for comp_name, comp in components.items():
        if comp.get("componentTypeId") == component_type_id:
          component_updates[comp_name] = {"updateType": "DELETE"}

      if component_updates:
        twinmaker_client.update_entity(workspaceId=workspace_name, entityId=entity["entityId"], componentUpdates=component_updates)
        logger.info("Deletion of components initiated.")
        
        while True:
          entity_details_2 = twinmaker_client.get_entity(workspaceId=workspace_name, entityId=entity["entityId"])
          components_2 = entity_details_2.get("components", {})

          if not set(component_updates.keys()) & set(components_2.keys()):
            logger.info(f"Deleted components.")
            break
          else:
            time.sleep(2)

  except ClientError as e:
    if e.response["Error"]["Code"] != "ValidationException":
      raise

  logger.info(f"Deleted all IoT Twinmaker Components with component type id: {component_type_id}")

  twinmaker_client.delete_component_type(workspaceId=workspace_name, componentTypeId=component_type_id)

  logger.info(f"Deletion of IoT Twinmaker Component Type initiated: {component_type_id}")

  while True:
    try:
      twinmaker_client.get_component_type(workspaceId=workspace_name, componentTypeId=component_type_id)
      time.sleep(2)
    except ClientError as e:
      if e.response['Error']['Code'] == 'ResourceNotFoundException':
        break
      else:
        raise

  logger.info(f"Deleted IoT Twinmaker Component Type: {component_type_id}")


# ==========================================
# 10. Info / Status Checks
# ==========================================

def _links():
    return util_aws

def check_twinmaker_s3_bucket(provider: 'AWSProvider'):
    bucket_name = provider.naming.twinmaker_s3_bucket()
    client = provider.clients["s3"]
    try:
        client.head_bucket(Bucket=bucket_name)
        logger.info(f"✅ TwinMaker S3 Bucket exists: {_links().link_to_s3_bucket(bucket_name, region=provider.region)}")
    except ClientError as e:
        if e.response["Error"]["Code"] == "404":
            logger.error(f"❌ TwinMaker S3 Bucket missing: {bucket_name}")
        else:
            raise

def check_twinmaker_iam_role(provider: 'AWSProvider'):
    role_name = provider.naming.twinmaker_iam_role()
    client = provider.clients["iam"]
    try:
        client.get_role(RoleName=role_name)
        logger.info(f"✅ TwinMaker IAM Role exists: {_links().link_to_iam_role(role_name, region=provider.region)}")
    except ClientError as e:
        if e.response["Error"]["Code"] == "NoSuchEntity":
            logger.error(f"❌ TwinMaker IAM Role missing: {role_name}")
        else:
            raise

def check_twinmaker_workspace(provider: 'AWSProvider'):
    workspace_name = provider.naming.twinmaker_workspace()
    client = provider.clients["twinmaker"]
    try:
        client.get_workspace(workspaceId=workspace_name)
        logger.info(f"✅ TwinMaker Workspace exists: {_links().link_to_twinmaker_workspace(workspace_name, region=provider.region)}")
    except ClientError as e:
        if e.response["Error"]["Code"] == "ResourceNotFoundException":
            logger.error(f"❌ TwinMaker Workspace missing: {workspace_name}")
        else:
            raise

def check_twinmaker_component_type(iot_device, provider: 'AWSProvider'):
    if provider is None:
        raise ValueError("provider is required")

    workspace_name = provider.naming.twinmaker_workspace()
    component_type_id = provider.naming.twinmaker_component_type_id(iot_device.get('name', 'unknown'))
    client = provider.clients["twinmaker"]

    try:
        client.get_component_type(workspaceId=workspace_name, componentTypeId=component_type_id)
        logger.info(f"✅ Twinmaker Component Type {component_type_id} exists: {_links().link_to_twinmaker_component_type(workspace_name, component_type_id, region=provider.region)}")
    except ClientError as e:
        if e.response["Error"]["Code"] == "ResourceNotFoundException":
            logger.error(f"❌ Twinmaker Component Type {component_type_id} missing: {component_type_id}")
        else:
            raise

def info_l4(context: 'DeploymentContext', provider: 'AWSProvider') -> None:
    """Check status of all L4 components."""
    check_twinmaker_s3_bucket(provider)
    check_twinmaker_iam_role(provider)
    check_twinmaker_workspace(provider)
    
    if context.config.twinmaker_hierarchy:
        info_twinmaker_hierarchy(provider, context.config.twinmaker_hierarchy, context.config)

    if context.config.devices:
        for device in context.config.devices:
            check_twinmaker_component_type(device, provider)
