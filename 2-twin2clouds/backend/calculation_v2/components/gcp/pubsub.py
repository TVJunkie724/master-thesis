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
from ...formulas import required_first_unit_price, tiered_unit_cost, transfer_cost


class GCPPubSubCalculator:
    """
    GCP Pub/Sub cost calculator for L1 Data Acquisition.
    
    Uses: CTransfer formula (data volume based)
    
    Pricing keys:
        - pricing["gcp"]["iot"]["pricePerGiB"] or ["pricePerGB"]
        - pricing["gcp"]["iot"]["pricePerTiB"] for block pricing
        - pricing["gcp"]["iot"]["pricing_tiers"] for tiered GiB pricing
        - optional ["storagePrice"] and ["transferPrice"] when those
          dimensions are represented by the workload
    """
    
    component_type = GCPComponent.PUBSUB
    formula_type = FormulaType.CTRANSFER
    
    def calculate_cost(
        self,
        data_volume_gb: float,
        pricing: Dict[str, Any],
        messages_per_month: float | None = None,
        average_message_size_kb: float | None = None,
        storage_gb: float = 0.0,
        transfer_gb: float = 0.0,
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
        billable_gb = self._billable_throughput_gb(
            data_volume_gb=data_volume_gb,
            messages_per_month=messages_per_month,
            average_message_size_kb=average_message_size_kb,
        )

        pricing_tiers = p.get("pricing_tiers")
        if pricing_tiers:
            throughput_cost = tiered_unit_cost(billable_gb, pricing_tiers)
        else:
            price_per_gb = required_first_unit_price(
                p,
                (
                    ("pricePerGiB", 1),
                    ("pricePerGB", 1),
                    ("pricePerTiB", 1024),
                    ("pricePerTebibyte", 1024),
                ),
                label="gcp.pubsub.throughput",
            )
            throughput_cost = transfer_cost(
                price_per_gb=price_per_gb,
                gb_transferred=billable_gb,
            )

        storage_cost = 0.0
        if storage_gb > 0:
            storage_price = required_first_unit_price(
                p,
                (("storagePrice", 1), ("storagePricePerGiBMonth", 1)),
                label="gcp.pubsub.storage",
            )
            storage_cost = storage_gb * storage_price

        transfer_cost_total = 0.0
        if transfer_gb > 0:
            transfer_price = required_first_unit_price(
                p,
                (("transferPrice", 1), ("pricePerTransferGiB", 1)),
                label="gcp.pubsub.transfer",
            )
            transfer_cost_total = transfer_gb * transfer_price

        return throughput_cost + storage_cost + transfer_cost_total

    @staticmethod
    def _billable_throughput_gb(
        *,
        data_volume_gb: float,
        messages_per_month: float | None,
        average_message_size_kb: float | None,
    ) -> float:
        if messages_per_month is None or average_message_size_kb is None:
            return data_volume_gb
        billable_message_size_kb = max(float(average_message_size_kb), 1.0)
        minimum_billed_gb = (float(messages_per_month) * billable_message_size_kb) / (1024 * 1024)
        return max(float(data_volume_gb), minimum_billed_gb)
