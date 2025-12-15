"""
Strategy Pattern: Cloud Provider Calculator Protocol
=====================================================
Defines the interface that all cloud provider cost calculators must implement.

This module provides:
- CloudProviderCalculator: Protocol (interface) for provider implementations
- LayerResult: TypedDict for consistent return structures
- CalculationParams: TypedDict for input parameters

Usage:
    from backend.calculation.base import CloudProviderCalculator
    
    class AWSCalculator(CloudProviderCalculator):
        name = "aws"
        ...
"""

from typing import Protocol, Dict, Any, TypedDict, runtime_checkable


# =============================================================================
# TypedDicts for Input/Output Consistency
# =============================================================================

class CalculationParams(TypedDict, total=False):
    """
    Input parameters for cost calculations.
    
    All cloud-specific calculators receive this same params structure,
    ensuring consistent inputs across providers.
    """
    # Core Parameters
    numberOfDevices: int
    deviceSendingIntervalInMinutes: float
    averageSizeOfMessageInKb: float
    
    # Storage Duration (months)
    hotStorageDurationInMonths: int
    coolStorageDurationInMonths: int
    archiveStorageDurationInMonths: int
    
    # Layer 4 (Twin Management)
    entityCount: int
    average3DModelSizeInMB: float
    
    # Layer 5 (Visualization)
    amountOfActiveEditors: int
    amountOfActiveViewers: int
    dashboardRefreshesPerHour: int
    dashboardActiveHoursPerDay: int
    
    # Optional Processing Features
    useEventChecking: bool
    triggerNotificationWorkflow: bool
    returnFeedbackToDevice: bool
    integrateErrorHandling: bool
    orchestrationActionsPerMessage: int
    eventsPerMessage: int
    apiCallsPerDashboardRefresh: int
    
    # GCP Self-Hosted Options
    allowGcpSelfHostedL4: bool
    allowGcpSelfHostedL5: bool


class LayerResult(TypedDict, total=False):
    """
    Standard return structure for layer cost calculations.
    
    All calculator methods return this structure, ensuring consistent
    outputs that can be processed generically by engine.py.
    """
    provider: str               # "AWS", "Azure", "GCP"
    totalMonthlyCost: float     # Total monthly cost in USD
    
    # Optional fields (layer-dependent)
    dataSizeInGB: float         # Data volume processed
    totalMessagesPerMonth: float  # Message count
    
    # Cost breakdown fields (present when applicable)
    entityCost: float
    apiCost: float
    storageCost: float
    queryCost: float
    glueCodeCost: float


# =============================================================================
# Cloud Provider Calculator Protocol
# =============================================================================

