"""
Azure Blob Storage Cost Calculators
=====================================

Calculates Azure Blob Storage costs for different tiers using the CS (Storage-Based) formula.

Storage Tiers:
    - Cool Storage (L3 Cool)
    - Archive Storage (L3 Archive)
"""

from typing import Dict, Any
from ..types import AzureComponent, FormulaType
from ...formulas import storage_based_cost, action_based_cost


class AzureBlobCoolCalculator:
    """
    Azure Blob Storage Cool tier cost calculator for L3 Cool Storage.
    
    Uses: CS formula (storage-based) + CA formula (for operations)
    
    Pricing keys:
        - pricing["azure"]["blobStorageCool"]["storagePrice"]
        - pricing["azure"]["blobStorageCool"]["writePrice"]
        - pricing["azure"]["blobStorageCool"]["dataRetrievalPrice"]
    """
    
    component_type = AzureComponent.BLOB_COOL
    formula_type = FormulaType.CS
    
    def calculate_cost(
        self,
        storage_gb: float,
        writes_per_month: float,
        pricing: Dict[str, Any],
        retrievals_gb: float = 0.0
    ) -> float:
        """
        Calculate Azure Blob Cool Storage monthly cost.
        
        Args:
            storage_gb: Storage volume in GB
            writes_per_month: Number of write operations
            pricing: Full pricing dictionary
            retrievals_gb: Data retrieved in GB
            
        Returns:
            Monthly cost in USD
        """
        p = pricing["azure"]["blobStorageCool"]
        
        # Storage cost
        storage_cost = storage_based_cost(
            price_per_gb_month=p["storagePrice"],
            volume_gb=storage_gb,
            duration_months=1.0
        )
        
        # Write cost
        write_price = p.get("writePrice", 0.01)
        write_cost = action_based_cost(
            price_per_action=write_price,
            num_actions=writes_per_month
        )
        
        # Retrieval cost
        retrieval_price = p.get("dataRetrievalPrice", 0.01)
        retrieval_cost = action_based_cost(
            price_per_action=retrieval_price,
            num_actions=retrievals_gb
        )
        
        return storage_cost + write_cost + retrieval_cost


class AzureBlobArchiveCalculator:
    """
    Azure Blob Storage Archive tier cost calculator for L3 Archive Storage.
    
    Uses: CS formula (storage-based) + CA formula (for operations)
    
    Pricing keys:
        - pricing["azure"]["blobStorageArchive"]["storagePrice"]
        - pricing["azure"]["blobStorageArchive"]["writePrice"]
        - pricing["azure"]["blobStorageArchive"]["dataRetrievalPrice"]
    """
    
    component_type = AzureComponent.BLOB_ARCHIVE
    formula_type = FormulaType.CS
    
    def calculate_cost(
        self,
        storage_gb: float,
        writes_per_month: float,
        pricing: Dict[str, Any],
        retrievals_gb: float = 0.0
    ) -> float:
        """
        Calculate Azure Blob Archive Storage monthly cost.
        
        Args:
            storage_gb: Storage volume in GB
            writes_per_month: Number of write/archive operations
            pricing: Full pricing dictionary
            retrievals_gb: Data retrieved in GB (expensive!)
            
        Returns:
            Monthly cost in USD
        """
        p = pricing["azure"]["blobStorageArchive"]
        
        # Storage cost - very cheap for archive
        storage_cost = storage_based_cost(
            price_per_gb_month=p["storagePrice"],
            volume_gb=storage_gb,
            duration_months=1.0
        )
        
        # Write cost (includes tier transition)
        write_price = p.get("writePrice", 0.10)
        write_cost = action_based_cost(
            price_per_action=write_price,
            num_actions=writes_per_month
        )
        
        # Retrieval cost - expensive for archive!
        retrieval_price = p.get("dataRetrievalPrice", 0.02)
        retrieval_cost = action_based_cost(
            price_per_action=retrieval_price,
            num_actions=retrievals_gb
        )
        
        return storage_cost + write_cost + retrieval_cost
