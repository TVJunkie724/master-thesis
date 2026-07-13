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
from ...formulas import action_based_cost, required_first_unit_price, storage_based_cost


class GCPFirestoreCalculator:
    """
    GCP Firestore cost calculator for L3 Hot Storage.
    
    Uses: CA formula (for read/write) + CS formula (for storage)
    
    Pricing keys:
        - pricing["gcp"]["storage_hot"]["readPrice"] or ["writePrice"] per op
        - explicit per-100K keys are normalized at the calculator boundary
        - pricing["gcp"]["storage_hot"]["storagePrice"]
    """
    
    component_type = GCPComponent.FIRESTORE
    formula_type = FormulaType.CA
    
    def calculate_cost(
        self,
        writes_per_month: float,
        reads_per_month: float,
        storage_gb: float,
        pricing: Dict[str, Any],
        deletes_per_month: float = 0.0,
        index_entry_reads_per_month: float = 0.0,
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
        write_price = required_first_unit_price(
            p,
            (
                ("pricePerWrite", 1),
                ("writePrice", 1),
                ("documentWritePrice", 1),
                ("writePricePer100kWrites", 100_000),
                ("documentWritePricePer100kWrites", 100_000),
            ),
            label="gcp.firestore.write",
        )
        read_price = required_first_unit_price(
            p,
            (
                ("pricePerRead", 1),
                ("readPrice", 1),
                ("documentReadPrice", 1),
                ("readPricePer100kReads", 100_000),
                ("documentReadPricePer100kReads", 100_000),
            ),
            label="gcp.firestore.read",
        )
        storage_price = required_first_unit_price(
            p,
            (("storagePrice", 1), ("storagePricePerGiBMonth", 1)),
            label="gcp.firestore.storage",
        )

        write_cost = action_based_cost(
            price_per_action=write_price,
            num_actions=writes_per_month
        )
        read_cost = action_based_cost(
            price_per_action=read_price,
            num_actions=reads_per_month
        )

        delete_cost = 0.0
        if deletes_per_month > 0:
            delete_price = required_first_unit_price(
                p,
                (
                    ("pricePerDelete", 1),
                    ("deletePrice", 1),
                    ("deletePricePer100kDeletes", 100_000),
                ),
                label="gcp.firestore.delete",
            )
            delete_cost = action_based_cost(delete_price, deletes_per_month)

        index_read_cost = 0.0
        if index_entry_reads_per_month > 0:
            index_read_price = required_first_unit_price(
                p,
                (
                    ("pricePerIndexEntryRead", 1),
                    ("indexEntryReadPrice", 1),
                    ("indexEntryReadPricePer100kReads", 100_000),
                ),
                label="gcp.firestore.index_entry_read",
            )
            index_read_cost = action_based_cost(
                index_read_price,
                index_entry_reads_per_month,
            )

        billable_storage_gb = max(0.0, storage_gb - float(p.get("freeStorage", 0)))
        storage_cost = storage_based_cost(
            price_per_gb_month=storage_price,
            volume_gb=billable_storage_gb,
            duration_months=1.0
        )
        
        return write_cost + read_cost + delete_cost + index_read_cost + storage_cost
