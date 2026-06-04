from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.schemas.cloud_connection import CloudConnectionCreate, CloudConnectionResponse, CloudProvider


BootstrapProvider = CloudProvider


class CloudBootstrapPlanRequest(BaseModel):
    """Request a safe manual bootstrap plan without sending admin credentials."""

    model_config = ConfigDict(extra="forbid")

    display_name: str = Field(default="twin2mc-deployer", min_length=1, max_length=120)
    region: str | None = None
    account_id: str | None = None
    subscription_id: str | None = None
    tenant_id: str | None = None
    project_id: str | None = None
    billing_account: str | None = None


class CloudBootstrapPlanResponse(BaseModel):
    provider: BootstrapProvider
    mode: Literal["manual_static_script"] = "manual_static_script"
    script_path: str
    required_tool: str
    output_auth_type: str
    permission_set_version: str
    dry_run_command: list[str]
    apply_command: list[str]
    rotation_flag: str
    cloud_scope: dict[str, Any]
    creates: list[str]
    security_notes: list[str]


class CloudBootstrapImportRequest(BaseModel):
    """Import generated bootstrap output as a CloudConnection."""

    model_config = ConfigDict(extra="forbid")

    source: Literal["bootstrap_script"] = "bootstrap_script"
    connection: CloudConnectionCreate

    @model_validator(mode="after")
    def validate_generated_connection(self):
        if self.connection.auth_type in {"assume_role", "workload_identity"}:
            raise ValueError(f"{self.connection.auth_type} bootstrap import is not supported yet")
        return self


class CloudBootstrapImportResponse(BaseModel):
    connection: CloudConnectionResponse
