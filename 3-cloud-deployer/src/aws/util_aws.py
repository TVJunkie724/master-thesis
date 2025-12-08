import globals
import aws.globals_aws as globals_aws
import util
from botocore.exceptions import ClientError

def compile_lambda_function(relative_folder_path):
  zip_path = util.zip_directory(relative_folder_path)

  with open(zip_path, "rb") as f:
    zip_code = f.read()

  return zip_code

def iot_rule_exists(rule_name):
  paginator = globals_aws.aws_iot_client.get_paginator('list_topic_rules')
  for page in paginator.paginate():
      for rule in page.get('rules', []):
          if rule['ruleName'] == rule_name:
              return True
  return False

def destroy_s3_bucket(bucket_name, s3_client=None):
  """Delete S3 bucket and all its contents.
  
  Args:
    bucket_name: Name of the S3 bucket to delete
    s3_client: Optional boto3 S3 client. If None, uses globals_aws.aws_s3_client
  """
  if s3_client is None:
    s3_client = globals_aws.aws_s3_client
    
  try:
    paginator = s3_client.get_paginator('list_objects_v2')
    for page in paginator.paginate(Bucket=bucket_name):
      if 'Contents' in page:
        objects = [{'Key': obj['Key']} for obj in page['Contents']]
        s3_client.delete_objects(Bucket=bucket_name, Delete={'Objects': objects})
    print(f"Deleted all objects from S3 Bucket: {bucket_name}")
  except ClientError as e:
    if e.response['Error']['Code'] != 'NoSuchBucket':
      raise

  try:
    paginator = s3_client.get_paginator('list_object_versions')
    for page in paginator.paginate(Bucket=bucket_name):
      versions = page.get('Versions', []) + page.get('DeleteMarkers', [])
      if versions:
        objects = [{'Key': v['Key'], 'VersionId': v['VersionId']} for v in versions]
        s3_client.delete_objects(Bucket=bucket_name, Delete={'Objects': objects})
    print(f"Deleted all object versions from S3 Bucket: {bucket_name}")
  except ClientError as e:
    if e.response['Error']['Code'] != 'NoSuchBucket':
      raise

  try:
    s3_client.delete_bucket(Bucket=bucket_name)
    print(f"Deleted S3 Bucket: {bucket_name}")
  except ClientError as e:
    if e.response['Error']['Code'] != 'NoSuchBucket':
      raise

def get_grafana_workspace_id_by_name(workspace_name, grafana_client=None):
    """Get Grafana workspace ID by name.
    
    Args:
        workspace_name: Name of the Grafana workspace
        grafana_client: Optional boto3 Grafana client. If None, uses globals_aws.aws_grafana_client
    """
    if grafana_client is None:
        grafana_client = globals_aws.aws_grafana_client
    
    paginator = grafana_client.get_paginator("list_workspaces")

    for page in paginator.paginate():
        for workspace in page["workspaces"]:
            if workspace["name"] == workspace_name:
                return workspace["id"] if "id" in workspace else workspace["workspaceId"]

    error_response = {
      "Error": {
        "Code": "ResourceNotFoundException",
        "Message": "The requested resource was not found."
      }
    }

    operation_name = "get_grafana_workspace_id_by_name"

    raise ClientError(error_response, operation_name)

def create_twinmaker_entity(entity_info, parent_info=None):
  create_entity_params = {
    "workspaceId": globals.twinmaker_workspace_name(),
    "entityName": entity_info["id"],
    "entityId": entity_info["id"],
  }

  if parent_info is not None:
    create_entity_params["parentEntityId"] = parent_info["id"]

  response = globals_aws.aws_twinmaker_client.create_entity(**create_entity_params)

  print(f"Created IoT TwinMaker Entity: {response['entityId']}")

  for child in entity_info["children"]:
    if child["type"] == "entity":
      create_twinmaker_entity(child, entity_info)
    elif child["type"] == "component":
      create_twinmaker_component(child, entity_info)

def create_twinmaker_component(component_info, parent_info):
  if "componentTypeId" in component_info:
    component_type_id = component_info["componentTypeId"]
  else:
    component_type_id = f"{globals.config['digital_twin_name']}-{component_info['iotDeviceId']}"

  globals_aws.aws_twinmaker_client.update_entity(
    workspaceId=globals.twinmaker_workspace_name(),
    entityId=parent_info["id"],
    componentUpdates={
        component_info["name"]: {
            "updateType": "CREATE",
            "componentTypeId": component_type_id
        }
    }
  )

  print(f"Created IoT TwinMaker Component: {component_info['name']}")

