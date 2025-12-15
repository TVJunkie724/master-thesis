"""
AWS DynamoDB Cost Calculator
============================

Calculates AWS DynamoDB costs using CA (Action-Based) + CS (Storage-Based) formulas.

Pricing Model:
    - Write operations: Price per write capacity unit (WCU)
    - Read operations: Price per read capacity unit (RCU)
    - Storage: Price per GB-month
    - Free tier: 25 GB storage included

DynamoDB is used for L3 Hot Storage in the architecture.
"""

from typing import Dict, Any
from ..types import AWSComponent, FormulaType
from ...formulas import action_based_cost, storage_based_cost


class AWSDynamoDBCalculator:
    """
    AWS DynamoDB cost calculator for L3 Hot Storage.
    
    Uses: CA formula (for read/write) + CS formula (for storage)
    
    Pricing keys:
        - pricing["aws"]["dynamoDB"]["writePrice"]
        - pricing["aws"]["dynamoDB"]["readPrice"]
        - pricing["aws"]["dynamoDB"]["storagePrice"]
        - pricing["aws"]["dynamoDB"]["freeStorage"]
    """
    
    component_type = AWSComponent.DYNAMODB
    formula_type = FormulaType.CA  # Primary formula is action-based
    
    def calculate_cost(
        self,
        writes_per_month: float,
        reads_per_month: float,
        storage_gb: float,
        pricing: Dict[str, Any]
    ) -> float:
        """
        Calculate AWS DynamoDB monthly cost.
        
        Args:
            writes_per_month: Number of write operations
            reads_per_month: Number of read operations
            storage_gb: Storage volume in GB
            pricing: Full pricing dictionary
            
        Returns:
            Monthly cost in USD
        """
        p = pricing["aws"]["dynamoDB"]
        
        # Write cost (CA formula)
        write_cost = action_based_cost(
            price_per_action=p["writePrice"],
            num_actions=writes_per_month
        )
        
        # Read cost (CA formula)
        read_cost = action_based_cost(
            price_per_action=p["readPrice"],
            num_actions=reads_per_month
        )
        
        # Storage cost (CS formula with free tier)
        free_storage = p.get("freeStorage", 25)
        billable_storage = max(0, storage_gb - free_storage)
        storage_cost = storage_based_cost(
            price_per_gb_month=p["storagePrice"],
            volume_gb=billable_storage,
            duration_months=1.0
        )
        
        return write_cost + read_cost + storage_cost
