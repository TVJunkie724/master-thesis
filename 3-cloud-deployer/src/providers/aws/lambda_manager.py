"""
AWS Lambda Manager - Lambda Function Operations.

This module provides utilities for updating, invoking, and fetching logs
from Lambda functions.
"""

import json
import os
from typing import TYPE_CHECKING, Optional, List
import constants as CONSTANTS
from logger import logger

if TYPE_CHECKING:
    from src.providers.aws.provider import AWSProvider




def update_function(
    local_function_name: str,
    environment: dict = None,
    provider: 'AWSProvider' = None,
    project_path: str = None,
    iot_devices: list = None
) -> None:
    """Update a Lambda function's code and optionally its environment.
    
    Args:
        local_function_name: Name of the local function directory
        environment: Optional environment variables dict
        provider: AWSProvider instance.
        project_path: Path to project directory.
        iot_devices: List of IoT device configs for processor updates.
    """
    import src.util as util
    
    if provider is None:
        raise ValueError("provider is required")
    if project_path is None:
        raise ValueError("project_path is required")

    lambda_client = provider.clients["lambda"]
    digital_twin_name = provider.naming.twin_name
    
    lambda_dir = os.path.join(project_path, CONSTANTS.LAMBDA_FUNCTIONS_DIR_NAME, local_function_name)
    
    if local_function_name == "default-processor":
        compiled_function = util.compile_lambda_function(lambda_dir)
        
        for iot_device in (iot_devices or []):
            function_name = f"{digital_twin_name}-{iot_device['id']}-processor"
            
            lambda_client.update_function_code(
                FunctionName=function_name,
                ZipFile=compiled_function,
                Publish=True
            )
            
            waiter = lambda_client.get_waiter("function_updated")
            waiter.wait(FunctionName=function_name)
            
            if environment is not None:
                lambda_client.update_function_configuration(
                    FunctionName=function_name,
                    Environment=environment
                )
            
            logger.info(f"Updated Lambda Function: {function_name}")
        return
    
    function_name = f"{digital_twin_name}-{local_function_name}"
    
    lambda_client.update_function_code(
        FunctionName=function_name,
        ZipFile=util.compile_lambda_function(lambda_dir),
        Publish=True
    )
    
    waiter = lambda_client.get_waiter("function_updated")
    waiter.wait(FunctionName=function_name)
    
    if environment is not None:
        lambda_client.update_function_configuration(
            FunctionName=function_name,
            Environment=environment
        )
    
    logger.info(f"Updated Lambda Function: {function_name}")


def fetch_logs(
    local_function_name: str,
    n: int = 10,
    filter_system_logs: bool = True,
    provider: 'AWSProvider' = None
) -> List[str]:
    """Fetch recent logs from a Lambda function.
    
    Args:
        local_function_name: Name of the local function
        n: Number of log entries to fetch
        filter_system_logs: Whether to filter out AWS system log entries
        provider: AWSProvider instance (required)
        
    Returns:
        List of log messages
    """
    if provider is None:
        raise ValueError("provider is required")

    logs_client = provider.clients["logs"]
    digital_twin_name = provider.naming.twin_name
    
    function_name = f"{digital_twin_name}-{local_function_name}"
    log_group = f"/aws/lambda/{function_name}"
    
    streams = logs_client.describe_log_streams(
        logGroupName=log_group,
        orderBy="LastEventTime",
        descending=True,
        limit=1
    )
    latest_stream = streams["logStreams"][0]["logStreamName"]
    
    events = logs_client.get_log_events(
        logGroupName=log_group,
        logStreamName=latest_stream,
        limit=n,
        startFromHead=False
    )
    messages = [e["message"] for e in events["events"]][-n:]
    
    if not filter_system_logs:
        return messages
    else:
        system_prefixes = ("INIT_START", "START", "END", "REPORT")
        return [msg for msg in messages if not msg.startswith(system_prefixes)]


def invoke_function(
    local_function_name: str,
    payload: dict = None,
    sync: bool = True,
    provider: 'AWSProvider' = None
) -> Optional[dict]:
    """Invoke a Lambda function.
    
    Args:
        local_function_name: Name of the local function
        payload: Payload to send to the function
        sync: Whether to wait for response (RequestResponse) or fire-and-forget (Event)
        provider: AWSProvider instance (required)
        
    Returns:
        Response payload if sync=True, None otherwise
    """
    if payload is None:
        payload = {}
    
    if provider is None:
        raise ValueError("provider is required")

    lambda_client = provider.clients["lambda"]
    digital_twin_name = provider.naming.twin_name
    
    function_name = f"{digital_twin_name}-{local_function_name}"
    
    response = lambda_client.invoke(
        FunctionName=function_name,
        InvocationType="RequestResponse" if sync else "Event",
        Payload=json.dumps(payload),
    )
    
    if sync:
        response_payload = response["Payload"].read()
        result = json.loads(response_payload)
        logger.info(f"Lambda response: {result}")
        return result
    else:
        logger.info("Lambda invoked.")
        return None
