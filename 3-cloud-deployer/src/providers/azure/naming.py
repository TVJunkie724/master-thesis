"""
Azure resource naming conventions.

This module provides functions to generate consistent, namespaced resource
names for all Azure resources following Azure naming restrictions.

Naming Convention:
    - Resource Group: rg-{twin_name}
    - Storage Account: {twin_name}storage (max 24 chars, no hyphens, lowercase)
    - Managed Identity: {twin_name}-identity
    - Function App: {twin_name}-l0-functions
    - Cosmos DB: {twin_name}-cosmos
    
    All resources follow Azure naming restrictions:
    - Storage accounts: 3-24 chars, lowercase alphanumeric only
    - Function Apps: 2-60 chars, alphanumeric and hyphens
    - Resource Groups: 1-90 chars, alphanumeric, underscores, hyphens, periods

Design Decision:
    Mirrors the AWS naming pattern with an AzureNaming class that takes
    twin_name and provides consistent resource names.

Usage:
    from providers.azure.naming import AzureNaming
    
    naming = AzureNaming("my-twin")
    rg_name = naming.resource_group()  # "rg-my-twin"
"""

from typing import Optional
import re


class AzureNaming:
    """
    Generates consistent Azure resource names for a digital twin.
    
    All resource names are prefixed/suffixed with the digital twin name to create
    isolated namespaces. This enables multiple twins to coexist in the
    same Azure subscription without conflicts.
    
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
        # Pre-compute sanitized version for storage accounts (no hyphens, lowercase)
        self._storage_safe_name = re.sub(r'[^a-z0-9]', '', twin_name.lower())
    
    @property
    def twin_name(self) -> str:
        """Get the digital twin name."""
        return self._twin_name
    
    # ==========================================
    # Setup Layer: Foundational Resources
    # ==========================================
    
    def resource_group(self) -> str:
        """
        Resource Group name for all twin resources.
        
        Pattern: {twin_name}-rg
        """
        return f"{self._twin_name}-rg"
    
    def managed_identity(self) -> str:
        """
        User-Assigned Managed Identity name for the twin.
        
        This identity is shared by all Function Apps in the twin.
        """
        return f"{self._twin_name}-identity"
    
    def storage_account(self) -> str:
        """
        Storage Account name for Function App deployment packages.
        
        Azure storage account naming restrictions:
        - 3-24 characters
        - Lowercase alphanumeric only (no hyphens)
        """
        # Remove hyphens and ensure lowercase, truncate to 24 chars
        base_name = f"{self._storage_safe_name}storage"
        return base_name[:24]
    
    # ==========================================
    # Layer 0: Glue Layer (Multi-Cloud)
    # ==========================================
    
    def glue_function_app(self) -> str:
        """
        Function App name for L0 glue functions.
        
        Contains: ingestion, hot-writer, cold-writer, archive-writer, hot-reader.
        """
        return f"{self._twin_name}-l0-functions"
    
    def glue_app_service_plan(self) -> str:
        """
        App Service Plan name for L0 glue Function App.
        
        Uses Y1 (Consumption/Dynamic) SKU for serverless execution.
        """
        return f"{self._twin_name}-l0-plan"
    
    def ingestion_function(self) -> str:
        """
        Function name for the ingestion function (multi-cloud L1→L2).
        
        Note: This is the function name within the Function App, not a full resource name.
        """
        return "ingestion"
    
    def hot_writer_function(self) -> str:
        """Function name for the hot writer (multi-cloud L2→L3)."""
        return "hot-writer"
    
    def cold_writer_function(self) -> str:
        """Function name for the cold writer (multi-cloud L3 Hot→Cold)."""
        return "cold-writer"
    
    def archive_writer_function(self) -> str:
        """Function name for the archive writer (multi-cloud L3 Cold→Archive)."""
        return "archive-writer"
    
    def hot_reader_function(self) -> str:
        """Function name for the hot reader (multi-cloud L3→L4)."""
        return "hot-reader"
    
    def hot_reader_last_entry_function(self) -> str:
        """Function name for the hot reader last entry (multi-cloud L3→L4)."""
        return "hot-reader-last-entry"
    
    # ==========================================
    # Layer 1: Data Acquisition (IoT Hub)
    # ==========================================
    
    def iot_hub(self) -> str:
        """IoT Hub name for device connectivity."""
        return f"{self._twin_name}-iothub"
    
    def l1_app_service_plan(self) -> str:
        """
        App Service Plan name for L1 Function App.
        
        Uses Y1 (Consumption/Dynamic) SKU for serverless execution.
        """
        return f"{self._twin_name}-l1-plan"
    
    def l1_function_app(self) -> str:
        """Function App name for L1 (IoT/Data Acquisition) functions."""
        return f"{self._twin_name}-l1-functions"
    
    def dispatcher_function(self) -> str:
        """Function name for the dispatcher."""
        return "dispatcher"
    
    def connector_function(self, device_id: str) -> str:
        """Function name for a device's connector (multi-cloud)."""
        return f"{device_id}-connector"
    
    def event_grid_subscription(self) -> str:
        """Event Grid subscription name for IoT Hub to Dispatcher routing."""
        return f"{self._twin_name}-dispatcher-sub"
    
    # ==========================================
    # Layer 2: Data Processing (Azure Functions)
    # ==========================================
    
    def l2_app_service_plan(self) -> str:
        """
        App Service Plan name for L2 Function App.
        
        Uses Y1 (Consumption/Dynamic) SKU for serverless execution.
        """
        return f"{self._twin_name}-l2-plan"
    
    def l2_function_app(self) -> str:
        """Function App name for L2 (Data Processing) functions."""
        return f"{self._twin_name}-l2-functions"
    
    def persister_function(self) -> str:
        """Function name for the persister."""
        return "persister"
    
    def event_checker_function(self) -> str:
        """Function name for the event checker."""
        return "event-checker"
    
    def event_feedback_function(self) -> str:
        """Function name for event feedback."""
        return "event-feedback"
    
    def logic_app_workflow(self) -> str:
        """
        Logic App Workflow name for notification workflow.
        
        Used when `triggerNotificationWorkflow` is enabled.
        Receives HTTP triggers from Event Checker.
        """
        return f"{self._twin_name}-notification-workflow"
    
    def processor_function(self, device_id: str) -> str:
        """Function name for a device's processor."""
        return f"{device_id}-processor"
    
    # ==========================================
    # Layer 3: Storage (Cosmos DB + Blob)
    # ==========================================
    
    def cosmos_account(self) -> str:
        """
        Cosmos DB account name for hot storage.
        
        Azure Cosmos DB naming restrictions:
        - 3-44 characters
        - Lowercase alphanumeric and hyphens
        """
        return f"{self._twin_name}-cosmos"
    
    def cosmos_database(self) -> str:
        """Cosmos DB database name for IoT data."""
        return "iot-data"
    
    def hot_cosmos_container(self) -> str:
        """Cosmos DB container name for hot data (L3 hot tier)."""
        return "hot-data"
    
    def cold_blob_container(self) -> str:
        """Blob container name for cold storage (L3 cold tier)."""
        return "cold-data"
    
    def archive_blob_container(self) -> str:
        """Blob container name for archive storage (L3 archive tier)."""
        return "archive-data"
    
    def l3_app_service_plan(self) -> str:
        """
        App Service Plan name for L3 Function App.
        
        Uses Y1 (Consumption/Dynamic) SKU for serverless execution.
        """
        return f"{self._twin_name}-l3-plan"
    
    def l3_function_app(self) -> str:
        """Function App name for L3 (Storage) functions."""
        return f"{self._twin_name}-l3-functions"
    
    def hot_cold_mover_function(self) -> str:
        """Function name for the hot-to-cold mover."""
        return "hot-to-cold-mover"
    
    def cold_archive_mover_function(self) -> str:
        """Function name for the cold-to-archive mover."""
        return "cold-to-archive-mover"
    
    def digital_twin_data_connector_function(self) -> str:
        """Function name for the Digital Twin Data Connector (L3→L4 multi-cloud)."""
        return "dt-data-connector"
    
    def digital_twin_data_connector_last_entry_function(self) -> str:
        """Function name for the Digital Twin Data Connector Last Entry."""
        return "dt-data-connector-last-entry"
    
    # ==========================================
    # Layer 4: Twin Management (Azure Digital Twins)
    # ==========================================
    
    def digital_twins_instance(self) -> str:
        """Azure Digital Twins instance name."""
        return f"{self._twin_name}-adt"
    
    def l4_app_service_plan(self) -> str:
        """
        App Service Plan name for L4 Function App.
        
        Uses Y1 (Consumption/Dynamic) SKU for serverless execution.
        """
        return f"{self._twin_name}-l4-plan"
    
    def l4_function_app(self) -> str:
        """
        Function App name for L4 (Twin Management) functions.
        
        Contains: adt-updater (Event Grid triggered for single-cloud).
        """
        return f"{self._twin_name}-l4-functions"
    
    def adt_updater_function(self) -> str:
        """
        Function name for the ADT Updater (single-cloud L4).
        
        This function receives events from IoT Hub via Event Grid
        and updates Azure Digital Twins properties.
        """
        return "adt-updater"
    
    def adt_pusher_function(self) -> str:
        """
        Function name for the ADT Pusher (multi-cloud L0).
        
        This function receives HTTP POST requests from remote Persisters
        and updates Azure Digital Twins. Part of L0 Glue layer.
        """
        return "adt-pusher"
    
    def adt_event_grid_subscription(self) -> str:
        """Event Grid subscription name for IoT Hub to ADT Updater routing."""
        return f"{self._twin_name}-adt-updater-sub"
    
    # ==========================================
    # Layer 5: Visualization (Grafana)
    # ==========================================
    
    def grafana_workspace(self) -> str:
        """Azure Managed Grafana workspace name."""
        return f"{self._twin_name}-grafana"
    
    # ==========================================
    # IoT Device Resources
    # ==========================================
    
    def iot_device(self, device_id: str) -> str:
        """IoT Hub device ID."""
        return f"{self._twin_name}-{device_id}"
