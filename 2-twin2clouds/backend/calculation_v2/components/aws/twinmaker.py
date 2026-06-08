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
from ...formulas import action_based_cost, storage_based_cost, required_first_unit_price


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
        entity_price = required_first_unit_price(
            p,
            (
                ("pricePerEntity", 1),
                ("entityPrice", 1),
                ("entityPricePerMonth", 1),
            ),
            label="aws.iotTwinMaker.entity",
        )
        entity_cost = entity_price * entity_count
        
        # Query cost (CA formula)
        query_price = required_first_unit_price(
            p,
            (
                ("pricePerQuery", 1),
                ("queryPrice", 1),
                ("queryPricePer10k", 10_000),
                ("pricePer10kQueries", 10_000),
            ),
            label="aws.iotTwinMaker.query",
        )
        query_cost = action_based_cost(
            price_per_action=query_price,
            num_actions=queries_per_month
        )
        
        # API calls cost (CA formula)
        api_price = required_first_unit_price(
            p,
            (
                ("pricePerUnifiedDataAccessAPICall", 1),
                ("unifiedDataAccessAPICallsPrice", 1),
                ("unifiedDataAccessAPICallsPricePerMillion", 1_000_000),
                ("pricePerMillionUnifiedDataAccessAPICalls", 1_000_000),
            ),
            label="aws.iotTwinMaker.unifiedDataAccessApiCall",
        )
        api_cost = action_based_cost(
            price_per_action=api_price,
            num_actions=api_calls_per_month
        )
        
        # 3D model storage cost (CS formula) - if applicable
        storage_cost = 0.0
        if model_storage_gb > 0:
            model_storage_price = required_first_unit_price(
                p,
                (("modelStoragePrice", 1),),
                label="aws.iotTwinMaker.modelStorage",
            )
            storage_cost = storage_based_cost(
                price_per_gb_month=model_storage_price,
                volume_gb=model_storage_gb,
                duration_months=1.0
            )
        
        return entity_cost + query_cost + api_cost + storage_cost
