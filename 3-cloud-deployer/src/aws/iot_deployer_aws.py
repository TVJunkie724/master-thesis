import json
import globals
from logger import logger
import aws.globals_aws as globals_aws
import os
from botocore.exceptions import ClientError
import shutil
import time
import util
import constants as CONSTANTS



def _generate_simulator_config(iot_device):
    """
    Generates config_generated.json for the IoT device simulator.
    Called after device certificate creation.
    
    This file contains all runtime information the simulator needs:
    - AWS IoT endpoint (fetched dynamically)
    - MQTT topic (derived from digital_twin_name)
    - Paths to device certificates (relative to config file location)
    - Path to Root CA (bundled in src/)
    - Path to payloads.json (same directory as config)
    """
    import globals
    
    # 1. Fetch IoT Endpoint (dynamically via Boto3)
    endpoint_response = globals_aws.aws_iot_client.describe_endpoint(endpointType='iot:Data-ATS')
    endpoint = endpoint_response['endpointAddress']
    
    # 2. Derive topic from digital_twin_name
    topic = globals.config["digital_twin_name"] + "/iot-data"
    
    # 3. Paths
    device_id = iot_device['id']
    
    # Resolve Root CA path (bundled in src)
    # This is an absolute path since it's in the system code, not project data
    # We are in src/aws/ so we need to go up to src/ then into iot_device_simulator/aws/
    root_ca_path = os.path.abspath(os.path.join(
        os.path.dirname(__file__), "..", "iot_device_simulator", "aws", "AmazonRootCA1.pem"
    ))
    
    config_data = {
        "endpoint": endpoint,
        "topic": topic,
        "device_id": device_id,
        # Relative paths from config file location (upload/{project}/iot_device_simulator/aws/)
        "cert_path": f"../../iot_devices_auth/{device_id}/certificate.pem.crt",
        "key_path": f"../../iot_devices_auth/{device_id}/private.pem.key",
        "root_ca_path": root_ca_path,  # Absolute path to bundled Root CA
        "payload_path": "payloads.json"  # Same directory as config_generated.json
    }
    
    # 4. Write to upload/{project}/iot_device_simulator/aws/
    sim_dir = os.path.join(util.get_path_in_project(), "iot_device_simulator", "aws")
    os.makedirs(sim_dir, exist_ok=True)
    config_path = os.path.join(sim_dir, "config_generated.json")
    with open(config_path, "w") as f:
        json.dump(config_data, f, indent=2)
    logger.info(f"Generated simulator config: {config_path}")

def create_iot_thing(iot_device):
  thing_name = globals_aws.iot_thing_name(iot_device)
  policy_name = globals_aws.iot_thing_policy_name(iot_device)

  globals_aws.aws_iot_client.create_thing(thingName=thing_name)
  logger.info(f"Created IoT Thing: {thing_name}")

  cert_response = globals_aws.aws_iot_client.create_keys_and_certificate(setAsActive=True)
  certificate_arn = cert_response['certificateArn']
  logger.info(f"Created IoT Certificate: {cert_response['certificateId']}")

  dir = f"{util.get_path_in_project(CONSTANTS.IOT_DATA_DIR_NAME)}/{iot_device['id']}/"
  os.makedirs(os.path.dirname(dir), exist_ok=True)

  with open(f"{dir}certificate.pem.crt", "w") as f:
    f.write(cert_response["certificatePem"])
  with open(f"{dir}private.pem.key", "w") as f:
    f.write(cert_response["keyPair"]["PrivateKey"])
  with open(f"{dir}public.pem.key", "w") as f:
    f.write(cert_response["keyPair"]["PublicKey"])

  logger.info(f"Stored certificate and keys to {dir}")

  policy_document = {
    "Version": "2012-10-17",
    "Statement": [{
      "Effect": "Allow",
      "Action": ["iot:*"],
      "Resource": "*"
    }]
  }

  globals_aws.aws_iot_client.create_policy(policyName=policy_name, policyDocument=json.dumps(policy_document))
  logger.info(f"Created IoT Policy: {policy_name}")

  globals_aws.aws_iot_client.attach_thing_principal(thingName=thing_name, principal=certificate_arn)
  logger.info(f"Attached IoT Certificate to Thing")

  globals_aws.aws_iot_client.attach_policy(policyName=policy_name, target=certificate_arn)
  logger.info(f"Attached IoT Policy to Certificate")

  _generate_simulator_config(iot_device)

