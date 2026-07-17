from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime

from src.schemas.optimizer_calculation import OptimizerCalculationParams
from src.schemas.pricing_catalog import PricingCatalogContext


class OptimizerParamsUpdate(BaseModel):
    """Update calculation params only."""
    model_config = ConfigDict(extra="forbid")

    params: Optional[OptimizerCalculationParams] = None


class OptimizerResultUpdate(BaseModel):
    """Save a calculation result already bound to trusted catalog references."""
    model_config = ConfigDict(extra="forbid")

    params: OptimizerCalculationParams
    result: dict                          # Full CalcResult
    cheapest_path: dict                   # {"l1": "AWS", "l2": "AZURE", ...}


class CheapestPathResponse(BaseModel):
    """Cheapest path for deployment."""
    l1: Optional[str] = None
    l2: Optional[str] = None
    l3_hot: Optional[str] = None
    l3_cool: Optional[str] = None
    l3_archive: Optional[str] = None
    l4: Optional[str] = None
    l5: Optional[str] = None


class OptimizerConfigResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: str
    twin_id: str
    params: Optional[dict] = None
    result: Optional[dict] = None
    pricing_catalog_context: Optional[PricingCatalogContext] = None
    cheapest_path: Optional[CheapestPathResponse] = None
    calculated_at: Optional[datetime] = None
    updated_at: datetime
