"""
GCP Pub/Sub Cost Calculator
============================

Calculates GCP Pub/Sub costs using the CTransfer (Data Transfer) formula.

Pricing Model:
    GCP Pub/Sub charges by data volume (GB) rather than message count.
    This is different from AWS IoT Core and Azure IoT Hub.
"""

from typing import Dict, Any
from ..types import GCPComponent, FormulaType
from ...formulas import transfer_cost


class GCPPubSubCalculator:
    """
    GCP Pub/Sub cost calculator for L1 Data Acquisition.
    
    Uses: CTransfer formula (data volume based)
    
    Pricing keys:
        - pricing["gcp"]["iot"]["pricePerGiB"] (Pub/Sub pricing)
    """
    
    component_type = GCPComponent.PUBSUB
    formula_type = FormulaType.CTRANSFER
    
    def calculate_cost(
        self,
        data_volume_gb: float,
        pricing: Dict[str, Any]
    ) -> float:
        """
        Calculate GCP Pub/Sub monthly cost.
        
        Args:
            data_volume_gb: Total data volume in GB
            pricing: Full pricing dictionary
            
        Returns:
            Monthly cost in USD
        """
        p = pricing["gcp"]["iot"]
        price_per_gb = p.get("pricePerGiB", p.get("pricePerGB", 0))
        
        return transfer_cost(
            price_per_gb=price_per_gb,
            gb_transferred=data_volume_gb
        )
