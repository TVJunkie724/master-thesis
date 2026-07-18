from datetime import datetime
import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.schemas.twin_config import AWSCredentials, AzureCredentials, GCPCredentials

CloudProvider = Literal["aws", "azure", "gcp"]
CloudConnectionPurpose = Literal["pricing", "deployment"]
CloudConnectionScope = Literal["user"]
CloudAuthType = Literal[
    "access_key",
    "service_principal",
    "service_account_key",
    "assume_role",
    "workload_identity",
]

class CloudConnectionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: CloudProvider
    purpose: CloudConnectionPurpose = "deployment"
    scope: CloudConnectionScope = "user"
    is_default_for_pricing: bool = False
    display_name: str = Field(..., min_length=1, max_length=120)
    auth_type: CloudAuthType | None = None
    permission_set_version: str | None = Field(
        default=None,
        min_length=1,
        max_length=80,
        description="Versioned deployment permission-set baseline for this connection.",
    )
    cloud_scope: dict[str, Any] = Field(default_factory=dict)
    aws: AWSCredentials | None = None
    azure: AzureCredentials | None = None
    gcp: GCPCredentials | None = None

    @model_validator(mode="after")
    def validate_provider_payload(self):
        payload = {"aws": self.aws, "azure": self.azure, "gcp": self.gcp}
        if payload[self.provider] is None:
            raise ValueError(f"{self.provider} payload is required")

        extra_payloads = [
            provider for provider, provider_payload in payload.items()
            if provider != self.provider and provider_payload is not None
        ]
        if extra_payloads:
            raise ValueError("Only the selected provider payload may be supplied")

        supported_auth_types = {
            "aws": {"access_key"},
            "azure": {"service_principal"},
            "gcp": {"service_account_key"},
        }
        if self.auth_type and self.auth_type not in supported_auth_types[self.provider]:
            raise ValueError(f"{self.auth_type} is not supported for {self.provider} Cloud Connections yet")
        if self.provider == "gcp" and self.gcp and not self.gcp.service_account_json:
            raise ValueError("gcp service_account_json is required for service_account_key Cloud Connections")
        if self.provider == "aws" and self.aws:
            cloud_scope = dict(self.cloud_scope)
            configured_region = str(cloud_scope.get("region") or "").strip()
            if configured_region and configured_region != self.aws.region:
                raise ValueError(
                    "cloud_scope.region must match the AWS credential region"
                )
            cloud_scope["region"] = self.aws.region
            configured_account_id = cloud_scope.get("account_id")
            if configured_account_id is not None:
                normalized_account_id = str(configured_account_id).strip()
                if not re.fullmatch(r"\d{12}", normalized_account_id):
                    raise ValueError(
                        "cloud_scope.account_id must be a twelve-digit AWS account ID"
                    )
                cloud_scope["account_id"] = normalized_account_id
            self.cloud_scope = cloud_scope
        if self.purpose == "pricing":
            if self.provider == "azure":
                raise ValueError("Azure pricing uses the public Retail Prices API")
            if self.permission_set_version is not None:
                raise ValueError("permission_set_version is only supported for deployment Cloud Connections")
        elif self.is_default_for_pricing:
            raise ValueError("Only pricing Cloud Connections may be selected as pricing default")
        return self


class CloudConnectionUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    display_name: str | None = Field(default=None, min_length=1, max_length=120)
    permission_set_version: str | None = Field(default=None, min_length=1, max_length=80)
    cloud_scope: dict[str, Any] | None = None
    is_default_for_pricing: bool | None = None


class CloudConnectionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    provider: CloudProvider
    purpose: CloudConnectionPurpose
    scope: CloudConnectionScope
    is_default_for_pricing: bool
    display_name: str
    auth_type: str
    permission_set_version: str | None = None
    cloud_scope: dict[str, Any]
    payload_fingerprint: str
    payload_summary: dict[str, Any]
    validation_status: str
    validation_message: str | None = None
    last_validated_at: datetime | None = None
    last_used_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class CloudConnectionValidationResponse(BaseModel):
    id: str
    provider: CloudProvider
    valid: bool
    validation_status: str
    message: str
    optimizer: dict[str, Any] | None = None
    deployer: dict[str, Any] | None = None


class CloudPreflightCheck(BaseModel):
    component: Literal["optimizer", "deployer"]
    status: Literal["passed", "failed"]
    code: str
    message: str
    action: str
    permissions: list[str] = Field(default_factory=list)


class CloudConnectionPreflightResponse(BaseModel):
    id: str
    provider: CloudProvider
    expected_permission_set_version: str
    supplied_permission_set_version: str | None = None
    permission_set_status: Literal["matched", "missing", "outdated"]
    ready: bool
    summary: str
    checks: list[CloudPreflightCheck]