def destroy_iot_thing(iot_device):
  thing_name = globals_aws.iot_thing_name(iot_device)
  policy_name = globals_aws.iot_thing_policy_name(iot_device)

  try:
    principals_resp = globals_aws.aws_iot_client.list_thing_principals(thingName=thing_name)
    principals = principals_resp.get('principals', [])

    if len(principals) > 1:
      raise ValueError("Error at deleting IoT Thing: Too many principals or certificates attached. Not sure which one to delete.")

    for principal in principals:
      globals_aws.aws_iot_client.detach_thing_principal(thingName=thing_name, principal=principal)
      logger.info(f"Detached IoT Certificate")

      policies = globals_aws.aws_iot_client.list_attached_policies(target=principal)
      for p in policies.get('policies', []):
        globals_aws.aws_iot_client.detach_policy(policyName=p['policyName'], target=principal)
        logger.info(f"Detached IoT Policy")

      cert_id = principal.split('/')[-1]
      globals_aws.aws_iot_client.update_certificate(certificateId=cert_id, newStatus='INACTIVE')
      globals_aws.aws_iot_client.delete_certificate(certificateId=cert_id, forceDelete=True)
      logger.info(f"Deleted IoT Certificate: {cert_id}")
  except ClientError as e:
    if e.response["Error"]["Code"] != "ResourceNotFoundException":
      raise

  try:
    versions = globals_aws.aws_iot_client.list_policy_versions(policyName=policy_name).get('policyVersions', [])
    for version in versions:
      if not version['isDefaultVersion']:
        try:
          globals_aws.aws_iot_client.delete_policy_version(policyName=policy_name, policyVersionId=version['versionId'])
          logger.info(f"Deleted IoT Policy version: {version['versionId']}")
        except ClientError as e:
          if e.response["Error"]["Code"] != "ResourceNotFoundException":
            raise
  except ClientError as e:
    if e.response["Error"]["Code"] != "ResourceNotFoundException":
      raise

  try:
    globals_aws.aws_iot_client.delete_policy(policyName=policy_name)
    logger.info(f"Deleted IoT Policy: {policy_name}")
  except ClientError as e:
    if e.response["Error"]["Code"] != "ResourceNotFoundException":
      raise

  try:
    globals_aws.aws_iot_client.describe_thing(thingName=thing_name)
    globals_aws.aws_iot_client.delete_thing(thingName=thing_name)
    logger.info(f"Deleted IoT Thing: {thing_name}")
  except ClientError as e:
    if e.response["Error"]["Code"] != "ResourceNotFoundException":
      raise

  try:
    shutil.rmtree(f"{util.get_path_in_project(CONSTANTS.IOT_DATA_DIR_NAME)}/{iot_device['id']}")
  except FileNotFoundError:
    pass


def create_processor_iam_role(iot_device):
  role_name = globals_aws.processor_iam_role_name(iot_device)

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

  time.sleep(10)

def destroy_processor_iam_role(iot_device):
  role_name = globals_aws.processor_iam_role_name(iot_device)

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


def create_processor_lambda_function(iot_device):
  l1_provider = globals.config_providers.get("layer_1_provider", "aws")
  l2_provider = globals.config_providers.get("layer_2_provider", "aws")
  
  # Scenario 1: L2 is Remote (e.g. AWS -> Azure)
  if l2_provider != "aws":
      function_name = globals_aws.connector_lambda_function_name(iot_device)
      # No separate role needed? Connector is simple. 
      # Reuse processor role or create new one? Processor role is fine.
      role_name = globals_aws.processor_iam_role_name(iot_device) 
      
      response = globals_aws.aws_iam_client.get_role(RoleName=role_name)
      role_arn = response['Role']['Arn']
      
      # Connection Info
      conn_id = f"{l1_provider}_l1_to_{l2_provider}_l2"
      connections = globals.config_inter_cloud.get("connections", {})
      conn = connections.get(conn_id, {})
      remote_url = conn.get("url", "")
      token = conn.get("token", "")
      
      if not remote_url or not token:
          raise ValueError(
              f"Missing inter-cloud connection info for '{conn_id}'. "
              f"Ensure config_inter_cloud.json contains 'url' and 'token' for this connection."
          )

      globals_aws.aws_lambda_client.create_function(
        FunctionName=function_name,
        Runtime="python3.13",
        Role=role_arn,
        Handler="lambda_function.lambda_handler", 
        Code={"ZipFile": util.compile_lambda_function(os.path.join(util.get_path_in_project(CONSTANTS.LAMBDA_FUNCTIONS_DIR_NAME), "connector"))},
        Description="Connector to Remote L2",
        Timeout=10, 
        MemorySize=128, 
        Publish=True,
        Environment={
          "Variables": {
            "REMOTE_INGESTION_URL": remote_url,
            "INTER_CLOUD_TOKEN": token
          }
        }
      )
      logger.info(f"Created Connector Lambda function: {function_name}")
      
  # Scenario 2: L2 is Local (AWS)
  else:
      function_name = globals_aws.processor_lambda_function_name(iot_device)
      role_name = globals_aws.processor_iam_role_name(iot_device)
      
      response = globals_aws.aws_iam_client.get_role(RoleName=role_name)
      role_arn = response['Role']['Arn']
      
      # Determine path to user's custom logic
      # It should be in upload/<project>/lambda_functions/processors/<iotDeviceId>/process.py
      # If not found, use default.
      
      # Check specific device folder first
      custom_rel_path = f"{CONSTANTS.LAMBDA_FUNCTIONS_DIR_NAME}/processors/{iot_device['iotDeviceId']}/process.py"
      if not os.path.exists(os.path.join(util.get_path_in_project(), custom_rel_path)):
          # Check default folder
          custom_rel_path = f"{CONSTANTS.LAMBDA_FUNCTIONS_DIR_NAME}/processors/default_processor/process.py"
      
      # Wrapper System Code
      wrapper_path = os.path.join(util.get_path_in_project(CONSTANTS.LAMBDA_FUNCTIONS_DIR_NAME), "processor_wrapper")
      
      # Merge
      zip_bytes = util.compile_merged_lambda_function(wrapper_path, custom_rel_path)

      globals_aws.aws_lambda_client.create_function(
        FunctionName=function_name,
        Runtime="python3.13",
        Role=role_arn,
        Handler="lambda_function.lambda_handler", 
        Code={"ZipFile": zip_bytes},
        Description="Merged Processor (Wrapper + User Logic)",
        Timeout=3,
        MemorySize=128, 
        Publish=True,
        Environment={
          "Variables": {
            "DIGITAL_TWIN_INFO": json.dumps(globals.digital_twin_info()),
            "PERSISTER_LAMBDA_NAME": globals_aws.persister_lambda_function_name()
          }
        }
      )
      logger.info(f"Created Merged Processor Lambda function: {function_name}")