def link_to_iam_role(role_name):
  return f"https://console.aws.amazon.com/iam/home?region={globals_aws.aws_iam_client.meta.region_name}#/roles/{role_name}"

def link_to_lambda_function(function_name):
  return f"https://console.aws.amazon.com/lambda/home?region={globals_aws.aws_lambda_client.meta.region_name}#/functions/{function_name}"

def link_to_iot_rule(rule_name):
  return f"https://console.aws.amazon.com/iot/home?region={globals_aws.aws_iot_client.meta.region_name}#/rule/{rule_name}"

def link_to_iot_thing(thing_name):
  return f"https://console.aws.amazon.com/iot/home?region={globals_aws.aws_iot_client.meta.region_name}#/thing/{thing_name}"

def link_to_dynamodb_table(table_name):
  return f"https://console.aws.amazon.com/dynamodbv2/home?region={globals_aws.aws_dynamodb_client.meta.region_name}#table?name={table_name}"

def link_to_event_rule(rule_name):
  return f"https://console.aws.amazon.com/events/home?region={globals_aws.aws_events_client.meta.region_name}#/eventbus/default/rules/{rule_name}"

def link_to_s3_bucket(bucket_name):
  return f"https://console.aws.amazon.com/s3/buckets/{bucket_name}"

def link_to_twinmaker_workspace(workspace_name):
  return f"https://console.aws.amazon.com/iottwinmaker/home?region={globals_aws.aws_twinmaker_client.meta.region_name}#/workspaces/{workspace_name}"

def link_to_twinmaker_component_type(workspace_name, component_type_id):
  return f"https://console.aws.amazon.com/iottwinmaker/home?region={globals_aws.aws_twinmaker_client.meta.region_name}#/workspaces/{workspace_name}/component-types/{component_type_id}"

def link_to_twinmaker_entity(workspace_name, entity_id):
  return f"https://console.aws.amazon.com/iottwinmaker/home?region={globals_aws.aws_twinmaker_client.meta.region_name}#/workspaces/{workspace_name}/entities/{entity_id}"

def link_to_twinmaker_component(workspace_name, entity_id, component_name):
  return f"https://console.aws.amazon.com/iottwinmaker/home?region={globals_aws.aws_twinmaker_client.meta.region_name}#/workspaces/{workspace_name}/entities/{entity_id}/components/{component_name}"

def link_to_grafana_workspace(workspace_id):
  return f"https://console.aws.amazon.com/grafana/home?region={globals.config_credentials_aws['aws_region']}#/workspaces/{workspace_id}"

def link_to_step_function(sf_arn):
  import urllib.parse
  encoded_arn = urllib.parse.quote(sf_arn, safe='')
  return f"https://console.aws.amazon.com/states/home?region={globals.config_credentials_aws['aws_region']}#/statemachines/view/{encoded_arn}?type=standard"

def get_lambda_arn_by_name(function_name: str):
    response = globals_aws.aws_lambda_client.get_function(FunctionName=function_name)
    return response["Configuration"]["FunctionArn"]

def get_api_id_by_name(api_name):
  paginator = globals_aws.aws_apigateway_client.get_paginator('get_apis')

  for page in paginator.paginate():
    for api in page["Items"]:
      if api["Name"] == api_name:
        return api["ApiId"]

  return None

def get_api_route_id_by_key(route_key):
  api_id = get_api_id_by_name(globals.api_name())
  paginator = globals_aws.aws_apigateway_client.get_paginator("get_routes")

  for page in paginator.paginate(ApiId=api_id):
    for route in page["Items"]:
      if route["RouteKey"] == route_key:
        return route["RouteId"]

  return None

def get_api_integration_id_by_uri(integration_uri):
    api_id = get_api_id_by_name(globals.api_name())
    paginator = globals_aws.aws_apigateway_client.get_paginator("get_integrations")

    for page in paginator.paginate(ApiId=api_id):
      for integration in page["Items"]:
        if integration.get("IntegrationUri") == integration_uri:
          return integration["IntegrationId"]

    return None

def link_to_api(api_id):
  return f"https://console.aws.amazon.com/apigateway/home?region={globals_aws.aws_events_client.meta.region_name}#/apis/{api_id}"

def link_to_api_integration(api_id, integration_id):
  return f"https://console.aws.amazon.com/apigateway/home?region={globals_aws.aws_events_client.meta.region_name}#/apis/{api_id}/integrations/{integration_id}"

def link_to_api_route(api_id, route_id):
  return f"https://console.aws.amazon.com/apigateway/home?region={globals_aws.aws_events_client.meta.region_name}#/apis/{api_id}/routes/{route_id}"
