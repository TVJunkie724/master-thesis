"""
AWS Utility Functions.

This module provides utility functions for AWS operations including:
- Lambda compilation
- Resource existence checks
- Console link generation
- TwinMaker entity/component creation

Functions now support optional provider parameter for new pattern,
with backward-compatible fallback to globals_aws.
"""

import warnings
from botocore.exceptions import ClientError
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from providers.aws.provider import AWSProvider



def compile_lambda_function(relative_folder_path, project_path: str = None):
    """Compile a Lambda function from a relative folder path.
    
    Args:
        relative_folder_path: Relative path to Lambda function folder
        project_path: Optional project path for resolution
    """
    import src.util as util
    zip_path = util.zip_directory(relative_folder_path, project_path=project_path)

    with open(zip_path, "rb") as f:
        zip_code = f.read()

    return zip_code


def iot_rule_exists(rule_name, iot_client=None):
    """Check if an IoT rule exists.
    
    Args:
        rule_name: Name of the IoT rule
        iot_client: Optional boto3 IoT client. If None, uses globals_aws.aws_iot_client
    """
    if iot_client is None:
        raise ValueError("iot_client is required")
        
    paginator = iot_client.get_paginator('list_topic_rules')
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
        raise ValueError("s3_client is required")
     
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
        raise ValueError("grafana_client is required")
    
    paginator = grafana_client.get_paginator("list_workspaces")

    for page in paginator.paginate():
        for workspace in page["workspaces"]:
            if workspace["name"] == workspace_name:
                return workspace.get("id") or workspace.get("workspaceId")

    error_response = {
        "Error": {
            "Code": "ResourceNotFoundException",
            "Message": "The requested resource was not found."
        }
    }

    operation_name = "get_grafana_workspace_id_by_name"

    raise ClientError(error_response, operation_name)


def create_twinmaker_entity(entity_info, parent_info=None, workspace_name: str = None, 
                            twinmaker_client=None, config: dict = None):
    """Create a TwinMaker entity.
    
    Args:
        entity_info: Entity information dict
        parent_info: Optional parent entity info
        workspace_name: TwinMaker workspace name. If None, uses globals.
        twinmaker_client: boto3 TwinMaker client. If None, uses globals_aws.
        config: Configuration dict. If None, uses globals.
    """
    if workspace_name is None:
        raise ValueError("workspace_name is required")
    if twinmaker_client is None:
        raise ValueError("twinmaker_client is required")
    if config is None:
        raise ValueError("config is required")
        
    create_entity_params = {
        "workspaceId": workspace_name,
        "entityName": entity_info["id"],
        "entityId": entity_info["id"],
    }

    if parent_info is not None:
        create_entity_params["parentEntityId"] = parent_info["id"]

    response = twinmaker_client.create_entity(**create_entity_params)

    print(f"Created IoT TwinMaker Entity: {response['entityId']}")

    for child in entity_info.get("children", []):
        if child["type"] == "entity":
            create_twinmaker_entity(child, entity_info, workspace_name, twinmaker_client, config)
        elif child["type"] == "component":
            create_twinmaker_component(child, entity_info, workspace_name, twinmaker_client, config)


def create_twinmaker_component(component_info, parent_info, workspace_name: str = None,
                               twinmaker_client=None, config: dict = None):
    """Create a TwinMaker component.
    
    Args:
        component_info: Component information dict
        parent_info: Parent entity info
        workspace_name: TwinMaker workspace name. If None, uses globals.
        twinmaker_client: boto3 TwinMaker client. If None, uses globals_aws.
        config: Configuration dict. If None, uses globals.
    """
    if workspace_name is None:
        raise ValueError("workspace_name is required")
    if twinmaker_client is None:
        raise ValueError("twinmaker_client is required")
    if config is None:
        raise ValueError("config is required")
        
    if "componentTypeId" in component_info:
        component_type_id = component_info["componentTypeId"]
    else:
        component_type_id = f"{config['digital_twin_name']}-{component_info['iotDeviceId']}"

    twinmaker_client.update_entity(
        workspaceId=workspace_name,
        entityId=parent_info["id"],
        componentUpdates={
            component_info["name"]: {
                "updateType": "CREATE",
                "componentTypeId": component_type_id
            }
        }
    )

    print(f"Created IoT TwinMaker Component: {component_info['name']}")


# ======================
# Console Link Functions
# ======================
# These accept optional client/region for new pattern

def link_to_iam_role(role_name, region: str = None):
    if region is None:
        raise ValueError("region is required")
    return f"https://console.aws.amazon.com/iam/home?region={region}#/roles/{role_name}"


def link_to_lambda_function(function_name, region: str = None):
    if region is None:
        raise ValueError("region is required")
    return f"https://console.aws.amazon.com/lambda/home?region={region}#/functions/{function_name}"


def link_to_iot_rule(rule_name, region: str = None):
    if region is None:
        raise ValueError("region is required")
    return f"https://console.aws.amazon.com/iot/home?region={region}#/rule/{rule_name}"


def link_to_iot_thing(thing_name, region: str = None):
    if region is None:
        raise ValueError("region is required")
    return f"https://console.aws.amazon.com/iot/home?region={region}#/thing/{thing_name}"


