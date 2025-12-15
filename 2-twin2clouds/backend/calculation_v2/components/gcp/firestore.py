"""
GCP Firestore Cost Calculator
==============================

Calculates GCP Firestore costs using CA (Action-Based) + CS (Storage-Based) formulas.

Pricing Model:
    - Document reads: Price per 100,000 reads
    - Document writes: Price per 100,000 writes
    - Storage: Price per GB-month
"""

from typing import Dict, Any
from ..types import GCPComponent, FormulaType
from ...formulas import action_based_cost, storage_based_cost


class GCPFirestoreCalculator:
    """
    GCP Firestore cost calculator for L3 Hot Storage.
    
    Uses: CA formula (for read/write) + CS formula (for storage)
    
    Pricing keys:
        - pricing["gcp"]["storage_hot"]["readPrice"] (per 100k reads)
        - pricing["gcp"]["storage_hot"]["writePrice"] (per 100k writes)
        - pricing["gcp"]["storage_hot"]["storagePrice"]
    """
    
    component_type = GCPComponent.FIRESTORE
    formula_type = FormulaType.CA
    
    def calculate_cost(
        self,
        writes_per_month: float,
        reads_per_month: float,
        storage_gb: float,
        pricing: Dict[str, Any]
    ) -> float:
        """
        Calculate GCP Firestore monthly cost.
        
        Args:
            writes_per_month: Number of document writes
            reads_per_month: Number of document reads
            storage_gb: Storage volume in GB
            pricing: Full pricing dictionary
            
        Returns:
            Monthly cost in USD
        """
        p = pricing["gcp"]["storage_hot"]
        
        # Firestore prices per 100,000 operations
        # Convert to per-operation price
        write_price_per_100k = p.get("writePrice", p.get("documentWritePrice", 0))
        read_price_per_100k = p.get("readPrice", p.get("documentReadPrice", 0))
        
        write_price = write_price_per_100k / 100_000
        read_price = read_price_per_100k / 100_000
        
        # Write cost (CA formula)
        write_cost = action_based_cost(
            price_per_action=write_price,
            num_actions=writes_per_month
        )
        
        # Read cost (CA formula)
        read_cost = action_based_cost(
            price_per_action=read_price,
            num_actions=reads_per_month
        )
        
        # Storage cost (CS formula)
        storage_cost = storage_based_cost(
            price_per_gb_month=p["storagePrice"],
            volume_gb=storage_gb,
            duration_months=1.0
        )
        
        return write_cost + read_cost + storage_cost
