"""
AWS CloudProvider implementation.

This module implements the CloudProvider protocol for Amazon Web Services.
It manages boto3 clients and provides resource naming conventions.

Design Pattern: Abstract Factory (Provider Pattern)
    AWSProvider creates and manages a family of related AWS objects:
    - SDK clients (boto3 clients for various services)
    - Resource naming functions
    - Deployer strategy (AWSDeployerStrategy)

Integration with Existing Code:
    This provider wraps the existing code in src/aws/globals_aws.py,
    providing a unified interface that follows the new pattern while
    reusing proven deployment logic.
"""

from typing import Dict, Any, TYPE_CHECKING

from providers.base import BaseProvider, generate_resource_name

if TYPE_CHECKING:
    from core.protocols import DeployerStrategy


class AWSProvider(BaseProvider):
    """
    AWS implementation of the CloudProvider protocol.
    
    This class manages all AWS-specific state and provides methods
    required by the CloudProvider protocol.
    
    Attributes:
        name: Always "aws" for this provider
        clients: Dictionary of initialized boto3 clients
    
    Example Usage:
        provider = AWSProvider()
        provider.initialize_clients({
            "aws_access_key_id": "...",
            "aws_secret_access_key": "...",
            "aws_region": "eu-central-1"
        }, twin_name="my-twin")
        
        # Access clients
        lambda_client = provider.clients["lambda"]
        
        # Generate resource names
        role_name = provider.get_resource_name("dispatcher-role")
        
        # Get deployment strategy
        strategy = provider.get_deployer_strategy()
        strategy.deploy_l1(context)
    """
    
    name: str = "aws"
    
    def __init__(self):
        """Initialize AWS provider with empty state."""
        super().__init__()
        self._region: str = ""
    
    @property
    def region(self) -> str:
        """Get the AWS region for this provider instance."""
        return self._region
    
    def initialize_clients(self, credentials: dict, twin_name: str) -> None:
        """
        Initialize boto3 clients for AWS services.
        
        Creates authenticated clients for all AWS services needed by
        the deployer. Clients are cached in self._clients for reuse.
        
        Args:
            credentials: AWS credentials dictionary containing:
                - aws_access_key_id: AWS access key
                - aws_secret_access_key: AWS secret key
                - aws_region: AWS region (e.g., "eu-central-1")
            twin_name: Digital twin name for resource naming
        
        Raises:
            ConfigurationError: If required credentials are missing
            
        Note:
            This imports boto3 lazily to avoid import errors when
            AWS SDK is not installed (e.g., when only using Azure).
        """
        import boto3
        
        # Store configuration
        self._twin_name = twin_name
        self._region = credentials.get("aws_region", "eu-central-1")
        
        # Common client configuration
        client_config = {
            "aws_access_key_id": credentials.get("aws_access_key_id"),
            "aws_secret_access_key": credentials.get("aws_secret_access_key"),
            "region_name": self._region,
        }
        
        # Initialize all required AWS clients
        # These match the clients created in src/aws/globals_aws.py
        self._clients = {
            "iam": boto3.client("iam", **client_config),
            "lambda": boto3.client("lambda", **client_config),
            "iot": boto3.client("iot", **client_config),
            "dynamodb": boto3.client("dynamodb", **client_config),
            "s3": boto3.client("s3", **client_config),
            "events": boto3.client("events", **client_config),
            "sfn": boto3.client("stepfunctions", **client_config),
            "twinmaker": boto3.client("iottwinmaker", **client_config),
            "grafana": boto3.client("grafana", **client_config),
            "apigateway": boto3.client("apigatewayv2", **client_config),
            "sts": boto3.client("sts", **client_config),
        }
        
        self._initialized = True
    
    def get_resource_name(self, resource_type: str, suffix: str = "") -> str:
        """
        Generate an AWS resource name with twin prefix.
        
        AWS has specific naming constraints for different resource types:
        - IAM: alphanumeric plus +=,.@-_ (max 64 chars)
        - Lambda: alphanumeric plus -_ (max 64 chars)
        - DynamoDB: alphanumeric plus .-_ (max 255 chars)
        - S3: lowercase alphanumeric plus .- (max 63 chars)
        
        This method generates names that are valid for most services.
        For S3, use get_s3_bucket_name() which lowercases the name.
        
        Args:
            resource_type: Type of resource (e.g., "dispatcher", "hot-table")
            suffix: Optional suffix (e.g., device ID)
        
        Returns:
            Formatted name like "{twin_name}-{resource_type}[-{suffix}]"
        """
        return generate_resource_name(self.twin_name, resource_type, suffix)
    
    def get_s3_bucket_name(self, suffix: str = "") -> str:
        """
        Generate an S3 bucket name (must be lowercase).
        
        S3 bucket names have stricter requirements:
        - Must be lowercase
        - Can contain only a-z, 0-9, . and -
        - 3-63 characters
        - Cannot start/end with . or -
        
        Args:
            suffix: Bucket type suffix (e.g., "cold", "archive")
        
        Returns:
            Lowercase bucket name
        """
        if suffix:
            return f"{self.twin_name}-{suffix}".lower()
        return self.twin_name.lower()
    
    def get_deployer_strategy(self) -> 'DeployerStrategy':
        """
        Return the AWS deployment strategy.
        
        Creates an AWSDeployerStrategy instance that uses this provider's
        clients and naming functions to deploy resources.
        
        Returns:
            AWSDeployerStrategy instance
        
        Note:
            Strategy is created fresh each time rather than cached,
            allowing for potential configuration changes between calls.
        """
        from .deployer_strategy import AWSDeployerStrategy
        return AWSDeployerStrategy(self)
