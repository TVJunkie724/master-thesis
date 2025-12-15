"""
AWS IoT TwinMaker Cost Calculator
==================================

Calculates AWS IoT TwinMaker costs using CA (Action-Based) + CS (Storage-Based) formulas.

Pricing Model:
    - Entity creation/management: Price per entity
    - API calls: Price per unified data access API call
    - Queries: Price per query
    - 3D model storage: Price per GB

TwinMaker is used for L4 Twin Management in the architecture.
"""

from typing import Dict, Any
from ..types import AWSComponent, FormulaType
from ...formulas import action_based_cost, storage_based_cost


class AWSTwinMakerCalculator:
    """
    AWS IoT TwinMaker cost calculator for L4 Twin Management.
    
    Uses: CA formula (for API/queries) + CS formula (for entities/storage)
    
    Pricing keys:
        - pricing["aws"]["iotTwinMaker"]["pricePerEntity"]  
        - pricing["aws"]["iotTwinMaker"]["queryPrice"]
        - pricing["aws"]["iotTwinMaker"]["unifiedDataAccessAPICallsPrice"]
    """
    
    component_type = AWSComponent.TWINMAKER
    formula_type = FormulaType.CA
    
    def calculate_cost(
        self,
        entity_count: int,
        queries_per_month: float,
        api_calls_per_month: float,
        pricing: Dict[str, Any],
        model_storage_gb: float = 0.0
    ) -> float:
        """
        Calculate AWS IoT TwinMaker monthly cost.
        
        Args:
            entity_count: Number of digital twin entities
            queries_per_month: Number of twin queries
            api_calls_per_month: Number of unified data API calls
            pricing: Full pricing dictionary
            model_storage_gb: 3D model storage in GB (optional)
            
        Returns:
            Monthly cost in USD
        """
        p = pricing["aws"]["iotTwinMaker"]
        
        # Entity cost (treated as storage-like recurring cost)
        entity_price = p.get("pricePerEntity", p.get("entityPrice", 0.0))
        entity_cost = entity_price * entity_count
        
        # Query cost (CA formula)
        query_price = p.get("queryPrice", 0.0)
        query_cost = action_based_cost(
            price_per_action=query_price,
            num_actions=queries_per_month
        )
        
        # API calls cost (CA formula)
        api_price = p.get("unifiedDataAccessAPICallsPrice", 0.0)
        api_cost = action_based_cost(
            price_per_action=api_price,
            num_actions=api_calls_per_month
        )
        
        # 3D model storage cost (CS formula) - if applicable
        storage_cost = 0.0
        if model_storage_gb > 0:
            # Use S3 standard pricing as proxy for 3D model storage
            storage_cost = storage_based_cost(
                price_per_gb_month=0.023,  # S3 standard rate
                volume_gb=model_storage_gb,
                duration_months=1.0
            )
        
        return entity_cost + query_cost + api_cost + storage_cost
