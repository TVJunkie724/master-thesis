"""
GCP CloudProvider implementation.

This module implements the CloudProvider protocol for Google Cloud Platform.
It manages GCP SDK clients, resource naming, and status checks.

Design Pattern: Abstract Factory (Provider Pattern)
    GCPProvider creates and manages a family of related GCP objects:
    - SDK clients (google-cloud-* for status checks only)
    - Resource naming (via GCPNaming class)
    - Status checks for SDK-managed resources

Note: Deployment is handled entirely by Terraform. This provider only
provides naming utilities and status checks (info_l* methods).

Usage:
    provider = GCPProvider()
    provider.initialize_clients({
        "gcp_project_id": "my-project",
        "gcp_region": "europe-west1"
    }, twin_name="my-twin")
    
    # Generate resource names
    function_name = provider.naming.dispatcher_function()
    
    # Check status
    status = provider.info_l1(context)
"""

from typing import Dict, Any, TYPE_CHECKING, Optional

from providers.base import BaseProvider

if TYPE_CHECKING:
    from src.core.context import DeploymentContext


class GCPProvider(BaseProvider):
    """
    GCP implementation of the CloudProvider protocol.
    
    Manages GCP SDK clients (for status checks only), resource naming,
    and layer status checks. Deployment is handled by Terraform.
    
    Attributes:
        name: Always "gcp" for this provider
        clients: Dictionary of initialized GCP SDK clients
        naming: GCPNaming instance for resource name generation
    """
    
    name: str = "gcp"
    
    def __init__(self):
        """Initialize GCP provider with empty state."""
        super().__init__()
        self._project_id: str = ""
        self._region: str = ""
        self._naming = None
    
    @property
    def project_id(self) -> str:
        """Get the GCP project ID."""
        return self._project_id
    
    @property
    def region(self) -> str:
        """Get the GCP region."""
        return self._region
    
    @property
    def naming(self):
        """
        Get the GCPNaming instance for this provider.
        
        Returns:
            GCPNaming instance configured with this provider's twin name
        
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
        Initialize GCP SDK clients for status checks.
        
        Args:
            credentials: GCP credentials dictionary containing:
                - gcp_project_id: GCP project ID (optional if creating new)
                - gcp_region: GCP region (REQUIRED)
            twin_name: Digital twin name for resource naming
        
        Raises:
            ValueError: If required credentials are missing
        """
        from .naming import GCPNaming
        
        # Validate required credential
        if "gcp_region" not in credentials:
            raise ValueError("Missing required credential: gcp_region")
        
        # Store configuration
        self._twin_name = twin_name
        self._project_id = credentials.get("gcp_project_id", "")
        self._region = credentials["gcp_region"]
        
        # Initialize naming helper
        self._naming = GCPNaming(twin_name)
        
        # Note: SDK clients are initialized lazily when needed for status checks
        # Deployment is handled entirely by Terraform
        self._clients = {}
        self._initialized = True
    
    def check_if_twin_exists(self) -> bool:
        """
        Check if a digital twin with the current name already exists in GCP.
        
        Uses the Firestore collection as the indicator since it's created
        in L3 and is a reliable marker of an existing deployment.
        
        Returns:
            True if the twin's resources exist, False otherwise.
            
        Raises:
            RuntimeError: If provider not initialized.
        """
        if not self._initialized:
            raise RuntimeError(
                "GCP provider not initialized. Call initialize_clients() first."
            )
        
        # For GCP, we check if the Firestore collection exists
        # This requires the Firestore client to be initialized
        try:
            from google.cloud import firestore
            
            if "firestore" not in self._clients:
                self._clients["firestore"] = firestore.Client(
                    project=self._project_id
                )
            
            collection_name = self.naming.firestore_collection()
            # Check if any documents exist in the collection
            docs = self._clients["firestore"].collection(collection_name).limit(1).get()
            return len(list(docs)) > 0
        except Exception as e:
            # If we can't check Firestore (not deployed, no perms, etc.)
            # assume twin doesn't exist
            print(f"Warning: Could not check GCP twin existence: {e}")
            return False
    
    # ==========================================
    # Status Checks (Used by API)
    # ==========================================
    
    def info_l1(self, context: 'DeploymentContext') -> dict:
        """
        Get status of L1 IoT (Pub/Sub) components.
        
        Checks if Pub/Sub topics exist for this digital twin.
        
        Returns:
            Dictionary with layer status info
        """
        if not self._initialized:
            return {"status": "not_initialized", "provider": self.name}
        
        result = {
            "status": "unknown",
            "provider": self.name,
            "resources": {}
        }
        
        try:
            from google.cloud import pubsub_v1
            
            if "publisher" not in self._clients:
                self._clients["publisher"] = pubsub_v1.PublisherClient()
            
            publisher = self._clients["publisher"]
            
            # Check telemetry topic
            telemetry_topic = f"projects/{self._project_id}/topics/{self.naming.telemetry_topic()}"
            try:
                publisher.get_topic(topic=telemetry_topic)
                result["resources"]["telemetry_topic"] = "exists"
            except Exception:
                result["resources"]["telemetry_topic"] = "not_found"
            
            # Check events topic
            events_topic = f"projects/{self._project_id}/topics/{self.naming.events_topic()}"
            try:
                publisher.get_topic(topic=events_topic)
                result["resources"]["events_topic"] = "exists"
            except Exception:
                result["resources"]["events_topic"] = "not_found"
            
            # Determine overall status
            if all(v == "exists" for v in result["resources"].values()):
                result["status"] = "deployed"
            elif all(v == "not_found" for v in result["resources"].values()):
                result["status"] = "not_deployed"
            else:
                result["status"] = "partial"
                
        except ImportError:
            result["status"] = "sdk_not_installed"
        except Exception as e:
            result["status"] = "error"
            result["error"] = str(e)
        
        return result
