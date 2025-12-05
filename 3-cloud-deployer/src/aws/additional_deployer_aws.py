import time
import globals
import aws.globals_aws as globals_aws
from logger import logger
import util
from botocore.exceptions import ClientError


def create_twinmaker_hierarchy():
  for entity in globals.config_hierarchy:
    util.create_twinmaker_entity(entity)

def destroy_twinmaker_hierarchy():
  workspace_name = globals_aws.twinmaker_workspace_name()
  deleting_entities = []

  for entity in globals.config_hierarchy:
    try:
      globals_aws.aws_twinmaker_client.delete_entity(workspaceId=workspace_name, entityId=entity["id"], isRecursive=True)
      deleting_entities.append(entity)
    except ClientError as e:
      if e.response["Error"]["Code"] != "ResourceNotFoundException":
        raise

  for entity in deleting_entities:
    while True:
      try:
        globals_aws.aws_twinmaker_client.get_entity(workspaceId=workspace_name, entityId=entity["id"])
        time.sleep(2)
      except ClientError as e:
        if e.response["Error"]["Code"] == "ResourceNotFoundException":
          break
        else:
          raise

    log(f"Deleted IoT TwinMaker Entity: {entity['id']}")

def info_twinmaker_hierarchy(hierarchy=None, parent=None):
  workspace_name = globals_aws.twinmaker_workspace_name()

  if hierarchy is None:
    hierarchy = globals.config_hierarchy

  for entry in hierarchy:
    if entry["type"] == "entity":
      try:
        response = globals_aws.aws_twinmaker_client.get_entity(workspaceId=workspace_name, entityId=entry["id"])
        log(f"✅ IoT TwinMaker Entity exists: {util.link_to_twinmaker_entity(workspace_name, entry['id'])}")

        if parent is not None and parent["entityId"] != response.get("parentEntityId"):
          log(f"❌ IoT TwinMaker Entity {entry['id']} is missing parent: {parent['entityId']}")

        if "children" in entry:
          info_twinmaker_hierarchy(entry["children"], response)
      except ClientError as e:
        if e.response["Error"]["Code"] == "ResourceNotFoundException":
          log(f"❌ IoT TwinMaker Entity missing: {entry['id']}")
        else:
          raise

    elif entry["type"] == "component":
      if parent is None:
        continue

      if entry["name"] not in parent.get("components", {}):
        log(f"❌ IoT TwinMaker Entity {parent['entityId']} is missing component: {entry['name']}")
        continue

      log(f"✅ IoT TwinMaker Component exists: {util.link_to_twinmaker_component(workspace_name, parent['entityId'], entry['name'])}")

      component_info = parent["components"][entry["name"]]

      if "componentTypeId" in entry:
        entry_component_type_id = entry["componentTypeId"]
      else:
        entry_component_type_id = f"{globals.config['digital_twin_name']}-{entry['iotDeviceId']}"

      if component_info["componentTypeId"] != entry_component_type_id:
        log(f"❌ IoT TwinMaker Component {entry['name']} has the wrong component type: {component_info['componentTypeId']} (expected: {entry_component_type_id})")



def log(string):
  logger.info(f"Additional Deployer (AWS): " + string)
