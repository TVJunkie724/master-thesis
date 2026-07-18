"""
Azure IoT Hub Cost Calculator
==============================

Calculates Azure IoT Hub costs using the CM (Message-Based) formula.

Pricing Model:
    Azure IoT Hub uses unit-based pricing with included messages per unit.
    Additional messages beyond the included amount incur extra cost.
    
    Standard tiers: S1, S2, S3 with increasing included messages
"""

from typing import Any, Dict

from ..types import AzureComponent, FormulaType
from ...formulas import (
    CapacityTierSelection,
    billable_block_units,
    select_capacity_tier,
)


IOT_HUB_TIER_SKUS = {
    "freeTier": "F1",
    "tier1": "S1",
    "tier2": "S2",
    "tier3": "S3",
    "F1": "F1",
    "S1": "S1",
    "S2": "S2",
    "S3": "S3",
}
IOT_HUB_MAXIMUM_CAPACITY = {
    "F1": 1,
    "S1": 200,
    "S2": 200,
    "S3": 10,
}
IOT_HUB_BILLING_BLOCK_KB = {
    "F1": 0.5,
    "S1": 4.0,
    "S2": 4.0,
    "S3": 4.0,
}


class AzureIoTHubCalculator:
    """
    Azure IoT Hub cost calculator for L1 Data Acquisition.
    
    Uses: CM formula (message-based)
    
    Pricing keys:
        Preferred:
        - pricing["azure"]["iotHub"]["pricing_tiers"]
          with free/paid tiers containing price, limit, and threshold.
        Legacy:
        - pricing["azure"]["iotHub"]["pricePerUnit"]
        - pricing["azure"]["iotHub"]["messagesPerUnit"]
        - pricing["azure"]["iotHub"]["additionalMessagePrice"]
    """
    
    component_type = AzureComponent.IOT_HUB
    formula_type = FormulaType.CM
    
    def calculate_cost(
        self,
        messages_per_month: float,
        pricing: Dict[str, Any],
        units: int = 1,
        average_message_size_kb: float | None = None,
    ) -> float:
        """
        Calculate Azure IoT Hub monthly cost.
        
        Args:
            messages_per_month: Total messages per month
            pricing: Full pricing dictionary
            units: Number of IoT Hub units (default 1)
            
        Returns:
            Monthly cost in USD
        """
        return self.calculate_selection(
            messages_per_month=messages_per_month,
            pricing=pricing,
            units=units,
            average_message_size_kb=average_message_size_kb,
        ).total_cost

    def calculate_selection(
        self,
        *,
        messages_per_month: float,
        pricing: Dict[str, Any],
        units: int = 1,
        average_message_size_kb: float | None = None,
    ) -> CapacityTierSelection:
        """Return the exact IoT Hub SKU/capacity used by the cost formula."""

        pricing_tiers = pricing["azure"]["iotHub"].get("pricing_tiers")
        if not isinstance(pricing_tiers, dict) or not pricing_tiers:
            raise ValueError(
                "Missing required pricing field for "
                "azure.iotHub.pricing_tiers"
            )
        unknown_tiers = sorted(set(pricing_tiers) - set(IOT_HUB_TIER_SKUS))
        if unknown_tiers:
            raise ValueError(
                "Azure IoT Hub pricing contains unsupported tiers: "
                + ", ".join(unknown_tiers)
            )
        quantity_by_sku = None
        if average_message_size_kb is not None:
            quantity_by_sku = {
                sku: billable_block_units(
                    messages_per_month,
                    average_message_size_kb,
                    block_size_kb=block_size_kb,
                )
                for sku, block_size_kb in IOT_HUB_BILLING_BLOCK_KB.items()
            }
        return select_capacity_tier(
            messages_per_month,
            pricing_tiers,
            tier_skus=IOT_HUB_TIER_SKUS,
            maximum_units_by_sku=IOT_HUB_MAXIMUM_CAPACITY,
            quantity_by_sku=quantity_by_sku,
            minimum_paid_units=units,
        )
