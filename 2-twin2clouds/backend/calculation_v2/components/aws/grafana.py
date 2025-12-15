"""
AWS Managed Grafana Cost Calculator
====================================

Calculates AWS Managed Grafana costs using the CU (User-Based) formula.

Pricing Model:
    - Editor users: Price per active editor per month
    - Viewer users: Price per active viewer per month

Grafana is used for L5 Visualization in the architecture.
"""

from typing import Dict, Any
from ..types import AWSComponent, FormulaType
from ...formulas import user_based_cost


class AWSGrafanaCalculator:
    """
    AWS Managed Grafana cost calculator for L5 Visualization.
    
    Uses: CU formula (user-based)
    
    Pricing keys:
        - pricing["aws"]["awsManagedGrafana"]["editorPrice"]
        - pricing["aws"]["awsManagedGrafana"]["viewerPrice"]
    """
    
    component_type = AWSComponent.MANAGED_GRAFANA
    formula_type = FormulaType.CU
    
    def calculate_cost(
        self,
        num_editors: int,
        num_viewers: int,
        pricing: Dict[str, Any]
    ) -> float:
        """
        Calculate AWS Managed Grafana monthly cost.
        
        Args:
            num_editors: Number of active editor users
            num_viewers: Number of active viewer users
            pricing: Full pricing dictionary
            
        Returns:
            Monthly cost in USD
        """
        p = pricing["aws"]["awsManagedGrafana"]
        
        return user_based_cost(
            price_per_editor=p["editorPrice"],
            num_editors=num_editors,
            price_per_viewer=p["viewerPrice"],
            num_viewers=num_viewers,
            price_per_hour=0.0,  # Not applicable for managed service
            total_hours=0.0
        )