def destroy_processor_lambda_function(iot_device):
  # Try to delete processor lambda (single-cloud scenario)
  processor_function_name = globals_aws.processor_lambda_function_name(iot_device)
  try:
    globals_aws.aws_lambda_client.delete_function(FunctionName=processor_function_name)
    logger.info(f"Deleted Lambda function: {processor_function_name}")
  except ClientError as e:
    if e.response["Error"]["Code"] != "ResourceNotFoundException":
      raise

  # Also try to delete connector lambda (multi-cloud scenario)
  connector_function_name = globals_aws.connector_lambda_function_name(iot_device)
  try:
    globals_aws.aws_lambda_client.delete_function(FunctionName=connector_function_name)
    logger.info(f"Deleted Lambda function: {connector_function_name}")
  except ClientError as e:
    if e.response["Error"]["Code"] != "ResourceNotFoundException":
      raise


def create_twinmaker_component_type(iot_device):
  connector_function_name = globals_aws.hot_reader_lambda_function_name()
  connector_last_entry_function_name = globals_aws.hot_reader_last_entry_lambda_function_name()
  workspace_name = globals_aws.twinmaker_workspace_name()
  component_type_id = globals_aws.twinmaker_component_type_id(iot_device)

  response = globals_aws.aws_lambda_client.get_function(FunctionName=connector_function_name)
  connector_function_arn = response["Configuration"]["FunctionArn"]

  response = globals_aws.aws_lambda_client.get_function(FunctionName=connector_last_entry_function_name)
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

  functions = {}

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

  globals_aws.aws_twinmaker_client.create_component_type(
    workspaceId=workspace_name,
    componentTypeId=component_type_id,
    propertyDefinitions=property_definitions,
    functions=functions
  )

  logger.info(f"Creation of IoT Twinmaker Component Type initiated: {component_type_id}")

  while True:
    response = globals_aws.aws_twinmaker_client.get_component_type(workspaceId=workspace_name, componentTypeId=component_type_id)
    if response["status"]["state"] == "ACTIVE":
      break
    time.sleep(2)

  logger.info(f"Created IoT Twinmaker Component Type: {component_type_id}")

def destroy_twinmaker_component_type(iot_device):
  workspace_name = globals_aws.twinmaker_workspace_name()
  component_type_id = globals_aws.twinmaker_component_type_id(iot_device)

  try:
    globals_aws.aws_twinmaker_client.get_component_type(workspaceId=workspace_name, componentTypeId=component_type_id)
  except ClientError as e:
    if e.response['Error']['Code'] == 'ResourceNotFoundException':
      return

  try:
    response = globals_aws.aws_twinmaker_client.list_entities(workspaceId=workspace_name)

    for entity in response.get("entitySummaries", []):
      entity_details = globals_aws.aws_twinmaker_client.get_entity(workspaceId=workspace_name, entityId=entity["entityId"])
      components = entity_details.get("components", {})
      component_updates = {}

      for comp_name, comp in components.items():
        if comp.get("componentTypeId") == component_type_id:
          component_updates[comp_name] = {"updateType": "DELETE"}

      if component_updates:
        globals_aws.aws_twinmaker_client.update_entity(workspaceId=workspace_name, entityId=entity["entityId"], componentUpdates=component_updates)
        logger.info("Deletion of components initiated.")

        while True:
          entity_details_2 = globals_aws.aws_twinmaker_client.get_entity(workspaceId=workspace_name, entityId=entity["entityId"])
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

  globals_aws.aws_twinmaker_client.delete_component_type(workspaceId=workspace_name, componentTypeId=component_type_id)

  logger.info(f"Deletion of IoT Twinmaker Component Type initiated: {component_type_id}")

  while True:
    try:
      globals_aws.aws_twinmaker_client.get_component_type(workspaceId=workspace_name, componentTypeId=component_type_id)
      time.sleep(2)
    except ClientError as e:
      if e.response['Error']['Code'] == 'ResourceNotFoundException':
        break
      else:
        raise

  logger.info(f"Deleted IoT Twinmaker Component Type: {component_type_id}")

