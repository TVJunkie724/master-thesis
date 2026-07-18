"""
GCP Cloud Storage Cost Calculators
====================================

Calculates GCP Cloud Storage costs for different tiers using the CS (Storage-Based) formula.

Storage Tiers:
    - Nearline (L3 Cool Storage)
    - Archive (L3 Archive Storage)
"""

from typing import Dict, Any
from ..types import GCPComponent, FormulaType
from ...formulas import action_based_cost, required_first_unit_price, storage_based_cost


class GCSNearlineCalculator:
    """
    GCP Cloud Storage Nearline cost calculator for L3 Cool Storage.
    
    Uses: CS formula (storage-based) + CA formula (for operations)
    
    Pricing keys:
        - pricing["gcp"]["storage_cool"]["storagePrice"]
        - pricing["gcp"]["storage_cool"]["writePrice"] or ["requestPrice"]
        - explicit per-1K/10K operation keys are normalized at the boundary
        - pricing["gcp"]["storage_cool"]["retrievalPrice"] or ["dataRetrievalPrice"]
    """
    
    component_type = GCPComponent.GCS_NEARLINE
    formula_type = FormulaType.CS
    
    def calculate_cost(
        self,
        storage_gb: float,
        writes_per_month: float,
        pricing: Dict[str, Any],
        reads_per_month: float = 0.0,
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
        storage_price = required_first_unit_price(
            p,
            (("storagePrice", 1), ("storagePricePerGiBMonth", 1)),
            label="gcp.storage_cool.storage",
        )
        
        storage_cost = storage_based_cost(
            price_per_gb_month=storage_price,
            volume_gb=storage_gb,
            duration_months=1.0
        )
        
        write_price = required_first_unit_price(
            p,
            (
                ("writePrice", 1),
                ("requestPrice", 1),
                ("pricePerClassAOperation", 1),
                ("writePricePer1kRequests", 1_000),
                ("requestPricePer1kRequests", 1_000),
                ("writePricePer10kRequests", 10_000),
                ("requestPricePer10kRequests", 10_000),
            ),
            label="gcp.storage_cool.write",
        )
        write_cost = action_based_cost(
            price_per_action=write_price,
            num_actions=writes_per_month
        )

        read_cost = 0.0
        if reads_per_month > 0:
            read_price = required_first_unit_price(
                p,
                (
                    ("readPrice", 1),
                    ("pricePerClassBOperation", 1),
                    ("readPricePer1kRequests", 1_000),
                    ("readPricePer10kRequests", 10_000),
                ),
                label="gcp.storage_cool.read",
            )
            read_cost = action_based_cost(read_price, reads_per_month)
        
        retrieval_cost = 0.0
        if retrievals_gb > 0:
            retrieval_price = required_first_unit_price(
                p,
                (("retrievalPrice", 1), ("dataRetrievalPrice", 1)),
                label="gcp.storage_cool.data_retrieval",
            )
            retrieval_cost = action_based_cost(
                price_per_action=retrieval_price,
                num_actions=retrievals_gb
            )
        
        return storage_cost + write_cost + read_cost + retrieval_cost


class GCSArchiveCalculator:
    """
    GCP Cloud Storage Archive cost calculator for L3 Archive Storage.
    
    Uses: CS formula (storage-based) + CA formula (for operations)
    
    Pricing keys:
        - pricing["gcp"]["storage_archive"]["storagePrice"]
        - pricing["gcp"]["storage_archive"]["writePrice"] or ["lifecycleAndWritePrice"]
        - explicit per-1K/10K operation keys are normalized at the boundary
        - pricing["gcp"]["storage_archive"]["retrievalPrice"] or ["dataRetrievalPrice"]
    """
    
    component_type = GCPComponent.GCS_ARCHIVE
    formula_type = FormulaType.CS
    
    def calculate_cost(
        self,
        storage_gb: float,
        writes_per_month: float,
        pricing: Dict[str, Any],
        reads_per_month: float = 0.0,
        retrievals_gb: float = 0.0
    ) -> float:
        """
        Calculate GCP Cloud Storage Archive monthly cost.
        
        Args:
            storage_gb: Storage volume in GB
            writes_per_month: Number of write/archive operations
            pricing: Full pricing dictionary
            retrievals_gb: Data retrieved in GB (expensive!)
            
        Returns:
            Monthly cost in USD
        """
        p = pricing["gcp"]["storage_archive"]
        storage_price = required_first_unit_price(
            p,
            (("storagePrice", 1), ("storagePricePerGiBMonth", 1)),
            label="gcp.storage_archive.storage",
        )
        
        storage_cost = storage_based_cost(
            price_per_gb_month=storage_price,
            volume_gb=storage_gb,
            duration_months=1.0
        )
        
        write_price = required_first_unit_price(
            p,
            (
                ("writePrice", 1),
                ("lifecycleAndWritePrice", 1),
                ("pricePerClassAOperation", 1),
                ("writePricePer1kRequests", 1_000),
                ("lifecycleAndWritePricePer1kRequests", 1_000),
                ("writePricePer10kRequests", 10_000),
                ("lifecycleAndWritePricePer10kRequests", 10_000),
            ),
            label="gcp.storage_archive.write",
        )
        write_cost = action_based_cost(
            price_per_action=write_price,
            num_actions=writes_per_month
        )

        read_cost = 0.0
        if reads_per_month > 0:
            read_price = required_first_unit_price(
                p,
                (
                    ("readPrice", 1),
                    ("pricePerClassBOperation", 1),
                    ("readPricePer1kRequests", 1_000),
                    ("readPricePer10kRequests", 10_000),
                ),
                label="gcp.storage_archive.read",
            )
            read_cost = action_based_cost(read_price, reads_per_month)
        
        retrieval_cost = 0.0
        if retrievals_gb > 0:
            retrieval_price = required_first_unit_price(
                p,
                (("retrievalPrice", 1), ("dataRetrievalPrice", 1)),
                label="gcp.storage_archive.data_retrieval",
            )
            retrieval_cost = action_based_cost(
                price_per_action=retrieval_price,
                num_actions=retrievals_gb
            )
        
        return storage_cost + write_cost + read_cost + retrieval_cost