def link_to_dynamodb_table(table_name, region: str = None):
    if region is None:
        raise ValueError("region is required")
    return f"https://console.aws.amazon.com/dynamodbv2/home?region={region}#table?name={table_name}"


def link_to_event_rule(rule_name, region: str = None):
    if region is None:
        raise ValueError("region is required")
    return f"https://console.aws.amazon.com/events/home?region={region}#/eventbus/default/rules/{rule_name}"


def link_to_s3_bucket(bucket_name):
    return f"https://console.aws.amazon.com/s3/buckets/{bucket_name}"


def link_to_twinmaker_workspace(workspace_name, region: str = None):
    if region is None:
        raise ValueError("region is required")
    return f"https://console.aws.amazon.com/iottwinmaker/home?region={region}#/workspaces/{workspace_name}"


def link_to_twinmaker_component_type(workspace_name, component_type_id, region: str = None):
    if region is None:
        raise ValueError("region is required")
    return f"https://console.aws.amazon.com/iottwinmaker/home?region={region}#/workspaces/{workspace_name}/component-types/{component_type_id}"


def link_to_twinmaker_entity(workspace_name, entity_id, region: str = None):
    if region is None:
        raise ValueError("region is required")
    return f"https://console.aws.amazon.com/iottwinmaker/home?region={region}#/workspaces/{workspace_name}/entities/{entity_id}"


def link_to_twinmaker_component(workspace_name, entity_id, component_name, region: str = None):
    if region is None:
        raise ValueError("region is required")
    return f"https://console.aws.amazon.com/iottwinmaker/home?region={region}#/workspaces/{workspace_name}/entities/{entity_id}/components/{component_name}"


def link_to_grafana_workspace(workspace_id, region: str = None):
    if region is None:
        raise ValueError("region is required")
    return f"https://console.aws.amazon.com/grafana/home?region={region}#/workspaces/{workspace_id}"


def link_to_step_function(sf_arn, region: str = None):
    import urllib.parse
    if region is None:
        raise ValueError("region is required")
    encoded_arn = urllib.parse.quote(sf_arn, safe='')
    return f"https://console.aws.amazon.com/states/home?region={region}#/statemachines/view/{encoded_arn}?type=standard"


def get_lambda_arn_by_name(function_name: str, lambda_client=None):
    """Get Lambda ARN by function name.
    
    Args:
        function_name: Name of the Lambda function
        lambda_client: Optional boto3 Lambda client
    """
    if lambda_client is None:
        raise ValueError("lambda_client is required")
    response = lambda_client.get_function(FunctionName=function_name)
    return response["Configuration"]["FunctionArn"]


def get_api_id_by_name(api_name, apigateway_client=None):
    """Get API Gateway ID by name.
    
    Args:
        api_name: Name of the API
        apigateway_client: Optional boto3 API Gateway client
    """
    if apigateway_client is None:
        raise ValueError("apigateway_client is required")
        
    paginator = apigateway_client.get_paginator('get_apis')

    for page in paginator.paginate():
        for api in page["Items"]:
            if api["Name"] == api_name:
                return api["ApiId"]

    return None


def get_api_route_id_by_key(route_key, api_name: str = None, apigateway_client=None):
    """Get API route ID by route key.
    
    Args:
        route_key: Route key to find
        api_name: API name. If None, uses globals.api_name()
        apigateway_client: Optional API Gateway client
    """
    if apigateway_client is None:
        raise ValueError("apigateway_client is required")
    if api_name is None:
        raise ValueError("api_name is required")
        
    api_id = get_api_id_by_name(api_name, apigateway_client)
    paginator = apigateway_client.get_paginator("get_routes")

    for page in paginator.paginate(ApiId=api_id):
        for route in page["Items"]:
            if route["RouteKey"] == route_key:
                return route["RouteId"]

    return None


def get_api_integration_id_by_uri(integration_uri, api_name: str = None, apigateway_client=None):
    """Get API integration ID by URI.
    
    Args:
        integration_uri: Integration URI to find
        api_name: API name. If None, uses globals.api_name()
        apigateway_client: Optional API Gateway client
    """
    if apigateway_client is None:
        raise ValueError("apigateway_client is required")
    if api_name is None:
        raise ValueError("api_name is required")
        
    api_id = get_api_id_by_name(api_name, apigateway_client)
    paginator = apigateway_client.get_paginator("get_integrations")

    for page in paginator.paginate(ApiId=api_id):
        for integration in page["Items"]:
            if integration.get("IntegrationUri") == integration_uri:
                return integration["IntegrationId"]

    return None


def link_to_api(api_id, region: str = None):
    if region is None:
        raise ValueError("region is required")
    return f"https://console.aws.amazon.com/apigateway/home?region={region}#/apis/{api_id}"


def link_to_api_integration(api_id, integration_id, region: str = None):
    if region is None:
        raise ValueError("region is required")
    return f"https://console.aws.amazon.com/apigateway/home?region={region}#/apis/{api_id}/integrations/{integration_id}"


def link_to_api_route(api_id, route_id, region: str = None):
    if region is None:
        raise ValueError("region is required")
    return f"https://console.aws.amazon.com/apigateway/home?region={region}#/apis/{api_id}/routes/{route_id}"
