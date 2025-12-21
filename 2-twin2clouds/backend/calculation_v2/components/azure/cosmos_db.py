"""
Azure Cosmos DB Cost Calculator
================================

Calculates Azure Cosmos DB costs using CA (Action-Based) + CS (Storage-Based) formulas.

Pricing Model:
    - Request Units (RU): Price per million RU/s
    - Storage: Price per GB-month
    
Cosmos DB is used for L3 Hot Storage in the Azure architecture.
"""

from typing import Dict, Any
from ..types import AzureComponent, FormulaType
from ...formulas import action_based_cost, storage_based_cost


class AzureCosmosDBCalculator:
    """
    Azure Cosmos DB cost calculator for L3 Hot Storage.
    
    Uses: CA formula (for RU operations) + CS formula (for storage)
    
    Pricing keys:
        - pricing["azure"]["cosmosDB"]["requestUnitPrice"] (per million RU)
        - pricing["azure"]["cosmosDB"]["storagePrice"]
    """
    
    component_type = AzureComponent.COSMOS_DB
    formula_type = FormulaType.CA
    
    # Default RU consumption per operation
    # Based on typical Cosmos DB workloads
    DEFAULT_RU_PER_READ = 1
    DEFAULT_RU_PER_WRITE = 5
    
    def calculate_cost(
        self,
        writes_per_month: float,
        reads_per_month: float,
        storage_gb: float,
        pricing: Dict[str, Any],
        ru_per_read: float = None,
        ru_per_write: float = None
    ) -> float:
        """
        Calculate Azure Cosmos DB monthly cost.
        
        Args:
            writes_per_month: Number of write operations
            reads_per_month: Number of read operations
            storage_gb: Storage volume in GB
            pricing: Full pricing dictionary
            ru_per_read: RUs consumed per read (default 1)
            ru_per_write: RUs consumed per write (default 5)
            
        Returns:
            Monthly cost in USD
        """
        ru_per_read = ru_per_read or self.DEFAULT_RU_PER_READ
        ru_per_write = ru_per_write or self.DEFAULT_RU_PER_WRITE
        
        p = pricing["azure"]["cosmosDB"]
        
        # Calculate total RUs
        total_rus = (writes_per_month * ru_per_write) + (reads_per_month * ru_per_read)
        
        # RU cost (price is per million RU)
        ru_price_per_million = p.get("requestUnitPrice", p.get("requestPrice", 0))
        ru_price_per_unit = ru_price_per_million / 1_000_000
        
        ru_cost = action_based_cost(
            price_per_action=ru_price_per_unit,
            num_actions=total_rus
        )
        
        # Storage cost
        storage_cost = storage_based_cost(
            price_per_gb_month=p["storagePrice"],
            volume_gb=storage_gb,
            duration_months=1.0
        )
        
        return ru_cost + storage_cost
