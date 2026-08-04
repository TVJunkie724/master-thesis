from datetime import datetime
from enum import StrEnum
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, SecretStr, model_validator

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


class CloudBootstrapEntryPoint(StrEnum):
    SETTINGS = "settings"
    TWIN_PREPARE = "twin_prepare"


class CloudBootstrapState(StrEnum):
    DRAFT = "draft"
    BOOTSTRAP_RUNNING = "bootstrap_running"
    GENERATED_CONNECTION_READY = "generated_connection_ready"
    DISPOSAL_RUNNING = "disposal_running"
    MANUAL_REVOCATION_REQUIRED = "manual_revocation_required"
    CREDENTIAL_REENTRY_REQUIRED = "credential_reentry_required"
    READY = "ready"
    FAILED = "failed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class CloudBootstrapCredentialOrigin(StrEnum):
    DEDICATED_DISPOSABLE = "dedicated_disposable"
    EXISTING_USER_OWNED = "existing_user_owned"


class CloudBootstrapDisposalStatus(StrEnum):
    REVOKED = "revoked"
    EXPIRES_AT_PROVIDER = "expires_at_provider"
    MANUAL_REVOCATION_REQUIRED = "manual_revocation_required"
    NOT_RETAINED_USER_MANAGED = "not_retained_user_managed"
    RELEASED_AFTER_FAILURE = "released_after_failure"


