from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime


class OptimizerParamsUpdate(BaseModel):
    """Update calculation params only."""
    params: Optional[dict] = None


class OptimizerResultUpdate(BaseModel):
    """Save calculation result + pricing snapshots."""
    params: dict                          # CalcParams
    result: dict                          # Full CalcResult
    cheapest_path: dict                   # {"l1": "AWS", "l2": "AZURE", ...}
    pricing_snapshots: dict               # {"aws": {...}, "azure": {...}, "gcp": {...}}
    pricing_timestamps: dict              # {"aws": "ISO", "azure": "ISO", "gcp": "ISO"}


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
    cheapest_path: Optional[CheapestPathResponse] = None
    calculated_at: Optional[datetime] = None
    pricing_aws_updated_at: Optional[datetime] = None
    pricing_azure_updated_at: Optional[datetime] = None
    pricing_gcp_updated_at: Optional[datetime] = None
    updated_at: datetime
