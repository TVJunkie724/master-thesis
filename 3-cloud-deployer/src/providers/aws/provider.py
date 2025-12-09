"""
AWS CloudProvider implementation.

This module implements the CloudProvider protocol for Amazon Web Services.
It manages boto3 clients and provides resource naming conventions.

Design Pattern: Abstract Factory (Provider Pattern)
    AWSProvider creates and manages a family of related AWS objects:
    - SDK clients (boto3 clients for various services)
    - Resource naming (via AWSNaming class)
    - Deployer strategy (AWSDeployerStrategy)

Integration with Existing Code:
    This provider centralizes AWS client and naming management,
    providing a unified interface that follows the new pattern while
    reusing proven deployment logic.
"""

from typing import Dict, Any, TYPE_CHECKING

from providers.base import BaseProvider

if TYPE_CHECKING:
    from src.core.protocols import DeployerStrategy


class AWSProvider(BaseProvider):
    """
    AWS implementation of the CloudProvider protocol.
    
    This class manages all AWS-specific state and provides methods
    required by the CloudProvider protocol.
    
    Attributes:
        name: Always "aws" for this provider
        clients: Dictionary of initialized boto3 clients
        naming: AWSNaming instance for resource name generation
    
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
        role_name = provider.naming.dispatcher_iam_role()
        
        # Get deployment strategy
        strategy = provider.get_deployer_strategy()
        strategy.deploy_l1(context)
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
        """
        # Lazy import to avoid issues when AWS SDK not installed
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
    
    def get_resource_name(self, resource_type: str, suffix: str = "") -> str:
        """
        Generate an AWS resource name with twin prefix.
        
        Note: For specific resource names, prefer using self.naming which
        provides type-safe methods like naming.dispatcher_iam_role().
        
        AWS has specific naming constraints for different resource types:
        - IAM: alphanumeric plus +=,.@-_ (max 64 chars)
        - Lambda: alphanumeric plus -_ (max 64 chars)
        - DynamoDB: alphanumeric plus .-_ (max 255 chars)
        - S3: lowercase alphanumeric plus .- (max 63 chars)
        
        This method generates names that are valid for most services.
        For S3, use naming.cold_s3_bucket() etc. which lowercase the name.
        
        Args:
            resource_type: Type of resource (e.g., "dispatcher", "hot-table")
            suffix: Optional suffix (e.g., device ID)
        
        Returns:
            Formatted name like "{twin_name}-{resource_type}[-{suffix}]"
        """
        if suffix:
            return f"{self.twin_name}-{resource_type}-{suffix}"
        return f"{self.twin_name}-{resource_type}"
    
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
