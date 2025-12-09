"""
AWS SDK client initialization.

This module provides client initialization for the AWSProvider class.
It provides centralized client initialization for the AWSProvider.

Design Decision:
    We return a dictionary of clients rather than individual module-level
    variables. This allows the provider to manage client lifecycle and
    enables easy testing via mocking.

Usage:
    from providers.aws.clients import create_aws_clients
    
    clients = create_aws_clients(
        access_key_id="...",
        secret_access_key="...",
        region="eu-central-1"
    )
    # clients["iam"], clients["lambda"], etc.
"""

from typing import Dict, Any
import boto3


def create_aws_clients(
    access_key_id: str,
    secret_access_key: str,
    region: str
) -> Dict[str, Any]:
    """
    Create and return all AWS boto3 clients needed for deployment.
    
    This function centralizes client creation, making it easy to:
    - Initialize all clients with consistent credentials
    - Replace with mock clients in tests
    - Add new clients in one place
    
    Args:
        access_key_id: AWS access key ID
        secret_access_key: AWS secret access key
        region: AWS region (e.g., "eu-central-1")
    
    Returns:
        Dictionary mapping service names to boto3 client instances.
        
    Client Keys:
        - iam: Identity and Access Management
        - lambda: Lambda functions
        - iot: IoT Core
        - iot_data: IoT Data Plane (for publishing messages)
        - sts: Security Token Service
        - events: EventBridge
        - dynamodb: DynamoDB
        - s3: Simple Storage Service
        - twinmaker: IoT TwinMaker
        - grafana: Managed Grafana
        - logs: CloudWatch Logs
        - apigateway: API Gateway v2 (HTTP APIs)
        - sfn: Step Functions
    """
    # Common configuration for all clients
    config = {
        "aws_access_key_id": access_key_id,
        "aws_secret_access_key": secret_access_key,
        "region_name": region,
    }
    
    return {
        # Layer 1: Data Acquisition
        "iam": boto3.client("iam", **config),
        "iot": boto3.client("iot", **config),
        "iot_data": boto3.client("iot-data", **config),
        
        # Layer 2: Processing
        "lambda": boto3.client("lambda", **config),
        "sfn": boto3.client("stepfunctions", **config),
        
        # Layer 3: Storage
        "dynamodb": boto3.client("dynamodb", **config),
        "s3": boto3.client("s3", **config),
        "events": boto3.client("events", **config),
        "apigateway": boto3.client("apigatewayv2", **config),
        
        # Layer 4: Twin Management
        "twinmaker": boto3.client("iottwinmaker", **config),
        
        # Layer 5: Visualization
        "grafana": boto3.client("grafana", **config),
        
        # Supporting
        "sts": boto3.client("sts", **config),
        "logs": boto3.client("logs", **config),
    }
