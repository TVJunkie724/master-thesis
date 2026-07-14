"""
GCP Compute Engine Cost Calculator
====================================

Calculates GCP Compute Engine (self-hosted VM) costs using the CU (User-Based) formula.

Pricing Model:
    - VM running time: Price per hour
    - Disk storage: Price per GB-month

GCP doesn't have managed TwinMaker or Grafana equivalents, so
L4 and L5 are self-hosted on Compute Engine VMs.
"""

from typing import Dict, Any
from ..types import FormulaType
from ...formulas import required_first_unit_price, storage_based_cost, user_based_cost


class GCPComputeEngineCalculator:
    """
    GCP Compute Engine cost calculator for L4/L5 (self-hosted).
    
    Uses: CU formula (time-based) + CS formula (for disk)
    
    Pricing keys for TwinMaker:
        - pricing["gcp"]["twinmaker"]["e2MediumPrice"]
        - pricing["gcp"]["twinmaker"]["storagePrice"]
        
    Pricing keys for Grafana:
        - pricing["gcp"]["grafana"]["e2MediumPrice"]
        - pricing["gcp"]["grafana"]["storagePrice"]
    """
    
    formula_type = FormulaType.CU
    
    # Default: 730 hours per month (24/7 operation)
    HOURS_PER_MONTH = 730
    
    def calculate_twinmaker_cost(
        self,
        pricing: Dict[str, Any],
        hours_per_month: float = None,
        disk_gb: float = 10.0
    ) -> float:
        """
        Calculate self-hosted TwinMaker (L4) monthly cost on GCP.
        
        Args:
            pricing: Full pricing dictionary
            hours_per_month: VM running hours (default 730)
            disk_gb: Persistent disk in GB
            
        Returns:
            Monthly cost in USD
        """
        hours = hours_per_month or self.HOURS_PER_MONTH
        p = pricing["gcp"]["twinmaker"]
        
        vm_price = required_first_unit_price(
            p,
            (("e2MediumPrice", 1), ("vmPrice", 1), ("pricePerHour", 1)),
            label="gcp.compute.twinmaker.vm_hour",
        )
        disk_price = required_first_unit_price(
            p,
            (("storagePrice", 1), ("diskStoragePrice", 1), ("storagePricePerGiBMonth", 1)),
            label="gcp.compute.twinmaker.disk_storage",
        )

        vm_cost = user_based_cost(
            price_per_editor=0,
            num_editors=0,
            price_per_viewer=0,
            num_viewers=0,
            price_per_hour=vm_price,
            total_hours=hours
        )
        
        disk_cost = storage_based_cost(
            price_per_gb_month=disk_price,
            volume_gb=disk_gb,
            duration_months=1.0
        )
        
        return vm_cost + disk_cost
    
    def calculate_grafana_cost(
        self,
        pricing: Dict[str, Any],
        hours_per_month: float = None,
        disk_gb: float = 10.0
    ) -> float:
        """
        Calculate self-hosted Grafana (L5) monthly cost on GCP.
        
        Args:
            pricing: Full pricing dictionary
            hours_per_month: VM running hours (default 730)
            disk_gb: Persistent disk in GB
            
        Returns:
            Monthly cost in USD
        """
        hours = hours_per_month or self.HOURS_PER_MONTH
        p = pricing["gcp"]["grafana"]
        
        vm_price = required_first_unit_price(
            p,
            (("e2MediumPrice", 1), ("vmPrice", 1), ("pricePerHour", 1)),
            label="gcp.compute.grafana.vm_hour",
        )
        disk_price = required_first_unit_price(
            p,
            (("storagePrice", 1), ("diskStoragePrice", 1), ("storagePricePerGiBMonth", 1)),
            label="gcp.compute.grafana.disk_storage",
        )

        vm_cost = user_based_cost(
            price_per_editor=0,
            num_editors=0,
            price_per_viewer=0,
            num_viewers=0,
            price_per_hour=vm_price,
            total_hours=hours
        )
        
        disk_cost = storage_based_cost(
            price_per_gb_month=disk_price,
            volume_gb=disk_gb,
            duration_months=1.0
        )
        
        return vm_cost + disk_cost
