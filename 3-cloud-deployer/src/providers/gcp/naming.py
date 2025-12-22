"""
GCP resource naming conventions.

This module provides functions to generate consistent, namespaced resource
names for all GCP resources.

Naming Convention:
    All resources follow the pattern: {twin_name}-{resource_type}[-{suffix}]
    
    Examples:
        - my-twin-dispatcher (Cloud Function)
        - my-twin-hot-data (Firestore collection)
        - my-twin-sensor-001-processor (device-specific Cloud Function)

Design Decision:
    Following the same patterns as AWS and Azure providers.
    Functions take twin_name as a parameter managed by the provider.
    This makes testing easier and dependencies explicit.

Usage:
    from providers.gcp.naming import GCPNaming
    
    naming = GCPNaming("my-twin")
    function_name = naming.dispatcher_function()  # "my-twin-dispatcher"
"""

from typing import Optional


class GCPNaming:
    """
    Generates consistent GCP resource names for a digital twin.
    
    All resource names are prefixed with the digital twin name to create
    isolated namespaces. This enables multiple twins to coexist in the
    same GCP project without conflicts.
    
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
    # Setup Layer: Project & Common Resources
    # ==========================================
    
    def project_id(self) -> str:
        """Generated GCP project ID for this digital twin."""
        return f"{self._twin_name}-project"
    
    def service_account(self) -> str:
        """Service account ID for Cloud Functions."""
        return f"{self._twin_name}-functions-sa"
    
    def function_source_bucket(self, project_id: str) -> str:
        """Cloud Storage bucket for function source code."""
        return f"{project_id}-{self._twin_name}-functions"
    
    def get_common_labels(self, layer: str = "Setup") -> dict:
        """
        Get common labels for all resources in this digital twin.
        
        Args:
            layer: Layer identifier (Setup, L0, L1, L2, L3, L4, L5)
        
        Returns:
            Dictionary of label key-value pairs
        """
        return {
            "digital-twin": self._twin_name,
            "project": "twin2multicloud",
            "layer": layer.lower(),
            "managed-by": "terraform",
        }
    
    # ==========================================
    # Layer 1: Data Acquisition (Pub/Sub)
    # ==========================================
    
    def telemetry_topic(self) -> str:
        """Pub/Sub topic name for telemetry ingestion."""
        return f"{self._twin_name}-telemetry"
    
    def events_topic(self) -> str:
        """Pub/Sub topic name for event processing."""
        return f"{self._twin_name}-events"
    
    def dispatcher_function(self) -> str:
        """Cloud Function name for the dispatcher."""
        return f"{self._twin_name}-dispatcher"
    
    def connector_function(self, device_id: str) -> str:
        """Cloud Function name for a device's connector (multi-cloud)."""
        return f"{self._twin_name}-{device_id}-connector"
    
    def ingestion_function(self) -> str:
        """Cloud Function name for ingestion (multi-cloud receiver)."""
        return f"{self._twin_name}-ingestion"
    
    # ==========================================
    # Layer 2: Data Processing
    # ==========================================
    
    def processor_function(self, device_id: Optional[str] = None) -> str:
        """Cloud Function name for the processor."""
        if device_id:
            return f"{self._twin_name}-{device_id}-processor"
        return f"{self._twin_name}-processor"
    
    def persister_function(self) -> str:
        """Cloud Function name for the persister."""
        return f"{self._twin_name}-persister"
    
    def event_checker_function(self) -> str:
        """Cloud Function name for event checking."""
        return f"{self._twin_name}-event-checker"
    
    def event_feedback_function(self) -> str:
        """Cloud Function name for event feedback."""
        return f"{self._twin_name}-event-feedback"
    
    # ==========================================
    # Layer 3: Storage
    # ==========================================
    
    def firestore_collection(self) -> str:
        """Firestore collection name for hot storage."""
        return f"{self._twin_name}-hot-data"
    
    def cold_bucket(self, project_id: str) -> str:
        """Cloud Storage bucket name for cold storage (Nearline)."""
        return f"{project_id}-{self._twin_name}-cold"
    
    def archive_bucket(self, project_id: str) -> str:
        """Cloud Storage bucket name for archive storage."""
        return f"{project_id}-{self._twin_name}-archive"
    
    def hot_to_cold_mover_function(self) -> str:
        """Cloud Function name for hot-to-cold mover."""
        return f"{self._twin_name}-hot-to-cold-mover"
    
    def cold_to_archive_mover_function(self) -> str:
        """Cloud Function name for cold-to-archive mover."""
        return f"{self._twin_name}-cold-to-archive-mover"
    
    def hot_reader_function(self) -> str:
        """Cloud Function name for hot data reader."""
        return f"{self._twin_name}-hot-reader"
    
    def hot_reader_last_entry_function(self) -> str:
        """Cloud Function name for last entry reader."""
        return f"{self._twin_name}-hot-reader-last-entry"
    
    def hot_writer_function(self) -> str:
        """Cloud Function name for hot writer (multi-cloud)."""
        return f"{self._twin_name}-hot-writer"
    
    def cold_writer_function(self) -> str:
        """Cloud Function name for cold writer (multi-cloud)."""
        return f"{self._twin_name}-cold-writer"
    
    def archive_writer_function(self) -> str:
        """Cloud Function name for archive writer (multi-cloud)."""
        return f"{self._twin_name}-archive-writer"
    
    def digital_twin_data_connector_function(self) -> str:
        """Cloud Function name for Digital Twin Data Connector."""
        return f"{self._twin_name}-dt-data-connector"
    
    def digital_twin_data_connector_last_entry_function(self) -> str:
        """Cloud Function name for DT Data Connector Last Entry."""
        return f"{self._twin_name}-dt-data-connector-last-entry"

