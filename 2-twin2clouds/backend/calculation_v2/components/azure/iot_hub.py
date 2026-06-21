"""
Azure IoT Hub Cost Calculator
==============================

Calculates Azure IoT Hub costs using the CM (Message-Based) formula.

Pricing Model:
    Azure IoT Hub uses unit-based pricing with included messages per unit.
    Additional messages beyond the included amount incur extra cost.
    
    Standard tiers: S1, S2, S3 with increasing included messages
"""

from typing import Dict, Any
import math
from ..types import AzureComponent, FormulaType
from ...formulas import message_based_cost


class AzureIoTHubCalculator:
    """
    Azure IoT Hub cost calculator for L1 Data Acquisition.
    
    Uses: CM formula (message-based)
    
    Pricing keys:
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
        units: int = 1
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
        p = pricing["azure"]["iotHub"]

        if "pricing_tiers" in p:
            return self._calculate_tier_table_cost(messages_per_month, p["pricing_tiers"])
        
        # Base unit cost
        unit_price = p.get("pricePerUnit", p.get("pricePerMonth", 0))
        base_cost = unit_price * units
        
        # Included messages per unit
        included_messages = p.get("messagesPerUnit", 400000) * units
        
        # Additional message cost
        extra_messages = max(0, messages_per_month - included_messages)
        additional_price = p.get("additionalMessagePrice", p.get("pricePerMessage", 0))
        
        additional_cost = message_based_cost(
            price_per_message=additional_price,
            num_messages=extra_messages
        )
        
        return base_cost + additional_cost

    def _calculate_tier_table_cost(self, messages_per_month: float, pricing_tiers: Dict[str, Any]) -> float:
        """
        Calculate IoT Hub cost from the canonical tier table.

        The fetched table stores each tier's monthly unit capacity in
        ``threshold`` and the tier's maximum total capacity in ``limit``. The
        calculator selects the cheapest tier that can serve the monthly volume.
        """
        free_tier = pricing_tiers.get("freeTier")
        if free_tier and messages_per_month <= float(free_tier.get("limit", 0)):
            return float(free_tier.get("price", 0))

        candidates = []
        for tier_name, tier in pricing_tiers.items():
            if tier_name == "freeTier":
                continue

            threshold = float(tier.get("threshold", 0) or 0)
            if threshold <= 0:
                continue

            limit = tier.get("limit", float("inf"))
            if isinstance(limit, str) and limit.lower() == "infinity":
                limit = float("inf")
            else:
                limit = float(limit)

            if messages_per_month > limit:
                continue

            units = max(1, math.ceil(messages_per_month / threshold))
            candidates.append(units * float(tier.get("price", 0)))

        if not candidates:
            raise ValueError("Azure IoT Hub pricing_tiers cannot cover requested message volume")

        return min(candidates)
