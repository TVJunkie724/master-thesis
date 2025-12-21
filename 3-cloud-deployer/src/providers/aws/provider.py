"""
AWS CloudProvider implementation.

This module implements the CloudProvider protocol for Amazon Web Services.
It manages boto3 clients, resource naming, and status checks.

Design Pattern: Abstract Factory (Provider Pattern)
    AWSProvider creates and manages a family of related AWS objects:
    - SDK clients (boto3 clients for various services)
    - Resource naming (via AWSNaming class)
    - Status checks for SDK-managed resources

Usage:
    provider = AWSProvider()
    provider.initialize_clients({
        "aws_access_key_id": "...",
        "aws_secret_access_key": "...",
        "aws_region": "eu-central-1"
    }, twin_name="my-twin")
    
    # Access clients
    lambda_client = provider.clients["lambda"]
    
    # Generate resource names
    role_name = provider.naming.dispatcher_iam_role()
    
    # Check status
    status = provider.info_l1(context)
"""

from typing import Dict, Any, TYPE_CHECKING

from src.providers.base import BaseProvider

if TYPE_CHECKING:
    from src.core.context import DeploymentContext


class AWSProvider(BaseProvider):
    """
    AWS implementation of the CloudProvider protocol.
    
    Manages AWS SDK clients, resource naming, and status checks.
    
    Attributes:
        name: Always "aws" for this provider
        clients: Dictionary of initialized boto3 clients
        naming: AWSNaming instance for resource name generation
    """
    
    name: str = "aws"
    
    def __init__(self):
        """Initialize AWS provider with empty state."""
        super().__init__()
        self._region: str = ""
        self._naming = None
    
    @property
    def region(self) -> str:
        """Get the AWS region for this provider instance."""
        return self._region
    
    @property
    def naming(self):
        """
        Get the AWSNaming instance for this provider.
        
        Returns:
            AWSNaming instance configured with this provider's twin name
        
        Raises:
            RuntimeError: If provider not initialized
        """
        if not self._naming:
            raise RuntimeError(
                "Provider not initialized. Call initialize_clients() first."
            )
        return self._naming
    
    def initialize_clients(self, credentials: dict, twin_name: str) -> None:
        """
        Initialize boto3 clients for AWS services.
        
        Args:
            credentials: AWS credentials dictionary containing:
                - aws_access_key_id: AWS access key (REQUIRED)
                - aws_secret_access_key: AWS secret key (REQUIRED)
                - aws_region: AWS region (default: "eu-central-1")
            twin_name: Digital twin name for resource naming
        
        Raises:
            ValueError: If required credentials are missing
        """
        from .clients import create_aws_clients
        from .naming import AWSNaming
        
        # Store configuration
        self._twin_name = twin_name
        self._region = credentials.get("aws_region", "eu-central-1")
        
        # Initialize naming helper
        self._naming = AWSNaming(twin_name)
        
        # Create all clients using centralized function
        self._clients = create_aws_clients(
            access_key_id=credentials.get("aws_access_key_id", ""),
            secret_access_key=credentials.get("aws_secret_access_key", ""),
            region=self._region
        )
        
        self._initialized = True
    
    def check_if_twin_exists(self) -> bool:
        """
        Check if a digital twin with the current name already exists in AWS.
        
        Uses the hot DynamoDB table as the indicator since it's created
        in L3 and is a reliable marker of an existing deployment.
        
        Returns:
            True if the twin's resources exist, False otherwise.
            
        Raises:
            RuntimeError: If clients are not initialized.
        """
        if not self._clients:
            raise RuntimeError("AWS clients not initialized. Call initialize_clients() first.")
        
        from botocore.exceptions import ClientError
        
        table_name = self.naming.hot_dynamodb_table()
        try:
            self._clients["dynamodb"].describe_table(TableName=table_name)
            return True
        except ClientError as e:
            if e.response["Error"]["Code"] == "ResourceNotFoundException":
                return False
            raise
    
    # ==========================================
    # Status Checks (Used by API)
    # ==========================================
    
    def info_l1(self, context: 'DeploymentContext') -> dict:
        """Get status of L1 IoT components."""
        from .layers.layer_1_iot import info_l1
        return info_l1(context, self)
    
    def info_l4(self, context: 'DeploymentContext') -> dict:
        """Get status of L4 TwinMaker components."""
        from .layers.layer_4_twinmaker import info_l4
        return info_l4(context, self)
    
    def info_l5(self, context: 'DeploymentContext') -> dict:
        """Get status of L5 Grafana components."""
        from .layers.layer_5_grafana import info_l5
        return info_l5(context, self)