class AWSBootstrapTarget(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    provider: Literal["aws"] = "aws"
    account_id: str = Field(pattern=r"^[0-9]{12}$")
    region: str = Field(min_length=1, max_length=64)
    session_expires_at: datetime | None = None


class AzureBootstrapTarget(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    provider: Literal["azure"] = "azure"
    tenant_id: str = Field(min_length=1, max_length=128)
    subscription_id: str = Field(min_length=1, max_length=128)
    region: str = Field(min_length=1, max_length=64)
    bootstrap_credential_key_id: str | None = Field(default=None, max_length=160)


class GCPExistingProjectBootstrapTarget(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    provider: Literal["gcp"] = "gcp"
    mode: Literal["existing_project"] = "existing_project"
    project_id: str = Field(pattern=r"^[a-z][a-z0-9-]{4,28}[a-z0-9]$")
    region: str = Field(min_length=1, max_length=64)


class GCPOrganizationBootstrapTarget(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    provider: Literal["gcp"] = "gcp"
    mode: Literal["organization"] = "organization"
    bootstrap_project_id: str = Field(pattern=r"^[a-z][a-z0-9-]{4,28}[a-z0-9]$")
    organization_id: str = Field(pattern=r"^[0-9]+$")
    folder_id: str | None = Field(default=None, pattern=r"^[0-9]+$")
    billing_account_id: str = Field(pattern=r"^[0-9A-F]{6}-[0-9A-F]{6}-[0-9A-F]{6}$")
    region: str = Field(min_length=1, max_length=64)


CloudBootstrapTarget = (
    AWSBootstrapTarget
    | AzureBootstrapTarget
    | GCPExistingProjectBootstrapTarget
    | GCPOrganizationBootstrapTarget
)


class CloudBootstrapGuideRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target: CloudBootstrapTarget


class CloudBootstrapPackReference(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    version: str
    digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class CloudBootstrapGuidePackReference(CloudBootstrapPackReference):
    scope_summary: str
    limitations: list[str]
    artifact_url: str = Field(pattern=r"^https://")


class CloudBootstrapCredentialField(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(pattern=r"^[a-z0-9_]+$")
    label: str
    input_type: Literal["identifier", "secret", "json"]
    required: bool
    redaction_rule: Literal["identifier", "secret", "private_key_document"]


class CloudBootstrapInstruction(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(pattern=r"^[a-z0-9_]+$")
    title: str
    description: str
    expected_outcome: str
    official_url: str = Field(pattern=r"^https://")


class CloudBootstrapFinding(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    code: str = Field(pattern=r"^[A-Z0-9_]+$")
    severity: Literal["info", "warning", "error"] = "error"
    title: str
    message: str
    blocking: bool
    action: str
    remediation_url: str | None = Field(default=None, pattern=r"^https://")


class CloudBootstrapGuideResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["cloud-bootstrap-guide.v1"] = "cloud-bootstrap-guide.v1"
    guide_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    provider: CloudProvider
    execution_mode: Literal["disabled", "deterministic_fake"]
    target: CloudBootstrapTarget
    bootstrap_authority_pack: CloudBootstrapGuidePackReference
    generated_deployment_pack: CloudBootstrapGuidePackReference
    credential_fields: list[CloudBootstrapCredentialField]
    credential_origins: tuple[
        Literal["dedicated_disposable"],
        Literal["existing_user_owned"],
    ] = ("dedicated_disposable", "existing_user_owned")
    preparation_steps: list[CloudBootstrapInstruction]
    known_blockers: list[CloudBootstrapFinding]
    legacy_fallback_available: Literal[True] = True

    @model_validator(mode="after")
    def validate_provider_target(self):
        if self.provider != self.target.provider:
            raise ValueError("provider must match target.provider")
        return self


class CloudBootstrapSessionCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: CloudProvider
    target: CloudBootstrapTarget
    entry_point: CloudBootstrapEntryPoint
    twin_id: str | None = None
    display_name: str = Field(min_length=1, max_length=120)
    guide_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    bootstrap_authority_pack_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    generated_deployment_pack_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    idempotency_key: str = Field(pattern=r"^[A-Za-z0-9._:-]{16,128}$")

    @model_validator(mode="after")
    def validate_scope(self):
        if self.provider != self.target.provider:
            raise ValueError("provider must match target.provider")
        if self.entry_point == CloudBootstrapEntryPoint.SETTINGS and self.twin_id is not None:
            raise ValueError("settings entry point forbids twin_id")
        if self.entry_point == CloudBootstrapEntryPoint.TWIN_PREPARE and not self.twin_id:
            raise ValueError("twin_prepare entry point requires twin_id")
        return self


class AWSBootstrapCredential(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: Literal["aws"] = "aws"
    access_key_id: SecretStr = Field(min_length=16, max_length=128)
    secret_access_key: SecretStr = Field(min_length=16, max_length=256)
    session_token: SecretStr | None = Field(default=None, min_length=16, max_length=4096)


class AzureBootstrapCredential(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: Literal["azure"] = "azure"
    tenant_id: SecretStr = Field(min_length=1, max_length=128)
    subscription_id: SecretStr = Field(min_length=1, max_length=128)
    client_id: SecretStr = Field(min_length=1, max_length=128)
    client_secret: SecretStr = Field(min_length=8, max_length=4096)


class GCPBootstrapCredential(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: Literal["gcp"] = "gcp"
    type: Literal["service_account"]
    project_id: str
    private_key_id: SecretStr = Field(min_length=1, max_length=256)
    private_key: SecretStr = Field(min_length=16, max_length=16384)
    client_email: str
    client_id: SecretStr = Field(min_length=1, max_length=256)
    auth_uri: str | None = None
    token_uri: str | None = None
    auth_provider_x509_cert_url: str | None = None
    client_x509_cert_url: str | None = None
    universe_domain: str | None = None


CloudBootstrapCredential = Annotated[
    AWSBootstrapCredential | AzureBootstrapCredential | GCPBootstrapCredential,
    Field(discriminator="provider"),
]


class CloudBootstrapExecuteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_revision: int = Field(ge=1)
    idempotency_key: str = Field(pattern=r"^[A-Za-z0-9._:-]{16,128}$")
    credential_origin: CloudBootstrapCredentialOrigin
    credential: CloudBootstrapCredential


class CloudBootstrapRevisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_revision: int = Field(ge=1)


class CloudBootstrapConnectionSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    provider: CloudProvider
    purpose: Literal["deployment"]
    display_name: str
    cloud_scope: dict[str, Any]
    permission_set_version: str
    validation_status: Literal["valid", "invalid", "untested"]


class CloudBootstrapSessionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["cloud-bootstrap-session.v1"] = "cloud-bootstrap-session.v1"
    id: str
    provider: CloudProvider
    target: CloudBootstrapTarget
    entry_point: CloudBootstrapEntryPoint
    twin_id: str | None
    display_name: str
    revision: int
    state: CloudBootstrapState
    guide_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    bootstrap_authority_pack: CloudBootstrapPackReference
    generated_deployment_pack: CloudBootstrapPackReference
    credential_origin: CloudBootstrapCredentialOrigin | None = None
    disposal_status: CloudBootstrapDisposalStatus | None = None
    credential_expires_at: datetime | None = None
    safe_credential_identifier: str | None = None
    finding: CloudBootstrapFinding | None = None
    connection: CloudBootstrapConnectionSummary | None = None
    command_permissions: list[
        Literal[
            "execute",
            "recheck",
            "acknowledge_manual_revocation",
            "cancel",
            "start_new",
        ]
    ]
    created_at: datetime
    updated_at: datetime

    @model_validator(mode="after")
    def validate_provider_target(self):
        if self.provider != self.target.provider:
            raise ValueError("provider must match target.provider")
        if self.entry_point == CloudBootstrapEntryPoint.SETTINGS and self.twin_id is not None:
            raise ValueError("settings entry point forbids twin_id")
        if self.entry_point == CloudBootstrapEntryPoint.TWIN_PREPARE and not self.twin_id:
            raise ValueError("twin_prepare entry point requires twin_id")
        return self


class CloudBootstrapSessionListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    items: list[CloudBootstrapSessionResponse]
