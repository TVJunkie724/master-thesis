from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


CloudAccessProvider = Literal["aws", "azure", "gcp"]
CloudAccessPurpose = Literal["pricing", "deployment"]
CloudAccessScope = Literal["user", "twin", "public"]
CloudAccessStatus = Literal[
    "active",
    "missing",
    "needs_validation",
    "invalid",
    "stale",
    "disabled",
]
CloudAccessPermissionSetStatus = Literal["matched", "missing", "outdated"]


class CloudAccessEntry(BaseModel):
    connection_id: str | None = None
    provider: CloudAccessProvider
    purpose: CloudAccessPurpose
    scope: CloudAccessScope
    identity_label: str
    status: CloudAccessStatus
    provider_account_id: str | None = None
    provider_project_id: str | None = None
    provider_subscription_id: str | None = None
    is_default_for_pricing: bool | None = None
    last_validated_at: datetime | None = None
    last_used_at: datetime | None = None
    permission_set_status: CloudAccessPermissionSetStatus | None = None
    bound_twin_count: int = 0
    bound_twin_labels: list[str] = Field(default_factory=list)
    actions: list[str] = Field(default_factory=list)
    primary_message: str | None = None


class CloudAccessProviderInventory(BaseModel):
    provider: CloudAccessProvider
    pricing: CloudAccessEntry
    deployment: list[CloudAccessEntry] = Field(default_factory=list)


class CloudAccessInventoryResponse(BaseModel):
    schema_version: str = "cloud-access-inventory.v1"
    providers: dict[CloudAccessProvider, CloudAccessProviderInventory]
