"""
AWS resource naming conventions.

This module provides functions to generate consistent, namespaced resource
names for all AWS resources.

Naming Convention:
    All resources follow the pattern: {twin_name}-{resource_type}[-{suffix}]
    
    Examples:
        - my-twin-dispatcher (Lambda function)
        - my-twin-hot-iot-data (DynamoDB table)
        - my-twin-sensor-001-processor (device-specific Lambda)

Design Decision:
    Functions take twin_name as a parameter managed by the provider.
    This makes testing easier and dependencies explicit.

Usage:
    from providers.aws.naming import AWSNaming
    
    naming = AWSNaming("my-twin")
    role_name = naming.dispatcher_iam_role()  # "my-twin-dispatcher"
"""

from typing import Optional


class AWSNaming:
    """
    Generates consistent AWS resource names for a digital twin.
    
    All resource names are prefixed with the digital twin name to create
    isolated namespaces. This enables multiple twins to coexist in the
    same AWS account without conflicts.
    
    Attributes:
        twin_name: The digital twin name prefix for all resources
    """
    
    def __init__(self, twin_name: str):
        """
        Initialize naming with the digital twin name.
        
        Args:
            twin_name: The digital twin name (e.g., "factory-twin")
        """
        self._twin_name = twin_name
    
    @property
    def twin_name(self) -> str:
        """Get the digital twin name."""
        return self._twin_name
    
    # ==========================================
    # Layer 1: Data Acquisition (IoT)
    # ==========================================
    
    def dispatcher_iam_role(self) -> str:
        """IAM role name for the dispatcher Lambda."""
        return f"{self._twin_name}-dispatcher"
    
    def dispatcher_lambda_function(self) -> str:
        """Lambda function name for the dispatcher."""
        return f"{self._twin_name}-dispatcher"
    
    def dispatcher_iot_rule(self) -> str:
        """
        IoT rule name for triggering the dispatcher.
        
        Note: IoT rule names cannot contain hyphens, so we replace with underscores.
        """
        return f"{self._twin_name}-trigger-dispatcher".replace("-", "_")
    
    def connector_lambda_function(self, device_id: str) -> str:
        """Lambda function name for a device's connector (multi-cloud)."""
        return f"{self._twin_name}-{device_id}-connector"
    
    def ingestion_lambda_function(self) -> str:
        """Lambda function name for the ingestion function (multi-cloud)."""
        return f"{self._twin_name}-ingestion"
    
    def ingestion_iam_role(self) -> str:
        """IAM role name for the ingestion Lambda (multi-cloud)."""
        return f"{self._twin_name}-ingestion"
    
    # ==========================================
    # Layer 2: Data Processing
    # ==========================================
    
    def persister_iam_role(self) -> str:
        """IAM role name for the persister Lambda."""
        return f"{self._twin_name}-persister"
    
    def persister_lambda_function(self) -> str:
        """Lambda function name for the persister."""
        return f"{self._twin_name}-persister"
    
    def event_checker_iam_role(self) -> str:
        """IAM role name for the event checker Lambda."""
        return f"{self._twin_name}-event-checker"
    
    def event_checker_lambda_function(self) -> str:
        """Lambda function name for the event checker."""
        return f"{self._twin_name}-event-checker"
    
    def lambda_chain_iam_role(self) -> str:
        """IAM role name for the Step Function state machine."""
        return f"{self._twin_name}-lambda-chain"
    
    def lambda_chain_step_function(self) -> str:
        """Step Function state machine name."""
        return f"{self._twin_name}-lambda-chain"
    
    def event_feedback_iam_role(self) -> str:
        """IAM role name for the event feedback Lambda."""
        return f"{self._twin_name}-event-feedback"
    
    def event_feedback_lambda_function(self) -> str:
        """Lambda function name for event feedback."""
        return f"{self._twin_name}-event-feedback"
    
    # ==========================================
    # Layer 3: Storage
    # ==========================================
    
    def hot_dynamodb_table(self) -> str:
        """DynamoDB table name for hot storage."""
        return f"{self._twin_name}-hot-iot-data"
    
    def hot_cold_mover_iam_role(self) -> str:
        """IAM role name for the hot-to-cold mover Lambda."""
        return f"{self._twin_name}-hot-to-cold-mover"
    
    def hot_cold_mover_lambda_function(self) -> str:
        """Lambda function name for the hot-to-cold mover."""
        return f"{self._twin_name}-hot-to-cold-mover"
    
    def hot_cold_mover_event_rule(self) -> str:
        """EventBridge rule name for the hot-to-cold mover schedule."""
        return f"{self._twin_name}-hot-to-cold-mover"
    
    def cold_s3_bucket(self) -> str:
        """
        S3 bucket name for cold storage.
        
        Note: S3 bucket names must be lowercase.
        """
        return f"{self._twin_name}-cold-iot-data".lower()
    
    def cold_archive_mover_iam_role(self) -> str:
        """IAM role name for the cold-to-archive mover Lambda."""
        return f"{self._twin_name}-cold-to-archive-mover"
    
    def cold_archive_mover_lambda_function(self) -> str:
        """Lambda function name for the cold-to-archive mover."""
        return f"{self._twin_name}-cold-to-archive-mover"
    
    def cold_archive_mover_event_rule(self) -> str:
        """EventBridge rule name for the cold-to-archive mover schedule."""
        return f"{self._twin_name}-cold-to-archive-mover"
    
    def archive_s3_bucket(self) -> str:
        """
        S3 bucket name for archive storage.
        
        Note: S3 bucket names must be lowercase.
        """
        return f"{self._twin_name}-archive-iot-data".lower()
    
    def hot_reader_iam_role(self) -> str:
        """IAM role name for the hot reader Lambda."""
        return f"{self._twin_name}-hot-reader"
    
    def hot_reader_lambda_function(self) -> str:
        """Lambda function name for reading hot data (TwinMaker queries)."""
        return f"{self._twin_name}-hot-reader"
    
    def hot_reader_last_entry_iam_role(self) -> str:
        """IAM role name for the last entry reader Lambda."""
        return f"{self._twin_name}-hot-reader-last-entry"
    
    def hot_reader_last_entry_lambda_function(self) -> str:
        """Lambda function name for reading last entry."""
        return f"{self._twin_name}-hot-reader-last-entry"
    
    def writer_lambda_function(self) -> str:
        """Lambda function name for the writer (multi-cloud)."""
        return f"{self._twin_name}-writer"
    
    def writer_iam_role(self) -> str:
        """IAM role name for the writer Lambda (multi-cloud)."""
        return f"{self._twin_name}-writer"
    
    def api_gateway(self) -> str:
        """API Gateway name for cross-cloud access."""
        return f"{self._twin_name}-api-gateway"
    
    # ==========================================
    # Layer 4: Twin Management
    # ==========================================
    
    def twinmaker_s3_bucket(self) -> str:
        """
        S3 bucket name for TwinMaker assets.
        
        Note: S3 bucket names must be lowercase.
        """
        return f"{self._twin_name}-twinmaker".lower()
    
    def twinmaker_iam_role(self) -> str:
        """IAM role name for TwinMaker workspace."""
        return f"{self._twin_name}-twinmaker"
    
    def twinmaker_workspace(self) -> str:
        """TwinMaker workspace name."""
        return f"{self._twin_name}-twinmaker"
    
    def twinmaker_component_type(self, device_id: str) -> str:
        """TwinMaker component type ID for a device."""
        return f"{self._twin_name}-{device_id}"
    
    # ==========================================
    # Layer 5: Visualization
    # ==========================================
    
    def grafana_workspace(self) -> str:
        """Grafana workspace name."""
        return f"{self._twin_name}-grafana"
    
    def grafana_iam_role(self) -> str:
        """IAM role name for Grafana workspace."""
        return f"{self._twin_name}-grafana"
    
    # ==========================================
    # IoT Device Resources
    # ==========================================
    
    def iot_thing(self, device_id: str) -> str:
        """IoT Thing name for a device."""
        return f"{self._twin_name}-{device_id}"
    
    def iot_thing_policy(self, device_id: str) -> str:
        """IoT policy name for a device."""
        return f"{self._twin_name}-{device_id}"
    
    def processor_iam_role(self, device_id: str) -> str:
        """IAM role name for a device's processor Lambda."""
        return f"{self._twin_name}-{device_id}-processor"
    
    def processor_lambda_function(self, device_id: str) -> str:
        """Lambda function name for a device's processor."""
        return f"{self._twin_name}-{device_id}-processor"


# ==========================================
# Helper function for backward compatibility
# ==========================================

def get_naming(twin_name: str) -> AWSNaming:
    """
    Create an AWSNaming instance for the given twin name.
    
    This is a convenience function for cases where you need
    quick access to naming without storing the instance.
    
    Args:
        twin_name: The digital twin name
    
    Returns:
        AWSNaming instance
    """
    return AWSNaming(twin_name)
