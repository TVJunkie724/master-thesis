"""
AWS IoT Core Cost Calculator
=============================

Calculates AWS IoT Core ingestion costs using the CM (Message-Based) formula.

Pricing Model:
    - Device connectivity: Price per device per month
    - Rules triggered: Price per rule action
    - Messages: Tiered pricing per million messages (5KB increments)
"""

from typing import Dict, Any
from ..types import AWSComponent, FormulaType
from ...formulas import tiered_unit_cost, unit_price


class AWSIoTCoreCalculator:
    """
    AWS IoT Core cost calculator for L1 Data Acquisition.
    
    Uses: CM formula (message-based) + tiered pricing
    
    Pricing keys:
        - pricing["aws"]["iotCore"]["pricePerDeviceAndMonth"]
        - pricing["aws"]["iotCore"]["priceRulesTriggered"]
        - pricing["aws"]["iotCore"]["pricing_tiers"]
    """
    
    component_type = AWSComponent.IOT_CORE
    formula_type = FormulaType.CM
    
    def calculate_cost(
        self,
        number_of_devices: int,
        messages_per_month: float,
        average_message_size_kb: float,
        pricing: Dict[str, Any]
    ) -> float:
        """
        Calculate AWS IoT Core monthly cost.
        
        Args:
            number_of_devices: Number of connected IoT devices
            messages_per_month: Total messages per month
            average_message_size_kb: Average message size in KB
            pricing: Full pricing dictionary
            
        Returns:
            Monthly cost in USD
        """
        p = pricing["aws"]["iotCore"]
        
        # AWS IoT Core bills messages in 5KB increments
        # If message > 5KB, count as multiple messages
        if average_message_size_kb > 5:
            import math
            billing_multiplier = math.ceil(average_message_size_kb / 5.0)
            billable_messages = messages_per_month * billing_multiplier
        else:
            billable_messages = messages_per_month
        
        # Device connectivity cost
        device_cost = number_of_devices * p["pricePerDeviceAndMonth"]
        
        # Rules triggered cost (2 rules per message in typical architecture)
        # Rule 1: Route to Lambda, Rule 2: Store/forward
        rules_triggered = billable_messages * 2
        rules_cost = rules_triggered * p["priceRulesTriggered"]
        
        # Tiered message pricing. Tier prices must be normalized to one
        # billable message before cost multiplication.
        tiers = self._build_tiers(p.get("pricing_tiers", {}))
        message_cost = tiered_unit_cost(billable_messages, tiers)
        
        return device_cost + rules_cost + message_cost
    
    def _build_tiers(self, pricing_tiers: Dict[str, Dict]) -> list:
        """
        Convert pricing_tiers dict to sorted list for tiered_message_cost.
        
        Args:
            pricing_tiers: Dict like {"tier1": {"limit": 1000000000, "price": 1.0}, ...}
            
        Returns:
            Sorted list of tier dicts
        """
        if not pricing_tiers:
            raise ValueError("AWS IoT Core pricing_tiers are required")
        
        tiers = []
        for tier_data in pricing_tiers.values():
            limit = tier_data.get("limit", float('inf'))
            # Handle string "Infinity" from JSON
            if isinstance(limit, str) and limit.lower() == "infinity":
                limit = float('inf')
            tiers.append({
                "limit": limit,
                "price": self._tier_price(tier_data),
            })
        
        # Sort by limit ascending
        return sorted(tiers, key=lambda x: x["limit"])

    @staticmethod
    def _tier_price(tier_data: Dict[str, Any]) -> float:
        if "pricePerMessage" in tier_data:
            return unit_price(tier_data["pricePerMessage"], 1)
        if "price" in tier_data:
            return unit_price(tier_data["price"], 1)
        if "pricePerMillionMessages" in tier_data:
            return unit_price(tier_data["pricePerMillionMessages"], 1_000_000)
        raise ValueError("AWS IoT Core tier missing message price")
