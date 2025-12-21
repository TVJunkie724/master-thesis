"""
GCP Cloud Storage Cost Calculators
====================================

Calculates GCP Cloud Storage costs for different tiers using the CS (Storage-Based) formula.

Storage Tiers:
    - Nearline (L3 Cool Storage) - 30 day min storage
    - Coldline (L3 Archive Storage) - 90 day min storage
"""

from typing import Dict, Any
from ..types import GCPComponent, FormulaType
from ...formulas import storage_based_cost, action_based_cost


class GCSNearlineCalculator:
    """
    GCP Cloud Storage Nearline cost calculator for L3 Cool Storage.
    
    Uses: CS formula (storage-based) + CA formula (for operations)
    
    Pricing keys:
        - pricing["gcp"]["storage_cool"]["storagePrice"]
        - pricing["gcp"]["storage_cool"]["writePrice"]
        - pricing["gcp"]["storage_cool"]["retrievalPrice"]
    """
    
    component_type = GCPComponent.GCS_NEARLINE
    formula_type = FormulaType.CS
    
    def calculate_cost(
        self,
        storage_gb: float,
        writes_per_month: float,
        pricing: Dict[str, Any],
        retrievals_gb: float = 0.0
    ) -> float:
        """
        Calculate GCP Cloud Storage Nearline monthly cost.
        
        Args:
            storage_gb: Storage volume in GB
            writes_per_month: Number of write operations
            pricing: Full pricing dictionary
            retrievals_gb: Data retrieved in GB
            
        Returns:
            Monthly cost in USD
        """
        p = pricing["gcp"]["storage_cool"]
        
        # Storage cost
        storage_cost = storage_based_cost(
            price_per_gb_month=p["storagePrice"],
            volume_gb=storage_gb,
            duration_months=1.0
        )
        
        # Write cost
        write_price = p.get("writePrice", p.get("requestPrice", 0.01))
        write_cost = action_based_cost(
            price_per_action=write_price,
            num_actions=writes_per_month
        )
        
        # Retrieval cost
        retrieval_price = p.get("retrievalPrice", p.get("dataRetrievalPrice", 0.01))
        retrieval_cost = action_based_cost(
            price_per_action=retrieval_price,
            num_actions=retrievals_gb
        )
        
        return storage_cost + write_cost + retrieval_cost


class GCSColdlineCalculator:
    """
    GCP Cloud Storage Coldline cost calculator for L3 Archive Storage.
    
    Uses: CS formula (storage-based) + CA formula (for operations)
    
    Pricing keys:
        - pricing["gcp"]["storage_archive"]["storagePrice"]
        - pricing["gcp"]["storage_archive"]["writePrice"]
        - pricing["gcp"]["storage_archive"]["retrievalPrice"]
    """
    
    component_type = GCPComponent.GCS_COLDLINE
    formula_type = FormulaType.CS
    
    def calculate_cost(
        self,
        storage_gb: float,
        writes_per_month: float,
        pricing: Dict[str, Any],
        retrievals_gb: float = 0.0
    ) -> float:
        """
        Calculate GCP Cloud Storage Coldline monthly cost.
        
        Args:
            storage_gb: Storage volume in GB
            writes_per_month: Number of write/archive operations
            pricing: Full pricing dictionary
            retrievals_gb: Data retrieved in GB (expensive!)
            
        Returns:
            Monthly cost in USD
        """
        p = pricing["gcp"]["storage_archive"]
        
        # Storage cost - cheap
        storage_cost = storage_based_cost(
            price_per_gb_month=p["storagePrice"],
            volume_gb=storage_gb,
            duration_months=1.0
        )
        
        # Write cost
        write_price = p.get("writePrice", p.get("lifecycleAndWritePrice", 0.05))
        write_cost = action_based_cost(
            price_per_action=write_price,
            num_actions=writes_per_month
        )
        
        # Retrieval cost - expensive
        retrieval_price = p.get("retrievalPrice", p.get("dataRetrievalPrice", 0.05))
        retrieval_cost = action_based_cost(
            price_per_action=retrieval_price,
            num_actions=retrievals_gb
        )
        
        return storage_cost + write_cost + retrieval_cost
