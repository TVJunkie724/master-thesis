"""
Azure Managed Grafana Cost Calculator
=======================================

Calculates Azure Managed Grafana costs using the CU (User-Based) formula.

Pricing Model:
    - Active users: Price per active user per month
    - Hourly compute: Price per hour of compute time
    
Note: Azure Managed Grafana uses per-user pricing (not separate editor/viewer).
"""

from typing import Dict, Any
from ..types import AzureComponent, FormulaType
from ...formulas import user_based_cost


class AzureGrafanaCalculator:
    """
    Azure Managed Grafana cost calculator for L5 Visualization.
    
    Uses: CU formula (user-based)
    
    Pricing keys (dynamic pricing format):
        - pricing["azure"]["azureManagedGrafana"]["userPrice"]
        - pricing["azure"]["azureManagedGrafana"]["hourlyPrice"]
    """
    
    component_type = AzureComponent.MANAGED_GRAFANA
    formula_type = FormulaType.CU
    
    def calculate_cost(
        self,
        num_editors: int,
        num_viewers: int,
        pricing: Dict[str, Any]
    ) -> float:
        """
        Calculate Azure Managed Grafana monthly cost.
        
        Args:
            num_editors: Number of active editor users
            num_viewers: Number of active viewer users
            pricing: Full pricing dictionary
            
        Returns:
            Monthly cost in USD
        """
        p = pricing["azure"]["azureManagedGrafana"]
        
        # Handle both dynamic pricing (userPrice) and legacy pricing (editorPrice)
        user_price = p.get("userPrice", p.get("editorPrice", 6.0))
        hourly_price = p.get("hourlyPrice", 0.0)
        
        # Azure charges per active user (combined editors + viewers)
        total_users = num_editors + num_viewers
        
        # Assume 730 hours per month for compute cost
        monthly_hours = 730
        
        return user_based_cost(
            price_per_editor=user_price,
            num_editors=total_users,
            price_per_viewer=0.0,  # Combined into total_users above
            num_viewers=0,
            price_per_hour=hourly_price,
            total_hours=monthly_hours
        )