@runtime_checkable
class CloudProviderCalculator(Protocol):
    """
    Strategy interface for cloud cost calculations.
    
    Each cloud provider (AWS, Azure, GCP) implements this protocol.
    The calculation engine uses this interface to iterate over providers
    generically, without knowing provider-specific details.
    
    Note: Each provider's implementation accesses its OWN pricing keys.
    For example:
        - AWSCalculator reads pricing["aws"]["iotCore"]
        - AzureCalculator reads pricing["azure"]["iotHub"]
        - GCPCalculator reads pricing["gcp"]["iot"]
    
    The protocol unifies METHOD SIGNATURES, not the underlying pricing structure.
    """
    
    name: str  # Provider identifier: "aws", "azure", or "gcp"
    
    # -------------------------------------------------------------------------
    # Layer 1: Data Acquisition (IoT Ingestion)
    # -------------------------------------------------------------------------
    
    def calculate_data_acquisition(
        self,
        params: CalculationParams,
        pricing: Dict[str, Any]
    ) -> LayerResult:
        """
        Calculate IoT ingestion costs.
        
        Services:
            - AWS: IoT Core
            - Azure: IoT Hub
            - GCP: Cloud IoT/Pub/Sub
        """
        ...
    
    # -------------------------------------------------------------------------
    # Layer 2: Data Processing (Serverless Compute)
    # -------------------------------------------------------------------------
    
    def calculate_data_processing(
        self,
        params: CalculationParams,
        pricing: Dict[str, Any]
    ) -> LayerResult:
        """
        Calculate serverless compute costs.
        
        Services:
            - AWS: Lambda + Step Functions + EventBridge
            - Azure: Functions + Logic Apps + Event Grid
            - GCP: Cloud Functions + Workflows + Cloud Scheduler
        """
        ...
    
    # -------------------------------------------------------------------------
    # Layer 3: Data Storage (Hot/Cool/Archive)
    # -------------------------------------------------------------------------
    
    def calculate_storage_hot(
        self,
        params: CalculationParams,
        pricing: Dict[str, Any],
        data_size_in_gb: float,
        total_messages_per_month: float
    ) -> LayerResult:
        """
        Calculate hot storage costs (fast access, high cost).
        
        Services:
            - AWS: DynamoDB
            - Azure: Cosmos DB
            - GCP: Firestore
        """
        ...
    
    def calculate_storage_cool(
        self,
        params: CalculationParams,
        pricing: Dict[str, Any],
        data_size_in_gb: float
    ) -> LayerResult:
        """
        Calculate cool storage costs (infrequent access).
        
        Services:
            - AWS: S3 Infrequent Access
            - Azure: Blob Cool
            - GCP: Cloud Storage Nearline
        """
        ...
    
    def calculate_storage_archive(
        self,
        params: CalculationParams,
        pricing: Dict[str, Any],
        data_size_in_gb: float
    ) -> LayerResult:
        """
        Calculate archive storage costs (long-term, cold).
        
        Services:
            - AWS: S3 Glacier Deep Archive
            - Azure: Blob Archive
            - GCP: Cloud Storage Coldline/Archive
        """
        ...
    
    # -------------------------------------------------------------------------
    # Layer 4: Twin Management
    # -------------------------------------------------------------------------
    
    def calculate_twin_management(
        self,
        params: CalculationParams,
        pricing: Dict[str, Any]
    ) -> LayerResult:
        """
        Calculate Digital Twin management costs.
        
        Services:
            - AWS: IoT TwinMaker
            - Azure: Azure Digital Twins
            - GCP: Self-hosted (Compute Engine + Cloud Storage)
        """
        ...
    
    # -------------------------------------------------------------------------
    # Layer 5: Visualization
    # -------------------------------------------------------------------------
    
    def calculate_visualization(
        self,
        params: CalculationParams,
        pricing: Dict[str, Any]
    ) -> LayerResult:
        """
        Calculate visualization/dashboard costs.
        
        Services:
            - AWS: Amazon Managed Grafana
            - Azure: Azure Managed Grafana
            - GCP: Self-hosted Grafana (Compute Engine + Disk)
        """
        ...
    
    # -------------------------------------------------------------------------
    # Cross-Cloud Glue Functions
    # -------------------------------------------------------------------------
    
    def calculate_connector_function_cost(
        self,
        number_of_messages: float,
        pricing: Dict[str, Any]
    ) -> float:
        """Calculate cost of connector function (cross-cloud data forwarding)."""
        ...
    
    def calculate_ingestion_function_cost(
        self,
        number_of_messages: float,
        pricing: Dict[str, Any]
    ) -> float:
        """Calculate cost of ingestion function (receiving cross-cloud data)."""
        ...
    
    def calculate_reader_function_cost(
        self,
        number_of_requests: float,
        pricing: Dict[str, Any]
    ) -> float:
        """Calculate cost of reader function (L4 data retrieval)."""
        ...
    
    def calculate_api_gateway_cost(
        self,
        number_of_requests: float,
        pricing: Dict[str, Any]
    ) -> float:
        """Calculate API Gateway cost (L3->L4 interface)."""
        ...


# =============================================================================
# Registry of Calculator Implementations
# =============================================================================

# Import calculator implementations here once they exist
# from backend.calculation.aws import AWSCalculator
# from backend.calculation.azure import AzureCalculator
# from backend.calculation.gcp import GCPCalculator

# CALCULATORS: Dict[str, CloudProviderCalculator] = {
#     "aws": AWSCalculator(),
#     "azure": AzureCalculator(),
#     "gcp": GCPCalculator(),
# }

def get_calculators():
    """
    Get all registered calculator instances.
    
    Returns:
        List of CloudProviderCalculator implementations.
    
    Note: Import is done inside function to avoid circular imports.
    """
    from backend.calculation.aws import AWSCalculator
    from backend.calculation.azure import AzureCalculator
    from backend.calculation.gcp import GCPCalculator
    
    return [AWSCalculator(), AzureCalculator(), GCPCalculator()]
